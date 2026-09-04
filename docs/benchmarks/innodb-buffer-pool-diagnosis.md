# Diagnosing the protocol-v1 InnoDB timing asymmetry

This note preserves the engineering interpretation of an unexpected
protocol-v1 result. [ADR-0011](../adr/0011-benchmark-protocol-v2-mechanism-probe.md)
and the retained files under `results/bench2/` are the authoritative test and
resolution. The mechanism described below was a candidate explanation.

## Protocol-v1 observation

Under the recorded 128 MB InnoDB buffer-pool configuration, the aware variant
answered each shared `q_agn` scan about 250 ms faster than the blind variant.
The query bodies and result hashes agreed. The captured plans had the same scan
shape, while the optimiser assigned different buffer-pool-residency costs.

The difference could not be interpreted as an intrinsic benefit of the aware
schema. The two variants ran different executable query mixes: the blind round
contained the two shared queries, whereas the aware round also contained the
two equality-oriented queries. Query order was shuffled, both variants shared
one server state, and protocol v1 retained optimiser estimates but no direct
buffer-pool counters.

## Candidate mechanism

InnoDB's default scan-resistant least-recently-used policy places pages read by
a large scan in the old sublist. With `innodb_old_blocks_pct` at 37%, the old
portion of a 128 MiB pool was about 47 MiB, smaller than the approximately 73 MiB
`fact_trip` table. A page was eligible for promotion only when revisited more
than `innodb_old_blocks_time` (1000 ms) after its first access.

The shorter blind round took about 0.85 seconds and could therefore cycle
through the table before pages became promotable. The longer aware round took
about 1.5 seconds and could cross the promotion threshold. This account fitted
the observed timing and plan-cost difference, but the unequal workloads and
shared pool state prevented a causal conclusion.

## State restoration and test isolation

A later pre-run inspection found that live InnoDB integration tests could
replace the shared mirror tables with fixture-scale data. The retained
protocol-v1 files were unaffected, but the finding made server-state isolation
explicitly necessary before further measurement. The tests were moved behind
the dedicated `GDGAP_MYSQL_TEST_URL` guard, and both full-scale mirrors were
rebuilt before protocol v2.

## Protocol-v2 resolution

ADR-0011 pre-specified an equal shared workload, counterbalanced ABBA/BAAB
blocks, direct InnoDB counters and three conditions: the original 128 MiB pool,
a 1 GiB pool, and a 128 MiB pool with `innodb_old_blocks_time = 0`. DuckLake was
also measured with the equalised sequence.

The large protocol-v1 advantage did not recur. Across the InnoDB conditions,
the aware-minus-blind effects for the shared queries were small relative to the
earlier difference, and the block-based t intervals included zero. The median
`Innodb_buffer_pool_reads` delta was zero for both variants in every measured
InnoDB cell. Protocol v2 therefore provided no evidence for an intrinsic
aware-variant speed advantage or for the proposed steady-state physical-read
mechanism under the retained conditions.

The defensible interpretation is narrower: the protocol-v1 asymmetry depended
on execution history, unequal query mixes, server state, or their combination.
It remains a valid observation from its frozen workload and configuration, but
it is not a general performance property of the design.

## Evidence authority

- Protocol v1: [ADR-0004](../adr/0004-benchmark-protocol.md), code commit
  `f9a0117`, evidence commit `8ed0899`, and `results/bench/`.
- Protocol v2: [ADR-0011](../adr/0011-benchmark-protocol-v2-mechanism-probe.md),
  code commit `7e544c2`, evidence commit `89256b8`, and `results/bench2/`.
