# ADR 0001: Query engine and lake layout

- Status: accepted
- Date: 2026-07-17

## Context

gdgap needs a local-first analytical engine and a lake-style data plane that stays out of git. The data plane (`data/`, `catalog/`, `*.ducklake`, `*.ducklake.wal`) is gitignored; only repo-plane artefacts (DDL under `sql/`, result summaries under `results/`, docs) are committed.

## Decision

Use DuckDB as the sole query engine, with a DuckLake table format and catalog: raw inputs under `data/raw/`, lake storage under `data/lake/`, and the catalog under `catalog/`.

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

## Addendum (2026-08-08): data file format — considered and deferred

Vortex (LF AI & Data incubation; first-class DuckDB extension) and F3 (Zeng et al., 2025; Wasm-embedded decoders; a self-declared research prototype) were evaluated as Parquet successors for the data plane. Deferred without change to this pin: DuckLake writes Parquet only — the experimental Vortex support PR (duckdb/ducklake #1193) was closed by the maintainers in May 2026 — the claimed wins target scales and access patterns this artefact does not have, and a format swap would invalidate stamped evidence without a re-collection protocol (cf. ADR-0010). Revisit only if DuckLake gains pluggable data-file formats; the `{schema}`-neutral query catalogue and the backend seam keep the file format an implementation detail below the artefact's interfaces.

## Scope clarification (2026-09-04)

The statement that DuckDB is the “sole query engine” applies to the canonical
lake architecture governed by this ADR. ADR-0008 later introduced
MySQL/InnoDB as a containerised, row-store benchmark foil, and ADR-0010 made
the boundary explicit: DuckDB/DuckLake remains canonical, while InnoDB is a
comparison component. The later foil neither supersedes the engine pin nor
creates a second source of truth.
