# Authority map

For every kind of knowledge in this project, exactly one source is authoritative; everything else is derived, secondary, or a discovery route. When artefacts disagree, the authoritative one wins and the derivative is regenerated or corrected — never the reverse. Derived artefacts are regenerated, not hand-edited.

## Bibliographic metadata

- Authoritative: cloud-synced Zotero library.
- Derived: the exports in the thesis workspace (`lit/THESIS.bib`, `lit/THESIS.json` CSL export, `lit/dbengines.bib`) and the Word bibliography inside the thesis document — all regenerated from Zotero, never patched by hand.

## Claims

- Evidence: original papers, standards (e.g. ISO/IEC 5218, the Stats NZ gender standard), and dataset documentation (FHWA NHTS 2017 codebook, User Guide, Weighting Report).
- Discovery routes only: search engines, Elicit, Research Rabbit — they locate sources and are never themselves citable authorities.

## Decisions

- Trail: dated working notes in the thesis workspace (scribble notes, subreads, supervision notes) preserve ideation and screening.
- Authority: a decision binds only once it lands in `docs/requirements.md` or `docs/adr/`; notes are provenance for how a decision was reached, not authority for what was decided.

## Intent

- Requirements: `docs/requirements.md` — the R1..R13 registry with greppable `## R<n> —` headings; the build gate enforces DDL linkage to it.
- Architectural decisions: `docs/adr/` — append-only; a decision changes by a superseding ADR, never by silent edit (see ADR-0010's supersession clause).

## Behaviour

- Authoritative: versioned code (`src/gdgap/`), schemas and query catalogue (`sql/ddl/`, `sql/bench/`), and tests (`tests/`), pinned by `uv.lock`/`.python-version` and checked in CI.
- Secondary: README and other prose explain behaviour but do not override it; when repo prose and code disagree, code wins and the prose is corrected.

## Data semantics

- Authoritative: the source documentation (FHWA codebook) for what the data means at origin, plus the versioned gdgap metadata for what the artefact commits to — `datasets/nhts2017/manifest.json`, `checksums.txt`, `DATASHEET.md`, and the executable `DATA_QUALITY_SPEC.json` (R13).
- Rule: semantic commitments live in versioned, preferably executable form; the R13 rules turn drift into a named conformance failure instead of a silent reinterpretation.

## Results

- Authoritative: a result is the output **plus** its producing command/configuration, data version, and Git commit — `results/**` therefore carries `git_commit`, the DuckLake `snapshot`, seeds, and engine settings (`envinfo.json`, `conformance.csv`, the sensitivity CSVs), and each emitting artefact states its regeneration command.
- Rule: a number without that provenance is not a result.

## Submitted argument

- The thesis `.docx` is authoritative for the argument. It shall not be taken to override code behaviour, schemas, or source documentation.
