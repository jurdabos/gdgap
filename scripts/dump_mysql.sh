#!/usr/bin/env bash
# Exports the InnoDB foil databases from the gdgap-mysql container as a gzipped
# logical dump for posterity and presentations (ADR-0008). The password never
# crosses the host shell: mysqldump reads MYSQL_PWD from the container's own
# environment. Target directory defaults to data/dumps/ (gitignored); override
# with GDGAP_DUMP_DIR to archive elsewhere (e.g. a /mnt/d thesis folder).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DUMP_DIR="${GDGAP_DUMP_DIR:-$REPO_ROOT/data/dumps}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$DUMP_DIR/gdgap_mysql_${STAMP}.sql.gz"
TMP="$OUT.part"

mkdir -p "$DUMP_DIR"
trap 'rm -f "$TMP"; echo "dump failed — partial file removed" >&2' ERR

docker compose -f "$REPO_ROOT/compose.yaml" exec -T mysql sh -c \
  'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump --databases gdgap_blind gdgap_aware --single-transaction --routines --triggers --events' \
  | gzip > "$TMP"
mv "$TMP" "$OUT"
echo "wrote $OUT"
