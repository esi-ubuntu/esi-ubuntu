# Market Intelligence Hub

Personal, read-only coordination hub for daily AI-assisted market analysis.

## v1 flow

```text
12:00 Tehran  Chat / GPT-5.6 Sol High (Scout)
      -> reports/iran-stocks/YYYY-MM-DD/scout.json + scout.md
12:05–12:10  Work / Max (Auditor)
      -> auditor.json + auditor.md + final.json
      -> generated indexes
      -> static read-only UI
```

The repository is analytical memory and an audit trail. It is **not** a tick database, trading engine, brokerage integration, or order-execution service.

## Ownership

Scout may write only:
- `reports/iran-stocks/YYYY-MM-DD/scout.json`
- `reports/iran-stocks/YYYY-MM-DD/scout.md`

Auditor may write only:
- `reports/iran-stocks/YYYY-MM-DD/auditor.json`
- `reports/iran-stocks/YYYY-MM-DD/auditor.md`
- `reports/iran-stocks/YYYY-MM-DD/final.json`

Auditor must never overwrite Scout history.

## Fundamental Core

Persistent symbol state belongs in `state/fundamentals/iran-stocks/<SYMBOL>.json`.
A Core Fundamental Score is stable. A changed score requires previous score, delta, date, reason, and non-empty material evidence. Daily price, RSI, money flow, or queue behavior alone cannot change it.

## Report identity
Iran-stock daily reports use `YYYY-MM-DD-IR-TSE-1200`.

## Prompts
- Scout: `prompts/iran-stock-scout.md`
- Auditor: `prompts/iran-stock-auditor.md`
- Shared contract: `prompts/shared-analysis-contract.md`

Use Scout in Chat High at 12:00 Tehran and Auditor in Work Max around 12:05–12:10. Both use the same report date and this GitHub repository.

## Verification
```bash
npm ci
npm test
node scripts/validate-reports.mjs
node scripts/build-index.mjs
node scripts/prepare-ui-data.mjs
npm ci --prefix ui
npm test --prefix ui
npm run build --prefix ui
bash -n scripts/deploy-ui.sh
```

`DATA_NOT_VERIFIED` and `DATA_CONFLICT` are explicit data-quality markers; material values must never be guessed.

## UI
v1 is a dependency-free static ESM dashboard served by Nginx. It is read-only and has no login/backend/database. It shows the latest final report when available and marks Scout-only output as provisional.

Default deploy target: `/var/www/market-intelligence-hub`.
Example Nginx config: `deploy/nginx-market-intelligence-hub.conf.example`.

## CI/CD
Workflow: `.github/workflows/market-intelligence-hub.yml`. Pull requests validate. Pushes to `main` additionally attempt deployment on `[self-hosted, linux, x64]`.
The self-hosted runner must be authorized for `esi-ubuntu/esi-ubuntu`.

## Adding Crypto later
Keep the Iran-stock contract unchanged. Add `market: "crypto"`, `reports/crypto/YYYY-MM-DD/...`, and crypto-specific prompts/metrics without restructuring Iran-stock history or the UI index model.
