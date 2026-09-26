# DevOps Log Investigator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully local, image-first, read-only log investigation assistant that answers Persian questions against existing Elasticsearch/Kibana data without requiring the operator to know index names, field names, or query syntax.

**Architecture:** Four containers: pinned Open WebUI for chat, pinned Ollama for local inference, pinned Elasticsearch MCP for read-only Elastic tools, and one small custom Investigator service. Open WebUI talks only to the Investigator through an OpenAI-compatible API; the Investigator owns orchestration, Kibana discovery, deterministic policy checks, MCP calls, query repair, cross-checks, redaction, and local audit output.

**Tech Stack:** Docker Compose v2, Python 3.12-slim, FastAPI, Uvicorn, httpx, Pydantic, official Python MCP SDK, PyYAML, stdlib sqlite3/json/logging, pytest, Open WebUI v0.11.4, Ollama v0.34.4, `qwen3:8b-q4_K_M`, Elasticsearch MCP v0.4.6.

**Spec:** `docs/superpowers/specs/2026-09-26-devops-log-investigator-design.md`

## Global Constraints

- Entire runtime operates in an isolated/offline environment.
- Target host performs no source build, package installation, image pull, or model download.
- Four runtime images only: Chat UI, Ollama, Elasticsearch MCP, Investigator.
- Investigator is the only custom image and must remain small.
- No agents/exporters/collectors on production servers.
- No Docker socket mount.
- No writes to Elasticsearch or Kibana.
- No new Kibana dashboards, saved objects, indices, mappings, alerts, or runtime configuration.
- No cloud LLM/API dependency.
- Elasticsearch credentials are read-only and restricted to explicit approved index patterns.
- Privilege enforcement exists below the LLM: Elastic RBAC plus deterministic Investigator guard.
- Target host requires only Linux, Docker Engine, and Docker Compose v2.
- Default model is `qwen3:8b-q4_K_M`; 14B is a later resource-profile option, not an MVP dependency.
- Open WebUI is pinned to `v0.11.4`; Ollama to `v0.34.4`; Elasticsearch MCP to `v0.4.6`.
- Elasticsearch MCP is an intentionally isolated compatibility component because it is deprecated upstream; no Investigator business logic may depend on undocumented MCP behavior.

## Review Focus

1. A model-generated query attempts to access an unapproved index: guard must reject it before MCP execution.
2. A question resolves to relevant data but the first query returns zero: investigator must probe/repair rather than silently report zero.
3. Kibana is unavailable but Elasticsearch is healthy: investigation must continue in degraded mode using Elastic discovery only.
4. Raw samples contain national IDs/account numbers: investigator must minimize or redact values before passing context to the LLM unless a value is required for grouping logic.
5. Offline bundle is started with no registry/network access: compose must use only locally loaded pinned images and must not pull.

---

## Planned Repository Layout

```text
projects/devops-log-investigator/
├── investigator/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py
│   │   ├── settings.py
│   │   ├── models.py
│   │   ├── policy.py
│   │   ├── llm.py
│   │   ├── mcp_client.py
│   │   ├── kibana.py
│   │   ├── catalog.py
│   │   ├── redaction.py
│   │   ├── orchestrator.py
│   │   └── audit.py
│   └── tests/
│       ├── test_policy.py
│       ├── test_redaction.py
│       ├── test_kibana.py
│       ├── test_orchestrator.py
│       └── test_api.py
├── config/
│   ├── policy.yaml
│   ├── system-prompt.txt
│   └── .env.example
├── deploy/
│   └── compose.yaml
├── scripts/
│   ├── build-bundle.sh
│   ├── install-offline.sh
│   ├── start.sh
│   ├── stop.sh
│   └── health.sh
├── tests/
│   └── acceptance/
│       ├── fixtures/
│       └── test_acceptance.py
└── README.md
```

### Task 1: Deterministic Read-only Policy Guard

**Files:**
- Create: `projects/devops-log-investigator/investigator/app/policy.py`
- Create: `projects/devops-log-investigator/investigator/app/models.py`
- Create: `projects/devops-log-investigator/config/policy.yaml`
- Test: `projects/devops-log-investigator/investigator/tests/test_policy.py`

**Interfaces:**
- Consumes: YAML policy containing `allowed_indices`, `denied_fields`, `max_time_range_hours`, `max_rows`, `max_sample_rows`, `max_calls`, `max_repairs`.
- Produces: `Policy.load(path: str) -> Policy`, `Policy.validate_tool_call(call: ToolCall) -> ValidatedToolCall`, `PolicyViolation`.

- [ ] **Step 1: Write failing guard tests** covering approved index, wildcard escape, explicit denied index, excessive row count, excessive time range, unsupported tool, and field denylist.
- [ ] **Step 2: Run `pytest investigator/tests/test_policy.py -v`** and confirm failures are due to missing policy implementation.
- [ ] **Step 3: Implement minimal typed policy loader and deterministic validator**; allow only `list_indices`, `get_mappings`, `search`, and `esql`; reject all non-allowlisted operations before network execution.
- [ ] **Step 4: Re-run policy tests** and require all PASS.
- [ ] **Step 5: Commit** with `feat: add deterministic elastic query guard`.

### Task 2: PII Minimization and Audit Primitives

**Files:**
- Create: `projects/devops-log-investigator/investigator/app/redaction.py`
- Create: `projects/devops-log-investigator/investigator/app/audit.py`
- Test: `projects/devops-log-investigator/investigator/tests/test_redaction.py`

**Interfaces:**
- Consumes: dictionaries/lists returned from Kibana or Elasticsearch probes.
- Produces: `redact_payload(payload: object, sensitive_fields: set[str]) -> object`, `AuditWriter.write(record: AuditRecord) -> pathlib.Path`.

- [ ] **Step 1: Write failing tests** proving national ID/account/card-like values are redacted while aggregate counts and field names remain available.
- [ ] **Step 2: Run redaction tests** and confirm expected failure.
- [ ] **Step 3: Implement recursive field-aware redaction and append-only JSON audit writer** with no Elastic dependency.
- [ ] **Step 4: Run tests** and require PASS.
- [ ] **Step 5: Commit** with `feat: add pii minimization and local audit`.

### Task 3: Read-only Kibana Knowledge Catalog

**Files:**
- Create: `projects/devops-log-investigator/investigator/app/kibana.py`
- Create: `projects/devops-log-investigator/investigator/app/catalog.py`
- Test: `projects/devops-log-investigator/investigator/tests/test_kibana.py`

**Interfaces:**
- Consumes: `KIBANA_URL`, read-only Kibana credential/API key, optional space ID.
- Produces: `KibanaClient.fetch_catalog() -> Catalog`, `Catalog.find_candidates(concepts: list[str]) -> list[CatalogEntry]`.

- [ ] **Step 1: Write failing HTTP-mocked tests** for successful discovery, 401/403, Kibana unavailable, malformed object, and absence of matching dashboards.
- [ ] **Step 2: Run Kibana tests** and confirm failure.
- [ ] **Step 3: Implement minimal read-only catalog retrieval** from existing Data Views, saved searches, dashboard/visualization references and labels; no create/update/import/delete methods exist in the client.
- [ ] **Step 4: Implement degraded mode** returning an empty catalog plus explicit health state when Kibana is unavailable.
- [ ] **Step 5: Run tests** and require PASS.
- [ ] **Step 6: Commit** with `feat: add read-only kibana discovery catalog`.

### Task 4: Ollama and Elasticsearch MCP Adapters

**Files:**
- Create: `projects/devops-log-investigator/investigator/app/llm.py`
- Create: `projects/devops-log-investigator/investigator/app/mcp_client.py`
- Test: `projects/devops-log-investigator/investigator/tests/test_orchestrator.py` (adapter fixtures section)

**Interfaces:**
- Produces: `OllamaClient.chat(messages: list[Message], tools: list[ToolSpec] | None = None) -> LLMResponse`.
- Produces: `ElasticMCPClient.call(tool: str, arguments: dict) -> dict`.
- MCP endpoint defaults to `http://elastic-mcp:8080/mcp`; Ollama endpoint defaults to `http://ollama:11434`.

- [ ] **Step 1: Write failing adapter tests** for tool-call parsing, MCP timeout, malformed JSON-RPC response, and Ollama unavailable.
- [ ] **Step 2: Run adapter tests** and confirm failure.
- [ ] **Step 3: Implement thin HTTP/SDK adapters**; adapters contain no business rules and expose typed errors.
- [ ] **Step 4: Run adapter tests** and require PASS.
- [ ] **Step 5: Commit** with `feat: add local llm and elastic mcp adapters`.

### Task 5: Investigation Loop with Probe, Repair, and Cross-check

**Files:**
- Create: `projects/devops-log-investigator/investigator/app/orchestrator.py`
- Create: `projects/devops-log-investigator/config/system-prompt.txt`
- Extend test: `projects/devops-log-investigator/investigator/tests/test_orchestrator.py`

**Interfaces:**
- Consumes: user question, `Catalog`, `Policy`, `OllamaClient`, `ElasticMCPClient`.
- Produces: `Investigator.investigate(question: str, now: datetime) -> InvestigationResult`.
- `InvestigationResult` includes `answer_fa`, `status`, `confidence`, `resolved_time_window`, `indices`, `fields`, `queries`, `verification`, `request_id`.

- [ ] **Step 1: Write failing scenario tests** for: HTTP 500 count, top timeout service, duplicate debit by transaction/account/amount; include first-query-zero then repair; include ambiguous semantics returning `DATA_NOT_VERIFIED`.
- [ ] **Step 2: Run orchestrator tests** and confirm failure.
- [ ] **Step 3: Implement bounded discovery loop**: intent → Kibana candidates → mappings → small probe → hypothesis → validated query → result evaluation → repair up to policy limit → independent cross-check where feasible.
- [ ] **Step 4: Ensure every MCP call passes through `Policy.validate_tool_call`** and every sample sent to LLM passes through redaction.
- [ ] **Step 5: Implement suspicious-zero rule**: zero is accepted only after a confirming probe/cross-check or explicit evidence of no matching events.
- [ ] **Step 6: Run orchestrator tests** and require PASS.
- [ ] **Step 7: Commit** with `feat: add autonomous investigation loop`.

### Task 6: OpenAI-compatible Investigator API for Open WebUI

**Files:**
- Create: `projects/devops-log-investigator/investigator/app/settings.py`
- Create: `projects/devops-log-investigator/investigator/app/main.py`
- Test: `projects/devops-log-investigator/investigator/tests/test_api.py`

**Interfaces:**
- Exposes: `GET /healthz`, `GET /v1/models`, `POST /v1/chat/completions`.
- `/v1/models` exposes one logical model: `log-investigator`.
- `/v1/chat/completions` accepts the latest user message and returns a normal OpenAI-compatible assistant response plus non-breaking metadata in an extension object.

- [ ] **Step 1: Write failing FastAPI tests** for health, model listing, successful Persian request, empty messages, unsupported model, and internal dependency failure.
- [ ] **Step 2: Run API tests** and confirm failure.
- [ ] **Step 3: Implement minimal API** with no custom frontend and no authentication logic beyond optional static internal token between Open WebUI and Investigator.
- [ ] **Step 4: Run API tests** and require PASS.
- [ ] **Step 5: Commit** with `feat: expose openai compatible investigator api`.

### Task 7: Investigator Image and Four-container Compose

**Files:**
- Create: `projects/devops-log-investigator/investigator/Dockerfile`
- Create: `projects/devops-log-investigator/investigator/requirements.txt`
- Create: `projects/devops-log-investigator/deploy/compose.yaml`
- Create: `projects/devops-log-investigator/config/.env.example`

**Interfaces:**
- Images:
  - `ghcr.io/open-webui/open-webui:v0.11.4`
  - `ollama/ollama:0.34.4`
  - `docker.elastic.co/mcp/elasticsearch:0.4.6`
  - `devops-log-investigator/investigator:<git-sha>`

- [ ] **Step 1: Add compose validation test/check** that exactly four services exist, only Open WebUI publishes a user-facing host port, no Docker socket is mounted, no service uses `latest`, and `pull_policy: never` is set for offline runtime.
- [ ] **Step 2: Run `docker compose -f deploy/compose.yaml config`** expecting failure until compose exists.
- [ ] **Step 3: Implement multi-stage/small Investigator image and compose** with private networks, healthchecks, dropped capabilities/no-new-privileges where compatible, explicit writable volumes only, and MCP in HTTP mode.
- [ ] **Step 4: Configure Open WebUI to use Investigator as its OpenAI-compatible backend** and Investigator to use Ollama internally.
- [ ] **Step 5: Run compose config validation** and require PASS.
- [ ] **Step 6: Commit** with `build: add four image offline compose stack`.

### Task 8: Offline Bundle Builder and Installer

**Files:**
- Create: `projects/devops-log-investigator/scripts/build-bundle.sh`
- Create: `projects/devops-log-investigator/scripts/install-offline.sh`
- Create: `projects/devops-log-investigator/scripts/start.sh`
- Create: `projects/devops-log-investigator/scripts/stop.sh`
- Create: `projects/devops-log-investigator/scripts/health.sh`

**Interfaces:**
- `build-bundle.sh <output-dir>` runs only on connected staging and exports the four images plus model assets and SHA256 manifest.
- `install-offline.sh <bundle-dir>` runs on isolated target and performs checksum verification, `docker load`, config validation, model import/copy, and `docker compose up -d --pull never`.

- [ ] **Step 1: Write shell-level tests/checks** proving installer aborts on missing image, checksum mismatch, or attempted pull dependency.
- [ ] **Step 2: Implement bundle builder** using pinned tags/digests and `docker save`.
- [ ] **Step 3: Implement offline installer and lifecycle scripts** with no package manager/network commands.
- [ ] **Step 4: Test against a network-disabled Docker environment** and require successful startup using only local assets.
- [ ] **Step 5: Commit** with `build: add reproducible offline bundle workflow`.

### Task 9: Acceptance Harness and Documentation

**Files:**
- Create: `projects/devops-log-investigator/tests/acceptance/test_acceptance.py`
- Create: `projects/devops-log-investigator/README.md`

**Interfaces:**
- Acceptance harness runs the three required Persian questions against fixture/mock Elastic data first, then against a configured read-only real environment when credentials are explicitly supplied.

- [ ] **Step 1: Add fixture data and failing acceptance tests** for 500 count, timeout ranking, and duplicate debit discovery without supplying field/index names.
- [ ] **Step 2: Run acceptance tests** and record failing baseline.
- [ ] **Step 3: Fix only defects required to pass acceptance**; no scope expansion.
- [ ] **Step 4: Run complete test suite**: `pytest -q` plus compose validation plus shell checks.
- [ ] **Step 5: Run offline smoke test**: UI health, Investigator health, Ollama model presence, MCP `/ping`, one end-to-end Persian query.
- [ ] **Step 6: Document installation, offline transfer, Elastic/Kibana least-privilege credentials, backup/restore of local audit/catalog volume, and known limitation that standalone Elastic MCP 0.4.6 is deprecated upstream.
- [ ] **Step 7: Commit** with `test: complete offline investigator mvp acceptance`.

## Definition of Done

- All Investigator unit/integration tests pass.
- Four-service Compose validates and starts with `--pull never`.
- No target-host build or package download is required.
- Only Open WebUI is user-facing.
- Elasticsearch/Kibana credentials are read-only and scoped.
- No write-capable code path exists in Investigator or Kibana client.
- All model-proposed Elastic operations pass deterministic guard before execution.
- The three MVP Persian questions pass without index names, field names, or user-written queries.
- A suspicious zero is not reported without validation.
- Each request has a local auditable record.
- Project can start in a network-disabled target environment from the exported bundle.

## Execution Method

Use the user’s established workflow: Chat → GitHub connector → GitHub Actions/self-hosted runner → build/test. Do not use Codex/Work. Implement natively task-by-task with TDD and verify each task before claiming completion.
