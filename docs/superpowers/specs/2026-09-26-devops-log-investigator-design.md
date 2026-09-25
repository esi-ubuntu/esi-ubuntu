# DevOps Log Investigator — Image-First Offline Design

Date: 2026-09-26
Status: Design approved in chat; implementation plan pending spec review

## 1. Goal

Build a fully local, isolated, read-only assistant for Elasticsearch/Kibana log investigation. The operator asks a natural-language question in Persian (for example, “How many national IDs had the same transaction debited twice since morning?”) and the system discovers the relevant indices, mappings, Kibana knowledge, and event semantics, executes safe read-only queries, validates the result, and returns an auditable answer without requiring the operator to provide index names, field names, or queries.

## 2. Non-negotiable constraints

- Entire runtime must operate in an isolated/offline environment.
- Image-first deployment: target host runs prebuilt container images; no application build on the target host.
- Minimal custom code.
- No agents/exporters/collectors installed on production servers.
- No Docker socket mount.
- No writes to Elasticsearch or Kibana.
- No new Kibana dashboards, saved objects, indices, mappings, alerts, or runtime configuration written back to Elastic.
- No cloud LLM/API dependency.
- Only pre-approved Elasticsearch index patterns are queryable.
- All privileged enforcement must exist below the LLM layer (Elastic RBAC + deterministic query guard).
- The target host only requires Linux, Docker Engine, and Docker Compose v2.

## 3. Four-image architecture

### Image 1 — Chat UI

Purpose: user-facing chat only.

Candidate: Open WebUI, version pinned.

Responsibilities:
- Local web chat UI.
- Authentication/session handling if required.
- Send user request to the Investigator endpoint.
- Show final answer, confidence, evidence summary, and optional technical details.

Must not have direct Elasticsearch credentials.

### Image 2 — Local LLM runtime

Purpose: inference only.

Candidate: Ollama, version pinned.

Initial model target:
- Qwen3 8B Instruct Q4 for the minimum viable deployment.
- Qwen3 14B Q4 preferred when approximately 32 GB RAM is available.

Responsibilities:
- Intent understanding.
- Investigation planning.
- Semantic field/event interpretation.
- Tool selection.
- Query repair reasoning.
- Natural-language answer generation.

The LLM never receives unrestricted Elasticsearch credentials and cannot bypass the Investigator guard.

### Image 3 — Elasticsearch MCP

Purpose: standardized read-only Elasticsearch tools.

Candidate: the pinned standalone Elasticsearch MCP server image compatible with the deployed Elastic version.

Responsibilities:
- list indices
- inspect mappings/field capabilities when supported
- search small samples
- execute ES|QL/search requests

Credentials are read-only and limited to approved index patterns.

### Image 4 — Investigator

Purpose: restore the stronger behavior of the original agentic design while keeping the project small and image-oriented.

This is the only custom image.

Preferred implementation: a very small Python service, using only the minimum libraries required for HTTP, MCP client/orchestration, configuration validation, and tests.

Responsibilities:
- Orchestrate the investigation loop.
- Read selected Kibana knowledge through read-only APIs.
- Build a local in-memory/on-disk catalog from existing Kibana data views, dashboards, saved searches, and visualization references.
- Perform schema/field discovery through Elasticsearch MCP.
- Run bounded probe queries before expensive queries.
- Detect suspicious zero/empty results when evidence suggests data exists.
- Allow the model to repair a query within strict iteration and cost limits.
- Cross-check final results with an independent second query when feasible.
- Apply deterministic policy enforcement before every Elasticsearch request.
- Redact or minimize PII before data is passed to the LLM whenever raw values are not required.
- Produce an audit record for each investigation.

The Investigator must remain thin. It is not a general observability platform, not a vector database, not a workflow engine, and not a replacement for Elasticsearch/Kibana.

## 4. Runtime flow

1. User submits a Persian question in Chat UI.
2. Investigator receives the question.
3. Investigator asks the local LLM to classify the intent and identify candidate concepts.
4. Investigator consults its read-only Kibana catalog for existing data views, saved searches, dashboards, visualizations, labels, and known fields relevant to those concepts.
5. Investigator queries Elasticsearch MCP for candidate indices/mappings/field capabilities.
6. Investigator permits only small bounded sample/probe searches.
7. LLM forms one or more hypotheses about field semantics and event relationships.
8. Investigator validates the proposed query against policy.
9. Query executes through the read-only Elasticsearch path.
10. If the result is an error, structurally inconsistent, or suspiciously empty, the LLM may repair the hypothesis/query within a fixed maximum number of attempts.
11. Investigator performs a second validation/cross-check where feasible.
12. Final answer is produced in Persian with confidence and evidence metadata.
13. Technical details remain available on demand: indices used, time range, fields selected, query text, validation steps, and counts.

## 5. Example investigation

User question:

“از صبح چند کد ملی داشتیم که بابت یک تراکنش دوبار از حسابشان برداشت شده؟”

Expected autonomous behavior:
- Resolve the user’s local ‘since morning’ time range.
- Find relevant payment/transaction data views or dashboards in Kibana.
- Discover candidate fields for national ID, account, transaction ID, amount, operation type, result, and timestamp.
- Inspect bounded samples to learn actual event values such as `DB`, `DEBIT`, or equivalent.
- Distinguish ‘two legitimate separate debits’ from ‘the same transaction debited twice’ using transaction/account/amount/event identity where the data supports it.
- Execute an aggregation/grouping query.
- Cross-check the duplicate population with an independent count or sample validation.
- Return the count and explain the criterion used.

The operator must not be asked to provide an index name, field name, or ES|QL query unless the underlying telemetry is genuinely ambiguous and cannot be resolved automatically.

## 6. Kibana use

Kibana is a knowledge source, not a write target.

Read-only information of interest:
- Data views and their index patterns.
- Saved searches.
- Dashboards and visualization references.
- Human-readable titles and labels.
- Existing filters/query fragments when readable from exported/read-only saved-object representations.

The Investigator may cache a normalized catalog locally to reduce repeated discovery. The cache is disposable and may be rebuilt from Kibana/Elasticsearch at any time.

No Kibana object is created, edited, imported, or deleted.

## 7. Security model

### Elastic RBAC

Use a dedicated account/API credential, for example `log-investigator-reader`, restricted to explicit approved index patterns.

Expected index privileges:
- `read`
- `view_index_metadata`

No cluster/index write privileges.

### Deterministic guard in Investigator

The guard must reject any operation not explicitly allowlisted.

Controls:
- Allowed index patterns only.
- Read/search/ES|QL only.
- Maximum time range per query.
- Maximum rows returned.
- Maximum sample size.
- Query timeout.
- Maximum investigation iterations.
- Maximum number of Elasticsearch calls per user request.
- Optional field denylist for sensitive PII.
- No arbitrary URL/tool execution by the LLM.

### Network

- Only Chat UI publishes a user-facing host port.
- Ollama, Elasticsearch MCP, and Investigator are on private Compose networks.
- No Docker socket mount.
- `no-new-privileges` and capability dropping are applied where compatible.
- Root filesystem is read-only where compatible; only explicit volumes are writable.
- Outbound network from the isolated host is not required for normal operation.

## 8. Offline/image-first delivery

Images and model assets are prepared on a connected staging machine, verified, exported, transferred to the isolated environment, and loaded locally.

Offline bundle target:

```text
devops-log-investigator-offline/
├── images/
│   ├── chat-ui.tar
│   ├── ollama.tar
│   ├── elasticsearch-mcp.tar
│   └── investigator.tar
├── models/
│   └── qwen3-8b-q4-or-approved-model/
├── config/
│   ├── compose.yaml
│   ├── .env.example
│   ├── policy.yaml
│   └── system-prompt.txt
├── scripts/
│   ├── install.sh
│   ├── start.sh
│   ├── stop.sh
│   ├── health.sh
│   └── uninstall.sh
└── docs/
    └── OFFLINE-INSTALL.md
```

Target-host install behavior:
- verify checksums
- `docker load` images
- import/copy local model assets
- validate configuration
- `docker compose up -d --pull never`
- run local health checks

No `docker pull`, package install, model download, npm/pip install, or source compilation on the target host.

## 9. Minimal-code principle

Do not build:
- custom frontend
- custom authentication unless required
- custom database server
- vector database
- LangChain/LangGraph stack unless a concrete limitation forces it later
- custom Elasticsearch client features already covered by MCP
- observability/monitoring infrastructure for this MVP

Investigator code should consist only of the orchestration, Kibana read-only catalog, deterministic guard, bounded audit trail, and tests that cannot be delegated safely to existing images.

## 10. Local state

Prefer a single small local SQLite file or equivalent file-backed store only if persistence materially improves discovery speed/auditability. If initial tests show it is unnecessary, run stateless and keep JSON audit logs on an explicit local volume.

No new Elasticsearch index will be created for application state.

## 11. Audit output

Every completed investigation should have a machine-readable record containing at least:
- request ID
- timestamp
- original user question
- resolved time window
- candidate/selected indices
- selected fields
- executed queries (or hashes plus secure detail storage if required)
- query attempts and repair reason
- result counts
- verification/cross-check status
- confidence level
- model identifier/version

Audit data stays local to the isolated deployment.

## 12. MVP acceptance tests

The system must answer the following without the operator providing index names, field names, or query syntax:

1. “از صبح چند خطای 500 داشتیم؟”
2. “کدام سرویس بیشترین timeout را داشته؟”
3. “از صبح چند کد ملی داشتیم که بابت یک تراکنش دوبار از حسابشان برداشت شده؟”

For each test, acceptance requires:
- autonomous discovery
- no Elastic/Kibana writes
- bounded query behavior
- final Persian answer
- inspectable technical evidence
- reproducible audit record

## 13. Failure behavior

The system must never fabricate a count when data semantics cannot be established reliably.

When evidence is insufficient, return a result such as:
- `DATA_NOT_VERIFIED`
- what was discovered
- what ambiguity remains
- what additional telemetry/semantic clue would be required

A zero result must not automatically be treated as valid when probes indicate relevant events exist.

## 14. Resource target

Initial CPU-only target:
- 8 vCPU
- 16 GB RAM for Qwen3 8B Q4 MVP
- SSD storage sized for images/model/cache/audit

Preferred CPU-only target for better reasoning headroom:
- 8–16 vCPU
- 32 GB RAM
- Qwen3 14B Q4

GPU is optional and primarily improves latency.

## 15. Explicitly deferred

Not in MVP:
- Prometheus/Grafana/Zabbix/Confluence connectors
- write actions
- alert creation
- automated remediation
- production server agents/exporters
- vector indexing of all logs
- full raw-log ingestion into the LLM
- multi-tenant authorization model

These may be considered only after the four-image Elasticsearch/Kibana investigation MVP passes acceptance tests.
