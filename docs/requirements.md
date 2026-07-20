# Requirements registry — R1..R12

This registry converts the advocacy corpus of thesis subchapter 2.3 into the numbered, engineer-inspectable requirements the artefact must satisfy. It is simultaneously the DSR "define requirements" activity (Johannesson & Perjons; see thesis 3.1), and it is the traceability spine of the project: 3.3 designs against these R-numbers, ch. 4 measures against them, and 5.1 audits each as satisfied / partial / unmet.

Corpus streams: disaggregation mandates (SAGER — Heidari et al., 2016; UN Women, 2018; Data2X — Vaitla et al., 2017), stewardship instruments (datasheets — Gebru et al., 2021; FAIR — Wilkinson et al., 2016), data-feminist design principles (D'Ignazio & Klein, 2020; the Manifest-No — Cifor et al., 2019), dataset-quality scoring (the Venus score — Chicco et al., 2025), professional duty (ACM, 2018), and gender-sensitive responsible innovation across all stages (AIRR — Finlay-Smits et al., 2024).

## Conventions (the traceability contract)

- Registry headings follow `## R<n> — <short name>` exactly; `grep -E '^## R[0-9]+' docs/requirements.md` enumerates the valid IDs.
- Every DDL file under `sql/ddl/<variant>/` must open with a header comment naming at least one R-number, e.g. `-- R3: provenance column sex_source records reported-vs-imputed` or `-- R2, R7: ...`. The Phase D build command refuses to run a file without one, so appendix A and the 3.3 traceability claim reduce to a grep.
- IDs are stable once cited: new requirements append at the end; retired ones are marked deprecated, never renumbered.
- The gender-blind build variant deliberately violates the design requirements (R1–R3, R6–R8); the contrast is the experiment, not an oversight.

## R1 — Sex and gender are distinct, deliberately modelled concepts

- Requirement: The conceptual and logical model gives sex and gender distinct, explicitly defined attributes, used carefully per SAGER's terminology discipline; the physical schema must not fold them into a single binary, default-male column.
- Sources: Heidari et al. (2016); forward-engaged in 3.3 via McClure et al. (2022).
- Design hook (3.3): aware-variant dimension with separately defined sex/gender attributes; the blind variant embodies the conflation for contrast.
- Evidence: DDL header grep (appendix A); 4.1 side-by-side query results.

## R2 — Person-level facts are disaggregable by sex at every analysis grain

- Requirement: Any measure computable from the warehouse is computable disaggregated by sex without schema change — the Q_eq query family must run on the aware build as plain SQL.
- Sources: Heidari et al. (2016) — disaggregate data by sex or gender whenever feasible; UN Women (2018); Vaitla et al. (2017).
- Design hook (3.3): sex/gender as a first-class dimension joinable to every fact grain.
- Evidence: 4.1 — which equity queries the aware build answers that the blind build cannot.

## R3 — Provenance of the sex value is first-class (reported vs imputed)

- Requirement: Every stored sex/gender value carries how it was obtained — a `sex_source` provenance column distinguishing reported / imputed / derived / undisclosed — preserving the NHTS `R_SEX` vs `R_SEX_IMP` distinction, with the imputation share queryable at any time.
- Sources: Gebru et al. (2021) — the datasheet's collection/preprocessing provenance questions, pushed down to row level.
- Design hook (3.3): provenance column in the aware dimension (`-- R3: provenance column sex_source records reported-vs-imputed`).
- Evidence: profiling pass (imputation share 277/264,234 = 0.1048%); 4.1 imputation-share visibility query.

## R4 — Every registered dataset ships a datasheet

- Requirement: No dataset enters the lake without `datasets/<ds>/DATASHEET.md` instantiating Gebru et al.'s seven sections, answered from the dataset's authoritative documentation.
- Sources: Gebru et al. (2021).
- Design hook: dataset registry plane (`datasets/<ds>/`), populated before ingest.
- Evidence: `datasets/nhts2017/DATASHEET.md`; 5.1 audit.

## R5 — Registered data is FAIR at repository scale

- Requirement: Each dataset carries machine-readable registration metadata — source URL, retrieval date, licence note, per-file SHA-256 and byte size — verified before every ingest (abort on mismatch), plus a documented reproduction path from raw files to lake, so a third party can re-acquire, re-verify, and re-build.
- Sources: Wilkinson et al. (2016) — findability, accessibility, and reusability via rich provenance metadata; interoperability via the open Parquet/DuckLake formats.
- Design hook: `manifest.json` + `checksums.txt` + manifest-verified ingest; engine pin in ADR-0001.
- Evidence: ingest log with per-run digests; 5.1 audit.

## R6 — The sex/gender code list is standard-based and never binary-closed

- Requirement: The physical code list implements a published standard and remains extensible beyond the binary — representation for identities outside male/female and for explicit undisclosed states must be possible by governed extension, not ad-hoc schema surgery.
- Sources: D'Ignazio & Klein (2020) — rethink binaries and hierarchies; Stats NZ (2024) as the production governance exemplar; ISO/IEC 5218 implemented-then-extended in 3.3.
- Design hook (3.3): code-list table with standard codes, extension rows, and constraints.
- Evidence: DDL; 4.2 code-list fit against the population (unknown/other shares).

## R7 — Nonresponse and unknown are meaningful values, never conflated with NULL

- Requirement: Reserve codes — prefer not to answer, don't know, not ascertained, appropriate skip — survive ingest, storage, and aggregation as distinct first-class values; no silent coercion to NULL, to a default sex, or to each other; aggregations can always exhibit them.
- Sources: D'Ignazio & Klein (2020) — embrace pluralism, consider context; Cifor et al. (2019) — refusal carries meaning and must not be erased.
- Design hook: raw codes preserved verbatim at ingest (zero-padded VARCHAR); aware-variant code list gives each reserve state its own row.
- Evidence: profiling structure/codelist CSVs (0 NULL cells, reserve codes intact); 4.1 queries exposing the categories.

## R8 — Gender is time-variant; the model records change

- Requirement: The aware dimension handles mutability with slowly-changing-dimension mechanics (validity intervals), so a change of recorded gender neither destroys history nor misattributes past facts.
- Sources: D'Ignazio & Klein (2020); Finlay-Smits et al. (2024) — responsiveness; SCD mechanics per Kimball & Ross in 3.3.
- Design hook (3.3): SCD-typed sex/gender dimension in the aware variant.
- Evidence: DDL; 4.2 complexity delta names the cost of carrying it.

## R9 — Disaggregation must not create exposure: minimisation and small-cell discipline

- Requirement: The artefact carries only attributes with a stated analytical purpose, and every equity output applies a small-cell suppression threshold so disaggregated results cannot single out individuals or tiny subgroups.
- Sources: Cifor et al. (2019); ACM (2018) — 1.2 avoid harm, 1.6 respect privacy; argued against GDPR data-minimisation and k-anonymity (Sweeney, 2002) in 4.2/5.2.
- Design hook: suppression rule inside the Q_eq query catalogue; attribute inventory justified in the datasheet.
- Evidence: 4.2 exposure observations on disaggregated outputs.

## R10 — Dataset quality is scored, not asserted

- Requirement: Each registered dataset is assessed against the ten Venus items and the assessment is recorded in the dataset registry, so the case description's quality claims are auditable rather than rhetorical.
- Sources: Chicco et al. (2025).
- Design hook: assessment artefact alongside the datasheet in `datasets/<ds>/`.
- Evidence: recorded assessment; 5.1 audit.

## R11 — Findings report benefits and costs symmetrically, reproducibly

- Requirement: The measurement harness emits effectiveness (Q_eq answerability, signal reproduction) and costs (complexity, storage, exposure) from one command, with the environment captured per run (engine version, image digest, threads, memory), so reporting cannot cherry-pick and any number can be regenerated.
- Sources: ACM (2018) — 1.3 honesty, 2.5 comprehensive evaluations; Le (2024) — activism needs contestable, credible numbers.
- Design hook: Phase E bench harness (fixed pragmas, N = 5, medians, envinfo per row).
- Evidence: `results/bench_summary.csv`, `results/plans/`, `results/storage_by_column.csv`; the 4.1/4.2 symmetry itself.

## R12 — Gender sensitivity is traceable at every lifecycle stage

- Requirement: Every pipeline stage — registration, ingest, storage, schema, query, reporting — names its gender-sensitivity control and the R-numbers it serves; anticipation and reflexivity are exercised through ADRs that record design decisions and their equity implications as they are made.
- Sources: Finlay-Smits et al. (2024) — the AIRR dimensions (anticipation, inclusion, reflexivity, responsiveness) applied across all stages; UN Women (2018).
- Design hook: this registry, the DDL header contract, and the `docs/adr/` trail.
- Evidence: header grep coverage; ADR sequence; 5.1 audit table mapping R1..R12 to ch. 4 evidence.

## Parked corpus extensions

Garzcarek & Steuer (2019), Franks (2020), and Regulation (EU) 2024/1689 are parked: they may harden R9 (exposure) and R11 (professional duty) if the corresponding thesis paragraphs demand it. Additions append as R13+ per the conventions above.
