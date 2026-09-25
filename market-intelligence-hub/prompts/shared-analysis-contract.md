# Shared Analysis Contract

Prompt-Version: 1.0

## Identity
Iran-stock reports use `REPORT_ID = YYYY-MM-DD-IR-TSE-1200`.

## Source priority
1. TSETMC / official exchange sources
2. Codal
3. Official company sources
4. Reputable economic/news sources
5. Secondary sources for cross-check only

## Data quality
Use `DATA_NOT_VERIFIED` when a material claim cannot be validated and `DATA_CONFLICT` when credible sources disagree.

## Scores
All scores are 0..100.

Daily Opportunity Score = Core Fundamental × 0.25 + Daily Valuation × 0.15 + Technical × 0.25 + Tape × 0.20 + News × 0.15.

## Labels
- FUNDAMENTAL_GEM: core fundamental >= 80
- EARLY_CANDIDATE: core fundamental >= 70 plus multiple early-move signals
- MOMENTUM_HUNTER: technical >= 75, tape >= 75, R/R >= 2, no critical news risk
- PRIME_CANDIDATE: core fundamental >= 70, technical >= 70, tape >= 65, R/R >= 2, no critical news risk
- HIGH_CONVICTION: Scout and Auditor independently agree on a strong candidate

## Ownership
Scout may write only `scout.json` and `scout.md` for its report date. Auditor writes only `auditor.json`, `auditor.md`, and `final.json`. Auditor never overwrites Scout history.

## Fundamental stability
Core Fundamental Score changes only with new material evidence. A score change requires previous score, new score, change amount, date, reason, and non-empty evidence.
