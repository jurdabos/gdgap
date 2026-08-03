"""Integration tests for the DuckLake ingest and the W1 profiling pass."""

import csv
from contextlib import closing

import click
import pytest

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


def test_tables_live_in_dataset_schema(lake_root):
    """Places every lake table in the schema named after the dataset, never in main."""
    nhts2017.ingest(root=lake_root)
    with nhts2017._chdir(lake_root), closing(nhts2017._connect(lake_root)) as con:
        rows = con.execute(
            "select schema_name, table_name from duckdb_tables() where database_name = 'lake' order by table_name"
        ).fetchall()
    assert rows == [(nhts2017.DATASET, table) for table in sorted(nhts2017.TABLES)]


def test_ingest_pins_sex_codes_verbatim(lake_root):
    """Stores R_SEX and R_SEX_IMP as declared VARCHAR, reserve codes and zero-padding intact (R7)."""
    nhts2017.ingest(root=lake_root)
    with nhts2017._chdir(lake_root), closing(nhts2017._connect(lake_root)) as con:
        types = dict(
            con.execute(
                f"select column_name, column_type from (describe {nhts2017._qualified('perpub')}) "
                f"where column_name in ('{nhts2017.SEX_COL}', '{nhts2017.SEX_IMP_COL}')"
            ).fetchall()
        )
        values = con.execute(
            f"select {nhts2017.SEX_COL}, {nhts2017.SEX_IMP_COL} from {nhts2017._qualified('perpub')} order by 1"
        ).fetchall()
    assert types == {nhts2017.SEX_COL: "VARCHAR", nhts2017.SEX_IMP_COL: "VARCHAR"}
    # Verbatim survival: the -7 reserve code and the zero-padded 01/02 codes, never numerics or NULLs
    assert values == [("-7", "02"), ("01", "01"), ("02", "02")]


def test_profile_emits_w1_csvs(lake_root):
    """Writes structure and null CSVs per table plus the sex code list and imputation share."""
    nhts2017.ingest(root=lake_root)
    written = nhts2017.profile(root=lake_root)
    assert len(written) == 10
    for path in written:
        assert (lake_root / path).is_file()
        assert path.parent == nhts2017.PROFILE_DIR
    share_path = lake_root / "results" / "profile" / "nhts2017" / "perpub_sex_imputation_share.csv"
    with open(share_path, newline="") as handle:
        share = next(csv.DictReader(handle))
    # One of the three fixture persons carries an imputed sex value (-7 reported, 02 imputed)
    assert share["rows_total"] == "3"
    assert share["rows_imputed"] == "1"


def test_summarize_renders_markdown_from_csvs(lake_root):
    """Formats the 3.2 summary from the profile CSVs alone and reports fixture ground truth."""
    nhts2017.ingest(root=lake_root)
    nhts2017.profile(root=lake_root)
    summary_path = nhts2017.summarize(root=lake_root)
    text = summary_path.read_text(encoding="utf-8")
    assert summary_path.parent == lake_root / nhts2017.PROFILE_DIR
    for table in nhts2017.TABLES:
        assert table in text
    # The fixture imputes one of three persons: 33.3333% share, and codebook labels are attached
    assert "33.3333%" in text
    assert "Male" in text


def test_summarize_requires_profile_outputs(lake_root):
    """Fails with a hint when the profiling CSVs have not been generated yet."""
    with pytest.raises(click.ClickException, match="gdgap profile"):
        nhts2017.summarize(root=lake_root)
