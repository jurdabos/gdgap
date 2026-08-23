"""
Benchmark protocol v2: the buffer-pool mechanism probe behind `gdgap bench2` (ADR-0011).

One invocation runs one backend x condition cell: the W_agn workload on both variants in
counterbalanced ABBA/BAAB blocks (identical fixed query sequence and warm-up per segment),
then the aware-only W_eq workload. InnoDB executions are instrumented with buffer-pool
counters captured outside the timed window; plans are captured during first warm-up
segments only (DuckDB runtime profiles; MySQL EXPLAIN FORMAT=JSON plus EXPLAIN ANALYZE).
Evidence lands under results/bench2/ (append-only runs.csv, run-keyed envinfo.json, the
derived summary.csv, and plans/) and is never pooled with the ADR-0004 v1 evidence.
"""

import csv
import json
import platform
import random
import statistics
import time
from datetime import UTC, datetime
from itertools import cycle, islice
from pathlib import Path

import click

from gdgap.bench.run import (
    _connect,
    _cpu_model,
    _engine_settings,
    _git_commit,
    _merge_envinfo,
    _ram_bytes,
    load_catalogue,
    render,
    result_hash,
    target_schema,
)
from gdgap.ingest.nhts2017 import DATASET, _append_csv, _chdir, find_root

BENCH2_DIR = Path("results/bench2")
RUNS2_CSV = BENCH2_DIR / "runs.csv"
SUMMARY2_CSV = BENCH2_DIR / "summary.csv"
ENVINFO2_JSON = BENCH2_DIR / "envinfo.json"
PLANS2_DIR = BENCH2_DIR / "plans"
VARIANT_OF = {"A": "blind", "B": "aware"}
BASE_PATTERNS = ("ABBA", "BAAB")
WORKLOAD_FAMILY = {"agn": "q_agn", "eq": "q_eq"}
# Conditions per ADR-0011; the pool is set via the compose knob and only verified here
DUCKLAKE_CONDITIONS = {"d0": {"pool_bytes": None, "old_blocks_time_ms": None}}
INNODB_CONDITIONS = {
    "c1": {"pool_bytes": 134217728, "old_blocks_time_ms": 1000},
    "c2": {"pool_bytes": 1073741824, "old_blocks_time_ms": 1000},
    "c3": {"pool_bytes": 134217728, "old_blocks_time_ms": 0},
}
DEFAULT_OLD_BLOCKS_TIME_MS = 1000
MIN_FULL_SCALE_TRIP_ROWS = 900_000
BOOTSTRAP_RESAMPLES = 10_000
# Two-sided 95 % Student-t critical values by degrees of freedom; the largest key <= df is
# used (conservative: fewer df give a wider interval), since the stdlib has no inverse t.
T_CRITICAL_95 = {
    1: 12.706,
    2: 4.303,
    3: 3.182,
    4: 2.776,
    5: 2.571,
    6: 2.447,
    7: 2.365,
    8: 2.306,
    9: 2.262,
    10: 2.228,
    15: 2.131,
    20: 2.086,
    30: 2.042,
}
COUNTER_FIELDS = [
    "d_pool_read_requests",
    "d_pool_reads",
    "d_pool_read_ahead",
    "d_pages_made_young",
    "d_pages_not_made_young",
    "free_buffers_after",
]
RUNS2_FIELDS = [
    "run_id",
    "timestamp_utc",
    "git_commit",
    "dataset",
    "backend",
    "condition",
    "pool_bytes",
    "old_blocks_time_ms",
    "workload",
    "block",
    "pattern",
    "segment",
    "variant",
    "query_id",
    "repetition",
    "outcome",
    "failure_reason",
    "elapsed_ms",
    "rows_returned",
    "result_hash",
    "rep_ts_utc",
    *COUNTER_FIELDS,
    "engine_version",
    "python_version",
    "kernel",
    "cpu_model",
    "ram_bytes",
]
SUMMARY2_FIELDS = [
    "run_id",
    "git_commit",
    "backend",
    "condition",
    "workload",
    "query_id",
    "n_blocks",
    "n_reps_per_variant",
    "blind_median_ms",
    "aware_median_ms",
    "delta_mean_ms",
    "delta_t95_low_ms",
    "delta_t95_high_ms",
    "delta_boot95_low_ms",
    "delta_boot95_high_ms",
    "delta_rel_pct",
    "hash_stable",
    "blind_phys_reads_median",
    "aware_phys_reads_median",
    "blind_made_young_median",
    "aware_made_young_median",
    "bootstrap_seed",
]


def conditions_for(backend_name: str) -> dict[str, dict]:
    """Returns the ADR-0011 condition table for one backend."""
    return DUCKLAKE_CONDITIONS if backend_name == "ducklake" else INNODB_CONDITIONS


def build_patterns(workload: str, blocks: int) -> tuple[str, ...]:
    """Returns the pre-specified per-block variant patterns for a workload (ADR-0011)."""
    if workload == "eq":
        return ("BB",) * blocks
    return tuple(islice(cycle(BASE_PATTERNS), blocks))


def _pool_counters(backend) -> dict[str, int]:
    """Reads the InnoDB buffer-pool counters used by the mechanism probe (ADR-0011)."""
    raw = backend.fetchall("show global status like 'Innodb_buffer_pool_read%'")
    status = {name: int(value) for name, value in raw}
    free, young, not_young = backend.fetchall(
        "select sum(free_buffers), sum(pages_made_young), sum(pages_not_made_young) "
        "from information_schema.innodb_buffer_pool_stats"
    )[0]
    return {
        "pool_read_requests": status["Innodb_buffer_pool_read_requests"],
        "pool_reads": status["Innodb_buffer_pool_reads"],
        "pool_read_ahead": status["Innodb_buffer_pool_read_ahead"],
        "pages_made_young": int(young),
        "pages_not_made_young": int(not_young),
        "free_buffers": int(free),
    }


def counter_delta(before: dict[str, int], after: dict[str, int]) -> dict[str, int]:
    """Returns the per-execution counter deltas plus the post-execution free-buffer level."""
    return {
        "d_pool_read_requests": after["pool_read_requests"] - before["pool_read_requests"],
        "d_pool_reads": after["pool_reads"] - before["pool_reads"],
        "d_pool_read_ahead": after["pool_read_ahead"] - before["pool_read_ahead"],
        "d_pages_made_young": after["pages_made_young"] - before["pages_made_young"],
        "d_pages_not_made_young": after["pages_not_made_young"] - before["pages_not_made_young"],
        "free_buffers_after": after["free_buffers"],
    }


def _empty_counters() -> dict[str, str]:
    """Returns honest-NA counter columns for backends without a buffer-pool probe."""
    return {field: "" for field in COUNTER_FIELDS}


def _innodb_settings(backend) -> tuple[int, int]:
    """Reads back innodb_buffer_pool_size and innodb_old_blocks_time from the live server."""
    pool = int(backend.fetchall("show global variables like 'innodb_buffer_pool_size'")[0][1])
    old_ms = int(backend.fetchall("show global variables like 'innodb_old_blocks_time'")[0][1])
    return pool, old_ms


def _verify_condition(backend, condition: str, spec: dict) -> tuple[int, int]:
    """
    Verifies the live server against the declared condition and applies the c3 toggle.

    The pool size must already match (it is a restart-scoped compose knob); the runner
    aborts with the restart instruction otherwise. innodb_old_blocks_time is set
    dynamically to the condition value and read back (ADR-0011).
    """
    pool, old_ms = _innodb_settings(backend)
    if pool != spec["pool_bytes"]:
        raise click.ClickException(
            f"condition {condition} needs innodb_buffer_pool_size={spec['pool_bytes']}, server reports {pool} — "
            f"restart the container: GDGAP_MYSQL_BUFFER_POOL={spec['pool_bytes']} docker compose up -d "
            "--force-recreate --wait"
        )
    if old_ms != spec["old_blocks_time_ms"]:
        backend.execute(f"set global innodb_old_blocks_time = {spec['old_blocks_time_ms']}")
        _, old_ms = _innodb_settings(backend)
        if old_ms != spec["old_blocks_time_ms"]:
            raise click.ClickException(f"could not set innodb_old_blocks_time to {spec['old_blocks_time_ms']}")
    return pool, old_ms


def _restore_old_blocks_time(backend_name: str, root: Path) -> None:
    """Restores innodb_old_blocks_time to the MySQL default after a c3 run (ADR-0011)."""
    backend = _connect(backend_name, root)
    try:
        backend.execute(f"set global innodb_old_blocks_time = {DEFAULT_OLD_BLOCKS_TIME_MS}")
    finally:
        backend.close()


def _scale_guard(backend, backend_name: str, allow_small: bool) -> None:
    """Refuses to record evidence against fixture-scale variants unless explicitly allowed."""
    if allow_small:
        return
    for variant in ("blind", "aware"):
        schema = target_schema(backend_name, variant)
        n = backend.fetchall(f"select count(*) from {schema}.fact_trip")[0][0]
        if int(n) < MIN_FULL_SCALE_TRIP_ROWS:
            raise click.ClickException(
                f"{schema}.fact_trip holds {n} rows (< {MIN_FULL_SCALE_TRIP_ROWS}) — rebuild the full-scale "
                f"variant first (gdgap build --variant {variant}"
                + (" --backend innodb" if backend_name == "innodb" else "")
                + "), or pass --allow-small for fixture runs"
            )


def _capture_plans(
    backend, backend_name: str, condition: str, variant: str, ordered: list, rendered: dict, root: Path
) -> None:
    """
    Captures per-query plan evidence during a first warm-up segment (ADR-0011).

    DuckDB profiles instrument the warm-up execution itself; MySQL captures both the
    optimizer estimate (EXPLAIN FORMAT=JSON) and an actual execution (EXPLAIN ANALYZE) —
    extra executions that stay inside the unrecorded warm-up phase by construction.
    """
    plans_dir = root / PLANS2_DIR
    plans_dir.mkdir(parents=True, exist_ok=True)
    for query in ordered:
        sql = rendered[query.query_id]
        stem = f"{backend_name}_{condition}_{variant}_{query.query_id}"
        if backend_name == "ducklake":
            profile = plans_dir / f"{stem}_profile.json"
            backend.execute("set enable_profiling = 'json'")
            backend.execute(f"set profiling_output = '{profile.as_posix()}'")
            backend.fetchall(sql)
            backend.execute("pragma disable_profiling")
        else:
            estimate = backend.fetchall(f"explain format=json {sql}")
            (plans_dir / f"{stem}_estimate.json").write_text(str(estimate[0][0]) + "\n", encoding="utf-8")
            actual = backend.fetchall(f"explain analyze {sql}")
            text = "\n".join(str(row[0]) for row in actual)
            (plans_dir / f"{stem}_analyze.txt").write_text(text + "\n", encoding="utf-8")


def _timed_fetch(backend, sql: str) -> tuple[float, list[tuple]]:
    """Executes one query and returns (elapsed_ms, rows), timed around execute-plus-full-fetch."""
    t0 = time.perf_counter_ns()
    rows = backend.fetchall(sql)
    return (time.perf_counter_ns() - t0) / 1e6, rows


def _execute_pass(
    backend, backend_name: str, ordered: list, rendered: dict, base: dict, repetition: int, outcome: str
) -> list[dict]:
    """
    Runs one full sequence pass (warm-up or recorded) and returns its evidence rows.

    Counter probes run outside the timed window, immediately before and after each
    execution, identically for every segment (ADR-0011).
    """
    rows_out: list[dict] = []
    for query in ordered:
        row = base | {"query_id": query.query_id, "repetition": repetition}
        before = _pool_counters(backend) if backend_name == "innodb" else None
        row["rep_ts_utc"] = datetime.now(UTC).isoformat(timespec="milliseconds")
        try:
            elapsed_ms, rows = _timed_fetch(backend, rendered[query.query_id])
            counters = counter_delta(before, _pool_counters(backend)) if before is not None else _empty_counters()
            row |= {
                "outcome": outcome,
                "failure_reason": "",
                "elapsed_ms": f"{elapsed_ms:.3f}",
                "rows_returned": len(rows),
                "result_hash": result_hash(rows),
            } | counters
        except Exception as exc:  # guardrail: logging the failure and continuing the run
            row |= {
                "outcome": "error",
                "failure_reason": str(exc).replace("\n", " ")[:500],
                "elapsed_ms": "",
                "rows_returned": "",
                "result_hash": "",
            } | _empty_counters()
            click.echo(f"  ⚠ {query.query_id} repetition {repetition}: {row['failure_reason']}")
        rows_out.append(row)
    return rows_out


def _t_critical(df: int) -> float | None:
    """Returns the conservative two-sided 95 % t critical value for the given df."""
    if df < 1:
        return None
    keys = [key for key in T_CRITICAL_95 if key <= df]
    return T_CRITICAL_95[max(keys)]


def block_delta_stats(deltas: list[float], bootstrap_seed: int) -> dict[str, float | None]:
    """
    Returns the ADR-0011 effect-size statistics over per-block aware-minus-blind deltas.

    Point estimate is the mean of block deltas; the t-interval uses blocks - 1 degrees of
    freedom; the bootstrap percentile interval resamples blocks with a seeded RNG.
    """
    mean = statistics.fmean(deltas)
    t_low = t_high = None
    if len(deltas) >= 2:
        crit = _t_critical(len(deltas) - 1)
        half = crit * statistics.stdev(deltas) / len(deltas) ** 0.5
        t_low, t_high = mean - half, mean + half
    rng = random.Random(bootstrap_seed)
    means = sorted(statistics.fmean(rng.choices(deltas, k=len(deltas))) for _ in range(BOOTSTRAP_RESAMPLES))
    boot_low = means[int(0.025 * BOOTSTRAP_RESAMPLES)]
    boot_high = means[int(0.975 * BOOTSTRAP_RESAMPLES) - 1]
    return {"mean": mean, "t_low": t_low, "t_high": t_high, "boot_low": boot_low, "boot_high": boot_high}


def _median_or_blank(values: list[float]) -> str:
    """Returns the formatted median of a sample, or an empty string for no data."""
    return f"{statistics.median(values):.3f}" if values else ""


def _counter_median(rows: list[dict], field: str) -> str:
    """Returns the median of one integer counter column over ok rows, blank when absent."""
    values = [int(row[field]) for row in rows if row.get(field, "") != ""]
    return f"{statistics.median(values):.1f}" if values else ""


def regenerate_summary2(root: Path) -> Path:
    """Rebuilds the derived bench2 summary.csv from every retained v2 raw row (ADR-0011)."""
    with open(root / RUNS2_CSV, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    envinfo_path = root / ENVINFO2_JSON
    envinfo = json.loads(envinfo_path.read_text(encoding="utf-8")) if envinfo_path.exists() else {}
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        if row["outcome"] not in ("ok",):
            continue
        key = (row["run_id"], row["git_commit"], row["backend"], row["condition"], row["workload"], row["query_id"])
        groups.setdefault(key, []).append(row)
    summary_rows: list[dict] = []
    for key, group in sorted(groups.items()):
        run_id, commit, backend_name, condition, workload, query_id = key
        seed = int(envinfo.get(run_id, {}).get("bootstrap_seed", 0))
        by_variant: dict[str, list[dict]] = {}
        for row in group:
            by_variant.setdefault(row["variant"], []).append(row)
        blind_ms = [float(row["elapsed_ms"]) for row in by_variant.get("blind", [])]
        aware_ms = [float(row["elapsed_ms"]) for row in by_variant.get("aware", [])]
        hashes = {row["result_hash"] for row in group}
        blocks = sorted({int(row["block"]) for row in group})
        record = {
            "run_id": run_id,
            "git_commit": commit,
            "backend": backend_name,
            "condition": condition,
            "workload": workload,
            "query_id": query_id,
            "n_blocks": len(blocks),
            "n_reps_per_variant": max(len(blind_ms), len(aware_ms)),
            "blind_median_ms": _median_or_blank(blind_ms),
            "aware_median_ms": _median_or_blank(aware_ms),
            "delta_mean_ms": "",
            "delta_t95_low_ms": "",
            "delta_t95_high_ms": "",
            "delta_boot95_low_ms": "",
            "delta_boot95_high_ms": "",
            "delta_rel_pct": "",
            "hash_stable": str(len(hashes) == 1),
            "blind_phys_reads_median": _counter_median(by_variant.get("blind", []), "d_pool_reads"),
            "aware_phys_reads_median": _counter_median(by_variant.get("aware", []), "d_pool_reads"),
            "blind_made_young_median": _counter_median(by_variant.get("blind", []), "d_pages_made_young"),
            "aware_made_young_median": _counter_median(by_variant.get("aware", []), "d_pages_made_young"),
            "bootstrap_seed": seed,
        }
        if blind_ms and aware_ms:
            deltas: list[float] = []
            for block in blocks:
                blind_block = [float(r["elapsed_ms"]) for r in by_variant["blind"] if int(r["block"]) == block]
                aware_block = [float(r["elapsed_ms"]) for r in by_variant["aware"] if int(r["block"]) == block]
                if blind_block and aware_block:
                    deltas.append(statistics.median(aware_block) - statistics.median(blind_block))
            if deltas:
                stats = block_delta_stats(deltas, seed)
                blind_median = statistics.median(blind_ms)
                record.update(
                    delta_mean_ms=f"{stats['mean']:.3f}",
                    delta_t95_low_ms="" if stats["t_low"] is None else f"{stats['t_low']:.3f}",
                    delta_t95_high_ms="" if stats["t_high"] is None else f"{stats['t_high']:.3f}",
                    delta_boot95_low_ms=f"{stats['boot_low']:.3f}",
                    delta_boot95_high_ms=f"{stats['boot_high']:.3f}",
                    delta_rel_pct=f"{100.0 * stats['mean'] / blind_median:.2f}" if blind_median else "",
                )
        summary_rows.append(record)
    summary_path = root / SUMMARY2_CSV
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY2_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)
    return summary_path


def run_bench2(
    backend_name: str = "ducklake",
    condition: str | None = None,
    workload: str = "both",
    blocks: int = 4,
    reps: int = 5,
    bootstrap_seed: int | None = None,
    allow_small: bool = False,
    root: Path | None = None,
) -> list[dict]:
    """
    Runs one bench2 backend x condition cell per the ADR-0011 mechanism-probe protocol.

    Appends raw rows to results/bench2/runs.csv, merges the environment snapshot into the
    v2 envinfo.json, regenerates the derived v2 summary, and returns the appended rows.
    """
    root = root or find_root()
    table = conditions_for(backend_name)
    condition = condition or next(iter(table))
    if condition not in table:
        raise click.ClickException(
            f"condition '{condition}' is not defined for {backend_name}; available: {', '.join(table)}"
        )
    spec = table[condition]
    workloads = ("agn", "eq") if workload == "both" else (workload,)
    bootstrap_seed = bootstrap_seed if bootstrap_seed is not None else random.SystemRandom().randrange(2**32)
    started = datetime.now(UTC)
    run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-bench2-{backend_name}-{condition}"
    commit = _git_commit(root)
    log_rows: list[dict] = []
    settings: dict = {}
    pool_readback: int | None = None
    old_ms_readback: int | None = None
    with _chdir(root):
        queries = load_catalogue(root)
        try:
            probe = _connect(backend_name, root)
            try:
                if backend_name == "innodb":
                    pool_readback, old_ms_readback = _verify_condition(probe, condition, spec)
                _scale_guard(probe, backend_name, allow_small)
                settings = _engine_settings(probe)
            finally:
                probe.close()
            base_static = {
                "run_id": run_id,
                "timestamp_utc": started.strftime("%Y-%m-%d %H:%M:%S"),
                "git_commit": commit,
                "dataset": DATASET,
                "backend": backend_name,
                "condition": condition,
                "pool_bytes": "" if pool_readback is None else pool_readback,
                "old_blocks_time_ms": "" if old_ms_readback is None else old_ms_readback,
                "engine_version": settings["engine_version"],
                "python_version": platform.python_version(),
                "kernel": platform.uname().release,
                "cpu_model": _cpu_model(),
                "ram_bytes": _ram_bytes(),
            }
            plans_done: set[tuple[str, str]] = set()
            for load in workloads:
                family = WORKLOAD_FAMILY[load]
                ordered = [query for query in queries if query.family == family]
                patterns = build_patterns(load, blocks)
                for block_index, pattern in enumerate(patterns, start=1):
                    for segment_index, letter in enumerate(pattern, start=1):
                        variant = VARIANT_OF[letter]
                        schema = target_schema(backend_name, variant)
                        rendered = {query.query_id: render(query.body, schema) for query in ordered}
                        base = base_static | {
                            "workload": load,
                            "block": block_index,
                            "pattern": pattern,
                            "segment": segment_index,
                            "variant": variant,
                        }
                        backend = _connect(backend_name, root)
                        try:
                            if (load, variant) not in plans_done:
                                _capture_plans(backend, backend_name, condition, variant, ordered, rendered, root)
                                plans_done.add((load, variant))
                            log_rows.extend(_execute_pass(backend, backend_name, ordered, rendered, base, 0, "warmup"))
                            for repetition in range(1, reps + 1):
                                log_rows.extend(
                                    _execute_pass(backend, backend_name, ordered, rendered, base, repetition, "ok")
                                )
                        finally:
                            backend.close()
                        click.echo(f"  {load} block {block_index} ({pattern}) segment {segment_index}: {variant} done")
        finally:
            # Restoring the c3 toggle even on failure, so the server never lingers off-default
            if backend_name == "innodb" and condition == "c3":
                _restore_old_blocks_time(backend_name, root)
        _append_csv(root / RUNS2_CSV, RUNS2_FIELDS, log_rows)
        post_old_ms = None
        if backend_name == "innodb":
            check = _connect(backend_name, root)
            try:
                _, post_old_ms = _innodb_settings(check)
            finally:
                check.close()
        _merge_envinfo(
            root / ENVINFO2_JSON,
            run_id,
            {
                "protocol": "bench2 (ADR-0011)",
                "timestamp_utc": base_static["timestamp_utc"] if log_rows else started.strftime("%Y-%m-%d %H:%M:%S"),
                "git_commit": commit,
                "dataset": DATASET,
                "backend": backend_name,
                "condition": condition,
                "condition_spec": spec,
                "pool_bytes_readback": pool_readback,
                "old_blocks_time_ms_readback": old_ms_readback,
                "old_blocks_time_ms_after_run": post_old_ms,
                "workloads": list(workloads),
                "blocks": blocks,
                "reps_per_segment": reps,
                "patterns": {load: list(build_patterns(load, blocks)) for load in workloads},
                "bootstrap_seed": bootstrap_seed,
                "queries": {
                    load: [q.query_id for q in queries if q.family == WORKLOAD_FAMILY[load]] for load in workloads
                },
                "engine_version": settings.get("engine_version", ""),
                "backend_native_settings": settings.get("native", {}),
                "python_version": base_static["python_version"] if log_rows else "",
                "kernel": base_static["kernel"] if log_rows else "",
                "cpu_model": base_static["cpu_model"] if log_rows else "",
                "ram_bytes": base_static["ram_bytes"] if log_rows else 0,
                "image_digest": "",
            },
        )
        regenerate_summary2(root)
    recorded = sum(1 for row in log_rows if row["outcome"] == "ok")
    click.echo(
        f"✓ Bench2 {backend_name}/{condition}: {recorded} recorded row(s) "
        f"(+{sum(1 for r in log_rows if r['outcome'] == 'warmup')} warm-up) appended to {RUNS2_CSV.as_posix()}"
    )
    click.echo(f"✓ Summary regenerated at {SUMMARY2_CSV.as_posix()} — v2 evidence stays separate from results/bench/")
    return log_rows
