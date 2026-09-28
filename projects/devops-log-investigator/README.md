# DevOps Log Investigator

A fully local, image-first, read-only assistant for investigating existing Elasticsearch/Kibana telemetry with Persian natural-language questions.

The operator asks questions such as:

- `از صبح چند خطای 500 داشتیم؟`
- `کدام سرویس بیشترین timeout را داشته؟`
- `از صبح چند کد ملی داشتیم که بابت یک تراکنش دوبار از حسابشان برداشت شده؟`

The operator does **not** provide index names, field names, or query syntax. The Investigator discovers relevant Kibana knowledge and Elasticsearch schema, performs bounded probes, executes guarded read-only queries, repairs suspicious/failed hypotheses, cross-checks important results, and returns a Persian answer with audit metadata.

## Runtime architecture

Exactly four runtime images:

1. `ghcr.io/open-webui/open-webui:0.11.4-slim` — chat UI only.
2. `ollama/ollama:0.34.4` — local inference runtime.
3. `docker.elastic.co/mcp/elasticsearch:0.4.6` — read-only Elasticsearch MCP compatibility layer.
4. `devops-log-investigator/investigator:<git-sha>` — the only custom image.

Default local model: `qwen3:8b-q4_K_M`.

Open WebUI cannot access Elasticsearch directly. It only sees the logical model `log-investigator` exposed by the Investigator API. The Investigator is the policy boundary and the only component allowed to orchestrate LLM/tool calls.

## Non-negotiable safety properties

- No Elastic/Kibana write path exists in the Investigator.
- Elastic credentials must be read-only and restricted to explicit approved index patterns.
- Every MCP call is validated by the deterministic policy guard before network execution.
- ES|QL `FROM` sources are parsed and checked against the allowlist.
- Raw PII fields are redacted before probe results are added to LLM context.
- Suspicious zero results are not accepted without additional evidence/cross-check.
- Ambiguous telemetry produces `DATA_NOT_VERIFIED`, not a fabricated count.
- No Docker socket mount.
- Only Open WebUI publishes a host port.
- Target runtime uses `pull_policy: never`; normal operation requires no Internet access.

## Repository layout

```text
investigator/        small custom Python image, tests, OpenAI-compatible API
config/              deterministic policy, system prompt, environment template
deploy/              four-container Compose runtime
scripts/             staging bundle builder + offline lifecycle scripts
tests/acceptance/    end-to-end acceptance harness with fake Elastic/MCP data
docs/                offline installation/runbook
```

## Development verification

From this directory:

```bash
python3 -m venv .venv
.venv/bin/pip install -r investigator/requirements.txt pytest pytest-asyncio
PYTHONPATH=investigator .venv/bin/pytest -q
bash -n scripts/*.sh
python3 -m compileall -q investigator/app
```

When Docker is available, also run:

```bash
docker compose --env-file config/.env.example -f deploy/compose.yaml config
```

Do not treat a successful unit test run as proof that the four images can start on the target architecture. A connected staging host must build/export the bundle, and a network-isolated Docker host must run the smoke test before production use.

## Configure approved data scope

Edit `config/policy.yaml` before building the deployment bundle. Replace the example allowlist with the actual index patterns that this assistant is allowed to read.

Never use a blanket `*` allowlist in production.

The MCP Elasticsearch identity should have only the minimum permissions needed for the approved indices, normally read access plus index metadata visibility. Do not grant index-management, document-write, delete, cluster-admin, or security-management privileges.

Kibana access is optional. If a read-only Kibana identity is configured, the Investigator uses existing data views/saved searches/dashboard metadata as discovery hints. If Kibana is unavailable, the system degrades to Elasticsearch-only discovery rather than failing the entire investigation.

## Offline delivery

See [`docs/OFFLINE-INSTALL.md`](docs/OFFLINE-INSTALL.md).

The connected staging host performs all network-dependent work:

```bash
bash scripts/build-bundle.sh /srv/export/devops-log-investigator-bundle
```

The isolated target performs only checksum verification, `docker load`, local model-store restoration, Compose validation, and:

```bash
docker compose ... up -d --pull never
```

No package manager, `docker pull`, model download, pip/npm install, or source build is required on the target.

## Audit

Each completed investigation can append a local JSONL audit record containing request ID, original question, selected indices/fields, executed queries, repair reasons, verification state, confidence, and model identifier. Audit data stays in the local `dli-investigator-audit` Docker volume and is never written back to Elasticsearch.

## Known compatibility limitation

The standalone Elastic MCP server used here is an isolated compatibility component and is deprecated upstream. The Investigator business logic does not depend on undocumented MCP behavior so the MCP image can be replaced later without redesigning the chat/UI or investigation policy layers.
