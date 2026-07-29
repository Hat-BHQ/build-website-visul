#!/bin/sh
set -eu
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
docker compose -f infra/compose/compose.yml exec -T postgres pg_dumpall \
  -U "${POSTGRES_SUPERUSER:-postgres}" | gzip > "backups/postgres-$stamp.sql.gz"
find backups -type f -mtime +14 -delete
