"""
Phase D build: one pipeline, parameterised by variant and backend.

Executes sql/ddl/<variant>/ in filename order after enforcing the R-number header gate
against docs/requirements.md, so appendix A and the 3.3 traceability claim reduce to a
grep. The InnoDB foil additionally copies every base table of the built lake variant into
MySQL, so both stores hold identical warehouse content from the identical Parquet source.
"""

import re
from pathlib import Path

import click

from gdgap.bench.backends import get_backend
from gdgap.bench.backends.ducklake import DucklakeBackend
from gdgap.ingest.nhts2017 import _chdir, find_root

DDL_ROOT = Path("sql/ddl")
VARIANTS = ("blind", "aware")
REQUIREMENTS_PATH = Path("docs/requirements.md")
REGISTRY_PATTERN = re.compile(r"^## (R\d+) ", re.MULTILINE)
HEADER_PATTERN = re.compile(r"^--\s*(R\d+(?:\s*,\s*R\d+)*)\s*:")


def registry_ids(root: Path) -> set[str]:
    """Returns the R-number IDs defined in docs/requirements.md."""
    text = (root / REQUIREMENTS_PATH).read_text(encoding="utf-8")
    ids = set(REGISTRY_PATTERN.findall(text))
    if not ids:
        raise click.ClickException(f"no R-numbers found in {REQUIREMENTS_PATH.as_posix()}")
    return ids


def validate_ddl_header(path: Path, valid_ids: set[str]) -> list[str]:
    """
    Returns the R-numbers claimed by a DDL file's header comment.

    Refuses files whose first non-empty line is not an R-number header, and headers
    naming IDs that are absent from the registry.
    """
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        match = HEADER_PATTERN.match(line)
        if not match:
            raise click.ClickException(
                f"{path.name}: first line must be an R-number header like '-- R3: ...' (see docs/requirements.md)"
            )
        claimed = [part.strip() for part in match.group(1).split(",")]
        unknown = [rid for rid in claimed if rid not in valid_ids]
        if unknown:
            raise click.ClickException(f"{path.name}: unknown requirement id(s): {', '.join(unknown)}")
        return claimed
    raise click.ClickException(f"{path.name}: file is empty")


def ddl_files(root: Path, variant: str, backend_name: str) -> list[Path]:
    """Returns the ordered DDL files for a variant and backend."""
    base = root / DDL_ROOT / variant
    directory = base / "innodb" if backend_name == "innodb" else base
    files = sorted(directory.glob("*.sql"))
    if not files:
        raise click.ClickException(f"no DDL files found under {directory.as_posix()}")
    return files


def _copy_lake_tables(root: Path, backend, variant: str) -> dict[str, int]:
    """Copies every base table of the built lake variant into the InnoDB foil, batched."""
    source = DucklakeBackend(root)
    try:
        tables = source.list_variant_tables(variant)
        if not tables:
            raise click.ClickException(
                f"lake.{variant} holds no tables — run 'gdgap build --variant {variant}' on ducklake first"
            )
        copied: dict[str, int] = {}
        for table in tables:
            cursor = source.con.execute(f"select * from lake.{variant}.{table}")
            columns = [description[0] for description in cursor.description]
            total = 0
            while True:
                rows = cursor.fetchmany(5000)
                if not rows:
                    break
                total += backend.insert_rows(f"gdgap_{variant}.{table}", columns, rows)
            copied[table] = total
            click.echo(f"  copied lake.{variant}.{table} -> gdgap_{variant}.{table}: {total} rows")
        return copied
    finally:
        source.close()


def build(variant: str, backend_name: str = "ducklake", root: Path | None = None) -> dict:
    """
    Builds one warehouse variant on one backend, R-gated.

    Validates every DDL header before executing anything, executes the files in filename
    order, and for the InnoDB foil copies each base table of the built lake variant.
    Returns a summary with the executed files and the claimed R-number coverage.
    """
    if variant not in VARIANTS:
        raise click.ClickException(f"unknown variant '{variant}'; expected one of: {', '.join(VARIANTS)}")
    root = root or find_root()
    valid_ids = registry_ids(root)
    files = ddl_files(root, variant, backend_name)
    # Validating every header before executing anything, so a bad file aborts the whole build
    claims = {path.name: validate_ddl_header(path, valid_ids) for path in files}
    covered = sorted({rid for ids in claims.values() for rid in ids}, key=lambda rid: int(rid[1:]))
    with _chdir(root):
        backend = get_backend(backend_name, root)
        try:
            backend.ensure_target(variant)
            for path in files:
                backend.run_sql_file(path)
                click.echo(f"  {path.relative_to(root).as_posix()}: ok ({', '.join(claims[path.name])})")
            if backend_name == "innodb":
                _copy_lake_tables(root, backend, variant)
        finally:
            backend.close()
    click.echo(f"✓ Built {variant} on {backend_name} — {len(files)} DDL file(s), R-coverage: {', '.join(covered)}")
    if variant == "aware":
        # R13 control (ADR-0009): the aware warehouse — including the InnoDB mirror migration —
        # must conform to every registered data-quality spec; the blind variant is exempt because
        # it violates the design requirements deliberately (docs/requirements.md conventions).
        # Importing lazily to keep module import light and cycle-free.
        from gdgap.quality import datasets_with_specs, validate

        for dataset in datasets_with_specs(root):
            validate(dataset=dataset, stage="aware_build", backend_name=backend_name, root=root)
    return {"variant": variant, "backend": backend_name, "files": [path.name for path in files], "r_coverage": covered}
