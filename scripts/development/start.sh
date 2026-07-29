#!/bin/sh
set -eu
[ -f .env ] || cp .env.example .env
docker compose -f infra/compose/compose.yml up -d --build
