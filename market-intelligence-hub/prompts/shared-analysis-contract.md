# Shared Analysis Contract

Prompt-Version: 1.2

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

## Run continuity — mandatory
A scheduled daily monitoring run must not be canceled merely because some sources, fields, symbols, indicators, or news items are unavailable.

- Continue the run with all verifiable data that is available.
- Mark unavailable material fields as `DATA_NOT_VERIFIED` and conflicting credible data as `DATA_CONFLICT`.
- Produce and persist a valid report even when the qualified-candidate list is empty.
- `NO QUALIFIED CANDIDATE` is a valid analytical result; a missing report is not.
- Only a true execution/persistence failure may prevent output. Such failure must be reported explicitly and must never be misrepresented as a successful run.
- Never fill a list with weak names merely to avoid an empty result.

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

## Fundamental state — source of truth
Core Fundamental is persistent state, not a daily calculation.

Canonical state path:
`state/fundamentals/iran-stocks/<SYMBOL>.json`

For every symbol considered by Scout or Auditor:
1. Read the symbol state file first if it exists.
2. Reuse the stored `core_fundamental_score`, component scores, evidence date, and baseline metadata exactly unless new material fundamental evidence has appeared after the state's last evidence timestamp.
3. Daily price action, tape, technical indicators, market mood, queue behavior, valuation movement caused only by price, or ordinary news must NEVER change Core Fundamental Score.
4. A Core Fundamental Score may change only because of new material fundamental evidence such as a new monthly operating report, quarterly/annual financial statement, material disclosure, major contract, verified selling-price change, material production change, margin change, feedstock/energy-cost change, capital-structure event, or structural industry change with direct company impact.
5. Any state change must record: previous score, new score, delta, timestamp/date, reason, source/evidence, affected components, and reviewer role.
6. If no new material evidence exists: `fundamental_status = UNCHANGED` and the stored score must be carried forward unchanged.
7. If no prior state exists: do NOT invent an `UNCHANGED` score. Either create an `INITIAL_BASELINE` only from sufficient verified fundamental evidence, or use `DATA_NOT_VERIFIED` until a valid baseline is established.
8. The daily Scout report is not itself the source of truth for fundamental state. Historical daily reports must not silently redefine the fundamental baseline.
9. Auditor may update the canonical fundamental state only when it has verified new material evidence and has documented the required change record. Scout should flag `Fundamental Review Required = YES` rather than casually rewriting the baseline.

## Fundamental stability invariant
Absent verified new material fundamental evidence, today’s Core Fundamental Score for a symbol MUST equal the canonical stored score. A different score without a documented state transition is a validation failure.
