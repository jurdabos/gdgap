# ADR 0002: Dataset scoping — one lake schema and one profile folder per dataset

- Status: accepted
- Date: 2026-07-18

## Context

The repo's umbrella scope allows further GDG datasets after September, while the thesis freezes a single case (NHTS 2017). The original Phase C layout wrote tables into the lake's default `main` schema and profile CSVs flat into `results/profile/`, so a second dataset with an identically named table would collide in both places. The registry plane (`datasets/<ds>/`, `data/raw/<ds>/`, `src/gdgap/ingest/<ds>.py`) was dataset-scoped from the start.

## Decision

Make the repo multi-dataset-native now rather than post-freeze:

- Every lake table lives in a schema named exactly after its dataset: `lake.<dataset>.<table>` (here `lake.nhts2017.hhpub`, ...). Ingest creates the schema idempotently; nothing is ever written to `main`.
- Every profiling artefact lands under `results/profile/<dataset>/`, including that dataset's `ingest_log.csv`.
- `sql/ddl/<variant>/` and the bench query catalogue stay keyed by architecture variant and query family — those are the thesis's axes of comparison (blind vs. aware over the same source), and the appendix A/B extraction at the freeze tag depends on those paths.

## Consequences

- The DuckLake data path mirrors the invariant (`data/lake/<dataset>/<table>/*.parquet`), making the data plane self-describing on disk.
- The lake and catalog were rebuilt from the raw CSVs to apply the layout — both are rebuildable by construction (ADR-0001); the snapshot audit trail restarts, with the schema creation itself snapshotted.
- A future dataset needs exactly three things: a `datasets/<ds>/` registry entry (datasheet, manifest, checksums), raw files under `data/raw/<ds>/`, and an ingest module declaring `DATASET = "<ds>"` — schema and results scoping follow from the constant.
- Bench artefacts (Phase E) remain build-and-query-keyed; if cross-dataset benchmarking ever lands, plans and summaries gain a dataset dimension then.
