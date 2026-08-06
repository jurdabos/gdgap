"""Integration tests for the imputation sensitivity audit on the fixture lake."""

import csv
from pathlib import Path

import click
import pytest

from gdgap import build as build_module
from gdgap import sensitivity
from gdgap.ingest import nhts2017


def _rows(root: Path, name: str) -> list[dict]:
    """Returns all rows of one audit CSV as dictionaries."""
    with open(root / sensitivity.SENSITIVITY_DIR / name, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _prepare(lake_root: Path) -> None:
    """Ingests the fixture CSVs and builds the aware variant."""
    nhts2017.ingest(root=lake_root)
    build_module.build("aware", root=lake_root)


def test_audit_requires_aware_build(lake_root):
    """Fails with a hint when the aware dimension has not been built yet."""
    nhts2017.ingest(root=lake_root)
    with pytest.raises(click.ClickException, match="gdgap build --variant aware"):
        sensitivity.audit_imputation(root=lake_root)


def test_audit_emits_deterministic_outputs(lake_root):
    """Writes all five outputs and regenerates the CSVs byte-identically."""
    _prepare(lake_root)
    written = sensitivity.audit_imputation(root=lake_root)
    assert [path.name for path in written] == [
        "provenance_split.csv",
        "imputation_rates.csv",
        "equity_sensitivity.csv",
        "scenario_coverage.csv",
        "sensitivity_summary.md",
    ]
    for path in written:
        assert (lake_root / path).is_file()
    blobs = {path.name: (lake_root / path).read_bytes() for path in written if path.name.endswith(".csv")}
    sensitivity.audit_imputation(root=lake_root)
    for path in written:
        if path.name.endswith(".csv"):
            assert (lake_root / path).read_bytes() == blobs[path.name]


def test_scenarios_and_suppression_on_fixture(lake_root):
    """Emits all three scenarios; three fixture persons can never clear n >= 30, so all cells suppress."""
    _prepare(lake_root)
    sensitivity.audit_imputation(root=lake_root)
    equity = _rows(lake_root, "equity_sensitivity.csv")
    assert equity
    assert {row["scenario"] for row in equity} == {"all_completed", "observed_only", "reported_values"}
    assert {row["measure"] for row in equity} == {"care_trip_share", "ppr"}
    assert all(row["suppressed"] == "True" and row["value"] == "" for row in equity)
    assert all(row["snapshot"] and row["git_commit"] for row in equity)


def test_provenance_rates_and_coverage(lake_root):
    """Reports the fixture provenance split, TOTAL rate rows with instability flags, and coverage bounds."""
    _prepare(lake_root)
    sensitivity.audit_imputation(root=lake_root)
    split = {row["sex_source"]: row for row in _rows(lake_root, "provenance_split.csv")}
    assert split["imputed"]["persons_n"] == "1"
    assert split["reported"]["persons_n"] == "2"
    # The imputed fixture person (houseid 1, personid 2) has no trips
    assert split["imputed"]["trips_n"] == "0"
    rates = _rows(lake_root, "imputation_rates.csv")
    assert {row["dimension"] for row in rates} == {"completed_sex_code", "age_band"}
    totals = [row for row in rates if row["category"] == "TOTAL"]
    assert len(totals) == 2
    assert all(row["persons_n"] == "3" and row["imputed_unstable"] == "True" for row in totals)
    coverage = {row["scenario"]: row for row in _rows(lake_root, "scenario_coverage.csv")}
    assert coverage["observed_only"]["persons_excluded_n"] == "1"
    assert coverage["observed_only"]["trips_excluded_n"] == "0"
    assert coverage["observed_only"]["persons_reclassified_n"] == "0"
    # The fixture has no edited rows, so reclassification stays zero in reported_values too
    assert coverage["reported_values"]["persons_reclassified_n"] == "0"


def test_markdown_carries_the_framing(lake_root):
    """States the audit framing, the weights caveat, and the regeneration command."""
    _prepare(lake_root)
    sensitivity.audit_imputation(root=lake_root)
    text = (lake_root / sensitivity.SENSITIVITY_DIR / sensitivity.SUMMARY_FILE).read_text(encoding="utf-8")
    assert "imputation sensitivity audit, not a bias detector" in text
    assert "never re-raked estimators" in text
    assert "gdgap audit-imputation" in text
    assert "Scenarios (frozen definitions)" in text
