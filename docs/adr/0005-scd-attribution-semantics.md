# ADR 0005: SCD attribution semantics — Type-2-style dimension, current-identity reporting

- Status: accepted
- Date: 2026-08-04

## Context

`lake.aware.dim_person_sex` carries Type-2 mechanics — `valid_from`/`valid_to` validity intervals, `is_current`, and row-level provenance — but the fact tables carry only the natural person key, and the equity views join the natural key plus `is_current`. NHTS 2017 is a single survey snapshot, so exactly one dimension version per person exists in the case data and all attribution variants return identical results on it. Classical Kimball Type-2 attribution keys each fact to the dimension version in effect at the fact event. For gender specifically, that notion of correctness competes with a legitimate alternative: reporting a person's history under their current recorded identity, which avoids resurfacing superseded categories in analytical outputs. Separately, putting version keys on facts would widen the aware fact tables while the blind variant can carry no sex-version key by design, breaking the identical-fact-grain contrast the blind-versus-aware experiment rests on.

## Decision

- The dimension retains full history: rows are never destroyed, and validity intervals plus `sex_source`/`sex_code_reported` provenance stay first-class (R3, R8).
- The analytical views deliberately report by current recorded identity (natural key plus `is_current`). This is the artefact's default reporting semantics, chosen consciously rather than inherited from convenience.
- The artefact claims Type-2-style mechanics and history retention, not historical Type-2 attribution. Wording across DDL headers, the conceptual model, the requirements registry, and the thesis appendices says "Type-2-style".
- The fact grain stays natural-key only, preserving the experiment's identical-fact contrast between the blind and aware variants.
- Richer attribution semantics remain future work in a general sense; they become demonstrable only with data whose recorded values actually change.

## Consequences

- The §6.1 audit records R8 as satisfied for history retention, with attribution semantics documented here.
- The reporting choice is itself an equity-relevant design decision surfaced per R12's reflexivity expectation; §6.2 can discuss the tension between temporal attribution and identity-respecting retroactive reporting.
- No schema change now: blind/aware fact symmetry, the Q_agn equivalence checks, and the storage-delta interpretation stay intact.
