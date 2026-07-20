"""
Execution backends for builds and benchmarks.

ducklake is the canonical columnar engine of the artefact; innodb is the row-oriented
foil for the row-vs-column comparison. Both expose the same small surface: ensure_target,
run_sql_file, execute, fetchall, and close.
"""

from pathlib import Path

import click

from gdgap.bench.backends.ducklake import DucklakeBackend
from gdgap.bench.backends.innodb import InnodbBackend

BACKENDS = {"ducklake": DucklakeBackend, "innodb": InnodbBackend}


def get_backend(name: str, root: Path):
    """Returns an instantiated backend by name."""
    try:
        return BACKENDS[name](root)
    except KeyError as exc:
        raise click.ClickException(f"unknown backend '{name}'; available: {', '.join(sorted(BACKENDS))}") from exc
