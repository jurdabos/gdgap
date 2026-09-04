# Project terminology

This glossary defines terms whose meaning is specific to the gdgap artefact or its evaluation.

**Aware variant.** The warehouse variant that retains a joinable recorded-sex
dimension, separates the governed sex and gender-identity domains, preserves
source response states and provenance, and supports the equality-oriented
queries in the frozen catalogue. Its person and trip fact grains match those
of the blind variant.

**Awareness by construction.** A design property achieved by preserving and
governing relevant information throughout registration, ingestion, modelling,
querying and evidence production.

**Blind variant.** The deliberate baseline whose person and trip facts have
the same grains as the aware variant but no joinable sex or gender path. A
query that requires such a path is recorded as `not_representable`.

**Code commit and evidence commit.** The code commit identifies the exact
implementation used for a retained run. The evidence commit is the later
commit that adds the resulting files. Protocol v1 uses code commit `f9a0117`
and evidence commit `8ed0899`; protocol v2 uses `7e544c2` and `89256b8`.

**DuckDB.** The embedded analytical database engine used to execute the
canonical local pipeline.

**DuckLake.** The table format and catalogue layer used by the canonical
warehouse. DuckDB is the query engine; DuckLake is the storage and catalogue
arrangement managed through that engine.

**Gender data gap.** In this project, a consequential absence, imbalance or
loss of sex- or gender-related information at any stage of the information
lifecycle. The term includes loss of representation, response state,
provenance, linkage or disaggregability; it is not limited to missing cells.

**Gender identity.** A domain governed separately from recorded sex. The 2017
NHTS source used by gdgap did not collect gender identity, so the implemented
dimension records the governed state `NC` instead of inferring a value.

**Governed code domain.** A controlled set of allowed values, labels, source
standards and documented extensions. The design uses separate governed domains
for sex and gender identity.

**InnoDB foil.** The containerised MySQL/InnoDB mirror used for a bounded
engineering comparison. It reproduces the relevant grains and logical
structures.

**`NC` (not collected).** A governed value stating that the source instrument
did not collect the attribute. It is distinct from an unanswered question, an
unknown value and a value removed during processing.

**`not_representable`.** A capability outcome stating that a query cannot be
expressed from the available schema without inventing absent information. It
is distinct from a zero result, a SQL `NULL`, an execution error or a decision
not to run an otherwise answerable query.

**Participant prevalence ratio (PPR).** For the implemented care-related-trip
query, a group's share of weighted care-related trips divided by its share of
the weighted person population. A value of 1 denotes proportionality between
the two shares.

**Provenance (`sex_source`).** The recorded origin of the analytical sex value:
`reported`, `imputed` or `edited`. It allows a result to distinguish a source
response from a completed or subsequently changed value.

**Recorded sex.** The sex-related value carried by the source data and mapped
into the analytical model. In gdgap, the analytical value uses the completed
NHTS field `R_SEX_IMP`, while `r_sex_raw`, `sex_code_reported` and `sex_source`
preserve the original response state and its provenance.

**Response state.** The source-level distinction among a substantive response
and reserved codes such as refusal, uncertainty or missingness. gdgap preserves
the verbatim NHTS state in `r_sex_raw` before mapping it to governed analytical
values.

**Sex-aware and gender-identity-ready.** A bounded description of the artefact:
it implements an auditable recorded-sex path and a separate governed
gender-identity domain.

**Survey weight.** A value that expands a sampled record to the population it
represents. `WTPERFIN` is the final person weight and `WTTRDFIN` is the final
trip weight; sums of these weights estimate represented people and annual
trips, respectively.

**Type-2-style dimension.** The versioned `dim_person_sex` structure, with
validity dates and a current-row flag. It is “style” because facts do not carry
a dimension-version key; reporting joins the natural person key to the row
marked current, as fixed by ADR-0005.
