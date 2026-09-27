#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <bundle-dir>" >&2
  exit 2
fi

BUNDLE="$(realpath "$1")"
INSTALL_DIR="${DLI_INSTALL_DIR:-/opt/devops-log-investigator}"
REQUIRED_IMAGES=(open-webui.tar ollama.tar elastic-mcp.tar investigator.tar)

command -v sha256sum >/dev/null || { echo "missing required command: sha256sum" >&2; exit 1; }

for image in "${REQUIRED_IMAGES[@]}"; do
  [[ -f "$BUNDLE/images/$image" ]] || { echo "missing required image: images/$image" >&2; exit 1; }
done
[[ -f "$BUNDLE/SHA256SUMS" ]] || { echo "missing SHA256SUMS" >&2; exit 1; }
[[ -f "$BUNDLE/runtime/deploy/compose.yaml" ]] || { echo "missing runtime compose" >&2; exit 1; }
[[ -d "$BUNDLE/models/ollama" ]] || { echo "missing Ollama model store" >&2; exit 1; }

echo "[1/6] Verifying bundle checksums"
if ! (cd "$BUNDLE" && sha256sum -c SHA256SUMS); then
  echo "checksum verification failed" >&2
  exit 1
fi

command -v docker >/dev/null || { echo "missing required command: docker" >&2; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "missing required component: docker compose v2" >&2; exit 1; }

echo "[2/6] Installing immutable runtime files"
mkdir -p "$INSTALL_DIR"
cp -a "$BUNDLE/runtime/." "$INSTALL_DIR/"
mkdir -p "$INSTALL_DIR/scripts"
cp -a "$BUNDLE/scripts/." "$INSTALL_DIR/scripts/"

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
  echo "runtime .env was missing; template created at $INSTALL_DIR/.env" >&2
  echo "fill local secrets and run installer again" >&2
  exit 2
fi
if grep -Eq '(CHANGE_ME|REPLACE_WITH)' "$INSTALL_DIR/.env"; then
  echo "runtime .env still contains placeholder values" >&2
  exit 2
fi

IMAGE_TAG="$(cat "$INSTALL_DIR/INVESTIGATOR_IMAGE_TAG" 2>/dev/null || true)"
if [[ -n "$IMAGE_TAG" ]] && ! grep -q '^INVESTIGATOR_IMAGE_TAG=' "$INSTALL_DIR/.env"; then
  printf '\nINVESTIGATOR_IMAGE_TAG=%s\n' "$IMAGE_TAG" >> "$INSTALL_DIR/.env"
fi
MODEL="$(cat "$INSTALL_DIR/OLLAMA_MODEL" 2>/dev/null || echo 'qwen3:8b-q4_K_M')"
if ! grep -q '^OLLAMA_MODEL=' "$INSTALL_DIR/.env"; then
  printf 'OLLAMA_MODEL=%s\n' "$MODEL" >> "$INSTALL_DIR/.env"
fi

echo "[3/6] Loading four local images"
for image in "${REQUIRED_IMAGES[@]}"; do
  docker load -i "$BUNDLE/images/$image"
done

echo "[4/6] Restoring prepared Ollama model store"
docker volume create dli-ollama-data >/dev/null
docker run --rm --pull never \
  -v dli-ollama-data:/target \
  -v "$BUNDLE/models/ollama:/source:ro" \
  --entrypoint /bin/sh ollama/ollama:0.34.4 \
  -c 'cp -a /source/. /target/'

echo "[5/6] Validating Compose without network pulls"
docker compose --env-file "$INSTALL_DIR/.env" -f "$INSTALL_DIR/deploy/compose.yaml" config >/dev/null

echo "[6/6] Starting offline stack"
docker compose --env-file "$INSTALL_DIR/.env" -f "$INSTALL_DIR/deploy/compose.yaml" up -d --pull never

echo "installed at $INSTALL_DIR"
