# Runtime Architecture

```text
User
  |
  v
Open WebUI (only published host port)
  |
  | OpenAI-compatible /v1/chat/completions
  v
Investigator (custom thin image)
  |---------------------> Ollama / Qwen3 local LLM
  |
  | guarded MCP calls
  v
Elasticsearch MCP 0.4.6
  |
  | read-only credential
  v
Existing Elasticsearch

Investigator ---- read-only metadata ----> Existing Kibana
```

The Investigator is the deterministic policy boundary. Open WebUI and the local LLM never receive Elasticsearch credentials. Kibana is used only as a discovery/knowledge source. Application audit data remains local and is never written to Elasticsearch.

Runtime contains exactly four container images. The isolated target performs no application build or dependency/model download.
