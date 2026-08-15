"""Unit tests for the live-InnoDB test-endpoint guard (no live server required)."""

import os

import pytest


def test_guard_skips_without_test_url(monkeypatch, request):
    """Skips live-InnoDB tests when no dedicated test endpoint is declared."""
    monkeypatch.delenv("GDGAP_MYSQL_TEST_URL", raising=False)
    with pytest.raises(pytest.skip.Exception):
        request.getfixturevalue("mysql_test_endpoint")


def test_guard_refuses_the_evidence_endpoint(monkeypatch, request):
    """Fails hard when the test URL resolves to the same server as the evidence URL."""
    monkeypatch.setenv("GDGAP_MYSQL_TEST_URL", "mysql+pymysql://root:x@*********:3307")
    monkeypatch.setenv("GDGAP_MYSQL_URL", "mysql+pymysql://root:y@*********:3307")
    with pytest.raises(pytest.fail.Exception):
        request.getfixturevalue("mysql_test_endpoint")


def test_guard_rebinds_the_backend_url_to_the_test_endpoint(monkeypatch, request):
    """Points GDGAP_MYSQL_URL at the test endpoint for the test's duration."""
    monkeypatch.setenv("GDGAP_MYSQL_TEST_URL", "mysql+pymysql://root:x@*********:3308")
    monkeypatch.setenv("GDGAP_MYSQL_URL", "mysql+pymysql://root:y@*********:3307")
    url = request.getfixturevalue("mysql_test_endpoint")
    assert url == "mysql+pymysql://root:x@*********:3308"
    assert os.environ["GDGAP_MYSQL_URL"] == url
