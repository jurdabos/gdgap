# ADR 0003: Cloud mirror — optional MotherDuck-hosted DuckLake publish target

- Status: accepted
- Date: 2026-07-19

## Context

The runbook anticipated an optional MotherDuck- or Postgres-hosted catalog behind an env var while noting that the reproducibility argument favours local-by-default. MotherDuck now offers managed DuckLake in two modes: fully managed (MotherDuck hosts catalog and storage) and bring-your-own-bucket (S3/R2). Neither mode can serve the repo's local `data/lake/` files, so "attaching the project's DuckLake to MotherDuck" in the literal sense is not possible; mirroring is. MotherDuck supports DuckDB clients up to 1.5.4 — exactly the engine pin from ADR-0001.

## Decision

- The local DuckLake (ADR-0001, ADR-0002) stays canonical: thesis measurements, profiling, and reproduction all run against it. The cloud side is a disposable mirror, not a second source of truth.
- The mirror is a fully managed MotherDuck DuckLake named `gdgap_lake` (`CREATE DATABASE ... (TYPE DUCKLAKE)`), populated by `gdgap publish [--target ...] [--force] [--maintain]`. Dataset schemas carry over unchanged (`gdgap_lake.nhts2017.<table>`), so the ADR-0002 invariant holds remotely.
- Authentication rides the `MOTHERDUCK_TOKEN` environment variable only; the token never enters the repo, logs, or SQL text.
- Publish hardening, born from an observed MotherDuck glitch (a fully qualified CREATE once landed in `main` mid-session): fresh connections per run, per-table placement and row-count verification on a fresh target-only connection, and automatic server-side repair (CTAS + drop) when a table sits in exactly one wrong schema with matching counts. Runs append to `results/profile/<dataset>/publish_log.csv`.
- Storage discipline: `SNAPSHOT_RETENTION_DAYS = 7` is set on `gdgap_lake`; because MotherDuck runs no automatic DuckLake maintenance yet, `gdgap publish --maintain` expires non-current snapshots (`ducklake_expire_snapshots`) and deletes their files (`ducklake_cleanup_old_files`). The mirror therefore carries no time-travel guarantees.

## Consequences

- The mirror can be dropped and republished at any time from the local lake, which itself rebuilds from the raw CSVs plus committed DDL — the reproducibility chain never depends on MotherDuck.
- Sharing and cloud querying become possible (MotherDuck shares, Postgres endpoint) without touching the measurement path; ch. 4 evidence remains local/containerised.
- The version pin gains a second anchor: clients newer than MotherDuck's supported ceiling would break `publish`, so engine upgrades check MotherDuck compatibility alongside DuckLake.
- If catalog hosting (rather than mirroring) is ever genuinely needed, the BYOB mode with own compute is the path; that would be a new ADR.
