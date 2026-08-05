"""
Phase E benchmark harness: the warm-protocol runner behind `gdgap bench` (ADR-0004).

One invocation runs one matrix cell (backend x variant): a fresh backend connection,
one unrecorded warm-up per query that doubles as plan capture, then seed-shuffled
recorded repetitions timed around execute-plus-full-fetch. Evidence lands in
results/bench/ (append-only runs.csv and storage.csv, run-keyed envinfo.json, and the
derived summary.csv regenerated from all retained raw runs) plus results/plans/.
q_eq queries on the blind variant are recorded as not_representable without execution;
storage is measured snapshot-aware per ADR-0004, never by globbing Parquet files.
"""

import csv
import hashlib
import json
import os
import platform
import random
import statistics
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import click

from gdgap.bench.backends import get_backend
from gdgap.ingest.nhts2017 import DATASET, _append_csv, _chdir, find_root

BENCH_SQL_DIR = Path("sql/bench")
BENCH_DIR = Path("results/bench")
RUNS_CSV = BENCH_DIR / "runs.csv"
SUMMARY_CSV = BENCH_DIR / "summary.csv"
STORAGE_CSV = BENCH_DIR / "storage.csv"
ENVINFO_JSON = BENCH_DIR / "envinfo.json"
PLANS_DIR = Path("results/plans")
FAMILIES = ("q_agn", "q_eq")
SCHEMA_PLACEHOLDER = "{schema}"
# Declared DuckDB controls per ADR-0004; the actual engine values are persisted per run set
DUCKDB_THREADS = 4
DUCKDB_MEMORY_LIMIT = "8GB"
RUNS_FIELDS = [
    "run_id",
    "timestamp_utc",
    "git_commit",
    "dataset",
    "backend",
    "variant",
    "query_id",
    "family",
    "temperature",
    "repetition",
    "outcome",
    "failure_reason",
    "elapsed_ms",
    "rows_returned",
    "result_hash",
    "plan_path",
    "engine_version",
    "python_version",
    "threads",
    "memory_limit_bytes",
    "image_digest",
    "kernel",
    "cpu_model",
    "ram_bytes",
]
SUMMARY_FIELDS = [
    "run_id",
    "git_commit",
    "backend",
    "variant",
    "query_id",
    "family",
    "temperature",
    "outcome",
    "n_recorded",
    "median_ms",
    "iqr_ms",
    "min_ms",
    "max_ms",
    "result_hash",
    "hash_stable",
]
STORAGE_FIELDS = ["ts_utc", "run_id", "git_commit", "backend", "variant", "table_name", "bytes", "method"]


@dataclass(frozen=True)
class BenchQuery:
    """One catalogue query: its ID, family, and backend-neutral body."""

    query_id: str
    family: str
    body: str


def load_catalogue(root: Path) -> list[BenchQuery]:
    """
    Returns the frozen sql/bench/ catalogue in filename order.

    Refuses files outside the q_agn/q_eq naming contract, bodies missing the {schema}
    placeholder, and bodies hardcoding a physical schema (ADR-0004 backend neutrality).
    """
    directory = root / BENCH_SQL_DIR
    paths = sorted(directory.glob("*.sql"))
    if not paths:
        raise click.ClickException(f"no benchmark queries found under {BENCH_SQL_DIR.as_posix()}")
    queries: list[BenchQuery] = []
    for path in paths:
        family = next((prefix for prefix in FAMILIES if path.stem.startswith(prefix + "_")), None)
        if family is None:
            raise click.ClickException(f"{path.name}: name must start with one of: {', '.join(FAMILIES)}")
        body = path.read_text(encoding="utf-8")
        if SCHEMA_PLACEHOLDER not in body:
            raise click.ClickException(f"{path.name}: body must reference relations via {SCHEMA_PLACEHOLDER}")
        if "lake." in body or "gdgap_" in body:
            raise click.ClickException(f"{path.name}: physical schema names are forbidden; use {SCHEMA_PLACEHOLDER}")
        queries.append(BenchQuery(query_id=path.stem, family=family, body=body))
    return queries


def target_schema(backend_name: str, variant: str) -> str:
    """Returns the physical schema for one backend/variant cell."""
    return f"lake.{variant}" if backend_name == "ducklake" else f"gdgap_{variant}"


def render(body: str, schema: str) -> str:
    """Substitutes every {schema} placeholder occurrence with the physical target."""
    return body.replace(SCHEMA_PLACEHOLDER, schema)


def is_runnable(query: BenchQuery, variant: str) -> bool:
    """Returns whether a query is representable on a variant (q_eq needs the aware schema)."""
    return query.family != "q_eq" or variant == "aware"


def _canonical_cell(value) -> str:
    """Returns the ADR-0004 canonical string for one result cell."""
    if value is None:
        return "NULL"
    if isinstance(value, Decimal):
        value = float(value)
    if isinstance(value, float):
        return format(value, ".9g")
    return str(value)


def result_hash(rows: list[tuple]) -> str:
    """Hashes normalised, order-independently sorted result rows (SHA-256 hex, ADR-0004)."""
    canonical = sorted("\x1f".join(_canonical_cell(cell) for cell in row) for row in rows)
    return hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest()


def _parse_memory_bytes(text: str) -> int:
    """Parses an engine memory string such as '8.0 GiB' or '8GB' into bytes."""
    units = {
        "kib": 1024,
        "mib": 1024**2,
        "gib": 1024**3,
        "tib": 1024**4,
        "kb": 1000,
        "mb": 1000**2,
        "gb": 1000**3,
        "tb": 1000**4,
        "b": 1,
    }
    cleaned = text.strip().lower()
    for unit, factor in units.items():
        if cleaned.endswith(unit):
            return int(float(cleaned[: -len(unit)].strip()) * factor)
    return int(float(cleaned))


def _connect(backend_name: str, root: Path):
    """Opens a fresh backend connection with the declared ADR-0004 controls applied."""
    backend = get_backend(backend_name, root)
    if backend_name == "ducklake":
        backend.execute(f"set threads = {DUCKDB_THREADS}")
        backend.execute(f"set memory_limit = '{DUCKDB_MEMORY_LIMIT}'")
    return backend


def _engine_settings(backend) -> dict:
    """Returns engine identity and controls, honest-NA for backend-specific ones (ADR-0004)."""
    version = backend.fetchall("select version()")[0][0]
    if backend.name == "ducklake":
        threads = backend.fetchall("select current_setting('threads')")[0][0]
        memory = backend.fetchall("select current_setting('memory_limit')")[0][0]
        return {
            "engine_version": f"duckdb {version}",
            "threads": str(threads),
            "memory_limit_bytes": str(_parse_memory_bytes(str(memory))),
            "native": {"threads": str(threads), "memory_limit": str(memory)},
        }
    # threads/memory_limit are DuckDB control names; faking them for MySQL would invent a common setting
    pool = backend.fetchall("show variables like 'innodb_buffer_pool_size'")
    native = {name: str(value) for name, value in pool}
    # Recording sanitized transport provenance (ADR-0008): container-loopback and
    # remote-host runs would otherwise look identical in the evidence
    native["mysql_host"] = str(getattr(backend, "host", ""))
    native["mysql_port"] = str(getattr(backend, "port", ""))
    return {
        "engine_version": f"mysql {version}",
        "threads": "",
        "memory_limit_bytes": "",
        "native": native,
    }


def _warm_up_and_capture_plan(backend, sql: str, plan_path: Path) -> None:
    """Runs the unrecorded warm-up execution and captures the backend-native plan (ADR-0004)."""
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    if backend.name == "ducklake":
        # Profiling instruments only this warm-up execution; recorded repetitions stay clean
        backend.execute("set enable_profiling = 'json'")
        backend.execute(f"set profiling_output = '{plan_path.as_posix()}'")
        backend.fetchall(sql)
        backend.execute("pragma disable_profiling")
    else:
        backend.fetchall(sql)
        rows = backend.fetchall(f"explain format=json {sql}")
        plan_path.write_text(str(rows[0][0]) + "\n", encoding="utf-8")


def _cpu_model() -> str:
    """Returns the CPU model from /proc/cpuinfo, empty when unavailable."""
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def _ram_bytes() -> int:
    """Returns total physical memory in bytes, 0 when undeterminable."""
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError):
        return 0


def _git_commit(root: Path) -> str:
    """Returns the current commit hash, or 'unknown' when git is unavailable."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, encoding="utf-8", check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _merge_envinfo(path: Path, run_id: str, snapshot: dict) -> None:
    """Merges one run set's environment snapshot into envinfo.json, keyed by run_id."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    existing[run_id] = snapshot
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _quantile_stats(values: list[float]) -> tuple[float, float, float, float]:
    """Returns median, inclusive-method IQR, min, and max for a sample (ADR-0004)."""
    median = statistics.median(values)
    if len(values) >= 2:
        q1, _, q3 = statistics.quantiles(values, n=4, method="inclusive")
        iqr = q3 - q1
    else:
        iqr = 0.0
    return median, iqr, min(values), max(values)


def regenerate_summary(root: Path) -> Path:
    """Rebuilds the derived summary.csv from every retained raw run row (ADR-0004)."""
    with open(root / RUNS_CSV, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        key = (
            row["run_id"],
            row["git_commit"],
            row["backend"],
            row["variant"],
            row["query_id"],
            row["family"],
            row["temperature"],
        )
        groups.setdefault(key, []).append(row)
    summary_rows: list[dict] = []
    for key, group in sorted(groups.items()):
        run_id, commit, backend_name, variant, query_id, family, temperature = key
        timed = [row for row in group if row["outcome"] == "ok"]
        record = {
            "run_id": run_id,
            "git_commit": commit,
            "backend": backend_name,
            "variant": variant,
            "query_id": query_id,
            "family": family,
            "temperature": temperature,
            "outcome": "ok" if timed else group[0]["outcome"],
            "n_recorded": len(timed),
            "median_ms": "",
            "iqr_ms": "",
            "min_ms": "",
            "max_ms": "",
            "result_hash": "",
            "hash_stable": "",
        }
        if timed:
            median, iqr, low, high = _quantile_stats([float(row["elapsed_ms"]) for row in timed])
            hashes = {row["result_hash"] for row in timed}
            record.update(
                median_ms=f"{median:.3f}",
                iqr_ms=f"{iqr:.3f}",
                min_ms=f"{low:.3f}",
                max_ms=f"{high:.3f}",
                result_hash=sorted(hashes)[0] if len(hashes) == 1 else "UNSTABLE",
                hash_stable=str(len(hashes) == 1),
            )
        summary_rows.append(record)
    summary_path = root / SUMMARY_CSV
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_FIELDS)
        writer.writeheader()
        writer.writerows(summary_rows)
    return summary_path


def _ducklake_active_bytes(backend, variant: str) -> dict[str, int]:
    """
    Returns active-snapshot data-file bytes per base table of one lake variant schema.

    Reads the DuckLake metadata catalog attached alongside the lake and counts only data
    files whose end_snapshot is open, per ADR-0004 — a recursive Parquet glob would also
    count files retained from superseded snapshots and overstate current storage. Tables
    whose small writes were data-inlined into the metadata catalog carry no data files
    yet and appear honestly with zero bytes (flushable via ducklake_flush_inlined_data).
    """
    rows = backend.fetchall(
        "select t.table_name, coalesce(sum(f.file_size_bytes), 0) "
        "from __ducklake_metadata_lake.ducklake_table as t "
        "join __ducklake_metadata_lake.ducklake_schema as s on s.schema_id = t.schema_id "
        "left join __ducklake_metadata_lake.ducklake_data_file as f "
        "on f.table_id = t.table_id and f.end_snapshot is null "
        f"where s.schema_name = '{variant}' and t.end_snapshot is null and s.end_snapshot is null "
        "group by t.table_name order by t.table_name"
    )
    return {name: int(size) for name, size in rows}


def _innodb_active_bytes(backend, variant: str) -> dict[str, int]:
    """Returns DATA_LENGTH + INDEX_LENGTH per base table after an ANALYZE refresh (ADR-0004)."""
    database = f"gdgap_{variant}"
    tables = [
        row[0]
        for row in backend.fetchall(
            "select table_name from information_schema.tables "
            f"where table_schema = '{database}' and table_type = 'BASE TABLE' order by table_name"
        )
    ]
    for table in tables:
        backend.fetchall(f"analyze table {database}.{table}")
    rows = backend.fetchall(
        "select table_name, data_length + index_length from information_schema.tables "
        f"where table_schema = '{database}' and table_type = 'BASE TABLE' order by table_name"
    )
    return {name: int(size) for name, size in rows}


def _storage_row(
    ts_utc: str, run_id: str, commit: str, backend_name: str, variant: str, table: str, size: int, method: str
) -> dict:
    """Returns one storage.csv row."""
    return {
        "ts_utc": ts_utc,
        "run_id": run_id,
        "git_commit": commit,
        "backend": backend_name,
        "variant": variant,
        "table_name": table,
        "bytes": size,
        "method": method,
    }


def measure_storage(backend, backend_name: str, root: Path, run_id: str, commit: str) -> list[dict]:
    """
    Measures active storage for both variants of one backend and appends storage.csv.

    Emits per-table and TOTAL rows per variant plus the aware_minus_blind delta when both
    variants are measurable; warns instead of failing when a variant is not built yet.
    """
    ts_utc = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    method = "ducklake_metadata_active_files" if backend_name == "ducklake" else "information_schema_after_analyze"
    totals: dict[str, int] = {}
    log_rows: list[dict] = []
    for variant in ("blind", "aware"):
        if backend_name == "ducklake":
            sizes = _ducklake_active_bytes(backend, variant)
        else:
            sizes = _innodb_active_bytes(backend, variant)
        if not sizes:
            click.echo(f"  ⚠ storage: no tables found for {backend_name}/{variant} — build it first; skipping")
            continue
        for table, size in sorted(sizes.items()):
            log_rows.append(_storage_row(ts_utc, run_id, commit, backend_name, variant, table, size, method))
        totals[variant] = sum(sizes.values())
        log_rows.append(_storage_row(ts_utc, run_id, commit, backend_name, variant, "TOTAL", totals[variant], method))
    if set(totals) == {"blind", "aware"}:
        delta = totals["aware"] - totals["blind"]
        log_rows.append(_storage_row(ts_utc, run_id, commit, backend_name, "aware_minus_blind", "TOTAL", delta, method))
        click.echo(f"  storage: aware - blind = {delta} bytes on {backend_name}")
    if log_rows:
        _append_csv(root / STORAGE_CSV, STORAGE_FIELDS, log_rows)
    return log_rows


def run_bench(
    backend_name: str = "ducklake",
    variant: str = "blind",
    temperature: str = "warm",
    repetitions: int = 5,
    seed: int | None = None,
    skip_storage: bool = False,
    root: Path | None = None,
) -> list[dict]:
    """
    Runs one warm matrix cell (backend x variant) per the ADR-0004 protocol.

    Appends raw runs, merges the environment snapshot into envinfo.json, regenerates the
    derived summary, and measures storage unless skipped. Returns the appended run rows.
    """
    if temperature != "warm":
        raise click.ClickException("only the warm protocol is frozen (ADR-0004); a cold path needs its own ADR first")
    root = root or find_root()
    seed = seed if seed is not None else int.from_bytes(os.urandom(4), "big")
    rng = random.Random(seed)
    started = datetime.now(UTC)
    ts_utc = started.strftime("%Y-%m-%d %H:%M:%S")
    run_id = f"{started.strftime('%Y%m%dT%H%M%SZ')}-{backend_name}-{variant}-{temperature}"
    commit = _git_commit(root)
    log_rows: list[dict] = []
    with _chdir(root):
        queries = load_catalogue(root)
        schema = target_schema(backend_name, variant)
        backend = _connect(backend_name, root)
        try:
            settings = _engine_settings(backend)
            base = {
                "run_id": run_id,
                "timestamp_utc": ts_utc,
                "git_commit": commit,
                "dataset": DATASET,
                "backend": backend_name,
                "variant": variant,
                "temperature": temperature,
                "engine_version": settings["engine_version"],
                "python_version": platform.python_version(),
                "threads": settings["threads"],
                "memory_limit_bytes": settings["memory_limit_bytes"],
                "image_digest": "",
                "kernel": platform.uname().release,
                "cpu_model": _cpu_model(),
                "ram_bytes": _ram_bytes(),
            }
            # Capability differences are recorded states, not failed timing runs (ADR-0004)
            for query in (q for q in queries if not is_runnable(q, variant)):
                log_rows.append(
                    base
                    | {
                        "query_id": query.query_id,
                        "family": query.family,
                        "repetition": "",
                        "outcome": "not_representable",
                        "failure_reason": "q_eq requires the aware schema; blind has no sex join path by design",
                        "elapsed_ms": "",
                        "rows_returned": "",
                        "result_hash": "",
                        "plan_path": "",
                    }
                )
                click.echo(f"  {query.query_id}: not representable on {variant} — recorded, not executed")
            runnable = [query for query in queries if is_runnable(query, variant)]
            rendered = {query.query_id: render(query.body, schema) for query in runnable}
            plan_paths: dict[str, str] = {}
            for query in runnable:
                plan_name = f"{backend_name}_{variant}_{query.query_id}_{temperature}_0.json"
                plan_path = root / PLANS_DIR / plan_name
                _warm_up_and_capture_plan(backend, rendered[query.query_id], plan_path)
                plan_paths[query.query_id] = (PLANS_DIR / plan_name).as_posix()
                click.echo(f"  {query.query_id}: warmed up, plan -> {plan_paths[query.query_id]}")
            for repetition in range(1, repetitions + 1):
                order = runnable[:]
                rng.shuffle(order)
                for query in order:
                    row = base | {
                        "query_id": query.query_id,
                        "family": query.family,
                        "repetition": repetition,
                        "plan_path": plan_paths[query.query_id],
                    }
                    try:
                        t0 = time.perf_counter_ns()
                        rows = backend.fetchall(rendered[query.query_id])
                        elapsed_ms = (time.perf_counter_ns() - t0) / 1e6
                        row |= {
                            "outcome": "ok",
                            "failure_reason": "",
                            "elapsed_ms": f"{elapsed_ms:.3f}",
                            "rows_returned": len(rows),
                            "result_hash": result_hash(rows),
                        }
                    except Exception as exc:  # guardrail: log the failure and continue the run
                        row |= {
                            "outcome": "error",
                            "failure_reason": str(exc).replace("\n", " ")[:500],
                            "elapsed_ms": "",
                            "rows_returned": "",
                            "result_hash": "",
                        }
                        click.echo(f"  ⚠ {query.query_id} repetition {repetition}: {row['failure_reason']}")
                    log_rows.append(row)
            _append_csv(root / RUNS_CSV, RUNS_FIELDS, log_rows)
            _merge_envinfo(
                root / ENVINFO_JSON,
                run_id,
                {
                    "timestamp_utc": ts_utc,
                    "git_commit": commit,
                    "dataset": DATASET,
                    "backend": backend_name,
                    "variant": variant,
                    "temperature": temperature,
                    "repetitions": repetitions,
                    "seed": seed,
                    "queries": [query.query_id for query in queries],
                    "engine_version": settings["engine_version"],
                    "backend_native_settings": settings["native"],
                    "python_version": base["python_version"],
                    "kernel": base["kernel"],
                    "cpu_model": base["cpu_model"],
                    "ram_bytes": base["ram_bytes"],
                    "image_digest": "",
                },
            )
            regenerate_summary(root)
            if not skip_storage:
                measure_storage(backend, backend_name, root, run_id, commit)
        finally:
            backend.close()
    recorded = sum(1 for row in log_rows if row["outcome"] == "ok")
    click.echo(
        f"✓ Bench {backend_name}/{variant}/{temperature}: {recorded} recorded run(s), "
        f"{len(log_rows)} row(s) appended to {RUNS_CSV.as_posix()} (seed {seed})"
    )
    click.echo(f"✓ Summary regenerated at {SUMMARY_CSV.as_posix()} — raw runs are retained, evidence is append-only")
    return log_rows
