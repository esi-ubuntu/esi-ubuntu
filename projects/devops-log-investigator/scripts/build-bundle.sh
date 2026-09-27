#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <output-dir>" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT="$(realpath -m "$1")"
[[ -n "$OUTPUT" && "$OUTPUT" != "/" ]] || { echo "refusing unsafe output path" >&2; exit 2; }

OPEN_WEBUI_IMAGE="ghcr.io/open-webui/open-webui:0.11.4-slim"
OLLAMA_IMAGE="ollama/ollama:0.34.4"
ELASTIC_MCP_IMAGE="docker.elastic.co/mcp/elasticsearch:0.4.6"
OPEN_WEBUI_SOURCE_IMAGE="${OPEN_WEBUI_SOURCE_IMAGE:-$OPEN_WEBUI_IMAGE}"
OLLAMA_SOURCE_IMAGE="${OLLAMA_SOURCE_IMAGE:-$OLLAMA_IMAGE}"
ELASTIC_MCP_SOURCE_IMAGE="${ELASTIC_MCP_SOURCE_IMAGE:-$ELASTIC_MCP_IMAGE}"
IMAGE_PULL_RETRIES="${DLI_IMAGE_PULL_RETRIES:-3}"
MODEL="${OLLAMA_MODEL:-qwen3:8b-q4_K_M}"
INVESTIGATOR_IMAGE_TAG="${INVESTIGATOR_IMAGE_TAG:-$(git -C "$PROJECT_ROOT" rev-parse --short=12 HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"
INVESTIGATOR_IMAGE="devops-log-investigator/investigator:${INVESTIGATOR_IMAGE_TAG}"
MODEL_CONTAINER="dli-bundle-model-$$"

command -v docker >/dev/null || { echo "docker is required on staging" >&2; exit 1; }
command -v sha256sum >/dev/null || { echo "sha256sum is required on staging" >&2; exit 1; }
[[ "$IMAGE_PULL_RETRIES" =~ ^[1-9][0-9]*$ ]] || { echo "DLI_IMAGE_PULL_RETRIES must be a positive integer" >&2; exit 2; }

rm -rf "$OUTPUT"
mkdir -p "$OUTPUT/images" "$OUTPUT/models/ollama" "$OUTPUT/runtime" "$OUTPUT/scripts"

cleanup() {
  docker rm -f "$MODEL_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

pull_runtime_image() {
  local runtime="$1"
  local source="$2"
  local attempt
  for attempt in $(seq 1 "$IMAGE_PULL_RETRIES"); do
    if docker pull "$source"; then
      if [[ "$source" != "$runtime" ]]; then
        docker tag "$source" "$runtime"
      fi
      docker image inspect "$runtime" >/dev/null
      return 0
    fi
    if [[ "$attempt" -lt "$IMAGE_PULL_RETRIES" ]]; then
      echo "pull failed for $source (attempt $attempt/$IMAGE_PULL_RETRIES); retrying" >&2
      sleep $((attempt * 3))
    fi
  done
  echo "failed to pull source image after $IMAGE_PULL_RETRIES attempts: $source" >&2
  return 1
}

echo "[1/7] Pulling pinned third-party images on connected staging"
pull_runtime_image "$OPEN_WEBUI_IMAGE" "$OPEN_WEBUI_SOURCE_IMAGE"
pull_runtime_image "$OLLAMA_IMAGE" "$OLLAMA_SOURCE_IMAGE"
pull_runtime_image "$ELASTIC_MCP_IMAGE" "$ELASTIC_MCP_SOURCE_IMAGE"

echo "[2/7] Building the only custom image"
docker build -t "$INVESTIGATOR_IMAGE" "$PROJECT_ROOT/investigator"

echo "[3/7] Downloading local model into transferable Ollama store"
docker run -d --name "$MODEL_CONTAINER" \
  -v "$OUTPUT/models/ollama:/root/.ollama" \
  "$OLLAMA_IMAGE" >/dev/null
for _ in $(seq 1 60); do
  if docker exec "$MODEL_CONTAINER" ollama list >/dev/null 2>&1; then break; fi
  sleep 1
done
docker exec "$MODEL_CONTAINER" ollama pull "$MODEL"
docker exec "$MODEL_CONTAINER" ollama show "$MODEL" >/dev/null
cleanup

echo "[4/7] Exporting exactly four runtime images"
docker save -o "$OUTPUT/images/open-webui.tar" "$OPEN_WEBUI_IMAGE"
docker save -o "$OUTPUT/images/ollama.tar" "$OLLAMA_IMAGE"
docker save -o "$OUTPUT/images/elastic-mcp.tar" "$ELASTIC_MCP_IMAGE"
docker save -o "$OUTPUT/images/investigator.tar" "$INVESTIGATOR_IMAGE"

echo "[5/7] Copying runtime configuration and lifecycle scripts"
mkdir -p "$OUTPUT/runtime/deploy" "$OUTPUT/runtime/config"
cp "$PROJECT_ROOT/deploy/compose.yaml" "$OUTPUT/runtime/deploy/compose.yaml"
cp "$PROJECT_ROOT/config/policy.yaml" "$OUTPUT/runtime/config/policy.yaml"
cp "$PROJECT_ROOT/config/system-prompt.txt" "$OUTPUT/runtime/config/system-prompt.txt"
cp "$PROJECT_ROOT/config/.env.example" "$OUTPUT/runtime/.env.example"
cp "$SCRIPT_DIR/install-offline.sh" "$SCRIPT_DIR/start.sh" "$SCRIPT_DIR/stop.sh" "$SCRIPT_DIR/health.sh" "$OUTPUT/scripts/"
chmod 0755 "$OUTPUT/scripts/"*.sh
printf '%s\n' "$INVESTIGATOR_IMAGE_TAG" > "$OUTPUT/runtime/INVESTIGATOR_IMAGE_TAG"
printf '%s\n' "$MODEL" > "$OUTPUT/runtime/OLLAMA_MODEL"

{
  echo "open-webui=$OPEN_WEBUI_IMAGE"
  echo "ollama=$OLLAMA_IMAGE"
  echo "elastic-mcp=$ELASTIC_MCP_IMAGE"
  echo "investigator=$INVESTIGATOR_IMAGE"
  echo "model=$MODEL"
  echo "open-webui-source=$OPEN_WEBUI_SOURCE_IMAGE"
  echo "ollama-source=$OLLAMA_SOURCE_IMAGE"
  echo "elastic-mcp-source=$ELASTIC_MCP_SOURCE_IMAGE"
  for image in "$OPEN_WEBUI_IMAGE" "$OLLAMA_IMAGE" "$ELASTIC_MCP_IMAGE" "$INVESTIGATOR_IMAGE"; do
    docker image inspect --format '{{join .RepoDigests ","}}' "$image" 2>/dev/null || true
  done
} > "$OUTPUT/IMAGE-MANIFEST.txt"

echo "[6/7] Writing SHA256SUMS"
(
  cd "$OUTPUT"
  find images models runtime scripts -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
  sha256sum IMAGE-MANIFEST.txt >> SHA256SUMS
)

echo "[7/7] Bundle ready: $OUTPUT"
echo "On target: copy runtime/.env.example to runtime/.env, fill local secrets, then run scripts/install-offline.sh $OUTPUT"
