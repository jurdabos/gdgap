# ADR 0006: Sex and gender identity as distinct governed code domains

- Status: accepted
- Date: 2026-08-04

## Context

The earlier `dim_sex_code` mixed the ISO/IEC 5218 sex core with a local row `X — Non-binary or another gender identity`, labelled as an extension of the ISO sex standard. That places a gender-identity concept inside a sex domain and describes it as an ISO extension, conflicting with R1's claim that sex and gender are distinct, deliberately modelled concepts — the artefact's only distinctness device was an `is_extension` flag inside one code list. Notably, no NHTS code ever mapped to `X`; it existed to demonstrate R6 extensibility. The R6 governance exemplar (Stats NZ) maintains sex and gender as separate statistical standards. NHTS 2017 collects a sex variable and no gender-identity variable at all.

## Decision

- `dim_sex_code` carries the ISO/IEC 5218:2022 core (`0/1/2/9`) plus exactly one local row: `U` (undisclosed), a governed application extension for a nonresponse process state, required by R7's refusal-versus-ignorance distinction (`-7` maps to `U`; `-8`/`-9` map to `0`). Local rows are always labelled application extensions, never additional ISO/IEC 5218 codes.
- Gender identity gets its own separately governed domain, `dim_gender_identity_code`, anchored to the Stats NZ gender standard (`1/2/3`) with `U` and `NC` as flagged application extensions. The former `X` concept lives here, in the domain where it belongs.
- `dim_person_sex` carries distinct `sex_code` and `gender_identity_code` attributes. Because NHTS 2017 collects no gender-identity variable, `gender_identity_code` is `NC` (not collected by source instrument) by construction.
- The stated analytical purpose of the all-`NC` attribute (R9's minimisation test): exhibiting non-collection. The gender data gap becomes a queryable state of the warehouse rather than an unrepresentable absence — `SELECT` returns the non-collection rate directly. A future instrument that collects gender identity populates the attribute without schema surgery (R6).
- The implemented case is described as sex-aware and gender-identity-ready: the sex path is exercised end to end by the data; the gender path is governed, populated only by the honest `NC` state.

## Consequences

- R1 is satisfied structurally: distinct domains, distinct attributes, distinct governance sources — not a flag inside one list. R6's extensibility is demonstrated in both domains with correctly labelled extensions.
- The schema complexity delta of the aware variant grows by one code table and one attribute; R11 reports that cost symmetrically rather than hiding it.
- The blind/aware experiment is untouched: fact tables, grains, equity views, and the bench catalogue are unchanged, so Q_agn equivalence and the storage-delta interpretation stay valid.
- Thesis wording follows the same rule everywhere: local values are governed application extensions, never additional standard codes; gender-identity representation is exercised by data only when an instrument supplies it.
