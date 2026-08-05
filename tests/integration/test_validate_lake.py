"""Integration tests for the R13 conformance validation on the fixture lake (ADR-0009)."""

import csv
from contextlib import closing
from pathlib import Path

import click
import pytest

from gdgap import build as build_module
from gdgap import quality
from gdgap.ingest import nhts2017


def _conformance_rows(root: Path) -> list[dict]:
    """Returns all appended conformance rows for the fixture dataset."""
    path = root / quality.QUALITY_DIR / "nhts2017" / "conformance.csv"
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_ingest_auto_validates_and_logs_conformance(lake_root):
    """Runs the ingest-stage contract automatically and appends rule-level evidence."""
    nhts2017.ingest(root=lake_root)
    rows = _conformance_rows(lake_root)
    assert {row["stage"] for row in rows} == {"ingest"}
    assert {row["backend"] for row in rows} == {"ducklake"}
    errors = [row for row in rows if row["severity"] == "error"]
    assert errors and all(row["passed"] == "True" for row in errors)
    assert all(row["run_id"] and row["rule_id"] and row["r_id"] and row["snapshot"] for row in rows)


def test_aware_build_validates_and_fixture_conforms(lake_root):
    """Aware build triggers the aware_build contract; every error rule passes on the fixture."""
    nhts2017.ingest(root=lake_root)
    build_module.build("aware", root=lake_root)
    rows = _conformance_rows(lake_root)
    assert {row["stage"] for row in rows} == {"ingest", "aware_build"}
    error_fails = [row for row in rows if row["severity"] == "error" and row["passed"] == "False"]
    assert error_fails == []
    # The drift-monitor warning exercises the severity split without failing the run
    warnings = [row for row in rows if row["severity"] == "warning"]
    assert warnings


def test_blind_build_is_not_validated(lake_root):
    """Leaves the blind variant out of the contract: its violations are the experiment."""
    nhts2017.ingest(root=lake_root)
    build_module.build("blind", root=lake_root)
    rows = _conformance_rows(lake_root)
    assert {row["stage"] for row in rows} == {"ingest"}


def test_error_violation_fails_and_is_logged(lake_root):
    """An out-of-domain raw code fails ingest-stage validation, naming and logging the rule."""
    nhts2017.ingest(root=lake_root)
    # Injecting the violation: '03' breaches the declared raw-code domain (R7)
    with nhts2017._chdir(lake_root), closing(nhts2017._connect(lake_root)) as con:
        con.execute(
            "insert into lake.nhts2017.perpub (HOUSEID, PERSONID, R_SEX, R_SEX_IMP, R_AGE, WTPERFIN) "
            "values (9, 9, '03', '01', 50, 10.0)"
        )
    with pytest.raises(click.ClickException, match="DQ-SYN-03"):
        quality.validate(dataset="nhts2017", stage="ingest", root=lake_root)
    fails = [row for row in _conformance_rows(lake_root) if row["passed"] == "False" and row["severity"] == "error"]
    assert any(row["rule_id"] == "DQ-SYN-03" for row in fails)
