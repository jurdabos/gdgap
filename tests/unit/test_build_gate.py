"""Unit tests for the R-number header gate of the Phase D build."""

from pathlib import Path

import click
import pytest

from gdgap import build

REGISTRY = "# registry\n## R1 — one\ntext\n## R2 — two\n## R12 — twelve\n"


@pytest.fixture
def gate_root(tmp_path: Path) -> Path:
    """Builds a minimal root with a registry and one variant DDL directory."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "requirements.md").write_text(REGISTRY, encoding="utf-8")
    (tmp_path / "sql" / "ddl" / "blind").mkdir(parents=True)
    return tmp_path


def test_registry_ids_parses_headings(gate_root):
    """Reads the R-number IDs from the registry headings."""
    assert build.registry_ids(gate_root) == {"R1", "R2", "R12"}


def test_valid_headers_pass(gate_root):
    """Accepts single- and multi-ID headers and returns the claims."""
    ddl = gate_root / "sql" / "ddl" / "blind" / "01_x.sql"
    ddl.write_text("-- R1: single id\nselect 1;\n", encoding="utf-8")
    assert build.validate_ddl_header(ddl, {"R1", "R2"}) == ["R1"]
    ddl.write_text("-- R1, R2: multiple ids\nselect 1;\n", encoding="utf-8")
    assert build.validate_ddl_header(ddl, {"R1", "R2"}) == ["R1", "R2"]


def test_missing_header_is_refused(gate_root):
    """Refuses to accept a DDL file without an R-number header."""
    ddl = gate_root / "sql" / "ddl" / "blind" / "01_x.sql"
    ddl.write_text("select 1;\n", encoding="utf-8")
    with pytest.raises(click.ClickException, match="R-number header"):
        build.validate_ddl_header(ddl, {"R1"})


def test_unknown_id_is_refused(gate_root):
    """Refuses headers naming IDs that are absent from the registry."""
    ddl = gate_root / "sql" / "ddl" / "blind" / "01_x.sql"
    ddl.write_text("-- R99: not registered\nselect 1;\n", encoding="utf-8")
    with pytest.raises(click.ClickException, match="unknown requirement id"):
        build.validate_ddl_header(ddl, {"R1"})


def test_repo_ddl_headers_all_valid():
    """Every shipped DDL file (canonical and innodb) passes the gate against the real registry."""
    root = Path(__file__).resolve().parents[2]
    valid = build.registry_ids(root)
    files = list((root / "sql" / "ddl").rglob("*.sql"))
    assert files
    for path in files:
        assert build.validate_ddl_header(path, valid)
