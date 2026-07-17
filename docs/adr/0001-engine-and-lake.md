# ADR 0001: Query engine and lake layout

- Status: accepted
- Date: 2026-07-17

## Context

gdgap needs a local-first analytical engine and a lake-style data plane that stays out of git. The data plane (`data/`, `catalog/`, `*.ducklake`, `*.ducklake.wal`) is gitignored; only repo-plane artefacts (DDL under `sql/`, result summaries under `results/`, docs) are committed.

## Decision

Use DuckDB as the sole query engine, with a DuckLake-style layout: raw inputs under `data/raw/`, lake storage under `data/lake/`, and the catalog under `catalog/`.

## Engine pin

- Runtime engine: **DuckDB v1.5.4** (output of `select version()`)
- Python package: `duckdb==1.5.4`, locked in `uv.lock` (declared as `duckdb>=1.5.4` in `pyproject.toml`)
- Interpreter: CPython 3.13 (`requires-python >= 3.13`)

Reproducing the probe:

```bash
uv run python -c "import duckdb; print(duckdb.sql('select version()'))"
```

## Consequences

- Engine upgrades are deliberate: bump via `uv lock --upgrade-package duckdb`, re-run the version probe, and record the new pin here.
- Lake and catalog artefacts are reproducible from raw data plus committed DDL; they are never restored from git.
