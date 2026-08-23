"""Unit tests for the ADR-0011 bench2 protocol primitives and summary math."""

import csv
import json

import pytest

from gdgap.bench import run2


def test_agn_patterns_alternate_and_cycle():
    """Checks the pre-specified ABBA/BAAB alternation, cycling past four blocks."""
    assert run2.build_patterns("agn", 4) == ("ABBA", "BAAB", "ABBA", "BAAB")
    assert run2.build_patterns("agn", 3) == ("ABBA", "BAAB", "ABBA")
    assert run2.build_patterns("agn", 6) == ("ABBA", "BAAB", "ABBA", "BAAB", "ABBA", "BAAB")


def test_eq_patterns_are_aware_only():
    """Checks that the W_eq workload never schedules the blind variant."""
    patterns = run2.build_patterns("eq", 4)
    assert patterns == ("BB",) * 4
    assert {run2.VARIANT_OF[letter] for pattern in patterns for letter in pattern} == {"aware"}


def test_condition_tables_match_adr_0011():
    """Checks the frozen condition specs, including the c3 promotion toggle."""
    innodb = run2.conditions_for("innodb")
    assert innodb["c1"] == {"pool_bytes": 134217728, "old_blocks_time_ms": 1000}
    assert innodb["c2"] == {"pool_bytes": 1073741824, "old_blocks_time_ms": 1000}
    assert innodb["c3"] == {"pool_bytes": 134217728, "old_blocks_time_ms": 0}
    assert list(run2.conditions_for("ducklake")) == ["d0"]


def test_counter_delta_subtracts_and_keeps_free_level():
    """Checks per-execution counter deltas plus the absolute post-execution free level."""
    before = {
        "pool_read_requests": 10,
        "pool_reads": 2,
        "pool_read_ahead": 1,
        "pages_made_young": 5,
        "pages_not_made_young": 7,
        "free_buffers": 100,
    }
    after = {
        "pool_read_requests": 40,
        "pool_reads": 12,
        "pool_read_ahead": 1,
        "pages_made_young": 25,
        "pages_not_made_young": 8,
        "free_buffers": 60,
    }
    assert run2.counter_delta(before, after) == {
        "d_pool_read_requests": 30,
        "d_pool_reads": 10,
        "d_pool_read_ahead": 0,
        "d_pages_made_young": 20,
        "d_pages_not_made_young": 1,
        "free_buffers_after": 60,
    }


def test_t_critical_is_conservative():
    """Checks the largest-key-below lookup, which widens rather than narrows intervals."""
    assert run2._t_critical(0) is None
    assert run2._t_critical(3) == 3.182
    assert run2._t_critical(12) == 2.228
    assert run2._t_critical(50) == 2.042


def test_block_delta_stats_point_estimate_and_intervals():
    """Checks the mean-of-block-deltas estimator, the t-interval, and bootstrap determinism."""
    deltas = [1.0, 2.0, 3.0, 4.0]
    stats = run2.block_delta_stats(deltas, bootstrap_seed=42)
    assert stats["mean"] == pytest.approx(2.5)
    half = 3.182 * (5.0 / 3.0) ** 0.5 / 2.0  # stdev([1,2,3,4]) = sqrt(5/3), df = 3
    assert stats["t_low"] == pytest.approx(2.5 - half, rel=1e-9)
    assert stats["t_high"] == pytest.approx(2.5 + half, rel=1e-9)
    assert 1.0 <= stats["boot_low"] <= stats["boot_high"] <= 4.0
    assert run2.block_delta_stats(deltas, bootstrap_seed=42) == stats


def _runs_row(**overrides) -> dict:
    """Returns one synthetic runs.csv row with every bench2 field present."""
    row = {field: "" for field in run2.RUNS2_FIELDS}
    row.update(
        run_id="r1",
        git_commit="c0ffee",
        dataset="nhts2017",
        backend="innodb",
        condition="c1",
        workload="agn",
        pattern="ABBA",
        segment=1,
        outcome="ok",
        result_hash="h",
    )
    row.update(overrides)
    return row


def test_regenerate_summary2_block_deltas_counters_and_warmup_exclusion(tmp_path):
    """Checks per-block deltas, interval fields, counter medians, and warm-up exclusion."""
    elapsed = {
        ("blind", 1): [100.0, 102.0],
        ("aware", 1): [90.0, 92.0],
        ("blind", 2): [110.0, 112.0],
        ("aware", 2): [91.0, 91.0],
    }
    rows = []
    for (variant, block), values in elapsed.items():
        for repetition, value in enumerate(values, start=1):
            rows.append(
                _runs_row(
                    variant=variant,
                    block=block,
                    repetition=repetition,
                    query_id="q_agn_01_care_trip_share_total",
                    elapsed_ms=f"{value:.3f}",
                    d_pool_reads="5" if variant == "blind" else "0",
                    d_pages_made_young="0" if variant == "blind" else "7",
                )
            )
    rows.append(
        _runs_row(
            variant="blind",
            block=1,
            repetition=0,
            outcome="warmup",
            query_id="q_agn_01_care_trip_share_total",
            elapsed_ms="999.000",
        )
    )
    rows.append(
        _runs_row(
            variant="aware",
            block=1,
            repetition=1,
            workload="eq",
            pattern="BB",
            query_id="q_eq_02_ppr",
            elapsed_ms="50.000",
        )
    )
    runs_path = tmp_path / run2.RUNS2_CSV
    runs_path.parent.mkdir(parents=True)
    with open(runs_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=run2.RUNS2_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    envinfo_path = tmp_path / run2.ENVINFO2_JSON
    envinfo_path.write_text(json.dumps({"r1": {"bootstrap_seed": 7}}), encoding="utf-8")
    run2.regenerate_summary2(tmp_path)
    with open(tmp_path / run2.SUMMARY2_CSV, newline="", encoding="utf-8") as handle:
        summary = {(row["workload"], row["query_id"]): row for row in csv.DictReader(handle)}
    agn = summary[("agn", "q_agn_01_care_trip_share_total")]
    # Block deltas: (91 - 101) and (91 - 111) → mean -15; the 999 ms warm-up stays excluded
    assert agn["blind_median_ms"] == "106.000"
    assert agn["aware_median_ms"] == "91.000"
    assert agn["delta_mean_ms"] == "-15.000"
    assert float(agn["delta_t95_low_ms"]) < -15.0 < float(agn["delta_t95_high_ms"])
    assert float(agn["delta_boot95_low_ms"]) <= -10.0
    assert float(agn["delta_boot95_high_ms"]) >= -20.0 or float(agn["delta_boot95_high_ms"]) <= -10.0
    assert agn["n_blocks"] == "2"
    assert agn["hash_stable"] == "True"
    assert agn["blind_phys_reads_median"] == "5.0"
    assert agn["aware_phys_reads_median"] == "0.0"
    assert agn["aware_made_young_median"] == "7.0"
    assert agn["bootstrap_seed"] == "7"
    eq = summary[("eq", "q_eq_02_ppr")]
    assert eq["aware_median_ms"] == "50.000"
    assert eq["blind_median_ms"] == ""
    assert eq["delta_mean_ms"] == ""
