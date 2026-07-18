"""Shared fixtures for gdgap tests."""

import hashlib
import json
from pathlib import Path

import pytest

ATTACH_SQL = """INSTALL ducklake;
ATTACH 'ducklake:catalog/gdgap.ducklake' AS lake (DATA_PATH 'data/lake/');
USE lake;
"""

CSV_FIXTURES = {
    "hhpub": "HOUSEID,HHSIZE\n1,2\n2,1\n",
    "perpub": "HOUSEID,PERSONID,R_SEX,R_SEX_IMP\n1,1,01,01\n1,2,-7,02\n2,1,02,02\n",
    "trippub": "HOUSEID,PERSONID,TDTRPNUM\n1,1,1\n1,1,2\n",
    "vehpub": "HOUSEID,VEHID\n1,1\n",
}


def _sha256_bytes(data: bytes) -> str:
    """Returns the SHA-256 hex digest of a byte string."""
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def lake_root(tmp_path: Path) -> Path:
    """Builds a minimal gdgap-shaped project root with fixture CSVs, manifest, and attach script."""
    (tmp_path / "sql").mkdir()
    (tmp_path / "sql" / "00_attach.sql").write_text(ATTACH_SQL, encoding="utf-8")
    (tmp_path / "catalog").mkdir()
    (tmp_path / "data" / "lake").mkdir(parents=True)
    raw = tmp_path / "data" / "raw" / "nhts2017"
    raw.mkdir(parents=True)
    entries = []
    for table, content in CSV_FIXTURES.items():
        data = content.encode("utf-8")
        (raw / f"{table}.csv").write_bytes(data)
        entries.append({"name": f"{table}.csv", "sha256": _sha256_bytes(data), "bytes": len(data)})
    manifest = {
        "dataset": "nhts2017",
        "source_url": "https://example.invalid/csv.zip",
        "retrieved": "2026-07",
        "license_note": "test fixture",
        "files": entries,
    }
    meta = tmp_path / "datasets" / "nhts2017"
    meta.mkdir(parents=True)
    (meta / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path
