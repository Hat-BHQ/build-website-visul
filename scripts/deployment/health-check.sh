#!/bin/sh
set -eu
url="${HQ_PLATFORM_URL:-http://localhost:8080}"
for attempt in $(seq 1 30); do
  if curl -fsS "$url/api/v1/auth/session" >/dev/null 2>&1; then
    echo "Gateway is reachable."
    exit 0
  fi
  if curl -fsS "$url/" >/dev/null 2>&1; then
    echo "Portal is reachable."
    exit 0
  fi
  sleep 2
done
echo "Health check failed." >&2
exit 1
