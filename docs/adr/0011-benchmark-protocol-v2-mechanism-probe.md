# ADR 0011: Benchmark protocol v2 — the buffer-pool mechanism probe

- Status: accepted
- Date: 2026-08-23

## Context

The frozen ADR-0004 run left one expectation unsupported: on InnoDB the aware variant answered the q_agn family ~250 ms faster per scan than the blind variant (additive across two queries with different CPU baselines), while the only plan-level divergence was the cost model's buffer-pool-residency pricing (read_cost 1418.31 vs 1115.75 against the recorded 128 MB default pool). The thesis applies the §3.3 deviation rule and reports the asymmetry at workload-and-configuration scope; the engineering note (`why-aware-is-cheaper-in-innodb-than-blind.qmd`) develops the candidate mechanism: InnoDB's scan-resistant LRU under defaults — full-scan pages enter the old sublist (37 % of a 128 MB pool ≈ 47 MB, smaller than the ~73 MB fact_trip), and are promoted only when re-touched more than `innodb_old_blocks_time` (1000 ms) after first access. The blind cell's two-query round (~0.85 s) stayed inside the window (nothing promoted — cyclic thrash); the aware cell's four-query round (~1.5 s) crossed it (promotion — memory-speed scans). v1 could not test this: the variants ran unequal runnable query mixes in shuffled order against one pool size, and only optimizer estimates were captured.

ADR-0004 requires protocol changes to arrive as a new ADR with separately identified evidence, and the evidence contract states that a later invocation creates new evidence under its own authority note. This ADR freezes that protocol v2 before any harness code, mirroring the ADR-0004 discipline.

## Decision

- Identity and separation: protocol v2 is a mechanism probe, not a re-run. It is executed by `gdgap bench2`, writes exclusively under `results/bench2/` (`runs.csv`, `envinfo.json`, `summary.csv`, `plans/`), and stamps run ids `<ts>-bench2-<backend>-<condition>`. v1 evidence under `results/bench/` remains the authoritative headline record; v2 rows are never pooled with v1 rows, and absolute DuckLake and MySQL runtimes are never presented as a product comparison — the reported quantities are within-backend aware-minus-blind effects and mechanism counters.
- Query catalogue: unchanged — the four frozen `sql/bench/` bodies with `{schema}` rendering. v2 regroups them at the runner level into two workloads: `W_agn` = {q_agn_01, q_agn_02} executed on both variants, and `W_eq` = {q_eq_01, q_eq_02} executed on the aware variant only, timed as its own workload after `W_agn`. No `not_representable` rows are re-recorded in v2 (that capability state is v1 evidence); the point of the split is that the variant contrast is computed from identical workloads only.
- Sequence and warm-up: within a segment the queries run in fixed catalogue filename order — no shuffling, because the suspected mechanism is order- and time-sensitive and both variants must receive exactly the same sequence. A segment = one fresh backend connection, one unrecorded warm-up pass of the full sequence, then `R` recorded repetitions of the sequence (default `R` = 5). Warm-up executions are logged as repetition 0 with outcome `warmup` (timed and counter-instrumented, excluded from all summary statistics) so first-touch promotion behaviour stays visible.
- Blocks and counterbalancing: a block is four segments in the pattern ABBA or BAAB (A = blind, B = aware), giving 2 segments × R = 10 recorded repetitions per variant per block at the default. A condition runs 4 blocks with patterns ABBA, BAAB, ABBA, BAAB (pre-specified, deterministic). `W_eq` reuses the block machinery with pattern BB per block (aware-only). No artificial sleeps anywhere; wall-clock timestamps per repetition keep promotion-window arithmetic analyzable.
- Conditions: DuckLake runs one condition `d0` (v1 controls: threads = 4, memory_limit = 8 GB, values read back). InnoDB runs three:
  - `c1` — pool 134217728 B (128 MB default), `innodb_old_blocks_time` = 1000 ms (defaults; the v1 configuration);
  - `c2` — pool 1073741824 B (1 GiB, non-constraining against ~194 MB of data + indexes), `innodb_old_blocks_time` = 1000 ms;
  - `c3` — pool 134217728 B, `innodb_old_blocks_time` = 0 ms (promotion at first touch; the surgical LRU toggle).
  The pool size is set by container restart via the compose knob (`GDGAP_MYSQL_BUFFER_POOL`, default 134217728 so plain `docker compose up` preserves the v1 server byte-for-byte); the runner never resizes the pool online — a restart gives a defined empty-pool state, and the runner verifies the read-back value and aborts on mismatch. `innodb_old_blocks_time` is set dynamically by the runner for `c3` (`SET GLOBAL innodb_old_blocks_time = 0`), read back before and after, and restored to 1000 in a finally block. Condition order is c1, c2, c3, each preceded by a fresh container start; no restarts inside a condition (steady-state pool behaviour is the phenomenon; the ABBA/BAAB patterns handle order and carryover symmetrically).
- Preconditions: both InnoDB mirrors rebuilt at full scale before any v2 InnoDB run (`gdgap build --variant blind|aware --backend innodb`) — a deliberate, changelog-recorded restoration after the 2026-08-10 fixture clobber. The runner guards scale (≥ 900,000 `fact_trip` rows per variant) and refuses otherwise; `--allow-small` exists solely for fixture-scale tests.
- Measurement: timing is `perf_counter_ns` around execute-plus-full-fetch, milliseconds with 3 decimals (v1 convention). Result rows are normalised and hashed exactly as v1; within an engine, q_agn hashes must agree across variants and repetitions. On InnoDB, buffer-pool counters are captured immediately before and after every execution (warm-up and recorded), outside the timed window and identically for both variants: deltas of `Innodb_buffer_pool_read_requests`, `Innodb_buffer_pool_reads`, `Innodb_buffer_pool_read_ahead`, `pages_made_young`, `pages_not_made_young`, plus the post-execution `free_buffers` level (`SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_read%'` and `information_schema.innodb_buffer_pool_stats`). DuckLake rows carry the counter columns empty (honest nonapplicability — the OS page cache has no equivalent probe; DuckDB-side evidence is the runtime profile).
- Plans: captured once per condition × variant × query during that variant's first warm-up segment, never inside recorded repetitions. DuckDB: runtime profile JSON as v1 (`duckdb-profile-json`). InnoDB: both `EXPLAIN FORMAT=JSON` (`mysql-explain-json`, the optimizer's residency pricing) and `EXPLAIN ANALYZE` (`mysql-explain-analyze`, an actual execution — allowed because warm-up executions are unrecorded). Files land under `results/bench2/plans/`.
- Effect sizes and intervals: per backend × condition × query, the estimator is block-based — per block, the median over that block's recorded repetitions per variant; the block delta is aware-minus-blind of those medians; the report is the mean of block deltas with a two-sided 95 % t-interval over blocks (df = blocks − 1) and a seeded 10,000-resample bootstrap percentile interval, plus the relative delta against the blind median. The bootstrap seed is user-supplied or generated and persisted in `envinfo.json`. Counter summaries report per-variant medians of per-repetition physical reads and promotion counters. `summary.csv` is a derived artefact regenerated from all retained v2 raw rows.
- Pre-specified expectations (the §3.3 deviation rule continues to govern interpretation):
  - E5a — DuckLake `d0`: q_agn block deltas ≈ 0 (replication of E3 under the equalized sequence).
  - E5b — InnoDB `c1`: with identical W_agn-only sequences and counterbalanced order, the v1 aware advantage should shrink toward 0 or lose its sign stability; per-repetition physical reads discriminate the thrash and resident regimes regardless of the delta's sign.
  - E5c — InnoDB `c2`: block deltas ≈ 0 and physical reads ≈ 0 after first warm-up for both variants (residency constraint removed).
  - E5d — InnoDB `c3`: relative to `c1`, the constrained-pool scan penalty attributable to promotion gating disappears (pages young at first touch). If `c1` thrashes and `c3` does not, the scan-resistant-LRU account is established from two independent directions (pool size and promotion window); if `c1` already shows no thrash, the v1 asymmetry is attributed to cross-variant pool state under the v1 co-scheduling, which the v2 design equalises — either way the §5.2 sentence gains a tested grounding.
- Non-goals: warm protocol only (no cold-cache claim — unchanged from ADR-0004); no cross-engine product table; `W_eq` timings document the aware workload under each condition and support no variant contrast; storage measurement is not repeated (v1's storage.csv remains authoritative).

## Evidence and freeze record

Protocol v2 was implemented at
`7e544c2628a6871dac20f183914d30f1f2845a16`; every retained v2 run records
that commit in `results/bench2/runs.csv` and `envinfo.json`. The complete
evidence was committed at `89256b89420107da1ca865cf81dab3dc1fac9568` on
2026-08-23.

The repository's initial feature-freeze declaration dates to 2026-08-15.
ADR-0011 was an authorised, separately governed evidence amendment to that
freeze. The amendment closed when the evidence landed at `89256b8`, which is
therefore the final thesis freeze of the measured path. Subsequent
documentation, citation-metadata and release commits may describe or package
the evidence, but they do not supersede either evidence stage's recorded code
and evidence commits.

## Consequences

- The thesis can cite v1 for the frozen headline numbers and v2 for the mechanism question, each under its own authority note; nothing in `results/bench/`, the v1 harness, or the catalogue changes.
- The compose knob's default keeps every existing workflow byte-identical; only an explicit `GDGAP_MYSQL_BUFFER_POOL` changes the server, and `envinfo` read-backs make the conditions separable in evidence.
- The mirror rebuild restores server state deliberately and visibly; any timings after it belong to v2 by construction.
- Changes to workloads, block structure, conditions, counters, or estimators invalidate v2 comparability and require ADR-0012+.
