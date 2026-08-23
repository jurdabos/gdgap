"""Integration tests for the ADR-0011 bench2 mechanism-probe harness on the fixture lake."""

import csv
import json
import os
from contextlib import closing
from pathlib import Path

import click
import pytest

from gdgap import build as build_module
from gdgap.bench import run2
from gdgap.ingest import nhts2017

requires_mysql = pytest.mark.skipif(
    not os.environ.get("GDGAP_MYSQL_TEST_URL"), reason="GDGAP_MYSQL_TEST_URL not set (dedicated test endpoint)"
)


def _read_rows(path: Path) -> list[dict]:
    """Returns all rows of a CSV file as dictionaries."""
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _prepare_lake(lake_root: Path) -> None:
    """Ingests the fixture CSVs and builds both DuckLake variants."""
    nhts2017.ingest(root=lake_root)
    build_module.build("blind", root=lake_root)
    build_module.build("aware", root=lake_root)
    with nhts2017._chdir(lake_root), closing(nhts2017._connect(lake_root)) as con:
        con.execute("call ducklake_flush_inlined_data('lake')")


def test_bench2_ducklake_end_to_end(lake_root):
    """Runs one d0 cell and checks rows, patterns, plans, envinfo, and the derived summary."""
    _prepare_lake(lake_root)
    rows = run2.run_bench2(
        backend_name="ducklake", condition="d0", blocks=1, reps=1, bootstrap_seed=7, allow_small=True, root=lake_root
    )
    # agn: ABBA -> 4 segments x (warm-up + 1 rep) x 2 queries; eq: BB -> 2 x 2 x 2
    assert len(rows) == 16 + 8
    ok_rows = [row for row in rows if row["outcome"] == "ok"]
    warmups = [row for row in rows if row["outcome"] == "warmup"]
    assert len(ok_rows) == 12
    assert len(warmups) == 12
    assert {row["pattern"] for row in rows if row["workload"] == "agn"} == {"ABBA"}
    assert {row["pattern"] for row in rows if row["workload"] == "eq"} == {"BB"}
    assert {row["variant"] for row in rows if row["workload"] == "eq"} == {"aware"}
    # Counters are honest-NA on DuckLake; hashes agree across variants for q_agn
    assert all(row["d_pool_reads"] == "" for row in rows)
    for query_id in ("q_agn_01_care_trip_share_total", "q_agn_02_mode_share"):
        hashes = {row["result_hash"] for row in ok_rows if row["query_id"] == query_id}
        assert len(hashes) == 1
    plans = sorted(path.name for path in (lake_root / run2.PLANS2_DIR).iterdir())
    assert len(plans) == 6  # agn: 2 variants x 2 queries; eq: aware x 2 queries
    assert all(name.startswith("ducklake_d0_") and name.endswith("_profile.json") for name in plans)
    envinfo = json.loads((lake_root / run2.ENVINFO2_JSON).read_text(encoding="utf-8"))
    (snapshot,) = envinfo.values()
    assert snapshot["protocol"] == "bench2 (ADR-0011)"
    assert snapshot["bootstrap_seed"] == 7
    assert snapshot["patterns"] == {"agn": ["ABBA"], "eq": ["BB"]}
    summary = _read_rows(lake_root / run2.SUMMARY2_CSV)
    agn = {row["query_id"]: row for row in summary if row["workload"] == "agn"}
    assert set(agn) == {"q_agn_01_care_trip_share_total", "q_agn_02_mode_share"}
    for row in agn.values():
        assert row["delta_mean_ms"] != ""
        assert row["delta_boot95_low_ms"] != ""
        assert row["delta_t95_low_ms"] == ""  # one block -> no t-interval
        assert row["hash_stable"] == "True"
    eq = [row for row in summary if row["workload"] == "eq"]
    assert all(row["delta_mean_ms"] == "" and row["aware_median_ms"] != "" for row in eq)


def test_bench2_scale_guard_refuses_fixture_scale(lake_root):
    """Refuses evidence-grade runs against fixture-scale variants without --allow-small."""
    _prepare_lake(lake_root)
    with pytest.raises(click.ClickException, match="rebuild the full-scale"):
        run2.run_bench2(backend_name="ducklake", condition="d0", blocks=1, reps=1, root=lake_root)


def test_bench2_rejects_unknown_condition(lake_root):
    """Refuses conditions outside the frozen ADR-0011 table for the backend."""
    _prepare_lake(lake_root)
    with pytest.raises(click.ClickException, match="not defined for ducklake"):
        run2.run_bench2(backend_name="ducklake", condition="c1", blocks=1, reps=1, allow_small=True, root=lake_root)


@requires_mysql
def test_bench2_innodb_c1_smoke(lake_root, mysql_test_endpoint):
    """Runs a c1 cell against the disposable test server and checks counters and plan kinds."""
    _prepare_lake(lake_root)
    build_module.build("blind", backend_name="innodb", root=lake_root)
    build_module.build("aware", backend_name="innodb", root=lake_root)
    rows = run2.run_bench2(
        backend_name="innodb", condition="c1", blocks=1, reps=1, bootstrap_seed=7, allow_small=True, root=lake_root
    )
    ok_rows = [row for row in rows if row["outcome"] == "ok"]
    assert ok_rows and all(row["d_pool_read_requests"] != "" for row in ok_rows)
    assert all(str(row["pool_bytes"]) == "134217728" for row in rows)
    plans = {path.name for path in (lake_root / run2.PLANS2_DIR).iterdir() if path.name.startswith("innodb_")}
    assert any(name.endswith("_estimate.json") for name in plans)
    assert any(name.endswith("_analyze.txt") for name in plans)
