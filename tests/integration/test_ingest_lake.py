"""Integration tests for the DuckLake ingest and the W1 profiling pass."""

import csv

from gdgap.ingest import nhts2017


def test_ingest_is_idempotent_and_logs(lake_root):
    """Creates on first run, skips on rerun, recreates under force, and logs every run."""
    first = nhts2017.ingest(root=lake_root)
    assert [row["action"] for row in first] == ["created"] * 4
    assert {row["table"]: row["rows"] for row in first} == {"hhpub": 2, "perpub": 3, "trippub": 2, "vehpub": 1}
    second = nhts2017.ingest(root=lake_root)
    assert [row["action"] for row in second] == ["skipped"] * 4
    third = nhts2017.ingest(root=lake_root, force=True)
    assert [row["action"] for row in third] == ["recreated"] * 4
    with open(lake_root / nhts2017.INGEST_LOG, newline="", encoding="utf-8") as handle:
        logged = list(csv.DictReader(handle))
    assert len(logged) == 12


def test_profile_emits_w1_csvs(lake_root):
    """Writes structure and null CSVs per table plus the sex code list and imputation share."""
    nhts2017.ingest(root=lake_root)
    written = nhts2017.profile(root=lake_root)
    assert len(written) == 10
    for path in written:
        assert (lake_root / path).is_file()
    with open(lake_root / "results" / "profile" / "perpub_sex_imputation_share.csv", newline="") as handle:
        share = next(csv.DictReader(handle))
    # One of the three fixture persons carries an imputed sex value (-7 reported, 02 imputed)
    assert share["rows_total"] == "3"
    assert share["rows_imputed"] == "1"
