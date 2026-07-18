"""
Manifest-verified, idempotent ingest of the 2017 NHTS CSVs into the DuckLake.

Implements the Phase C contract: verifies each raw CSV's SHA-256 against
datasets/nhts2017/manifest.json before reading, creates one lake table per file
(each CREATE TABLE is a DuckLake snapshot; lake.snapshots() is the audit trail),
records row counts into results/profile/nhts2017/ingest_log.csv, and emits the W1
profiling CSVs (structure, null shares, sex code list, imputation share).

Multi-dataset invariant (ADR-0002): every table lives in a lake schema named after
its dataset (lake.nhts2017.<table>) and every profile artefact lands under
results/profile/<dataset>/, so a second dataset can never collide with this one.
"""

import csv
import hashlib
import json
import os
from collections import Counter
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path

import click
import duckdb
from tabulate import tabulate

DATASET = "nhts2017"
TABLES = ("hhpub", "perpub", "trippub", "vehpub")
RAW_DIR = Path("data/raw/nhts2017")
MANIFEST_PATH = Path("datasets/nhts2017/manifest.json")
ATTACH_SQL = Path("sql/00_attach.sql")
PROFILE_DIR = Path("results/profile") / DATASET
INGEST_LOG = PROFILE_DIR / "ingest_log.csv"
# Sex variable and its imputed companion, spelled exactly as in the FHWA codebook. R_SEX holds the reported
# code (01/02, with -7/-8 reserve codes); R_SEX_IMP holds the same value with imputations filled in, so a row
# was imputed exactly when the two differ. Both arrive as zero-padded VARCHAR codes and stay that way raw.
SEX_COL = "R_SEX"
SEX_IMP_COL = "R_SEX_IMP"
# Code labels per the FHWA codebook, for the human-readable summary only; raw codes stay untouched
SEX_CODE_LABELS = {
    "-9": "Not ascertained",
    "-8": "I don't know",
    "-7": "I prefer not to answer",
    "01": "Male",
    "02": "Female",
}
SUMMARY_FILE = "profile_summary.md"


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


def _qualified(table: str) -> str:
    """Returns the fully qualified lake table name in this dataset's schema."""
    return f"lake.{DATASET}.{table}"


def _table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    """Checks whether a table exists in this dataset's schema of the lake catalog."""
    row = con.execute(
        "select count(*) from duckdb_tables() where database_name = 'lake' and schema_name = ? and table_name = ?",
        [DATASET, table],
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
        # Keeping one lake schema per dataset so table names can never collide across datasets
        con.execute(f"create schema if not exists lake.{DATASET}")
        for table in TABLES:
            csv_name = f"{table}.csv"
            exists = _table_exists(con, table)
            if exists and not force:
                action = "skipped"
            else:
                action = "recreated" if exists else "created"
                if exists:
                    con.execute(f"drop table {_qualified(table)}")
                con.execute(
                    f"create table {_qualified(table)} as "
                    f"select * from read_csv('{(RAW_DIR / csv_name).as_posix()}', header = true, sample_size = -1)"
                )
            n = con.execute(f"select count(*) from {_qualified(table)}").fetchone()[0]
            click.echo(f"  {_qualified(table)}: {action}, {n} rows")
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
            con.execute(f"copy (select * from (describe {_qualified(table)})) to '{structure.as_posix()}'")
            written.append(structure)
            # Null shares per column, the COLUMNS(*) idiom: one wide row of count(*) - count(col)
            nulls = PROFILE_DIR / f"{table}_nulls.csv"
            con.execute(f"copy (select count(*) - count(COLUMNS(*)) from {_qualified(table)}) to '{nulls.as_posix()}'")
            written.append(nulls)
        codelist = PROFILE_DIR / "perpub_sex_codelist.csv"
        con.execute(
            f"""
            copy (
                select '{SEX_COL}' as variable, {SEX_COL} as value, count(*) as n
                from {_qualified("perpub")} group by 2
                union all
                select '{SEX_IMP_COL}' as variable, {SEX_IMP_COL} as value, count(*) as n
                from {_qualified("perpub")} group by 2
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
                from {_qualified("perpub")}
            ) to '{share.as_posix()}'
            """
        )
        written.append(share)
    for path in written:
        click.echo(f"  wrote {path.as_posix()}")
    return written


def _read_csv_rows(path: Path) -> list[dict]:
    """Returns all rows of a CSV file as dictionaries."""
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _latest_row_counts(profile_dir: Path) -> dict[str, int]:
    """Returns the most recent ingest row count per table from ingest_log.csv."""
    counts: dict[str, int] = {}
    for row in _read_csv_rows(profile_dir / "ingest_log.csv"):
        counts[row["table"]] = int(row["rows"])
    return counts


def _structure_summary(profile_dir: Path, table: str) -> tuple[int, str]:
    """Returns the column count and a compact type breakdown from a table's structure CSV."""
    rows = _read_csv_rows(profile_dir / f"{table}_structure.csv")
    type_counts = Counter(row["column_type"] for row in rows)
    breakdown = " · ".join(f"{n} {t}" for t, n in sorted(type_counts.items(), key=lambda item: -item[1]))
    return len(rows), breakdown


def _null_summary(profile_dir: Path, table: str) -> tuple[int, int]:
    """Returns the count of null-carrying columns and total null cells from a table's nulls CSV."""
    with open(profile_dir / f"{table}_nulls.csv", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader)
        values = [int(value) for value in next(reader)]
    return sum(1 for value in values if value > 0), sum(values)


def summarize(root: Path | None = None) -> Path:
    """
    Renders the profile summary for the 3.2 case description and returns its path.

    A pure formatting pass over results/profile/<dataset>/*.csv — no lake access.
    Writes profile_summary.md next to the inputs and echoes the markdown.
    """
    root = root or find_root()
    profile_dir = root / PROFILE_DIR
    required = [profile_dir / "ingest_log.csv", profile_dir / "perpub_sex_codelist.csv"]
    required += [profile_dir / "perpub_sex_imputation_share.csv"]
    required += [profile_dir / f"{table}_{kind}.csv" for table in TABLES for kind in ("structure", "nulls")]
    missing = [path.name for path in required if not path.is_file()]
    if missing:
        raise click.ClickException(
            f"Missing profile inputs: {', '.join(missing)} — run 'gdgap ingest {DATASET}' and 'gdgap profile' first."
        )
    counts = _latest_row_counts(profile_dir)
    structure_rows = []
    for table in TABLES:
        n_columns, breakdown = _structure_summary(profile_dir, table)
        null_columns, null_cells = _null_summary(profile_dir, table)
        n_rows = counts.get(table, 0)
        null_share = 100.0 * null_cells / (n_rows * n_columns) if n_rows and n_columns else 0.0
        structure_rows.append(
            [table, f"{n_rows:,}", n_columns, breakdown, null_columns, f"{null_cells:,}", f"{null_share:.4f}%"]
        )
    codelist = _read_csv_rows(profile_dir / "perpub_sex_codelist.csv")
    variable_totals = Counter()
    for row in codelist:
        variable_totals[row["variable"]] += int(row["n"])
    codelist_rows = [
        [
            row["variable"],
            row["value"],
            SEX_CODE_LABELS.get(row["value"], ""),
            f"{int(row['n']):,}",
            f"{100.0 * int(row['n']) / variable_totals[row['variable']]:.4f}%",
        ]
        for row in codelist
    ]
    imputation = _read_csv_rows(profile_dir / "perpub_sex_imputation_share.csv")[0]
    imputation_row = [
        [f"{int(imputation['rows_total']):,}", f"{int(imputation['rows_imputed']):,}", f"{imputation['imputed_pct']}%"]
    ]
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    content = "\n".join(
        [
            f"# {DATASET} profile summary (case description ground truth)",
            "",
            f"Generated {generated} by `gdgap summarize` — a formatting pass over `{PROFILE_DIR.as_posix()}/*.csv`.",
            f"Regenerate with `gdgap ingest {DATASET} && gdgap profile && gdgap summarize`. Source: own results.",
            "",
            "## Structure and null shares",
            "",
            tabulate(
                structure_rows,
                headers=[
                    "file",
                    "rows",
                    "columns",
                    "column types",
                    "columns with nulls",
                    "null cells",
                    "null cell share",
                ],
                tablefmt="github",
            ),
            "",
            f"## Code lists for the sex variable and its imputed companion (`{SEX_COL}`, `{SEX_IMP_COL}`)",
            "",
            tabulate(codelist_rows, headers=["variable", "code", "codebook label", "n", "share"], tablefmt="github"),
            "",
            "## Sex imputation share (perpub)",
            "",
            tabulate(imputation_row, headers=["rows total", "rows imputed", "imputed share"], tablefmt="github"),
            "",
            f"Imputed means the value in `{SEX_IMP_COL}` differs from the reported `{SEX_COL}` "
            "(reserve codes -7/-8 resolved, plus consistency edits).",
            "",
        ]
    )
    summary_path = profile_dir / SUMMARY_FILE
    summary_path.write_text(content, encoding="utf-8")
    click.echo(content)
    click.echo(f"✓ Summary written to {summary_path.relative_to(root).as_posix()}")
    return summary_path
