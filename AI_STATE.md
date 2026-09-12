# AI DEVELOPMENT STATE
Last updated: 2026-09-12

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

This document consolidates superseded historical status into current actionable state. Older PR chronology remains in Git history; durable negative results and safety invariants are preserved here to prevent accidental retry or weakening.

## PRIMARY OBJECTIVE
1. Maximize **genuine sustainable after-cost profitability** and expected dollars earned per unit of risk.
2. Then maximize genuine forward BUY/SELL precision/accuracy.

Headline accuracy, trade count, model count, worker count, or paper P&L are never objectives by themselves. Reject accuracy gains that reduce net profitability. Lower-hit-rate strategies are acceptable only when rigorous chronological evidence shows superior after-cost expectancy with controlled risk.

Research must account for realistic fees, spread, slippage, funding/carry, adverse selection, missed fills, market impact, liquidity, and drawdown/risk.

## CURRENT MAIN / SERVICES
Authoritative runtime baseline after PR #321: `a4471433a85d0a86a50dfd5e0d3bb40b6a2861c0`.

PR #321 exact head `fd045ed3b4eefd3110737176b86f1909951c77b5` passed Security and Reliability #2205 before expected-head merge. Its first head failed unit tests and was not merged; stale worker-binding and compatibility-test expectations were corrected without weakening safety behavior.

Primary production service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project: `dxgksvzibucwuzmppoqy`.
Recurring infrastructure ceiling: USD 30/month unless explicitly approved otherwise.

Both Render production and research-coordinator services reached `live` on PR #321 merge `a4471433a85d0a86a50dfd5e0d3bb40b6a2861c0`.

GitHub `main` branch protection remains disabled. Isolated branches, exact-head Security and Reliability, current-main compatibility review, expected-head merge protection, and post-deploy verification are mandatory operational controls.

## SAFETY INVARIANTS
No AI opinion, ranking, dashboard value, paper P&L, model count, ensemble weight, historical diagnostic, research-memory lesson, experiment priority, feature count, order-book snapshot, single OOS result, or single forward result may authorize live BUY/SELL by itself.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, persistence-unsafe, chronology-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Broker remains disconnected. Signing keys remain unused. Do not add credentials or real-order capability without explicit approval plus every canonical gate.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace, or manufacture its history. Paper performance is evidence only.

The USD 30/month recurring ceiling remains hard. No paid feed/service/compute and no physical-concurrency increase without explicit approval.

## SCIENTIFIC DISCIPLINE
- Chronological development -> validation -> untouched OOS separation is mandatory.
- Genuine forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.
- Never use lookahead/leakage, threshold mining, OOS reuse, survivorship substitution, retroactive enrichment, or fabricated evidence.
- Never pool historical/OOS observations with genuine forward observations to inflate confidence.
- Simultaneous cross-symbol crypto outcomes and overlapping forecasts are not automatically independent.
- Realistic fees, spread, slippage, funding/carry, adverse selection, missed fills and market impact remain mandatory.
- Untouched OOS remains sealed until predeclared validation admission passes.
- Point-in-time universe and source provenance are mandatory.
- Repeated/disproven hypotheses receive durable negative memory rather than blind recycling.
- Missing or malformed chronology/data fails closed.
- Research scheduling ranks expected incremental after-cost profitability first, then information gain / forward signal quality, compute cost, and overfitting/redundancy risk.
- Remove or deprioritize features and strategies that repeatedly fail falsification or add complexity without incremental economic value.
- Production WAIT may be studied using immutable research direction, but research cannot mutate production action.
- Every production or research rule change must remain fingerprint-safe and timestamp-defensible.

## DURABLE NEGATIVE RESULTS — DO NOT RESURRECT WITHOUT MATERIAL NEW CONDITIONS
### DATA-BASIS-001
Frozen exact-shared-timestamp OKX 1H mark/index basis was rejected under its current fingerprint after bounded chronological falsification. `orchestration/specialist_coordination.json` records:
- 24h OOS samples: 134
- 24h average net: approximately `-8.49 bps`
- 7d OOS samples: 19
- 7d average net: approximately `-51.21 bps`

Status: `REJECTED_CURRENT_FINGERPRINT`. Do not tune, rescue, reopen its untouched OOS, or retain it merely because the feature is available.

### DATA-FUNDING-001
Frozen timestamp-safe funding candidate was also rejected under its current fingerprint. Current durable evidence records:
- 24h incremental OOS expectancy versus frozen training-only baseline: `0.0 bps`
- 24h OOS halves: approximately `+91.54 bps` then `-4.40 bps`, demonstrating instability
- 7d OOS samples: 6, below the predeclared minimum of 8

Status: rejected. Do not tune, rescue, or resurrect the same fingerprint.

### FFriZz / historical OI source lessons
- Binance historical-OI acquisition from current Render is confirmed HTTP 451. A per-run circuit breaker may suppress redundant requests after one confirmed 451 but must not bypass the restriction.
- Bybit historical-OI accessibility from current Render was confirmed HTTP 403 under the bounded probe. Do not repeatedly re-probe unchanged access unless deployment/network environment, access policy, or endpoint contract materially changes.
- Do not proxy around or spoof geography.
- FFriZz V2 exact completed-candle-end = OI period-end matching is a durable negative timestamp-coverage result. Do not loosen exact matching to rescue it.
- FFriZz V3 causal-as-of alignment remains separate and is not alpha evidence. Preserve `<1H` staleness, no-future selection, no nearest-neighbour/interpolation, duplicate-OI rejection, and ambiguous endpoint-reuse rejection.
- Never silently substitute Binance and Bybit evidence or pool venue fingerprints.

## CURRENT RESEARCH GOVERNANCE
Persistent specialist priorities live in `orchestration/specialist_coordination.json`.
The profitability/accuracy roadmap lives in `orchestration/accuracy_profitability_roadmap.json`.
Active worker bindings live in `orchestration/signal_worker_bindings.json`.

PR #319 made scarce research allocation profitability-first. PR #320 made the central research director explicitly prioritize expected after-cost profitability impact, with signal quality/accuracy secondary. No profitability improvement was claimed from those control-plane changes.

PR #321 removed `basis-falsification-btc` / `basis_falsification_runner.py` from the always-on worker army because DATA-BASIS-001 and DATA-FUNDING-001 are already permanently rejected under their frozen fingerprints. The historical compatibility runner remains only for reproducible audit evidence and performs zero market-data requests/evaluation. It may not consume an always-on heavy research slot.

After #321 the active logical worker roster is 20 workers: 18 heavy and 2 lightweight. Physical heavy concurrency and the existing cost ceiling were not increased. The roadmap top-level objective is explicitly profitability-first, and active worker bindings no longer include the retired rejected-candidate process.

`COORD-DATA-005` is the next READY data-market task: select at most one genuinely new timestamp-safe profitability candidate materially distinct from rejected DATA-BASIS-001 and DATA-FUNDING-001, state its economic mechanism before testing, use a bounded free/public path or existing timestamp-safe data, and evaluate 24h and 7d separately with chronological non-overlapping evidence and realistic costs. Reject rather than tune if incremental after-cost evidence fails.

Do not retry unchanged Binance or Bybit historical-OI routes as the next candidate.

## ACC-002 / CROSS-ASSET STATUS
ACC-002 remains governed by existing fail-closed liquidity/history rules. Never lower `minimum_subset_coverage=0.80`, required supported-subset count, Top-N ordering, required history, chronology, or untouched-OOS rules merely to pass.

Fresh sampled live coordinator evidence immediately before PR #321 showed:
- 24h research was not blocked, with roughly 28–29/30 universe histories resolving and supported liquidity subsets `[15, 30]`; untouched OOS remained unopened.
- 7d remained blocked for `insufficient_supported_liquidity_subsets`, with roughly 19/30 histories resolving and remaining failures classified as `InsufficientHistory`; untouched OOS remained unopened.

Treat 7d natural-history insufficiency as low-priority recheck work, not a reason to weaken gates. Prefer currently data-ready 24h after-cost profitability research when expected information value is higher.

## LIVE OPERATIONS / FAIL-CLOSED EVIDENCE
Immediately before #321, the research coordinator was healthy with zero observed worker failures/timeouts, no stale/crashed workers, zero task restarts, and a healthy deployment canary. Production `/health` continued returning HTTP 200.

Current production paper decisions continue to fail closed when strategy review is missing, WAIT, direction-mismatched, or other actionability/risk evidence is insufficient. Do not reinterpret rejection volume as a reason to loosen gates.

FFriZz sampled cycles continued to show no unexpected WAIT-state drift. The Binance OI circuit-breaker remained in the intended single-attempt 451 shape. These are operational-integrity observations only, not profitability evidence.

The canonical FFriZz prospective prediction-ledger configuration blocker must be treated fail-closed whenever eligible persistence cannot be completed. Never commit secrets, substitute anonymous credentials for privileged research persistence, weaken RLS, or create an unauthenticated persistence bypass.

## PROFITABILITY / PAPER-EVIDENCE INTERPRETATION
Authentic paper results are small-sample evidence and must never be reset or overinterpreted. Separate 24h and 7d economics; do not pool horizons merely to improve an aggregate statistic.

Recent research found an economically interesting but still under-sampled 7d execution pattern: losing stop-outs showed materially worse measured entry slippage than measured target winners. Direction-aware microstructure research and incremental normal-execution baselines were added so this can be tested prospectively rather than converted into an overfit cutoff. No production slippage threshold is authorized from the small sample.

Any future claim of improved profitability requires genuine chronological/OOS/forward evidence after realistic costs and risk, not a code-path change or better research instrumentation.

## EXACT NEXT STEP
1. Re-read this file plus `orchestration/specialist_coordination.json` from current `main` before further development.
2. Prefer `COORD-DATA-005` or another clearly higher expected-profitability-impact falsifiable experiment only if it is genuinely new, timestamp-safe, and economically motivated before outcome inspection.
3. Keep 24h and 7d economics separate. Favor data-ready 24h mechanisms while 7d remains natural-history blocked unless material new evidence changes that ranking.
4. Diagnose losing trades and missed profitable opportunities into predeclared hypotheses: selective WAIT, economic calibration, regime conditioning, cross-sectional residual signals, execution/adverse-selection vetoes, feature removal, and strategy selection.
5. Require incremental after-cost value versus an appropriate frozen/normal baseline and reject weak or redundant candidates rather than tuning them to survive.
6. Keep `live_promotions.json` empty, broker disconnected, authentic paper ledger append-only, and recurring infrastructure <= USD 30/month.
7. Every integration remains isolated branch -> regression tests -> exact-head Security and Reliability green -> current-main compatibility -> expected-head merge -> AI_STATE synchronization -> post-deploy health verification when runtime code changes.

## CURRENT OPEN DEVELOPMENT / NEXT ACTIONS
At this state sync there are no known open development PRs after #321 integration other than this state synchronization itself. Preserve negative results, direction-aware microstructure logic, separate horizon baselines, and profitability-first experiment ranking. Reject any accuracy gain that reduces net expectancy, profit factor, or risk-adjusted return.

## LATEST INTEGRATION — PR #321
PR #321 is a research-efficiency/governance integration, not an alpha result.

It removed a retired compatibility process for already-rejected DATA-BASIS/DATA-FUNDING research from the always-on heavy/accuracy lane, removed obsolete active binding/recheck wiring, aligned the roadmap with profitability-first priority, and added regression coverage so the rejected candidate cannot silently re-enter the active worker army.

The first exact head failed unit tests because two tests/config bindings correctly still encoded the old compatibility-worker layout. Nothing was merged from that head. Those stale expectations were reconciled, and replacement exact head `fd045ed3b4eefd3110737176b86f1909951c77b5` passed Security and Reliability #2205 before expected-head merge as `a4471433a85d0a86a50dfd5e0d3bb40b6a2861c0`.

Both Render services reached `live` on the merge. No strategy threshold, strategy fingerprint, production action, broker state, paper history, live promotion, validation gate, execution/risk gate, physical concurrency, or recurring paid service changed. No profitability or accuracy improvement is claimed from #321; it removes wasted scheduling and reduces objective ambiguity so scarce research capacity is better aligned with genuine after-cost profitability.
