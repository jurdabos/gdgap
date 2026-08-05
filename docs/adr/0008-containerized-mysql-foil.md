# ADR 0008: Containerized MySQL as the InnoDB foil's server

- Status: accepted
- Date: 2026-08-05

## Context

The InnoDB foil originally pointed `GDGAP_MYSQL_URL` at a MySQL 8.0.x server on the Windows host, reached from WSL. Under WSL NAT networking that required Windows-side `portproxy` and firewall rules, and a proposed endpoint-resolver design (a `windows-host` target, `wslinfo` mode detection, NAT-gateway discovery, transport-half doctor checks) existed solely to make that boundary deterministic. The arrangement also handicapped the foil: DuckLake runs in-process inside the WSL VM on ext4, while the Windows server sat across a virtualized network hop with an NTFS datadir — a transport asymmetry a reviewer could challenge — and the benchmark environment depended on whatever MySQL happened to be installed on the host.

## Decision

- MySQL runs as a compose-managed container inside WSL (`compose.yaml`): image pinned to `mysql:8.4.11` — the current 8.4 LTS patch, deliberately superseding the host's 8.0.x while staying on the LTS track rather than the innovation series — published loopback-only at `127.0.0.1:3307` and health-gated on an authenticated `mysqladmin ping`.
- The datadir lives in the named Docker volume `gdgap_mysql_data` (ext4-native I/O). Bind-mounting the datadir under `/mnt/*` is rejected: 9p filesystem latency would poison the timing evidence.
- Durable evidence is never the volume: the mirrors rebuild from committed DDL via `gdgap build --backend innodb`, and `scripts/dump_mysql.sh` exports gzipped logical dumps into gitignored `data/dumps/` (or `GDGAP_DUMP_DIR`) for posterity, thesis argumentation, and presentations.
- Credentials stay in `.env` only: `GDGAP_MYSQL_ROOT_PASSWORD` (compose interpolation) and the matching `GDGAP_MYSQL_URL` the backend consumes. The dump script reads the password from the container's own environment, so it never crosses the host shell or process list.
- `tests/conftest.py` loads the root `.env` before test modules evaluate their `requires_mysql` markers; `gdgap mysql-doctor` reports sanitized connectivity facts (endpoint, TCP, auth, server version — never username, password, or the full URL); PyMySQL connects with an explicit `connect_timeout`; and `envinfo.json` records sanitized transport provenance (`mysql_host`/`mysql_port`) per run set, so container-loopback and remote-host runs stay distinguishable in evidence.

## Consequences

- Both engines execute in the same VM on the same kernel and filesystem, so the row-vs-column contrast no longer carries a hidden transport asymmetry, and the whole server configuration is declared in a committed file — a reproducibility statement the methods chapter can cite.
- Any InnoDB numbers collected against the Windows-host server are not comparable to container runs (different server version, I/O path, and transport) and must be re-collected; the `mysql_host`/`mysql_port` provenance plus `engine_version` make the two populations separable in `results/`.
- MySQL upgrades become deliberate tag bumps in `compose.yaml`, recorded like the DuckDB engine pin (ADR-0001).
- WSL networking mode (NAT vs mirrored) stops mattering.

