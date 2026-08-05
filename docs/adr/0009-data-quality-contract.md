# ADR 0009: Executable data-quality contract for equity-critical data (R13)

- Status: accepted
- Date: 2026-08-05

## Context

King & Schwarzenbach (2020) identify migration and transformation as general quality-risk points and prescribe a specification → monitoring/control mechanism; they study neither sex/gender nor NHTS, so they supply the mechanism while R1/R3/R6/R7/R9/R12 and their advocacy/standards sources supply the gender-sensitive content. gdgap's pipeline contains two migrations (raw CSV → lake at ingest; lake → InnoDB mirror at the foil build) and one transformation chain (the aware build), yet the profiling pass only observes — nothing compared observations with declared expectations or logged discrepancies. For this artefact, "loss" is equity-specific: attribute omission, collapse of distinct response states, sex/gender conflation, provenance loss, grain detachment, or aggregation that forecloses disaggregation. A string can survive while its meaning is lost — an un-padded `'01'` is intact bytes-wise on some path and still a broken code.

## Decision

- R13 (`docs/requirements.md`) requires each registered dataset carrying sex/gender information to ship a machine-readable, use-specific quality specification: `datasets/<ds>/DATA_QUALITY_SPEC.json` with purpose/syntax/semantics/pragmatics declarations plus executable rules — stable `DQ-(SYN|SEM|PRAG)-NN` IDs, a linked R-ID, stage, severity, applicable backends, a check (`sql_scalar` with `{schema}` rendering, or `sql_executes` against the frozen query catalogue), and an evidence pointer.
- `gdgap validate` (`src/gdgap/quality.py`) executes one stage on one backend and appends rule-level outcomes to `results/quality/<ds>/conformance.csv` (run id, snapshot, commit, stage, backend, rule, R-ID, expected, observed, severity, pass/fail, evidence). It runs automatically after `gdgap ingest` (lake) and after every aware build on the backend just built — the lake → MySQL copy is a migration in exactly King & Schwarzenbach's sense, and the mirror rules would catch e.g. a coercion un-padding the sex codes. The blind variant is never validated: it violates the design requirements deliberately (the experiment's contrast, registry conventions).
- Severity policy: `error` fails the run with the failing rule IDs; `warning` stays visible in the conformance log and the echo only. Only mechanically checkable properties become rules — accuracy, representativeness, ethics, and population fit remain with R10's Venus assessment and the datasheet, so the contract never pretends those are machine-verifiable.
- Rules are scale-invariant (memberships, zero-violation counts, set cardinalities, executability probes — never absolute row counts), so the pytest fixture lake and the full dataset satisfy one and the same contract, and the integration tests exercise the real rules rather than a parallel toy set.
- Reuse over framework: checks ride the existing backend seam (`{schema}` rendering, `fetchall`), evidence rides `_append_csv` append-only discipline, evidence pointers reference the existing manifest/profiling/DDL artefacts, and rule linkage rides the R-registry. No dashboards and no continuous monitor — deterministic validation per run is the proportionate form of monitoring/control for a static bachelor-thesis artefact.

## Consequences

- Every ingest and aware build now yields rule-level conformance evidence keyed by snapshot and commit, so ch. 4 can cite pass/fail facts instead of asserting quality; R10 keeps answering "was quality assessed?", R13 answers "did this transformation preserve the equity-critical fields?".
- A future NHTS revision, DDL edit, or mirror-dialect coercion that breaches the contract stops the pipeline naming the failed rules, instead of silently degrading equity queries.
- The drift-monitor warning (DQ-SEM-09) is expected to stay red on NHTS 2017 — `-9` is governed in `map_nhts_sex` but unobserved in the data — an honest, logged observation rather than a failure; it also demonstrates the severity split.
- A second dataset means writing its spec; discovery (`datasets_with_specs`) and the validator are already dataset-generic, so no framework work is needed — deliberately none was built.
