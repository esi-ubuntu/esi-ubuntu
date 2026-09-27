# Verification Status

Last updated: 2026-09-27

## Verified locally during implementation

- Deterministic read-only policy tests.
- PII redaction and local JSONL audit tests.
- Kibana degraded-mode/catalog tests.
- Ollama and MCP adapter tests.
- Investigation loop tests for HTTP 500 count, timeout ranking, duplicate debit, suspicious-zero repair and DATA_NOT_VERIFIED.
- OpenAI-compatible API tests.
- Four-service Compose structural tests.
- Offline bundle/checksum/no-pull tests.
- Three end-to-end Persian acceptance scenarios with no user-supplied index or field names.
- Shell syntax validation and Python compile validation.
- Elastic MCP compatibility contract tests against the documented v0.4.6 tool schemas: list_indices(index_pattern), get_mappings(index), search(index, fields, query_body), esql(query).
- Compatibility patch tests: safe index discovery pattern injection, result filtering, search translation/capping, MCP content normalization, and ES|QL LOOKUP JOIN/ENRICH rejection.

## Independently verified against current upstream documentation

- `mcp==2.2.0` exists as the current stable MCP Python SDK release line.
- Elasticsearch MCP 0.4.6 supports streamable HTTP with `/mcp` on port 8080 and `/ping` health endpoint.
- `qwen3:8b-q4_K_M` is a real Ollama model tag suitable for the default local profile.
- Open WebUI 0.11.4 provides the reduced slim image intended for external model/services.

## Not yet verified

The following require a Docker-capable staging/self-hosted environment and must not be treated as complete until the queued GitHub Actions run or an equivalent staging run succeeds:

- `docker compose config` against the exact branch HEAD.
- Building the Investigator Docker image from the branch HEAD.
- Pulling/exporting all three pinned third-party images with `build-bundle.sh`.
- Loading the four image tar files on a network-isolated target.
- Starting all four containers together with `--pull never`.
- Real connection to the organization's Elasticsearch/Kibana using read-only credentials.
- Real Qwen tool-calling quality against the organization's actual schemas and business event semantics.

## Release gate

Do not merge/deploy as production-ready until:

1. the full CI job succeeds on a Docker-capable runner;
2. the offline bundle is built on connected staging;
3. a network-isolated smoke test starts the four-container stack;
4. the three acceptance questions are run against approved real telemetry and their queries/answers are manually verified once;
5. Elasticsearch/Kibana credentials are confirmed read-only and index-scoped.
