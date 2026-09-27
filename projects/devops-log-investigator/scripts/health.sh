#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$BASE/deploy/compose.yaml" ]] || BASE="$BASE/runtime"
[[ -f "$BASE/.env" ]] || { echo "missing $BASE/.env" >&2; exit 2; }
COMPOSE=(docker compose --env-file "$BASE/.env" -f "$BASE/deploy/compose.yaml")
"${COMPOSE[@]}" ps
"${COMPOSE[@]}" exec -T investigator python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).read(); print('investigator: healthy')"
"${COMPOSE[@]}" exec -T ollama ollama list
