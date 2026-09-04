# gdgap

`gdgap` is a design-science software artefact for examining how choices in
analytical data-warehouse design make sex-related information available or
unavailable.
It builds two warehouse variants from the same 2017 National Household Travel
Survey (NHTS) public-use source:

- `blind` retains the shared analytical facts but omits the sex attribute and
  therefore cannot represent sex-disaggregated queries; and
- `aware` retains recorded sex, source response states and provenance, while
  governing sex and gender identity as separate domains. The NHTS does not
  collect gender identity, so that field is populated as `NC` (not collected)
  by construction.

DuckDB with DuckLake is the canonical in-process implementation. A
Compose-managed MySQL/InnoDB deployment provides a row-store foil for the
bounded benchmark study; it is not a second canonical architecture. Version
pins, manifest-verified input, executable data-quality rules and retained
provenance provide the reproducibility chain (ADR-0010).

## Repository guide

- [`docs/README.md`](docs/README.md) is the documentation index.
- [`docs/requirements.md`](docs/requirements.md) defines the R1–R13
  requirements.
- [`docs/adr/`](docs/adr/) records the architectural and evaluation decisions.
- [`docs/model/architecture_overview.png`](docs/model/architecture_overview.png)
  and [`docs/model/conceptual_overview.png`](docs/model/conceptual_overview.png)
  provide the reader-facing architecture and data-model views; the Mermaid
  sources and detailed diagrams are retained beside them.
- `datasets/nhts2017/` contains the source manifest, datasheet and executable
  data-quality specification, but not the source CSV files.
- `sql/ddl/` and `sql/bench/` contain the warehouse definitions and the frozen
  query catalogue.
- `results/` contains the retained profile, quality, sensitivity and benchmark
  evidence.
- [`docs/authority-map.md`](docs/authority-map.md) identifies the authoritative
  source for each kind of claim, decision, behaviour, data meaning and result.

## Install and build the canonical artefact

Prerequisites are [uv](https://docs.astral.sh/uv/), `curl` and the four 2017
NHTS public-use CSV files. FHWA distributes them through the
[official NHTS downloads page](https://nhts.ornl.gov/downloads); the repository
manifest pins the page's 2017 survey-data CSV archive. From the repository root
in WSL or another Linux shell:

```bash
uv sync --frozen
mkdir -p data/raw/nhts2017
curl --fail --location --show-error \
  https://nhts.ornl.gov/media/2016/download/csv.zip \
  --output /tmp/nhts2017-csv.zip
uv run python -m zipfile -e \
  /tmp/nhts2017-csv.zip data/raw/nhts2017
rm /tmp/nhts2017-csv.zip

uv run gdgap ingest nhts2017
uv run gdgap profile
uv run gdgap summarize
uv run gdgap build --variant blind
uv run gdgap build --variant aware
uv run gdgap audit-imputation
```

The archive also contains the publisher's `Citation.docx`; `gdgap` ignores it
and reads only the four CSV files named in
`datasets/nhts2017/manifest.json`. Their expected filenames, byte sizes and
SHA-256 digests are recorded there, and ingest stops on any mismatch.

The ingest and aware-build commands run the applicable R13 conformance checks.
The resulting local DuckLake catalogue and data files are rebuildable and
gitignored; the versioned evidence is under `results/`.

An offline repository check does not require MySQL:

```bash
env GDGAP_MYSQL_TEST_URL= uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

## Optional MySQL/InnoDB foil

Docker with Compose is required only for the InnoDB foil. Copy `.env.example`
to `.env`, replace the MySQL placeholders and keep the dedicated
`GDGAP_MYSQL_TEST_URL` unset unless it points to a disposable test server.
Tests refuse to use the evidence server as their test endpoint.

```bash
docker compose up -d --wait
uv run gdgap mysql-doctor
uv run gdgap build --variant blind --backend innodb
uv run gdgap build --variant aware --backend innodb
scripts/dump_mysql.sh
```

The container data directory persists in the `gdgap_mysql_data` Docker volume.
That volume is operational state, not evidence. The committed DDL, logical
exports prepared by the operator and files under `results/` are the durable
record.

## Frozen evaluation evidence

The two benchmark protocols answer different questions and remain separate:

| Evidence stage | Code commit recorded by the runs | Commit containing the evidence | Location |
|---|---|---|---|
| Protocol v1 headline evaluation | `f9a011727e3954ba68fb5f040a3485a71eb9cf08` | `8ed0899b1b0d2b0da74a8229eb4ce869a49146b3` | `results/bench/` and `results/plans/` |
| Protocol v2 mechanism probe | `7e544c2628a6871dac20f183914d30f1f2845a16` | `89256b89420107da1ca865cf81dab3dc1fac9568` | `results/bench2/` |

The project entered an initial feature freeze on 2026-08-15. ADR-0011 then
authorised protocol v2 as a separately governed evidence amendment. Its final
evidence landed at `89256b8` on 2026-08-23, which is the final thesis freeze of
the measured path. Later documentation and release-metadata commits do not
replace the code and evidence commits recorded above.

The retained files are the submission evidence. Do not run `gdgap bench` or
`gdgap bench2` as smoke tests: a new invocation creates new evidence and needs
its own authority record. ADR-0004 defines protocol v1; ADR-0011 defines the
mechanism probe and the separation between the two stages.

## Scope and limitations

- The implemented case concerns one public-use household travel survey. It is
  an inspectable design demonstration, not evidence that the same schema or
  measures transfer unchanged to every domain.
- The source variable describes recorded sex. The NHTS does not collect gender
  identity, and the artefact does not infer it.
- The benchmark evidence covers the declared warm protocols and configurations.
  DuckDB/DuckLake runs in process, whereas MySQL is a client/server system, so
  the results do not support an unqualified product-performance comparison.
- Published survey weights are used as supplied. Sensitivity analysis measures
  the influence of the source imputation; it does not reconstruct donor
  assignments or re-rake the weights.

## Data provenance and licence

The source CSV files are not redistributed. They remain subject to the source
publisher's terms and must be obtained independently from the URL recorded in
the manifest. `datasets/nhts2017/DATASHEET.md` documents their provenance,
composition, preprocessing and known limitations.

The software and repository documentation are licensed under the MIT License;
see `LICENSE`. That licence does not relicense the NHTS source data.

## Citation

The DOI `10.5281/zenodo.22288496` is reserved for the `v1.0.0` release and
will begin resolving when the Zenodo draft is published.

For the study-level citation, use the thesis metadata under preferred-citation in CITATION.cff or GitHub’s Cite this repository panel. To identify the archived software release, use the top-level software metadata and version DOI 10.5281/zenodo.22288496.
