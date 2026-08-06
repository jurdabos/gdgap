# ADR 0010: Deployment form — in-process canonical engine, containerised foil only

- Status: accepted
- Date: 2026-08-06

## Context

The original plan was container-first delivery: a "containerised prototype running two pipelines" over the identical source. The bench schema even reserved an `image_digest` column for image-pinned evidence runs. What was actually built diverges: the canonical DuckDB/DuckLake engine runs in-process under WSL, and only the MySQL/InnoDB comparison service is containerised — a Compose-managed, version-pinned MySQL 8.4 LTS with an authenticated healthcheck, loopback-only port, and ext4-backed named volume (ADR-0008). The repo carries `compose.yaml` for that foil and no Dockerfile for the canonical application, while some thesis drafts still state the original claim. The deviation needs to be recorded and reasoned, not silently papered over.

## Decision

- The deployment form stays as built: in-process canonical engine, containerised foil. The asymmetry mirrors the artefact's central comparison rather than contradicting it — DuckDB is an embedded, zero-server engine *by design*, so there is no server process to containerise, and wrapping the Python host process in an image would pin OS userland and nothing else (DuckDB ships its own binary wheel; dependencies are already exactly locked). The client–server foil is the component that genuinely needs environment control — server version, configuration, isolation — and that is precisely the component that received it.
- Reproducibility comes from the pin/manifest/contract chain, not from an application image: the engine pin (DuckDB 1.5.4, ADR-0001) with `uv.lock` and `.python-version`; manifest-verified source data with SHA-256 aborts (R5) — noting that the NHTS CSVs are not redistributed, so any reproduction path, containerised or not, starts with manual data acquisition; R-gated DDL builds; the executable R13 data-quality contract with rule-level conformance evidence (ADR-0009); and run-scoped environment capture (engine versions, kernel, CPU, memory) in the bench evidence per ADR-0004.
- `image_digest` stays honest-NA: the column remains in `results/bench/runs.csv` and `envinfo.json` and remains empty for every non-containerised run. It is a recorded absence, consistent with the artefact's honest-NA discipline — populated only if an image-pinned evidence path ever exists.
- A Dockerfile may be added later as a reproduction convenience without touching evidence claims. If bench evidence is ever collected inside an image, those runs record the digest and stay separable from the existing population — no re-collection of current ch. 4 evidence is required or implied by this ADR.
- Thesis wording aligns with this ADR: the prototype is described as reproducibility-pinned at every layer with the client–server comparison component containerised, and the deviation from the container-first plan cites this record.

## Consequences

- The examiner-facing story is a reasoned deviation exercised as reflexivity (R12) rather than an unexplained gap; the embedded-vs-server argument turns the asymmetry into part of the row-vs-column narrative.
- Avoided footguns stay avoided: no dual endpoint configuration (loopback `:3307` natively vs. service-name networking in-compose), no git/`.env`/MotherDuck passthrough into containers, no NTFS bind-mount performance trap for a datadir that must stay on ext4 (ADR-0008).
- Existing evidence populations remain valid and internally consistent — nothing was collected under one deployment form and claimed under another.
- Should full containerisation ever become genuinely needed, this ADR is superseded by a new one that also defines the evidence re-collection protocol, not by a quiet Dockerfile commit.
