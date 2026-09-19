# AI_STATE.md

Last reconciled: 2026-09-19T06:15Z

This is the compact canonical handoff for `rnnyrgs-web/tradingview-ai-crypto`. On every run, verify actual `main` SHA first, then read `UNIFIED_PROFITABILITY_LEAD_SPEC.md`, `AGENTS.md`, `orchestration/strategy_discovery_queue.json`, `orchestration/rejected_fingerprints.json`, specialist coordination plus all override layers, `orchestration/model_routing_policy.json`, current Big-Move/Money Intelligence evidence, open PRs, latest Strategy Discovery Supervisor snapshot, relevant autonomous-worker state, and exact-head CI. GitHub/persistent machine-readable state outranks chat memory.

## PRIMARY OBJECTIVE

Find and rigorously validate one algorithmic strategy with sustainable positive after-cost expectancy and useful frequency, while independently improving scientifically defensible 90-day large-upside / 2x-candidate intelligence. Do not call backtests real profit and do not manufacture a 2x forecast.

Exactly one candidate may consume expensive deep-validation capacity at a time. Cheap predeclared screening may reject many candidates. Failure means explain -> preserve evidence -> learn -> pivot -> continue. A waiting or blocked lane must not stop independent useful work that cannot contaminate protected evidence.

## CURRENT CANONICAL STRATEGY STATE

- No validated profitable strategy exists.
- Discovery lifecycle: **SELECTION**.
- `active_deep_candidate`: **null**.
- There is currently **no scientifically actionable `CHEAP_SCREEN_READY` strategy candidate** after the DATA-004 source-resolution result.
- `DISC-SQUEEZE-RETENTION-001-v1` is **BLOCKED_DATA_CONTRACT**, not strategy-rejected.
- `DISC-RESIDUAL-MOMENTUM-001-v1` remains **DEPRIORITIZED_EVIDENCE_LIMITED** because the current-survivor universe prevents promotion-grade point-in-time interpretation.
- `DISC-FRIZZ-PLAYBIT-EMA-001-v1` remains **BLOCKED_SOURCE_FINGERPRINT**; never approximate it or silently substitute existing FFRIZZ logic.
- Untouched OOS for all unresolved candidates remains **LOCKED / unopened**.
- Broker/live authority: **OFF**; research/paper/shadow only.
- Combined variable paid-project ceiling: approximately **$30/month total** unless the user explicitly changes it.

## DATA-004 RESULT — SQUEEZE/RETENTION SOURCE RESOLUTION

`COORD-DISC-DATA-004` is **DONE** via PR #431. The exact result is **`TERMINAL_NO_ZERO_COST_TIMESTAMP_SAFE_SOURCE` for the current frozen data contract and approved access**, not a strategy rejection and not evidence that the squeeze/retention economic mechanism is false.

Frozen scope:
- venue/market semantics: Binance USDⓈ-M;
- instruments: BTCUSDT / ETHUSDT / SOLUSDT;
- required families: liquidations / open_interest / mark_price;
- historical interval: `2025-07-01T00:00:00Z` inclusive through `2026-09-01T00:00:00Z` exclusive;
- strategy outcomes inspected: **false**;
- untouched OOS opened: **false**;
- new paid source authorized: **false**.

What was learned:
- the bounded DATA-003 sample proved individual CryptoHFTData objects can exist and be validated, but did not prove complete historical inventory or publication chronology;
- complete CryptoHFTData prefix/inventory enumeration requires dashboard-generated temporary S3 credentials under the current access path, so anonymous exact-path probing cannot prove the full historical contract;
- Binance zero-cost alternatives do not provide an equivalent historical forced-liquidation family for the frozen contract;
- public liquidation broadcasts remain lower-bound observations and cannot be silently treated as complete liquidation notional;
- missing liquidation objects may not be converted to zero events;
- no venue/instrument substitution or outcome-driven proxy was used.

Canonical evidence:
- PR #431 exact head: `503cbc5402bd0096b327c8aae9481633c354373f`;
- exact-head Security & Reliability run `35424497257`: **SUCCESS**;
- verified merge commit: `c51a59dbac604a2e0b2eefa2b68ae025d4c5b0e3`;
- post-merge Security & Reliability run `35425911144`: **SUCCESS**;
- source-resolution artifact: `research_data/squeeze_preflight/data004_source_resolution.json`.

Reopen `DISC-SQUEEZE-RETENTION-001-v1` only if the documented DATA-004 reopen conditions are satisfied by materially improved timestamp-safe source access. Do not rescue it with another venue, current snapshots, inferred missing liquidation flow, or post-hoc proxying.

## CURRENT SPECIALIST EXECUTION QUEUE

Canonical coordination must be loaded through `orchestration/coordination_overrides.py`, which applies the historical override ledger and the Lead reconciliation layer. Do **not** read only the base JSON.

Current strategy-discovery execution state:
- `COORD-DISC-DATA-004` — **DONE**: current squeeze-retention data path terminally blocked under current approved zero-new-cost access.
- `COORD-DISC-QUANT-003` — **BLOCKED**: do not screen or proxy-rescue the data-blocked squeeze fingerprint.
- `COORD-DISC-VAL-003` — **BLOCKED**: preserve its pre-outcome design, but do not spend additional candidate-specific validation capacity until the data contract reopens or a new candidate is frozen.
- `COORD-DISC-TEST-003` — **BLOCKED FOR DUPLICATION AVOIDANCE** while generic discovery-firewall hardening PR #432 awaits independent Lead review; the remaining candidate-specific audit waits for a new executable contract.
- `COORD-DISC-QUANT-004` — **READY** and is the next strategy-discovery action: freeze one materially distinct hypothesis with a demonstrably timestamp-safe available-data path before any returns are inspected.

`COORD-DISC-QUANT-004` must:
- choose a genuinely different economic mechanism rather than tuning/rescuing a rejected or blocked exact fingerprint;
- use data families already demonstrably available under current approved access;
- freeze market/venue, instruments, timeframe, signal definition, entry, exit, hold, no-trade rules, chronology, train/validation split, untouched-OOS boundary, benchmark, realistic costs/stress, sample floors, search breadth and multiple-testing treatment **before** outcome inspection;
- state an economic mechanism and explicit falsification rule;
- preserve durable rejected-fingerprint memory and evidence-limited lanes;
- either add exactly one highest-ranked `CHEAP_SCREEN_READY` candidate with the complete frozen contract or persist a precise reason why none is defensible yet.

## DURABLE NEGATIVE MEMORY

Do not rescue rejected exact fingerprints without materially new data or a genuinely different frozen scientific/economic hypothesis. Rejected exact fingerprints include at least:
- `ACC-002`;
- `DATA-BASIS-001`;
- `DATA-FUNDING-001`;
- `DISC-VOL-BREAKOUT-001-v1`;
- `DISC-LIQUIDITY-MEANREV-001-v1`.

The volatility-breakout and liquidity-shock mean-reversion failures remain durable pre-OOS rejections; untouched OOS stayed locked. `DISC-SQUEEZE-RETENTION-001-v1` is **not** in this rejected registry because the mechanism was never tested: its required data contract failed first.

## 90-DAY BIG-MOVE / MONEY INTELLIGENCE LANE

Big-Move Intelligence and Money Intelligence remain independent hypothesis/evidence generators when they cannot contaminate protected strategy evidence.

Rules:
- study historical roughly-2x-within-90-days events and other large moves against outcome-blind matched pre-event controls;
- use point-in-time-safe universes and covariates where possible;
- optimize for top-ranked precision/lift, PR-AUC/calibration, realized forward returns, tradability and regime stability rather than raw accuracy;
- label OBSERVED FACT / INFERENCE / HYPOTHESIS / FORECAST / UNKNOWN;
- preserve failed precursors and never rewrite them after outcomes;
- never retroactively call an already-moved asset an early prediction;
- only produce a ranked Big-Move Evidence Profile when current evidence is strong enough to support it.

Current truth: there is **no promotion-grade 90-day 2x candidate**. Latest Money Intelligence evidence remains hypothesis-generation evidence, not a frozen forecast.

PR #433 is **OPEN / NOT CANONICAL** and therefore must not be described as deployed functionality. It implements a DEVELOPMENT-only deterministic 2x-within-90d event/matched-control lab with explicit censoring and outcome-blind control construction. Its exact head `bc68d0c3d6aefe01bd67170539d8caaa7b047f63` passed Security & Reliability run `35425535682`. Independent Lead review is still required before merge; even if merged, infrastructure alone is not market evidence and does not create a current 2x candidate.

## OTHER OPEN RESEARCH-INTEGRITY WORK

PR #432 is **OPEN / NOT MERGED**. It hardens strategy-discovery public boundaries so rejected fingerprints, unsafe policy flags, or multiple deep candidates cannot bypass loader validation. Its existence does not complete candidate-specific TEST-003 and does not create profitability evidence. Avoid duplicate worker execution while it awaits independent Lead review.

The latest Strategy Discovery Supervisor snapshot before DATA-004 completion still ranked squeeze-retention because it was generated from earlier canonical state. After this reconciliation, the supervisor should show no actionable cheap screen until QUANT-004 freezes a new candidate. A stale snapshot must not override newer merged state.

## PRESERVED DATA-BREADTH HANDOFF

- `COORD-DATA-005`: **DONE** — breadth evaluator integrated; historical point-in-time history unavailable.
- `COORD-DATA-006`: **DONE** — prospective point-in-time capture verified; no fabricated historical backfill.
- `COORD-DATA-007`: **BLOCKED** — wait for enough genuinely matured independent prospective cohorts.

Do not select another DATA-BREADTH candidate while `COORD-DATA-007` remains blocked on genuine prospective maturation. This legacy breadth maturation wait does not block strategy discovery.

## COST / INFRASTRUCTURE / MODEL ROUTING

- Obey `orchestration/model_routing_policy.json`.
- Deterministic Python/GitHub Actions first when possible.
- API routing uses GPT-5.6 Luna/Terra/Sol only within approved budgets.
- GPT-6 Astra belongs to ChatGPT Work/Codex, not the OpenAI API; never claim an API Astra run.
- One autonomous cloud specialist model run at a time; branch-isolated; cannot merge itself or trade.
- Do not add OpenAI/Anthropic spend merely to relay work between sessions.
- Supabase Pro is approved by the user, but egress/query/window/throttling safeguards from PRs #413/#414 remain mandatory; do not reintroduce unbounded resolved-ledger polling or broad repeated reads.

## SAFETY / SCIENTIFIC INVARIANTS

- Broker disconnected; no real-order authority or fund transfer.
- Do not rewrite historical predictions, frozen OOS, genuine-forward evidence, or rejected fingerprints.
- Isolated branches only for code/state changes.
- Exact-head **Security & Reliability** must pass before merge.
- Runtime-affecting changes also require actual deployed-SHA verification.
- Missing/stale/malformed/future/ambiguous/provenance-uncertain evidence fails closed to WAIT / RESEARCH_ONLY.
- Never weaken chronology, purging, non-overlap, point-in-time universe safety, realistic costs, robustness, multiple-testing controls, or promotion gates to obtain a pass.
- One attractive backtest/OOS result grants no production or live authority.
- If frozen rigorous criteria genuinely pass, report the success clearly with exact evidence and limitations.

## EXACT NEXT STEP

Execute **`COORD-DISC-QUANT-004`**: freeze the next materially distinct strategy hypothesis that can be tested using a timestamp-defensible data path already available under approved access, without inspecting candidate returns while choosing the contract. Only after that contract is frozen may the deterministic cheap screen run.

Independent Big-Move/Money Intelligence work may continue in parallel when it cannot contaminate protected strategy evidence. PR #433 may be independently reviewed/integrated on its own evidence, but it is not a substitute for selecting a testable strategy candidate.

## STATUS VOCABULARY

Do not conflate IMPLEMENTED / TESTED / MERGED / DEPLOYED / BACKTESTED / OOS TESTED / ROBUSTNESS TESTED / CROSS-ENGINE VERIFIED / FORWARD TESTED / LIVE TESTED / VALIDATED PROFITABLE.

Current truth: **no validated profitable strategy, no promotion-grade 90-day 2x candidate, no active deep candidate, squeeze-retention scientifically data-blocked before outcomes, untouched OOS locked, broker/live authority off.**
