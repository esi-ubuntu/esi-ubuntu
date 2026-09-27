#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$BASE/deploy/compose.yaml" ]] || BASE="$BASE/runtime"
[[ -f "$BASE/.env" ]] || { echo "missing $BASE/.env" >&2; exit 2; }
docker compose --env-file "$BASE/.env" -f "$BASE/deploy/compose.yaml" stop
