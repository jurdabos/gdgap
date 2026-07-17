# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- `pyproject.toml`: added the missing `[build-system]` table (hatchling) so uv packages the project and installs the `gdgap` console script. Modern `uv init` scaffolds an unpackaged app, so uv skipped `[project.scripts]` entry-point installation and `uv run gdgap --help` failed with "Failed to spawn".
