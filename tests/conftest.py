"""Shared fixtures for gdgap tests."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]

# Loading the root .env before test modules are imported, so the requires_mysql markers
# (evaluated from os.environ at import time) unskip without a shell export; override=False
# keeps deliberate shell exports authoritative (ADR-0008)
load_dotenv(REPO_ROOT / ".env", override=False)

ATTACH_SQL = """INSTALL ducklake;
ATTACH 'ducklake:catalog/gdgap.ducklake' AS lake (DATA_PATH 'data/lake/');
USE lake;
"""

CSV_FIXTURES = {
    "hhpub": "HOUSEID,HHSIZE\n1,2\n2,1\n",
    "perpub": (
        "HOUSEID,PERSONID,R_SEX,R_SEX_IMP,R_AGE,WTPERFIN\n1,1,01,01,30,150.0\n1,2,-7,02,40,120.0\n2,1,02,02,25,90.0\n"
    ),
    "trippub": (
        "HOUSEID,PERSONID,TDTRPNUM,TRPTRANS,WHYTO,WHYFROM,TRIPPURP,TRPMILES,WTTRDFIN\n"
        "1,1,1,03,06,01,HBO,5.0,100.0\n"
        "1,1,2,01,01,06,HBO,2.5,80.0\n"
    ),
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
    # Shipping the R13 data-quality spec so ingest/build auto-validation exercises the real contract
    shutil.copy(REPO_ROOT / "datasets" / "nhts2017" / "DATA_QUALITY_SPEC.json", meta / "DATA_QUALITY_SPEC.json")
    # Shipping the real DDL tree, bench catalogue, and requirements registry so builds, the R-gate,
    # and the bench harness all run against the canon
    shutil.copytree(REPO_ROOT / "sql" / "ddl", tmp_path / "sql" / "ddl")
    shutil.copytree(REPO_ROOT / "sql" / "bench", tmp_path / "sql" / "bench")
    (tmp_path / "docs").mkdir()
    shutil.copy(REPO_ROOT / "docs" / "requirements.md", tmp_path / "docs" / "requirements.md")
    return tmp_path
