# AI DEVELOPMENT STATE
Last updated: 2026-09-09

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously on the existing Render coordinator with bounded heavy concurrency under the USD 30/month ceiling.

Research architecture includes the original 17 logical research workers plus continuous research-learning and experiment-factory roles from PR #104 and the bounded heavy experiment admission scheduler from PR #107. The scheduler prioritizes immutable predeclared research candidates without increasing total heavy concurrency or stealing the reserved ACC-002 lane.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Parallel ChatGPT development coordination exists through `AGENTS.md` / `docs/CHATGPT_SPECIALISTS.md`. The autonomous lead remains review-only with no automated merge authority to `main`.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, observability metric, supervisor status, diagnostic, incident fingerprint, canary result, risk-gate result, selective-precision result, research-memory lesson, experiment priority, saved market-consensus provenance, microstructure snapshot, residual-momentum challenger result, or shadow execution result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically search-breadth-weak, survivorship-unsafe, identity-incomplete, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real order capability without explicit user approval plus all canonical evidence gates.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress and false-discovery/search-breadth penalties. Prediction ledger is append-only with fixed `due_at`; forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

Evidence score is not probability. Never choose a production threshold by looking at untouched/forward outcomes and then treat that same evidence as confirmatory. Any future production selectivity change must be predeclared, restrictive-only, fingerprint-aware, and independently validated.

PR #116 prevents dense overlapping 15-minute forecast streams from inflating selective-precision confidence/readiness. Confidence/readiness use deterministic non-overlapping full-horizon rows reconstructed from immutable `due_at`, require `resolved_at >= due_at`, expose raw counts separately, and fail closed on malformed chronology.

PRs #122/#124 apply the same independence discipline to continuous research learning and experiment prioritization. PR #124 reconstructs forecast origin from immutable `due_at - declared horizon` because production intentionally has no `forecast_at`/`created_at` field; malformed/premature chronology remains excluded.

PR #123 completed future-only market-consensus provenance. New prediction-ledger rows freeze timestamped preforecast consensus context inside existing calibration JSON. Historical rows are never backfilled or fabricated, and agreement evidence has no trade/promotion authority.

PR #125 completed strategy-identity integrity hardening. Exact head `76818d665991d244b3f25df7b23829c94a32b225` passed Security and Reliability run `34318186208` (#951) and was squash-merged as `1f0cb1923b842861ac7a0d402ba594f1b67eb322`. Incomplete or unsupported strategy identities receive no valid fingerprint and are rejected before promotion/forward-proof lookup.

PR #131 completed a fresh current-main rebuild of the beta-neutral residual-momentum challenger. Exact head `67b867929bc88843f79deb482af08856761e5c0e` passed Security and Reliability run `34338587228` (#979) and was squash-merged as `86146125d31c42dd33cce1a913e461e92075954f`. The challenger remains research-only, uses forecast-time closes only, keeps future returns as labels, and opens untouched OOS only after fixed train/validation preconditions against the canonical control. Unit tests include future-price mutation/no-lookahead, finite bounded beta, and fail-closed untouched-OOS regressions. No accuracy or profitability improvement is claimed from implementation integrity alone.

PR #133 fixed a confirmed research-observability contract defect without changing strategy behavior. Exact head `7d3a3e20fc543444bd5d6dd99912a04f0416538b` passed Security and Reliability run `34341508345` (#988) and was squash-merged as `deb312d4721976c19deec533615eb8c4538ef0e4`. The ACC-002 producer emits bounded `selected_oos` evidence and `history_network.network_latency_ms`; the coordinator had been reading nonexistent legacy keys, causing successful worker runs to appear as unknown and network latency to remain hidden. The coordinator now consumes the producer-shaped contract, distinguishes blocked research from missing telemetry, and still exposes no trade/promotion authority.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS. Dedicated 24h/7d workers continue genuine chronological/OOS/robustness evidence generation. The beta-neutral residual-momentum challenger from PR #131 is now available as one predeclared research-only feature family; it has no production authority and requires real canonical evidence before any improvement claim. PR #133 restores visibility into whether each worker is genuinely blocked, opened untouched OOS, or produced a pass/fail result; it does not itself improve signal quality.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE, including regime gating, champion/challenger, data provenance, deterioration, robustness, genuine forward proof, portfolio/execution risk, size-aware execution, point-in-time universe safety, multiple-testing firewall, shadow champion/challenger, and chaos/failure gates.
- SELECTIVE PRECISION — research-only; non-overlapping full-horizon evidence required.
- CONTINUOUS RESEARCH LEARNING / EXPERIMENT FACTORY — research-only; independent full-horizon windows required before diagnostic readiness or experiment-priority sample sufficiency.
- FUTURE-ONLY INDEPENDENT AGREEMENT EVIDENCE — accumulating prospectively from PR #123; no historical backfill and no precision claim yet.
- KRAKEN PUBLIC-BOOK MICROSTRUCTURE — PR #129 integrated as prospective research-only measurement. It summarizes only genuine timestamped public snapshots and exposes spread, top-level/visible-depth imbalance, visible quote depth and microprice. Stale/future/crossed/one-sided/malformed/policy-invalid books fail closed. No historical reconstruction, hidden-liquidity inference, trade authority, promotion authority, or profitability/accuracy claim.
- BOUNDED HEAVY EXPERIMENT SCHEDULER — active without heavy-concurrency increase or trade/promotion authority.

## OPERATIONS / RELIABILITY
The earlier production persistence incident caused by nonexistent `prediction_ledger.created_at` was fixed in PR #98. Repeated post-fix `/scan` requests remain 200.

Continuous AI observer rate-limit backoff from PR #100 remains active and does not affect scan/health availability. Fresh post-PR #127 startup again showed the bounded `RateLimitError` path with `retry_in=600s` rather than a tight retry loop.

PR #127 rebuilt stale PR #118 directly from current main. Exact head `ac72113cf504bd7cb03c7596476d15bf6f537c07` passed Security and Reliability run `34320626916` (#960) and was squash-merged as `aa59e04317ea4f824c9e59fe27eb26dd1de67227`. The paper engine now suppresses only a new opposite-direction same-symbol entry across 24h/7d horizons; it does not close, mutate, reset, or rewrite existing paper positions. Same-direction cross-horizon agreement remains allowed. Invalid candidate symbol/direction fails closed. Stale PR #118 was closed as superseded.

PR #129 rebuilt stale PR #113 directly from current main. Exact head `a842bb3200bd62dda4f03ac104594820ffdd4594` passed Security and Reliability run `34326555109` (#969) and was squash-merged as `ff979ff61afa37409dec5bb5c78fdca2a2c716f4`. Stale PR #113 was closed as superseded. The module is broker-disconnected and research-only and does not change production signal thresholds, fingerprints, paper behavior, paid-data policy, worker concurrency, or any live-trading authority.

PR #131 rebuilt stale PR #115 directly from current main. Exact head `67b867929bc88843f79deb482af08856761e5c0e` passed Security and Reliability run `34338587228` (#979) and was squash-merged as `86146125d31c42dd33cce1a913e461e92075954f`. Stale PR #115 was closed as superseded. The new module is research-only and does not change production signal thresholds, fingerprints, broker status, paper behavior, paid-data policy, worker concurrency, or any live-trading authority.

PR #133 repaired coordinator-only observability for genuine ACC-002 worker evidence and deep-history network latency. Regression coverage uses the exact producer field names, checks both selected-OOS and fail-closed blocked evidence, and confirms raw bootstrap/sample arrays are not copied into bounded private logs. No research thresholds, OOS gates, worker allocation, execution behavior, paper state, broker state, or production signals changed.

Live verification after PR #133:
- exact merge `deb312d4721976c19deec533615eb8c4538ef0e4` auto-deployed successfully to the continuous coordinator and reached `live`;
- fresh application startup completed normally and the service became live;
- the first fresh observability cycles immediately restored real deep-history network latency telemetry (for example p50 about 4.03s and p95 about 6.14s on 9 fetches, then p50 about 3.93s and p95 about 6.50s on 22 fetches), proving the corrected producer/consumer network contract is active;
- fresh worker samples showed 0 failures/timeouts/restarts, supervisor healthy, no stale/crashed workers, and trade/promotion/signal authority false;
- the first observed post-deploy cycles had not yet completed a fresh 24h/7d ACC-002 worker on the new instance, so no ACC-002 pass/fail or blocked conclusion is recorded yet. Remain fail-closed until a genuine fresh summary appears.

Live verification after PR #129:
- exact merge `ff979ff61afa37409dec5bb5c78fdca2a2c716f4` auto-deployed successfully to both production and the continuous coordinator;
- both Render deploys reached `live`;
- production switched to the fresh instance and the service root returned 200 immediately after cutover; pre-cutover `/health` also returned 200;
- coordinator switched to the fresh instance and the service root returned 200; initial research observability was clean with supervisor healthy, 0 worker failures/timeouts/restarts, no stale/crashed workers, and trade/promotion/signal authority false; canary was correctly `warming` at zero fresh samples rather than claiming health prematurely.

Live verification after PR #127:
- exact merge `aa59e04317ea4f824c9e59fe27eb26dd1de67227` auto-deployed successfully to both production and the continuous coordinator;
- production application startup completed and `/health` returned 200 after cutover;
- coordinator application startup completed, then a fresh canary cycle reached `healthy` with rollback recommendation false;
- fresh coordinator observability showed 829 completed jobs, 0 worker failures, 0 timeouts, 0 task restarts, no stale/crashed workers, about 95.45% cache hits, and trade/promotion/signal authority false;
- immediately before PR #127, a production `/scan` completed 200 with two explicit symbol-level collection errors after a cross-exchange `HTTPStatusError`; those errors remained visible and fail-closed rather than fabricated away.

Cross-exchange batch collection can occasionally be unavailable. Never manufacture consensus/agreement or microstructure data when source evidence is unavailable.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. Authentic baseline is exactly `$100,000` from `2026-09-08T01:17:49Z`; never reset or rewrite it. Current account value = immutable starting capital plus realized/open P&L. Safety/execution gates may reject entries but never fabricate or reset history. Paper performance is evidence only.

PR #127 is a restrictive after-cost paper-risk improvement only. It removes deterministic self-cancelling gross exposure/duplicate transaction-cost behavior when 24h and 7d signals disagree on the same asset. No profitability or signal-accuracy improvement is claimed until genuine forward paper evidence resolves.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without approval.

Preserve stable exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, change market-data source behavior, or cherry-pick confidence thresholds merely to accelerate results.

## CURRENT OPEN DEVELOPMENT
Highest-value remaining specialist candidates must be refreshed from current main and rerun through fresh exact-head Security and Reliability before integration:
- PRs #120/#121 — coordination/autonomous cloud specialist runner work; review separately and preserve the $30/month ceiling and review-only/no-auto-merge safety model. PR #120 is currently stale/conflicting against current main; PR #121 is stacked on #120 and must not be merged as-is.
- stale PRs #105, #113, #114, #115, #117, #118 and #119 are superseded/closed or otherwise stale and must not be merged as-is.

## EXACT NEXT STEP
1. Inspect the first genuine fresh 24h and 7d ACC-002 worker summaries through the corrected PR #133 telemetry. Record whether research is blocked, whether untouched OOS opened, and any actual ACC-002/survivorship result. Do not convert missing or blocked evidence into a pass.
2. Run the PR #131 beta-neutral residual-momentum challenger only as a predeclared ACC-002 research experiment against the canonical control. Preserve the untouched-OOS seal unless fixed train/validation criteria pass, retain non-overlapping evaluation, cost stress, bootstrap robustness, point-in-time universe safety, multiple-testing accounting, and genuine forward proof. Do not tune beta-window/clipping after seeing OOS without declaring a new experiment.
3. Allow PR #129 prospective timestamped microstructure measurements to accumulate only from genuine available public-book snapshots. Do not reconstruct historical books or infer hidden liquidity. Before any production use, predeclare a research hypothesis and test whether spread/depth imbalance/microprice information improves after-cost 24h/7d OOS/forward results with multiple-testing and execution controls intact.
4. Let PR #123 future-only consensus provenance and PR #125 strategy fingerprints accumulate naturally. Do not backfill historical rows or claim improved precision/profitability until enough genuinely independent forward evidence resolves.
5. Continue ACC-002 genuine 24h/7d OOS/forward evidence and worker-health monitoring.
6. Monitor future paper cycles for `cross_horizon_symbol_conflict` suppression and compare genuine after-cost forward paper behavior without rewriting historical trades.
7. Review PRs #120/#121 separately for coordination value versus added complexity/cost; preserve no-auto-merge and the $30/month ceiling.
8. Preserve empty `live_promotions.json`, unused signing keys, broker-disconnected state, immutable $100k paper ledger, bounded heavy concurrency, and the USD 30/month ceiling.
9. Optimize after-cost risk-adjusted realized performance with abstention and tail protection, not headline accuracy.
