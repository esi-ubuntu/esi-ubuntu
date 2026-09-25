# Market Intelligence Hub — Design Specification

**Date:** 2026-09-25  
**Project path:** `market-intelligence-hub/` inside `esi-ubuntu/esi-ubuntu`  
**Owner:** Personal project  
**Primary market:** Iran Stocks  
**Future market:** Crypto  
**Deployment target:** Self-hosted Ubuntu  
**UI:** Lightweight, no login in v1

## 1. Purpose

`market-intelligence-hub` is a lightweight, auditable coordination layer between two independent AI analysis stages:

1. **Scout** — Chat / GPT-5.6 Sol / High
2. **Auditor** — Work / Max

The repository is the shared source of truth between these stages. Scout discovers and ranks opportunities. Auditor independently validates, rejects, upgrades, or downgrades those candidates and produces the final report.

The project is not a trading engine, broker integration, tick database, or live market-data platform.

## 2. Core principles

- GitHub stores reports, prompts, schemas, fundamental state, generated indexes, UI source, and deployment config.
- GitHub does not store tick-by-tick data, full live order books, raw feeds, or large candle databases.
- Scout and Auditor are independent; Auditor can proceed if Scout is missing.
- Scout-owned historical files are immutable from the Auditor side.
- Core Fundamental Score changes only when new material fundamental evidence exists.
- Every fundamental change records previous score, new score, date, reason, and evidence.
- All schemas are market-agnostic so Crypto can be added later.

## 3. High-level flow

```text
Chat / GPT-5.6 Sol High
        |
        | 12:00 Tehran
        v
 Market Scout
        |
        | scout.json + scout.md
        v
GitHub: esi-ubuntu/esi-ubuntu/market-intelligence-hub
        |
        | matching REPORT_ID
        v
 Work / Max
 Final Auditor
        |
        | auditor.json + auditor.md + final.json
        v
GitHub
        |
        | Actions / self-hosted runner
        v
Ubuntu Server
        |
        v
Lightweight read-only UI
```

## 4. Report identity

Iran stock daily reports use:

```text
YYYY-MM-DD-IR-TSE-1200
```

The same `REPORT_ID` links Scout, Auditor, final UI data, and history.

## 5. Repository structure

```text
market-intelligence-hub/
├── docs/superpowers/specs/
├── docs/superpowers/plans/
├── prompts/
│   ├── iran-stock-scout.md
│   ├── iran-stock-auditor.md
│   └── shared-analysis-contract.md
├── schemas/
│   ├── scout-report.schema.json
│   ├── auditor-report.schema.json
│   ├── final-report.schema.json
│   └── fundamental-state.schema.json
├── reports/
│   ├── iran-stocks/YYYY-MM-DD/
│   └── crypto/
├── state/
│   ├── fundamentals/iran-stocks/
│   └── latest.json
├── generated/
│   ├── report-index.json
│   └── symbol-history.json
├── ui/
├── scripts/
├── .github/workflows/
└── README.md
```

## 6. Shared scoring contract

All scores use 0–100:

- `core_fundamental_score`
- `daily_valuation_score`
- `technical_score`
- `tape_score`
- `news_score`
- `daily_opportunity_score`

Daily Opportunity Score:

```text
Core Fundamental × 0.25
+ Daily Valuation × 0.15
+ Technical × 0.25
+ Tape × 0.20
+ News × 0.15
```

Labels:

- **Fundamental Gem:** Core Fundamental >= 80
- **Early Candidate:** Core Fundamental >= 70 plus multiple early-move indicators
- **Momentum Hunter:** Technical >= 75, Tape >= 75, R/R >= 2, no critical news risk
- **Prime Candidate:** Core Fundamental >= 70, Technical >= 70, Tape >= 65, R/R >= 2, no critical news risk
- **High Conviction:** Scout and Auditor independently agree on the same strong candidate

## 7. Scout responsibilities

Target: Saturday–Wednesday, 12:00 Tehran.

Scout assesses market condition, scans the Iran stock market, filters weak liquidity, evaluates price/volume/money-flow/tape/technical/news conditions, identifies key labels, returns at most 10 candidates, and writes structured plus human-readable reports.

Scout does not make the final decision.

## 8. Auditor responsibilities

Target: Saturday–Wednesday, approximately 12:05–12:10 Tehran.

Auditor loads the matching Scout report when available, validates material data independently, evaluates fundamentals, daily valuation, technicals, tape, news, catalysts, risk/reward, false positives, missed candidates, and produces 3–5 finalists plus final market action status.

Auditor classifies Scout candidates as `CONFIRMED`, `REJECTED`, `UPGRADED`, or `DOWNGRADED`.

## 9. Fundamental state

Each symbol has persistent state, e.g.:

```text
state/fundamentals/iran-stocks/FMLI.json
```

If there is no new material evidence, `fundamental_status = UNCHANGED` and the score is preserved.

## 10. Report contracts

### Scout

Must include schema version, report ID, market, generation timestamp, agent metadata, market status, candidates, top-five list, best category picks, and data-quality findings.

### Auditor

Must include schema version, report ID, market, generation timestamp, whether Scout was found, Scout validation results, missed candidates, finalists, final action state, and data-quality findings.

### Final

UI-optimized representation containing report identity, market/action state, top candidates, best category picks, key risks/catalysts, and timestamp.

## 11. Data quality

Use:

- `DATA_NOT_VERIFIED` when a material claim cannot be verified.
- `DATA_CONFLICT` when credible sources disagree.

Source priority:

1. TSETMC / official exchange sources
2. Codal
3. official company sources
4. reputable economic/news sources
5. secondary sources only for cross-checking

## 12. UI v1

No login. Read-only.

Dashboard shows market state, action state, report ID/time, category cards, ranking table, symbol detail, Scout-vs-Auditor comparison, entry/stop/targets/RR, catalysts, risk, and fundamental history.

Recommended stack: Vite + React + TypeScript + static JSON + Nginx, with no backend.

## 13. Generated indexes

Build scripts produce:

- `generated/report-index.json`
- `generated/symbol-history.json`

The UI does not scan the Git tree at runtime.

## 14. CI/CD

On relevant changes:

```text
Checkout
→ Validate JSON/schema rules
→ Build indexes
→ Run UI tests
→ Build Vite
→ Deploy through self-hosted runner
→ Health check
```

Deployment target is the user's Ubuntu server. No database migrations.

## 15. Validation rules

Before accepting reports:

1. JSON must parse.
2. Schema version must be supported.
3. REPORT_ID format must be valid.
4. Scores must remain in 0–100.
5. R/R must be numeric or explicitly unavailable.
6. Required evidence fields must be present.
7. Invalid label combinations must fail validation.
8. Scout cannot write Auditor-owned fields.
9. Auditor cannot overwrite Scout history.

## 16. Security

- Private repository is preferred.
- UI is read-only.
- No broker credentials.
- No API secrets committed to Git.
- Deployment values use GitHub secrets/environment config.
- Nginx/VPN/IP restriction can be added later if desired.

## 17. Explicit non-goals for v1

No brokerage integration, auto-ordering, live tick streaming, PostgreSQL, Redis, Kafka, WebSockets, multi-user RBAC, user accounts, alerting engine, portfolio execution, or market-data warehouse.

## 18. Crypto expansion

Crypto reuses the report contract, scores, UI, history, validation, and audit model. Crypto-specific prompts and later metrics such as funding, OI, liquidations, basis, exchange flows, dominance, and on-chain catalysts are added without restructuring the repo.

## 19. Failure handling

- Scout missing: Auditor proceeds independently.
- Auditor missing: UI marks Scout as provisional and final audit unavailable.
- Invalid Scout JSON: structured file is ignored; Markdown may be non-authoritative context only.
- Invalid final report: UI keeps the last valid final report.
- GitHub unavailable: deployed UI continues serving the last valid static data.

## 20. Versioning

All structured data includes `schema_version`, starting at `1.0`. Breaking schema changes increment the major version. Prompt files contain a prompt version header.

## 21. Success criteria

v1 is successful when Scout can write a valid report, Auditor can independently validate it and write a final report, Scout history stays immutable, fundamentals persist unless evidence changes, UI shows latest results/history/comparisons, CI rejects malformed reports, deployment is automated through the self-hosted runner, and Crypto can be added without restructuring.

## 22. v1 implementation boundary

Only:

- repository/project skeleton under `market-intelligence-hub/`
- schemas
- shared analysis contract
- Scout prompt
- Auditor prompt
- sample fixtures
- validators
- generated index builder
- lightweight UI
- GitHub Actions deployment
- Ubuntu static deployment

No additional services are introduced unless v1 proves them necessary.
