"""Shared fixtures for gdgap tests."""

import hashlib
import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlparse

import pytest
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]

# Loading the root .env before test modules are imported, so a deliberately declared
# GDGAP_MYSQL_TEST_URL unskips the live-InnoDB tests without a shell export; override=False
# keeps deliberate shell exports authoritative (ADR-0008). The markers never key off
# GDGAP_MYSQL_URL: pointing tests at the evidence server clobbered the full-scale mirrors
# on 2026-08-10, because the InnoDB DDL hard-codes the gdgap_% database names.
load_dotenv(REPO_ROOT / ".env", override=False)


def _mysql_host_port(url: str) -> tuple[str, int]:
    """Returns the (hostname, port) pair identifying a MySQL endpoint URL."""
    parsed = urlparse(url)
    return ((parsed.hostname or "*********").lower(), parsed.port or 3306)


@pytest.fixture
def mysql_test_endpoint(monkeypatch) -> str:
    """
    Routes live-InnoDB tests at the dedicated disposable MySQL test endpoint.

    Reads GDGAP_MYSQL_TEST_URL, refuses to run while it resolves to the same server as
    GDGAP_MYSQL_URL (the evidence endpoint), and rebinds GDGAP_MYSQL_URL for the test's
    duration so the backend cannot reach the evidence server at all.
    """
    test_url = os.environ.get("GDGAP_MYSQL_TEST_URL")
    if not test_url:
        pytest.skip("GDGAP_MYSQL_TEST_URL not set (dedicated disposable MySQL test endpoint)")
    evidence_url = os.environ.get("GDGAP_MYSQL_URL")
    if evidence_url and _mysql_host_port(test_url) == _mysql_host_port(evidence_url):
        pytest.fail(
            "GDGAP_MYSQL_TEST_URL resolves to the same server as GDGAP_MYSQL_URL — refusing to run "
            "live-InnoDB tests against the evidence endpoint; use a disposable server (e.g. a "
            "throwaway container on another port)"
        )
    monkeypatch.setenv("GDGAP_MYSQL_URL", test_url)
    return test_url


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
