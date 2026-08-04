# ADR 0007: Response-state granularity — ISO analysis codes plus verbatim raw retention

- Status: accepted
- Date: 2026-08-04

## Context

R7 promises that the reserve codes — prefer not to answer (`-7`), don't know (`-8`), not ascertained (`-9`) — survive ingest, storage, and aggregation as distinct first-class values. The registered raw tables satisfy this fully (verbatim VARCHAR codes under the declared ingest override, exhibited by the profiling code lists), and refusal survives into the analysis domain as `U`. But ISO/IEC 5218 offers a single `0 — Not known`, so `map_nhts_sex` sends both `-8` and `-9` to `0` — documented in the map's note column — and the dimension previously carried only mapped codes: warehouse aggregations could not distinguish the two ignorance kinds without joining back to the raw layer. Minting distinct sex codes for the ignorance kinds would re-violate the ADR-0006 labelling rule (local rows are governed application extensions, never additional standard codes) and would push response-process detail into the analysis domain. In the case data, `-9` never occurs in `R_SEX` (`-7` × 209 and `-8` × 34 do), so the merge is latent rather than exercised — but the schema, not the data accident, should carry the guarantee.

## Decision

- `dim_person_sex` retains the reported NHTS code verbatim as `r_sex_raw`, alongside the mapped `sex_code_reported`. Warehouse aggregations exhibit `-7`/`-8`/`-9` directly from the dimension; the ISO-granularity merge remains in the analysis code where it belongs.
- A derived response-status vocabulary (e.g. reported/refused/dont_know/not_ascertained) was considered and rejected: it duplicates what the verbatim raw already provides while adding a code list to govern.
- The stated analytical purpose of the column (R9's minimisation test): exhibitability of source response states at the analytical layer.
- The imputed-side raw (`R_SEX_IMP`) is not duplicated into the dimension: in this dataset it contains no reserve codes, its mapped value is lossless, and `sex_source` already records when imputation changed the value. Revisit per dataset.

## Consequences

- R7 holds at every layer — ingest, registered storage, and warehouse aggregation — without pseudo-standard codes; the fix follows the ADR-0006 pattern (raw truth retained, standards kept clean).
- Cost: one VARCHAR column on the dimension (dictionary-encoded in Parquet, negligible), reported through the R11 complexity/storage accounting like everything else.
- Blind/aware fact symmetry, equity views, and the bench catalogue are untouched.
