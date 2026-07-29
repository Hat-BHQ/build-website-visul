#!/bin/sh
set -eu
docker compose -f infra/compose/compose.yml down
