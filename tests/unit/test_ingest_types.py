"""Unit tests for the declared type overrides in the NHTS ingest options builder."""

from gdgap.ingest import nhts2017


def test_read_csv_options_pin_sex_codes_for_perpub():
    """Appends the VARCHAR override map for perpub, the R7 schema-on-write declaration."""
    options = nhts2017._read_csv_options("perpub")
    assert options.startswith("header = true, sample_size = -1")
    assert "types = {'R_SEX': 'VARCHAR', 'R_SEX_IMP': 'VARCHAR'}" in options


def test_read_csv_options_leave_other_tables_to_inference():
    """Applies no override map to tables without declared columns."""
    for table in ("hhpub", "trippub", "vehpub"):
        assert nhts2017._read_csv_options(table) == "header = true, sample_size = -1"
