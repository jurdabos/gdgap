"""Unit tests for manifest verification in gdgap.ingest.nhts2017."""

import pytest

from gdgap.ingest import nhts2017


def test_verify_manifest_passes_on_intact_fixture(lake_root):
    """Returns one digest per manifest file when everything matches."""
    digests = nhts2017.verify_manifest(lake_root)
    assert set(digests) == {f"{table}.csv" for table in nhts2017.TABLES}


def test_verify_manifest_rejects_corruption(lake_root):
    """Raises with a per-file message when a raw CSV was tampered with."""
    target = lake_root / "data" / "raw" / "nhts2017" / "hhpub.csv"
    target.write_bytes(target.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="hhpub.csv: sha256 mismatch"):
        nhts2017.verify_manifest(lake_root)


def test_verify_manifest_reports_missing_file(lake_root):
    """Raises when a manifest-listed file is absent from data/raw."""
    (lake_root / "data" / "raw" / "nhts2017" / "vehpub.csv").unlink()
    with pytest.raises(ValueError, match="vehpub.csv: missing"):
        nhts2017.verify_manifest(lake_root)
