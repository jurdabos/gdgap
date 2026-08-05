# gdgap

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
