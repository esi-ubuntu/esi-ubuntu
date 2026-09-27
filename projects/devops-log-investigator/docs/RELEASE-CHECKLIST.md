# Release Checklist

- [ ] Latest `DevOps Log Investigator CI` run is green on a Docker-capable runner.
- [ ] `docker compose config` succeeds with target configuration.
- [ ] Investigator image builds successfully from the release commit.
- [ ] Connected staging builds the complete offline bundle and SHA256 verification passes.
- [ ] Target host is disconnected from registries/Internet before installation test.
- [ ] Four image tar files load successfully on the isolated target.
- [ ] `qwen3:8b-q4_K_M` appears in the restored Ollama model store.
- [ ] All four services start with `--pull never`.
- [ ] Only Open WebUI publishes a host port.
- [ ] Elasticsearch API credential has read-only/index-scoped privileges only.
- [ ] Kibana credential is read-only or Kibana integration is disabled.
- [ ] Real telemetry test: HTTP 500 count is manually cross-checked.
- [ ] Real telemetry test: timeout service ranking is manually cross-checked.
- [ ] Real telemetry test: duplicate-debit semantics/count are manually cross-checked.
- [ ] Audit record contains selected indices/fields/queries/verification state.
- [ ] A deliberately ambiguous question returns `DATA_NOT_VERIFIED` rather than a fabricated count.
