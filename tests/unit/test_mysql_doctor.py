"""Unit tests for the sanitized MySQL doctor diagnostics (no live server required)."""

import socket

import pytest

from gdgap.bench.backends.innodb import diagnose


@pytest.fixture
def closed_port() -> int:
    """Returns a loopback port that is currently closed."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_diagnose_reports_missing_url(tmp_path, monkeypatch):
    """States the missing configuration without inventing an endpoint."""
    monkeypatch.delenv("GDGAP_MYSQL_URL", raising=False)
    facts = diagnose(tmp_path)
    assert facts["configured_endpoint"] is None
    assert facts["tcp_reachable"] is False
    assert facts["auth_ok"] is False
    assert "GDGAP_MYSQL_URL" in facts["error"]


def test_diagnose_never_leaks_credentials(tmp_path, monkeypatch, closed_port):
    """Reports an unreachable endpoint by error class only — no username, password, or full URL."""
    monkeypatch.setenv("GDGAP_MYSQL_URL", f"mysql+pymysql://alice:supersecret@127.0.0.1:{closed_port}")
    facts = diagnose(tmp_path)
    assert facts["configured_endpoint"] == f"127.0.0.1:{closed_port}"
    assert facts["tcp_reachable"] is False
    assert facts["auth_ok"] is False
    dumped = str(facts)
    assert "alice" not in dumped
    assert "supersecret" not in dumped
    assert "mysql+pymysql" not in dumped
