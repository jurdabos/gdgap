# gdgap documentation

The root [README](../README.md) gives the installation and reproduction
workflow. This directory records the design contract, the decisions that
shaped the artefact, its principal data structures, and the interpretation of
its retained evidence.

## Start here

- [Requirements](requirements.md) defines the R1–R13 design and evaluation
  contract.
- [Architecture overview](model/architecture_overview.png) and [conceptual
  overview](model/conceptual_overview.png) are the compact reader-facing
  diagrams. Their Mermaid sources are stored beside them.
- [Physical columns](model/physical-columns.md) identifies the columns and keys
  that carry the design argument. The detailed architecture and conceptual
  diagrams provide the corresponding expanded views.
- [Architectural decision records](adr/) explain why the implementation took
  its present form.
- [InnoDB buffer-pool diagnosis](benchmarks/innodb-buffer-pool-diagnosis.md)
  preserves the interpretation of the protocol-v1 anomaly and its protocol-v2
  resolution.
- [Terminology](terminology.md) defines the project-specific vocabulary used in
  the code, evidence and documentation.
- [Authority map](authority-map.md) identifies the controlling source for each
  kind of claim, decision, behaviour, data meaning and result.

## Decision records

| ADR | Decision |
| --- | --- |
| [0001](adr/0001-engine-and-lake.md) | Use DuckDB with DuckLake as the canonical analytical store. |
| [0002](adr/0002-dataset-scoping.md) | Scope the implemented corpus to the 2017 NHTS public-use data. |
| [0003](adr/0003-cloud-mirror.md) | Keep cloud deployment outside the submission artefact. |
| [0004](adr/0004-benchmark-protocol.md) | Freeze the principal benchmark protocol and evidence contract. |
| [0005](adr/0005-scd-attribution-semantics.md) | Report facts against the current recorded identity. |
| [0006](adr/0006-sex-gender-domain-separation.md) | Govern recorded sex and gender identity as separate domains. |
| [0007](adr/0007-response-state-granularity.md) | Preserve the source response state and imputation provenance. |
| [0008](adr/0008-containerized-mysql-foil.md) | Use containerised MySQL/InnoDB as a bounded engineering foil. |
| [0009](adr/0009-data-quality-contract.md) | Make the data-quality contract executable. |
| [0010](adr/0010-deployment-form.md) | Keep deployment local and reproducible for submission. |
| [0011](adr/0011-benchmark-protocol-v2-mechanism-probe.md) | Test the protocol-v1 InnoDB anomaly with an equalised mechanism probe. |

## Diagram maintenance

The Mermaid files are the editable sources; the PNG files are their derived renderings. The overview diagrams are intended for ordinary reading, while the detailed versions are best opened at full resolution.

| Model | Overview | Detailed | Mermaid sources |
| --- | --- | --- | --- |
| Architecture | [PNG](model/architecture_overview.png) | [PNG](model/architecture.png) | [Overview](model/architecture_overview.mmd) · [Detailed](model/architecture.mmd) |
| Conceptual data model | [PNG](model/conceptual_overview.png) | [PNG](model/conceptual.png) | [Overview](model/conceptual_overview.mmd) · [Detailed](model/conceptual.mmd) |

## Scope boundary

The repository documentation describes the released software and its retained
evidence. Thesis-specific abbreviations, broad literature terminology and
research-process records belong in the thesis workspace rather than this
software repository.
