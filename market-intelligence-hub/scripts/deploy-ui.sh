#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BUILD_DIR="${MIH_BUILD_DIR:-$PROJECT_DIR/ui/dist}"
DEPLOY_DIR="${MIH_DEPLOY_DIR:-/var/www/market-intelligence-hub}"
[[ -f "$BUILD_DIR/index.html" ]] || { echo "BUILD_NOT_FOUND: $BUILD_DIR" >&2; exit 20; }
parent="$(dirname "$DEPLOY_DIR")"; base="$(basename "$DEPLOY_DIR")"; stage="$parent/.${base}.stage.$$"; old="$parent/.${base}.old.$$"
mkdir -p "$stage"; cp -a "$BUILD_DIR/." "$stage/"
if [[ -d "$DEPLOY_DIR" ]]; then mv "$DEPLOY_DIR" "$old"; fi
mv "$stage" "$DEPLOY_DIR"
rm -rf "$old"
if [[ -n "${MIH_HEALTHCHECK_URL:-}" ]]; then curl -fsS --max-time 10 "$MIH_HEALTHCHECK_URL" >/dev/null; fi
echo "DEPLOY_OK: $DEPLOY_DIR"
