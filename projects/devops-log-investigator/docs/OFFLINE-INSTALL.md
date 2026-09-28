# Offline Installation Runbook

## 1. Connected staging host

Prerequisites on staging only:

- Linux
- Docker Engine and Docker Compose v2
- Internet/registry access for the pinned third-party images and local model download
- enough disk space for the exported four images and Ollama model store

Before building, edit `config/policy.yaml` to the real approved Elasticsearch index patterns.

Build the transferable bundle:

```bash
cd projects/devops-log-investigator
bash scripts/build-bundle.sh /srv/export/dli-bundle
```

The builder:

1. pulls the three pinned third-party images;
2. builds the single custom Investigator image;
3. downloads `qwen3:8b-q4_K_M` into a transferable Ollama store;
4. exports exactly four image tar files;
5. copies Compose/config/lifecycle scripts;
6. records image/model metadata;
7. creates `SHA256SUMS` for all transferable files.

Transfer the entire `dli-bundle/` directory to the isolated environment using the organization's approved offline-media process.

## 2. Prepare secrets on the isolated target

The target needs only Linux, Docker Engine and Docker Compose v2. It does not need Python, pip, Node.js, npm, Git, Ollama packages, source compilers, or Internet access.

Create the runtime environment file inside the transferred bundle:

```bash
cp /media/dli-bundle/runtime/.env.example /media/dli-bundle/runtime/.env
chmod 600 /media/dli-bundle/runtime/.env
```

Fill these locally:

- `WEBUI_SECRET_KEY`
- `INVESTIGATOR_INTERNAL_TOKEN`
- `ES_URL`
- `ES_API_KEY` — read-only, scoped to approved indices
- optional `KIBANA_URL` / `KIBANA_API_KEY` / `KIBANA_SPACE_ID`

Do not put real credentials into Git or the bundle built on a connected machine.

## 3. Install with the network disconnected

Recommended validation: disconnect/deny Internet egress before running the installer.

```bash
bash /media/dli-bundle/scripts/install-offline.sh /media/dli-bundle
```

Default install path:

```text
/opt/devops-log-investigator
```

Override only when required:

```bash
DLI_INSTALL_DIR=/opt/custom-path bash /media/dli-bundle/scripts/install-offline.sh /media/dli-bundle
```

The installer intentionally performs checks in this order:

1. confirm the four required image tar files exist;
2. verify every `SHA256SUMS` entry;
3. only then inspect Docker/Compose;
4. copy immutable runtime files;
5. reject placeholder secrets;
6. `docker load` exactly four images;
7. restore the prepared Ollama model store into `dli-ollama-data`;
8. validate Compose;
9. start with `--pull never`.

A missing image or checksum mismatch aborts before any Docker command is executed.

## 4. Runtime operations

```bash
bash /opt/devops-log-investigator/scripts/health.sh
bash /opt/devops-log-investigator/scripts/stop.sh
bash /opt/devops-log-investigator/scripts/start.sh
```

Only Open WebUI publishes a host port (`3000` by default). Ollama, MCP and Investigator remain on private Compose networks.

## 5. Required read-only boundary

The Elasticsearch credential used by `elastic-mcp` must not have write/manage privileges. Grant access only to the exact patterns present in `config/policy.yaml` and the metadata visibility required for mappings/field discovery.

The deterministic Investigator guard is a second boundary; it does not replace Elasticsearch RBAC.

Kibana is a knowledge source only. The code has no create/update/import/delete Saved Object methods. If Kibana is down, discovery continues with Elasticsearch and the audit should record the degraded condition.

## 6. Smoke-test checklist

After startup verify:

```bash
bash /opt/devops-log-investigator/scripts/health.sh
```

Then, from Open WebUI, confirm only the logical model `log-investigator` is presented for this deployment and test:

```text
از صبح چند خطای 500 داشتیم؟
کدام سرویس بیشترین timeout را داشته؟
از صبح چند کد ملی داشتیم که بابت یک تراکنش دوبار از حسابشان برداشت شده؟
```

For each result inspect technical metadata/audit and confirm the selected time range, indices, fields, queries and verification state match the real telemetry semantics.

A `DATA_NOT_VERIFIED` result is expected when telemetry semantics cannot be established safely. It must not be manually reclassified as zero without evidence.

## 7. Backup / restore local state

Persistent volumes:

- `dli-open-webui-data`
- `dli-ollama-data`
- `dli-investigator-audit`

Back up these volumes using the organization's standard Docker-volume backup process while services are stopped or with an application-consistent snapshot procedure.

The Ollama volume can also be reconstructed from the original offline bundle. Audit data cannot be reconstructed from Elasticsearch because the application intentionally never writes its audit trail there.

## 8. Upgrade procedure

Do not run `docker pull` on the isolated target.

Build a new complete bundle on connected staging, transfer it through the same approved process, verify checksums, load the new images/model assets, validate configuration, and restart with `--pull never`.

Keep the previous bundle until the new bundle passes the three acceptance questions and audit verification.
