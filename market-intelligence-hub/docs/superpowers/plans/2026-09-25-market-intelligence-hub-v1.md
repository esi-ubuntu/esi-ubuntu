# Market Intelligence Hub v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working `market-intelligence-hub` inside `esi-ubuntu/esi-ubuntu`, with schema-validated Scout/Auditor reports, persistent fundamental state, generated report indexes, a lightweight read-only UI, and self-hosted Ubuntu deployment automation.

**Architecture:** GitHub is the durable coordination and audit layer. Scout writes its own daily report files; Auditor reads the matching report when available, validates independently, writes separate final files, and never mutates Scout history. The UI consumes generated static JSON only; there is no backend or database in v1.

**Tech Stack:** JSON Schema, Node.js 20+, Ajv, JavaScript/ES modules for repository tooling, Vite + React + TypeScript for the UI, Vitest/React Testing Library for UI tests, GitHub Actions, self-hosted Ubuntu runner, Nginx static hosting.

**Spec:** `market-intelligence-hub/docs/superpowers/specs/2026-09-25-market-intelligence-hub-design.md`

## Global Constraints

- Keep the root profile `README.md` untouched; all project files live under `market-intelligence-hub/`.
- v1 has no login, database, backend API, Redis, Kafka, WebSocket, brokerage integration, or automatic order execution.
- All report scores are integers or numbers in the inclusive range 0–100.
- Iran-stock `REPORT_ID` format is `YYYY-MM-DD-IR-TSE-1200`.
- Scout and Auditor outputs are separate and append-only by date; Auditor must never overwrite Scout history.
- Core Fundamental Score changes only when new material fundamental evidence is recorded.
- UI is read-only and consumes generated static JSON.
- Secrets and deployment-specific values must not be committed.
- Structured documents start at `schema_version: "1.0"`.
- Design report contracts so `market: "crypto"` can be added later without restructuring.

## Review Focus

1. **Malformed or partially valid report JSON:** validation must fail deterministically and identify the file and schema rule.
2. **Scout/Auditor ownership violations:** a Scout payload containing Auditor-only fields, or an Auditor process attempting to replace Scout history, must be rejected.
3. **Missing daily stages:** index generation must tolerate Scout-only days and expose final-audit availability explicitly instead of crashing.
4. **Fundamental score drift without evidence:** state validation must reject a changed Core Fundamental Score when change metadata/evidence is absent.
5. **No valid current final report:** UI data selection must fall back to the latest valid deployed report and clearly mark provisional/missing final audit when applicable.

---

### Task 1: Project foundation, shared contract, and JSON Schemas

**Files:**
- Create: `market-intelligence-hub/README.md`
- Create: `market-intelligence-hub/package.json`
- Create: `market-intelligence-hub/prompts/shared-analysis-contract.md`
- Create: `market-intelligence-hub/schemas/common.schema.json`
- Create: `market-intelligence-hub/schemas/scout-report.schema.json`
- Create: `market-intelligence-hub/schemas/auditor-report.schema.json`
- Create: `market-intelligence-hub/schemas/final-report.schema.json`
- Create: `market-intelligence-hub/schemas/fundamental-state.schema.json`
- Create: `market-intelligence-hub/fixtures/valid/scout.json`
- Create: `market-intelligence-hub/fixtures/valid/auditor.json`
- Create: `market-intelligence-hub/fixtures/valid/final.json`
- Create: `market-intelligence-hub/fixtures/valid/fundamental.json`
- Test: `market-intelligence-hub/tests/schema-contract.test.mjs`

**Interfaces:**
- Produces: canonical field names, label enums, score range rules, report ID pattern, and four schema `$id` values consumed by all later tasks.

- [ ] **Step 1: Write failing schema-contract tests** asserting the four schema files exist, expose version `1.0`, require market/report identity fields where applicable, constrain scores to 0–100, and reject an invalid Iran-stock `REPORT_ID`.
- [ ] **Step 2: Run `npm test -- tests/schema-contract.test.mjs`** and verify failure because project/schema files do not yet exist.
- [ ] **Step 3: Add the root project package and canonical shared-analysis contract** with the agreed scoring formula, labels, source hierarchy, data-quality markers, and agent ownership rules.
- [ ] **Step 4: Implement the four JSON Schemas** using shared `$defs` from `common.schema.json`; prohibit unknown top-level ownership fields where practical.
- [ ] **Step 5: Add one minimal valid fixture for each schema.**
- [ ] **Step 6: Run the schema-contract test and verify PASS.**
- [ ] **Step 7: Commit** with `feat: define market intelligence report contracts`.

### Task 2: Report validator and ownership/fundamental invariants

**Files:**
- Create: `market-intelligence-hub/scripts/lib/schema-loader.mjs`
- Create: `market-intelligence-hub/scripts/lib/validation.mjs`
- Create: `market-intelligence-hub/scripts/validate-reports.mjs`
- Create: `market-intelligence-hub/fixtures/invalid/scout-with-auditor-fields.json`
- Create: `market-intelligence-hub/fixtures/invalid/fundamental-change-without-evidence.json`
- Test: `market-intelligence-hub/tests/validation.test.mjs`

**Interfaces:**
- Produces: `validateDocument(kind, value) -> { valid, errors }`, `validateFundamentalTransition(previous, next) -> { valid, errors }`, and CLI exit code `0` on success / non-zero on invalid input.

- [ ] **Step 1: Write failing validation tests** for a valid Scout report, malformed score >100, ownership violation, invalid report ID, and fundamental score change without reason/evidence.
- [ ] **Step 2: Run `npm test -- tests/validation.test.mjs`** and verify expected failures.
- [ ] **Step 3: Implement schema loading and Ajv-based document validation.**
- [ ] **Step 4: Implement transition validation** that permits unchanged Core Fundamental state without change evidence but requires previous score, change amount, reason, date, and non-empty evidence whenever the score changes.
- [ ] **Step 5: Implement the CLI** to validate explicit files or the repository's `reports/` and `state/` trees and print file-scoped errors.
- [ ] **Step 6: Run validation tests and the CLI against valid fixtures; verify PASS/exit 0.**
- [ ] **Step 7: Run the CLI against invalid fixtures; verify non-zero exit and actionable diagnostics.**
- [ ] **Step 8: Commit** with `feat: validate analytical reports and fundamental state`.

### Task 3: Report index and symbol-history generator

**Files:**
- Create: `market-intelligence-hub/scripts/lib/report-loader.mjs`
- Create: `market-intelligence-hub/scripts/build-index.mjs`
- Create: `market-intelligence-hub/generated/report-index.json`
- Create: `market-intelligence-hub/generated/symbol-history.json`
- Create: `market-intelligence-hub/fixtures/reports/2026-09-24/scout.json`
- Create: `market-intelligence-hub/fixtures/reports/2026-09-25/scout.json`
- Create: `market-intelligence-hub/fixtures/reports/2026-09-25/auditor.json`
- Create: `market-intelligence-hub/fixtures/reports/2026-09-25/final.json`
- Test: `market-intelligence-hub/tests/build-index.test.mjs`

**Interfaces:**
- Produces: `buildReportIndex(reportRoot)`, `buildSymbolHistory(reportRoot)`, and deterministic static JSON outputs consumed by the UI.

- [ ] **Step 1: Write failing index tests** for chronological report ordering, Scout-only day handling, latest-final selection, and symbol history across multiple days.
- [ ] **Step 2: Run the index test and verify failure because generator functions do not exist.**
- [ ] **Step 3: Implement validated report loading** that skips invalid files with diagnostics rather than poisoning the generated index.
- [ ] **Step 4: Implement `buildReportIndex`** with explicit `scout_available`, `audit_available`, `final_available`, paths, date, report ID, and latest-valid-final metadata.
- [ ] **Step 5: Implement `buildSymbolHistory`** with daily score/label snapshots and fundamental-change markers.
- [ ] **Step 6: Run tests and verify PASS, including Scout-only days.**
- [ ] **Step 7: Generate committed empty/fixture-safe initial index files.**
- [ ] **Step 8: Commit** with `feat: generate report and symbol history indexes`.

### Task 4: Production Scout and Auditor prompt contracts

**Files:**
- Create: `market-intelligence-hub/prompts/iran-stock-scout.md`
- Create: `market-intelligence-hub/prompts/iran-stock-auditor.md`
- Test: `market-intelligence-hub/tests/prompt-contract.test.mjs`

**Interfaces:**
- Consumes: canonical schema field names and scoring rules from Task 1.
- Produces: versioned Chat High and Work Max prompts that require JSON + Markdown outputs at exact repository paths.

- [ ] **Step 1: Write failing prompt-contract tests** asserting each prompt contains Prompt-Version, REPORT_ID rule, repository output path, data-quality markers, and its allowed ownership boundary.
- [ ] **Step 2: Run the prompt-contract test and verify failure because prompts do not exist.**
- [ ] **Step 3: Add the Scout prompt** with full-market screening, technical/tape/news scan, stable Fundamental Core behavior, maximum candidate limits, and exact `reports/iran-stocks/YYYY-MM-DD/scout.{json,md}` output contract.
- [ ] **Step 4: Add the Auditor prompt** with independent validation, Scout comparison, missed-candidate search, final ranking, conflict handling, and exact Auditor/final output paths.
- [ ] **Step 5: Require both prompts to validate output against schema semantics before writing and to never overwrite the other agent's files.**
- [ ] **Step 6: Run prompt-contract tests and verify PASS.**
- [ ] **Step 7: Commit** with `feat: add scout and auditor production prompts`.

### Task 5: Lightweight UI data layer and dashboard

**Files:**
- Create: `market-intelligence-hub/ui/package.json`
- Create: `market-intelligence-hub/ui/vite.config.ts`
- Create: `market-intelligence-hub/ui/tsconfig.json`
- Create: `market-intelligence-hub/ui/index.html`
- Create: `market-intelligence-hub/ui/src/main.tsx`
- Create: `market-intelligence-hub/ui/src/App.tsx`
- Create: `market-intelligence-hub/ui/src/types.ts`
- Create: `market-intelligence-hub/ui/src/data.ts`
- Create: `market-intelligence-hub/ui/src/components/MarketHeader.tsx`
- Create: `market-intelligence-hub/ui/src/components/CandidateCards.tsx`
- Create: `market-intelligence-hub/ui/src/components/RankingTable.tsx`
- Create: `market-intelligence-hub/ui/src/components/SymbolDetail.tsx`
- Create: `market-intelligence-hub/ui/src/components/SymbolHistory.tsx`
- Create: `market-intelligence-hub/ui/src/app.css`
- Test: `market-intelligence-hub/ui/src/App.test.tsx`
- Test: `market-intelligence-hub/ui/src/data.test.ts`

**Interfaces:**
- Consumes: `generated/report-index.json`, `generated/symbol-history.json`, and `reports/.../final.json` copied into the Vite public asset tree at build time.
- Produces: a read-only single-page dashboard with report state, category cards, ranking table, Scout-vs-Auditor state, symbol details, and history.

- [ ] **Step 1: Write failing data-layer tests** for latest-valid-final selection and provisional Scout fallback when final audit is unavailable.
- [ ] **Step 2: Write a failing UI test** asserting market/action status, ranking table, and provisional-audit badge render from fixture data.
- [ ] **Step 3: Run UI tests and verify expected failures.**
- [ ] **Step 4: Implement typed static-data loading and fallback logic.**
- [ ] **Step 5: Implement the dashboard components** with responsive layout and no mutation/network write capability.
- [ ] **Step 6: Add symbol detail/history rendering**, including Fundamental Core history and Scout/Auditor comparison state.
- [ ] **Step 7: Run UI unit tests and verify PASS.**
- [ ] **Step 8: Run `npm run build` in `ui/` and verify Vite production build succeeds.**
- [ ] **Step 9: Commit** with `feat: add read-only market intelligence dashboard`.

### Task 6: Static asset preparation and deployment automation

**Files:**
- Create: `market-intelligence-hub/scripts/prepare-ui-data.mjs`
- Create: `market-intelligence-hub/scripts/deploy-ui.sh`
- Create: `market-intelligence-hub/deploy/nginx-market-intelligence-hub.conf.example`
- Create: `market-intelligence-hub/.github/workflows/validate-and-deploy.yml`
- Test: `market-intelligence-hub/tests/prepare-ui-data.test.mjs`

**Interfaces:**
- Produces: deterministic copy of latest generated/report assets into `ui/public/data/`; deployment script accepts `MIH_DEPLOY_DIR`; workflow validates before build/deploy.

- [ ] **Step 1: Write failing preparation tests** proving only validated generated/report assets are copied and stale output is removed.
- [ ] **Step 2: Run preparation test and verify failure because the script does not exist.**
- [ ] **Step 3: Implement `prepare-ui-data.mjs`** to rebuild indexes, validate inputs, and populate `ui/public/data/` deterministically.
- [ ] **Step 4: Implement `deploy-ui.sh`** with `set -euo pipefail`, required build-dir checks, atomic-ish staged copy, configurable `MIH_DEPLOY_DIR`, and no secret logging.
- [ ] **Step 5: Add Nginx example configuration** for SPA/static JSON serving; do not mutate system Nginx automatically.
- [ ] **Step 6: Add GitHub Actions workflow**: checkout → Node setup → install → validate → test → prepare data → UI build → self-hosted deploy → HTTP/local health check when configured.
- [ ] **Step 7: Run preparation tests and shell syntax checks; verify PASS.**
- [ ] **Step 8: Commit** with `ci: validate build and deploy market intelligence ui`.

### Task 7: End-to-end fixtures, documentation, and final verification

**Files:**
- Create: `market-intelligence-hub/reports/iran-stocks/.gitkeep`
- Create: `market-intelligence-hub/state/fundamentals/iran-stocks/.gitkeep`
- Modify: `market-intelligence-hub/README.md`
- Test: existing full test suite

**Interfaces:**
- Consumes: all prior tasks.
- Produces: documented operational workflow for Chat Scout → GitHub → Work Auditor → generated indexes → UI deployment.

- [ ] **Step 1: Add an end-to-end fixture flow** that validates Scout → Auditor → Final and regenerates indexes without errors.
- [ ] **Step 2: Document exact daily write paths, ownership rules, scheduled times, local validation commands, and Ubuntu deployment prerequisites.**
- [ ] **Step 3: Document how to add Crypto later without changing the Iran-stock schema contract.**
- [ ] **Step 4: Run root tests, validator, index generation, UI tests, and UI production build.**
- [ ] **Step 5: Verify no file outside `market-intelligence-hub/` changed except intentional repository metadata; specifically verify root profile README is unchanged.**
- [ ] **Step 6: Review the branch diff against the design spec and fix any uncovered requirement.**
- [ ] **Step 7: Commit** with `docs: finalize market intelligence hub v1 workflow`.

## Final acceptance commands

From `market-intelligence-hub/`:

```bash
npm ci
npm test
node scripts/validate-reports.mjs
node scripts/build-index.mjs
node scripts/prepare-ui-data.mjs
npm ci --prefix ui
npm test --prefix ui -- --run
npm run build --prefix ui
bash -n scripts/deploy-ui.sh
```

Acceptance requires all commands to exit `0`, schemas and indexes to be deterministic, root profile README to remain unchanged, and the built UI to render the latest valid final report or an explicit provisional Scout state when no audit exists.
