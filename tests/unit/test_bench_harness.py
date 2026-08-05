"""Unit tests for the ADR-0004 benchmark harness building blocks."""

from decimal import Decimal
from pathlib import Path

import click
import pytest

from gdgap.bench import run as bench_run

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_catalogue_is_frozen_and_backend_neutral():
    """Discovers the four frozen queries with families, placeholders, and no physical schemas."""
    queries = bench_run.load_catalogue(REPO_ROOT)
    assert [query.query_id for query in queries] == [
        "q_agn_01_care_trip_share_total",
        "q_agn_02_mode_share",
        "q_eq_01_care_trip_share_by_sex",
        "q_eq_02_ppr",
    ]
    assert [query.family for query in queries] == ["q_agn", "q_agn", "q_eq", "q_eq"]
    for query in queries:
        assert bench_run.SCHEMA_PLACEHOLDER in query.body
        assert "lake." not in query.body
        assert "gdgap_" not in query.body


def test_catalogue_refuses_hardcoded_schema(tmp_path):
    """Rejects bodies that bypass the {schema} placeholder contract."""
    directory = tmp_path / "sql" / "bench"
    directory.mkdir(parents=True)
    (directory / "q_agn_99_bad.sql").write_text("SELECT 1 FROM lake.blind.fact_trip;", encoding="utf-8")
    with pytest.raises(click.ClickException, match="schema"):
        bench_run.load_catalogue(tmp_path)


def test_catalogue_refuses_unknown_family(tmp_path):
    """Rejects files outside the q_agn/q_eq naming contract."""
    directory = tmp_path / "sql" / "bench"
    directory.mkdir(parents=True)
    (directory / "q_new_01_x.sql").write_text("SELECT 1 FROM {schema}.fact_trip;", encoding="utf-8")
    with pytest.raises(click.ClickException, match="q_agn"):
        bench_run.load_catalogue(tmp_path)


def test_render_and_target_schemas():
    """Substitutes every placeholder occurrence for both backends."""
    body = "SELECT * FROM {schema}.fact_trip JOIN {schema}.dim_person_sex USING (houseid);"
    assert bench_run.target_schema("ducklake", "aware") == "lake.aware"
    assert bench_run.target_schema("innodb", "blind") == "gdgap_blind"
    rendered = bench_run.render(body, "lake.aware")
    assert bench_run.SCHEMA_PLACEHOLDER not in rendered
    assert rendered.count("lake.aware") == 2


def test_result_hash_is_order_independent_and_normalised():
    """Hashes rows independent of order and of float/Decimal representation, with NULL handling."""
    first = bench_run.result_hash([(1, 0.30000000000000004, None), ("x", Decimal("2.5"), "y")])
    second = bench_run.result_hash([("x", 2.5, "y"), (1, 0.3, None)])
    assert first == second
    assert bench_run.result_hash([(1,)]) != bench_run.result_hash([(2,)])
    assert bench_run.result_hash([]) == bench_run.result_hash([])


def test_quantile_stats_median_and_inclusive_iqr():
    """Computes median, inclusive-method IQR, and the range."""
    median, iqr, low, high = bench_run._quantile_stats([1.0, 2.0, 3.0, 4.0, 5.0])
    assert (median, iqr, low, high) == (3.0, 2.0, 1.0, 5.0)
    median, iqr, low, high = bench_run._quantile_stats([7.5])
    assert (median, iqr, low, high) == (7.5, 0.0, 7.5, 7.5)


def test_q_eq_is_not_representable_on_blind():
    """Classifies q_eq as aware-only while q_agn runs everywhere (the R2 capability contrast)."""
    q_eq = bench_run.BenchQuery(query_id="q_eq_01_x", family="q_eq", body="SELECT 1")
    q_agn = bench_run.BenchQuery(query_id="q_agn_01_x", family="q_agn", body="SELECT 1")
    assert not bench_run.is_runnable(q_eq, "blind")
    assert bench_run.is_runnable(q_eq, "aware")
    assert bench_run.is_runnable(q_agn, "blind")
    assert bench_run.is_runnable(q_agn, "aware")


def test_parse_memory_bytes_units():
    """Parses engine memory strings in decimal and binary units."""
    assert bench_run._parse_memory_bytes("8GB") == 8_000_000_000
    assert bench_run._parse_memory_bytes("8.0 GiB") == 8 * 1024**3
    assert bench_run._parse_memory_bytes("512") == 512


class _FakeInnodbBackend:
    """Duck-typed InnodbBackend stand-in answering only the settings queries."""

    name = "innodb"
    host = "127.0.0.1"
    port = 3307

    def fetchall(self, sql: str) -> list[tuple]:
        """Returns canned rows for the version and buffer-pool queries."""
        if "version()" in sql:
            return [("8.4.11",)]
        return [("innodb_buffer_pool_size", 134217728)]


def test_engine_settings_record_sanitized_mysql_transport():
    """Persists mysql host/port (never credentials) alongside the buffer pool for envinfo (ADR-0008)."""
    settings = bench_run._engine_settings(_FakeInnodbBackend())
    assert settings["engine_version"] == "mysql 8.4.11"
    assert settings["native"]["mysql_host"] == "127.0.0.1"
    assert settings["native"]["mysql_port"] == "3307"
    assert settings["native"]["innodb_buffer_pool_size"] == "134217728"
