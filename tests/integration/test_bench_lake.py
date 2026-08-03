"""Integration tests for the Phase E warm benchmark harness on the fixture lake."""

import csv
import json
import os
from contextlib import closing
from pathlib import Path

import click
import pytest

from gdgap import build as build_module
from gdgap.bench import run as bench_run
from gdgap.ingest import nhts2017

requires_mysql = pytest.mark.skipif(not os.environ.get("GDGAP_MYSQL_URL"), reason="GDGAP_MYSQL_URL not set")


def _read_rows(path: Path) -> list[dict]:
    """Returns all rows of a CSV file as dictionaries."""
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _bench_both_variants(lake_root: Path) -> None:
    """Ingests, builds both DuckLake variants, and benches both cells with a fixed seed."""
    nhts2017.ingest(root=lake_root)
    build_module.build("blind", root=lake_root)
    build_module.build("aware", root=lake_root)
    # Fixture-scale writes are data-inlined into the metadata catalog; flushing materialises
    # Parquet files so the snapshot-aware storage probe sees real bytes (ADR-0004)
    with nhts2017._chdir(lake_root), closing(nhts2017._connect(lake_root)) as con:
        con.execute("call ducklake_flush_inlined_data('lake')")
    bench_run.run_bench(backend_name="ducklake", variant="blind", repetitions=2, seed=7, root=lake_root)
    bench_run.run_bench(backend_name="ducklake", variant="aware", repetitions=2, seed=7, root=lake_root)


def test_bench_emits_runs_capability_states_hashes_plans_and_envinfo(lake_root):
    """Checks raw rows, not_representable states, cross-variant q_agn hash agreement, plans, envinfo."""
    _bench_both_variants(lake_root)
    rows = _read_rows(lake_root / bench_run.RUNS_CSV)
    # blind: 2 q_agn x 2 reps + 2 q_eq capability rows; aware: 4 queries x 2 reps
    assert len(rows) == 4 + 2 + 8
    blind_eq = [row for row in rows if row["variant"] == "blind" and row["family"] == "q_eq"]
    assert {row["outcome"] for row in blind_eq} == {"not_representable"}
    assert all(row["elapsed_ms"] == "" and row["result_hash"] == "" for row in blind_eq)
    ok_rows = [row for row in rows if row["outcome"] == "ok"]
    assert len(ok_rows) == 12
    assert all(row["result_hash"] and row["elapsed_ms"] for row in ok_rows)
    # q_agn results must agree across variants on the same engine (identical fact grain, ADR-0004)
    for query_id in ("q_agn_01_care_trip_share_total", "q_agn_02_mode_share"):
        hashes = {row["result_hash"] for row in ok_rows if row["query_id"] == query_id}
        assert len(hashes) == 1
    for row in ok_rows:
        assert (lake_root / row["plan_path"]).is_file()
    envinfo = json.loads((lake_root / bench_run.ENVINFO_JSON).read_text(encoding="utf-8"))
    assert len(envinfo) == 2
    assert {info["seed"] for info in envinfo.values()} == {7}
    assert all(info["temperature"] == "warm" for info in envinfo.values())
    assert all(info["backend_native_settings"] for info in envinfo.values())


def test_bench_regenerates_summary_and_snapshot_aware_storage(lake_root):
    """Checks the derived summary statistics and the snapshot-aware storage accounting."""
    _bench_both_variants(lake_root)
    summary = _read_rows(lake_root / bench_run.SUMMARY_CSV)
    ok = [row for row in summary if row["outcome"] == "ok"]
    assert len(ok) == 6  # blind: 2 q_agn; aware: 4 queries
    assert all(row["n_recorded"] == "2" and row["hash_stable"] == "True" for row in ok)
    assert all(float(row["median_ms"]) >= 0.0 for row in ok)
    not_representable = [row for row in summary if row["outcome"] == "not_representable"]
    assert {(row["variant"], row["family"]) for row in not_representable} == {("blind", "q_eq")}
    storage = _read_rows(lake_root / bench_run.STORAGE_CSV)
    totals = {
        row["variant"]: int(row["bytes"])
        for row in storage
        if row["table_name"] == "TOTAL" and row["variant"] in ("blind", "aware")
    }
    assert totals["blind"] > 0
    assert totals["aware"] > totals["blind"]
    deltas = [row for row in storage if row["variant"] == "aware_minus_blind"]
    assert len(deltas) == 2  # one per bench invocation, both measuring the same built lake
    assert int(deltas[0]["bytes"]) == totals["aware"] - totals["blind"]
    aware_tables = {row["table_name"] for row in storage if row["variant"] == "aware"}
    assert {"fact_person", "fact_trip", "dim_person_sex", "TOTAL"} <= aware_tables
    assert all(row["method"] == "ducklake_metadata_active_files" for row in storage)


def test_bench_rejects_non_warm_temperature(lake_root):
    """Refuses a cold run until the reset method has its own ADR (ADR-0004)."""
    with pytest.raises(click.ClickException, match="warm"):
        bench_run.run_bench(backend_name="ducklake", variant="blind", temperature="cold", root=lake_root)


@requires_mysql
def test_bench_innodb_smoke(lake_root):
    """Benches the InnoDB foil cell end to end (needs GDGAP_MYSQL_URL and the built mirrors)."""
    nhts2017.ingest(root=lake_root)
    build_module.build("blind", root=lake_root)
    build_module.build("aware", root=lake_root)
    build_module.build("blind", backend_name="innodb", root=lake_root)
    build_module.build("aware", backend_name="innodb", root=lake_root)
    rows = bench_run.run_bench(backend_name="innodb", variant="aware", repetitions=2, seed=7, root=lake_root)
    assert {row["outcome"] for row in rows} == {"ok"}
    storage = _read_rows(lake_root / bench_run.STORAGE_CSV)
    assert any(row["method"] == "information_schema_after_analyze" for row in storage)
