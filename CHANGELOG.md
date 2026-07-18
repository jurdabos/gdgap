# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `docs/adr/0002-dataset-scoping.md`: ADR pulling the multi-dataset decision forward — one lake schema per dataset (`lake.<dataset>.<table>`, never `main`) and one profile folder per dataset (`results/profile/<dataset>/`), while `sql/ddl/<variant>/` and the query catalogue stay keyed by the thesis's comparison axes.
- `src/gdgap/ingest/nhts2017.py` plus `gdgap ingest nhts2017 [--force]` and `gdgap profile` subcommands in `src/gdgap/cli.py`: manifest-verified (SHA-256, aborts on mismatch), idempotent ingest of the four NHTS CSVs into the DuckLake via `read_csv(..., header = true, sample_size = -1)` — skip when present, drop-and-recreate behind `--force`, row counts appended to `results/profile/ingest_log.csv`, each CREATE TABLE a DuckLake snapshot (verified: snapshots 1–4). The profiling pass emits the W1 CSVs under `results/profile/`: per-table structure (`COPY (SELECT * FROM (DESCRIBE ...))`, since `COPY (DESCRIBE ...)` is not parseable) and null shares (`COLUMNS(*)` idiom), the `R_SEX`/`R_SEX_IMP` code list, and the sex imputation share (277/264,234 = 0.1048%, defined as rows whose imputed value differs from the reported one — the codebook's `R_SEX_IMP` is the imputed companion value, not a yes/no flag; both are zero-padded VARCHAR codes in the raw CSVs).
- `tests/conftest.py`, `tests/unit/test_manifest.py`, `tests/integration/test_ingest_lake.py`: pytest coverage for manifest verification (intact/tampered/missing) and an end-to-end mini-lake ingest + profile round-trip on fixture CSVs (idempotency, force-recreate, log append, W1 outputs).
- `sql/00_attach.sql`: DuckLake bootstrap per runbook Phase C — installs the `ducklake` extension and attaches `catalog/gdgap.ducklake` (local catalog by default, per ADR-0001) with `DATA_PATH 'data/lake/'`; verified end-to-end (snapshot 0 recorded, catalog file created, both gitignored as data plane).
- `datasets/nhts2017/DATASHEET.md`: Gebru et al.-style datasheet (Motivation/Composition/Collection/Preprocessing/Uses/Distribution/Maintenance) answered for the 2017 NHTS public-use files from the FHWA User Guide and Codebook v1.2; instance counts verified against the local CSVs via DuckDB and tied to `manifest.json`/`checksums.txt`.
- `docs/adr/0001-engine-and-lake.md`: ADR recording the engine pin — DuckDB v1.5.4 at runtime, `duckdb==1.5.4` locked in `uv.lock` — plus the lake/catalog layout and the upgrade procedure.
- `.gitkeep` placeholders in `sql/ddl/blind`, `sql/ddl/aware`, `results/profile`, `results/plans`, `docs/adr`, and `tests` so the empty repo-plane directory skeleton is committable (git tracks files only, never bare directories).

### Changed

- `src/gdgap/ingest/nhts2017.py`: multi-dataset-native layout per ADR-0002 — tables now live in `lake.nhts2017.<table>` (schema created idempotently at ingest), and all profiling outputs including `ingest_log.csv` moved under `results/profile/nhts2017/`; lake and catalog rebuilt from raw CSVs to apply the layout (rebuildable per ADR-0001). `tests/integration/test_ingest_lake.py` extended with a schema-placement assertion.
- `.gitignore`: re-included `sql/**/*.sql` via a negation rule so DDL scripts are committable despite the global `*.sql` ignore inherited from the skeletal template; data-plane dirs (`data/`, `catalog/`) stay ignored.
- `.gitignore`: re-included `datasets/` (negation of the template rule) so dataset metadata — `DATASHEET.md`, `manifest.json`, `checksums.txt` — is committable; bulk data files inside remain ignored via the extension rules (`*.csv`, `*.zip`, …).
- `.gitignore`: re-included `results/**/*.csv` so the profiling/bench evidence stays tracked per the runbook ("results are evidence"), despite the global `*.csv` ignore.

### Removed

- Root `main.py` scaffolding leftover (`src/gdgap/main.py` remains the packaged module).
- Flat `results/profile/*.csv` evidence files, superseded by the dataset-scoped `results/profile/nhts2017/` set.

### Fixed

- `datasets/nhts2017/manifest.json`: consolidated four concatenated JSON objects into one valid document (single `files` array with name/sha256/bytes per CSV) so `json.load`-based manifest verification works.
- `src/gdgap/cli.py`: `gdgap push` now detects commits that exist locally but not on the upstream (`git rev-list --count @{u}..HEAD`) and pushes them even when the working tree is clean; previously an aborted push left the commit stranded and re-running reported "Nothing to push". Same fix applied to the skeletal template (`~/skeletal/scripts/cli_push_template.py`) for future repos.
- `src/gdgap/cli.py`: commit messages no longer get a hardcoded `Co-Authored-By: Warp <agent@warp.dev>` trailer, in line with the ecosystem signing policy (responsibility stays with the human author); also removed from the skeletal template.
- `pyproject.toml`: added the missing `[build-system]` table (hatchling) so uv packages the project and installs the `gdgap` console script. Modern `uv init` scaffolds an unpackaged app, so uv skipped `[project.scripts]` entry-point installation and `uv run gdgap --help` failed with "Failed to spawn".
