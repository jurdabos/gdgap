# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `sql/00_attach.sql`: DuckLake bootstrap per runbook Phase C — installs the `ducklake` extension and attaches `catalog/gdgap.ducklake` (local catalog by default, per ADR-0001) with `DATA_PATH 'data/lake/'`; verified end-to-end (snapshot 0 recorded, catalog file created, both gitignored as data plane).
- `datasets/nhts2017/DATASHEET.md`: Gebru et al.-style datasheet (Motivation/Composition/Collection/Preprocessing/Uses/Distribution/Maintenance) answered for the 2017 NHTS public-use files from the FHWA User Guide and Codebook v1.2; instance counts verified against the local CSVs via DuckDB and tied to `manifest.json`/`checksums.txt`.
- `docs/adr/0001-engine-and-lake.md`: ADR recording the engine pin — DuckDB v1.5.4 at runtime, `duckdb==1.5.4` locked in `uv.lock` — plus the lake/catalog layout and the upgrade procedure.
- `.gitkeep` placeholders in `sql/ddl/blind`, `sql/ddl/aware`, `results/profile`, `results/plans`, `docs/adr`, and `tests` so the empty repo-plane directory skeleton is committable (git tracks files only, never bare directories).

### Changed

- `.gitignore`: re-included `sql/**/*.sql` via a negation rule so DDL scripts are committable despite the global `*.sql` ignore inherited from the skeletal template; data-plane dirs (`data/`, `catalog/`) stay ignored.
- `.gitignore`: re-included `datasets/` (negation of the template rule) so dataset metadata — `DATASHEET.md`, `manifest.json`, `checksums.txt` — is committable; bulk data files inside remain ignored via the extension rules (`*.csv`, `*.zip`, …).

### Fixed

- `src/gdgap/cli.py`: `gdgap push` now detects commits that exist locally but not on the upstream (`git rev-list --count @{u}..HEAD`) and pushes them even when the working tree is clean; previously an aborted push left the commit stranded and re-running reported "Nothing to push". Same fix applied to the skeletal template (`~/skeletal/scripts/cli_push_template.py`) for future repos.
- `src/gdgap/cli.py`: commit messages no longer get a hardcoded `Co-Authored-By: Warp <agent@warp.dev>` trailer, in line with the ecosystem signing policy (responsibility stays with the human author); also removed from the skeletal template.
- `pyproject.toml`: added the missing `[build-system]` table (hatchling) so uv packages the project and installs the `gdgap` console script. Modern `uv init` scaffolds an unpackaged app, so uv skipped `[project.scripts]` entry-point installation and `uv run gdgap --help` failed with "Failed to spawn".
