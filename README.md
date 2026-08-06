# gdgap

The canonical DuckDB/DuckLake engine runs in-process, as embedded engines are designed to;
only the client–server comparison component (MySQL/InnoDB) is containerised. Reproducibility
comes from version pins, manifest-verified data, and the executable R13 contract rather than
an application image (ADR-0010).

## Reproduction

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker with Compose (for the InnoDB foil), and
the 2017 NHTS public-use CSVs — not redistributed here; the source URL and per-file SHA-256
digests sit in `datasets/nhts2017/manifest.json`, and ingest aborts on any mismatch.

```bash
uv sync                                      # locked environment (uv.lock, .python-version)
cp .env.example .env                         # then fill in real values
# place hhpub/perpub/trippub/vehpub.csv under data/raw/nhts2017/
uv run gdgap ingest nhts2017                 # manifest-verified ingest + R13 validation
uv run gdgap profile && uv run gdgap summarize
uv run gdgap build --variant blind
uv run gdgap build --variant aware           # ends with the R13 conformance run
docker compose up -d --wait                  # MySQL foil — see next section
uv run gdgap build --variant blind --backend innodb
uv run gdgap build --variant aware --backend innodb
uv run gdgap bench --variant blind           # one warm cell; repeat per backend × variant
uv run gdgap audit-imputation                # imputation sensitivity audit
```

Evidence lands under `results/`, keyed by Git commit and lake snapshot; which artefact is
authoritative for what is fixed in `docs/authority-map.md`.

## MySQL foil (containerized)

The InnoDB benchmark foil runs in a compose-managed MySQL 8.4 LTS container (ADR-0008):

```bash
docker compose up -d --wait            # gdgap-mysql on 127.0.0.1:3307
uv run gdgap mysql-doctor              # sanitized connectivity check
uv run gdgap build --variant blind --backend innodb
uv run gdgap build --variant aware --backend innodb
scripts/dump_mysql.sh                  # gzipped logical dump into data/dumps/
```

Credentials live in `.env` (see `.env.example`). The datadir persists in the
`gdgap_mysql_data` Docker volume; durable evidence is the committed DDL, the dump
exports, and `results/` — never the volume.
