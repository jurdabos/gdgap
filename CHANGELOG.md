# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `datasets/nhts2017/DATASHEET.md`: Gebru et al.-style datasheet (Motivation/Composition/Collection/Preprocessing/Uses/Distribution/Maintenance) answered for the 2017 NHTS public-use files from the FHWA User Guide and Codebook v1.2; instance counts verified against the local CSVs via DuckDB and tied to `manifest.json`/`checksums.txt`.
- `docs/adr/0001-engine-and-lake.md`: ADR recording the engine pin — DuckDB v1.5.4 at runtime, `duckdb==1.5.4` locked in `uv.lock` — plus the lake/catalog layout and the upgrade procedure.
- `.gitkeep` placeholders in `sql/ddl/blind`, `sql/ddl/aware`, `results/profile`, `results/plans`, `docs/adr`, and `tests` so the empty repo-plane directory skeleton is committable (git tracks files only, never bare directories).

### Changed

- `.gitignore`: re-included `sql/**/*.sql` via a negation rule so DDL scripts are committable despite the global `*.sql` ignore inherited from the skeletal template; data-plane dirs (`data/`, `catalog/`) stay ignored.
- `.gitignore`: re-included `datasets/` (negation of the template rule) so dataset metadata — `DATASHEET.md`, `manifest.json`, `checksums.txt` — is committable; bulk data files inside remain ignored via the extension rules (`*.csv`, `*.zip`, …).

### Fixed

- `pyproject.toml`: added the missing `[build-system]` table (hatchling) so uv packages the project and installs the `gdgap` console script. Modern `uv init` scaffolds an unpackaged app, so uv skipped `[project.scripts]` entry-point installation and `uv run gdgap --help` failed with "Failed to spawn".
