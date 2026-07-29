#!/bin/sh
set -eu
if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <previous-image-tag>" >&2
  exit 1
fi
export IMAGE_TAG="$1"
docker compose -f infra/compose/compose.yml -f infra/compose/compose.prod.yml pull
docker compose -f infra/compose/compose.yml -f infra/compose/compose.prod.yml up -d
bash scripts/deployment/health-check.sh
