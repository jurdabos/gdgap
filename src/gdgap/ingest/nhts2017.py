"""
Manifest-verified, idempotent ingest of the 2017 NHTS CSVs into the DuckLake.

Implements the Phase C contract: verifies each raw CSV's SHA-256 against
datasets/nhts2017/manifest.json before reading, creates one lake table per file
(each CREATE TABLE is a DuckLake snapshot; lake.snapshots() is the audit trail),
records row counts into results/profile/ingest_log.csv, and emits the W1
profiling CSVs (structure, null shares, sex code list, imputation share).
"""

import csv
import hashlib
import json
import os
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

import click
import duckdb

DATASET = "nhts2017"
TABLES = ("hhpub", "perpub", "trippub", "vehpub")
RAW_DIR = Path("data/raw/nhts2017")
MANIFEST_PATH = Path("datasets/nhts2017/manifest.json")
ATTACH_SQL = Path("sql/00_attach.sql")
PROFILE_DIR = Path("results/profile")
INGEST_LOG = PROFILE_DIR / "ingest_log.csv"
# Sex variable and its imputed companion, spelled exactly as in the FHWA codebook. R_SEX holds the reported
# code (01/02, with -7/-8 reserve codes); R_SEX_IMP holds the same value with imputations filled in, so a row
# was imputed exactly when the two differ. Both arrive as zero-padded VARCHAR codes and stay that way raw.
SEX_COL = "R_SEX"
SEX_IMP_COL = "R_SEX_IMP"


def find_root() -> Path:
    """Locates the project root by walking up to find pyproject.toml."""
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    return current


@contextmanager
def _chdir(path: Path):
    """Temporarily switches the working directory so the lake's relative paths resolve."""
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _sha256(path: Path) -> str:
    """Returns the streaming SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(root: Path) -> dict:
    """Returns the parsed dataset manifest."""
    with open(root / MANIFEST_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def verify_manifest(root: Path) -> dict[str, str]:
    """
    Verifies every manifest entry's SHA-256 against the raw CSV on disk.

    Returns a name-to-digest mapping and raises ValueError listing all mismatches.
    """
    manifest = load_manifest(root)
    digests: dict[str, str] = {}
    errors: list[str] = []
    for entry in manifest["files"]:
        name = entry["name"]
        path = root / RAW_DIR / name
        if not path.is_file():
            errors.append(f"{name}: missing at {path}")
            continue
        actual = _sha256(path)
        digests[name] = actual
        if actual != entry["sha256"]:
            errors.append(f"{name}: sha256 mismatch (manifest {entry['sha256']}, actual {actual})")
    if errors:
        raise ValueError("Manifest verification failed:\n" + "\n".join(errors))
    return digests


def _connect(root: Path) -> duckdb.DuckDBPyConnection:
    """Opens a connection with the DuckLake attached per sql/00_attach.sql."""
    con = duckdb.connect()
    con.execute((root / ATTACH_SQL).read_text(encoding="utf-8"))
    return con


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    """Checks whether a table exists in the attached lake catalog."""
    row = con.execute(
        "select count(*) from duckdb_tables() where database_name = 'lake' and table_name = ?",
        [table],
    ).fetchone()
    return bool(row and row[0])


def _append_log(root: Path, rows: list[dict]) -> None:
    """Appends ingest rows to results/profile/ingest_log.csv, writing the header once."""
    log_path = root / INGEST_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["ts_utc", "dataset", "table", "action", "rows", "sha256"]
    is_new = not log_path.exists()
    with open(log_path, "a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if is_new:
            writer.writeheader()
        writer.writerows(rows)


def ingest(root: Path | None = None, force: bool = False) -> list[dict]:
    """
    Ingests the four NHTS 2017 CSVs into the lake, idempotently.

    Existing tables are skipped unless force is set, in which case they are dropped
    and recreated (a fresh DuckLake snapshot either way). Returns the log rows written.
    """
    root = root or find_root()
    digests = verify_manifest(root)
    click.echo(f"✓ Manifest verified — sha256 match for {len(digests)} file(s)")
    ts_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    log_rows: list[dict] = []
    with _chdir(root), closing(_connect(root)) as con:
        for table in TABLES:
            csv_name = f"{table}.csv"
            exists = _table_exists(con, table)
            if exists and not force:
                action = "skipped"
            else:
                action = "recreated" if exists else "created"
                if exists:
                    con.execute(f"drop table lake.{table}")
                con.execute(
                    f"create table lake.{table} as "
                    f"select * from read_csv('{(RAW_DIR / csv_name).as_posix()}', header = true, sample_size = -1)"
                )
            n = con.execute(f"select count(*) from lake.{table}").fetchone()[0]
            click.echo(f"  lake.{table}: {action}, {n} rows")
            log_rows.append(
                {
                    "ts_utc": ts_utc,
                    "dataset": DATASET,
                    "table": table,
                    "action": action,
                    "rows": n,
                    "sha256": digests[csv_name],
                }
            )
        snapshot = con.execute("select max(snapshot_id) from lake.snapshots()").fetchone()[0]
        click.echo(f"✓ Lake at snapshot {snapshot} — audit trail: select * from lake.snapshots()")
    _append_log(root, log_rows)
    click.echo(f"✓ Row counts recorded in {INGEST_LOG.as_posix()}")
    return log_rows


def profile(root: Path | None = None) -> list[Path]:
    """
    Emits the W1 profiling CSVs under results/profile/ and returns their paths.

    Covers structure and null shares for all four tables, the code list for the sex
    variable and its imputed companion, and the sex imputation share.
    """
    root = root or find_root()
    written: list[Path] = []
    with _chdir(root), closing(_connect(root)) as con:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        for table in TABLES:
            structure = PROFILE_DIR / f"{table}_structure.csv"
            con.execute(f"copy (select * from (describe lake.{table})) to '{structure.as_posix()}'")
            written.append(structure)
            # Null shares per column, the COLUMNS(*) idiom: one wide row of count(*) - count(col)
            nulls = PROFILE_DIR / f"{table}_nulls.csv"
            con.execute(f"copy (select count(*) - count(COLUMNS(*)) from lake.{table}) to '{nulls.as_posix()}'")
            written.append(nulls)
        codelist = PROFILE_DIR / "perpub_sex_codelist.csv"
        con.execute(
            f"""
            copy (
                select '{SEX_COL}' as variable, {SEX_COL} as value, count(*) as n
                from lake.perpub group by 2
                union all
                select '{SEX_IMP_COL}' as variable, {SEX_IMP_COL} as value, count(*) as n
                from lake.perpub group by 2
                order by variable, value
            ) to '{codelist.as_posix()}'
            """
        )
        written.append(codelist)
        # Imputation share = share of rows whose imputed value differs from the reported one
        share = PROFILE_DIR / "perpub_sex_imputation_share.csv"
        con.execute(
            f"""
            copy (
                select
                    count(*) as rows_total,
                    count(*) filter (where {SEX_COL} <> {SEX_IMP_COL}) as rows_imputed,
                    round(100.0 * count(*) filter (where {SEX_COL} <> {SEX_IMP_COL}) / count(*), 4) as imputed_pct
                from lake.perpub
            ) to '{share.as_posix()}'
            """
        )
        written.append(share)
    for path in written:
        click.echo(f"  wrote {path.as_posix()}")
    return written
