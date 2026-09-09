# AI DEVELOPMENT STATE
Last updated: 2026-09-09

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after every completed development/integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current runtime integration baseline after PR #165: `581121bd2585e4bfdee82b9b7685b74320e44afd`.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

PR #149 established `UNIVERSAL_SIGNAL_DEVELOPMENT_V1`: optimize genuine forward 24h/7d BUY/SELL/WAIT quality and positive after-cost expectancy, never headline historical accuracy.

PR #160 added the research-only Autonomous Research Director on the live coordinator: deterministic mission IDs, blocker-aware scheduling, claim/lease primitives, duplicate-suppression visibility, and a `/director` endpoint. It has no trade/promotion/deployment authority.

PR #161 added a bounded OpenAI API governor targeting about USD 1/day with a USD 29/month internal allowance plus buffer under the USD 30 hard cap, routine Luna usage, Sol disabled in the bounded lane, and a 3x prospective-call reserve. Paid API work must be information-dense and may not bypass evidence gates.

PR #162 added 32 continuously running token-free logical research specialists using one shared immutable-ledger read per refresh, zero normal-operation AI calls, and no increase to heavy research concurrency.

PR #163 connected scope-safe specialist diagnoses into the existing quant-science experiment queue. Asset-specific or conjunctive hypotheses remain deferred unless an evaluator can preserve the original scope. No validation/OOS/promotion gate was weakened.

PR #164 added a strict massive-research firewall: huge virtual idea spaces may not increase physical heavy concurrency; each hypothesis gets one predeclared search and one candidate mutation; parameter mining, untouched-OOS reuse, OOS/forward pooling, paid-compute escalation and production authority are forbidden; multiple-testing, independent replication, genuine-forward replication and duplicate-hypothesis penalties remain mandatory.

PR #165 expanded the token-free logical specialist factory from 32 to 256 active deterministic specialists per refresh using a fixed predeclared lattice slice. The virtual namespace is metadata only; materialized workers still share one ledger read, make zero normal-operation AI calls, do not raise the one-slot heavy experiment concurrency, and have no trade, promotion or strategy-mutation authority.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, order-book snapshot, paper P&L, ensemble weight, single OOS result, historical promotion, diagnostic, research-memory lesson, experiment priority, consensus provenance, microstructure result, adaptive-accuracy result, specialist result, virtual-lattice result, shadow execution result, or paper result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, identity-incomplete, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical evidence gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace, or manufacture its history. Paper performance is evidence only.

## VALIDATION / RESEARCH MEMORY
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress and false-discovery/search-breadth penalties. Forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

PR #116 prevents overlapping 15-minute forecast streams from inflating selective-precision readiness. PRs #122/#124 apply the same independence discipline to learning and experiment prioritization. PR #123 records future-only preforecast market-consensus provenance; no historical backfill. PR #125 fails closed on incomplete strategy identities. PR #129 adds prospective timestamp-safe Kraken public-book microstructure research only. PR #131 adds beta-neutral residual momentum as a challenger only.

PR #155 added predeclared scientific methods, primary/secondary/guardrail endpoints, minimum effects, one-search budgets, no-parameter-mining/no-OOS-reuse/no-OOS-forward-pooling rules and bounded hypothesis breadth. PR #158 made supported restrictive abstention hypotheses executable development -> validation -> conditionally opened untouched OOS. Continuation requires at least 2 percentage points absolute precision lift, positive after-cost expectancy, minimum evaluation samples and minimum actionable coverage. Conclusive results enter bounded research memory; exact repeats are deferred until materially more independent evidence exists or the mechanism changes.

No accuracy or profitability improvement is claimed from research-process PRs themselves. Any signal-quality claim still requires genuine independent evidence through the canonical chain.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — FAIL-CLOSED before untouched OOS because the second predeclared liquidity subset is not yet defensibly supported.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE.
- SELECTIVE PRECISION — research-only; independent non-overlapping full-horizon evidence required.
- FUTURE-ONLY AGREEMENT EVIDENCE — accumulating naturally from PR #123; no backfill or precision claim.
- KRAKEN PUBLIC-BOOK MICROSTRUCTURE — prospective research-only measurement from PR #129.
- BETA-NEUTRAL RESIDUAL MOMENTUM — PR #131 challenger only.
- QUANT-SCIENCE / ADAPTIVE ACCURACY — active research-only lane with bounded research memory.
- TOKEN-FREE SPECIALIST FACTORY — 256 active deterministic logical specialists after PR #165; one shared ledger read per refresh, zero normal-operation AI calls, one heavy experiment slot unchanged.

### ACC-002 bounded evidence
The blocker remains natural history unless aggregate failure classes materially change. Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history merely to pass, fabricate/backfill history, or repeatedly spend scarce research cycles re-diagnosing pure `InsufficientHistory` outcomes.

Last authoritative bounded sample before the later specialist-factory integrations:
- 24h: requested 30, resolved 27, supported subsets `[15]`, required coverage `0.80`, failed histories 3, `failure_type_counts={InsufficientHistory: 3}`.
- 7d: requested 30, resolved 17, supported subsets `[15]`, required coverage `0.80`, failed histories 13, `failure_type_counts={InsufficientHistory: 13}`.
- Both remained `insufficient_supported_liquidity_subsets`; untouched OOS remained unopened.

PR #158 gives pure ACC-002 `InsufficientHistory` outcomes a bounded six-hour recheck. Mixed request/source/software failure classes must not receive that exemption.

## OPERATIONS / RELIABILITY
Prediction-ledger persistence, rate-limit backoff, coordinator observability, queue-state supervision, conflict suppression and conservative Kraken paper-execution marking fixes remain active. Existing paper history is append-only.

PR #165 exact candidate head `1067e7c79443fbe532fa36e7e922529d83d5eafb` passed Security and Reliability run #1238 before squash merge as `581121bd2585e4bfdee82b9b7685b74320e44afd`.

Immediately after merge, Render coordinator deployment `dep-dagqn69srm7s73abh6k0` for `581121bd...` reached `live` successfully. This is deployment evidence only, not a signal-quality or profitability claim.

No `adaptive-accuracy` application log lines were observed in the queried 2026-09-09 12:00Z–19:00Z coordinator log window. This does not prove the worker is inactive because the worker may not emit that literal label; inspect coordinator state/output artifacts directly before drawing a research conclusion.

GitHub still reports `main` branch protection disabled. Workflow-level exact-head/manual-review controls remain mandatory. Enable branch/ruleset protection for defense in depth when repository-admin access is available.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

The 256 logical specialists do not authorize more physical heavy concurrency. Heavy experiment concurrency remains exactly one slot. The virtual hypothesis address space is not evidence and must not be materialized beyond the bounded deterministic slice merely to increase search breadth.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, change source behavior, or cherry-pick thresholds merely to accelerate results.

## CURRENT OPEN DEVELOPMENT
PRs #120/#121/#141/#147/#149/#151/#153/#155/#157/#158/#160/#161/#162/#163/#164/#165 are integrated and must not be re-applied. PR #142 is closed/superseded. Old PRs #105, #34, #33 and #13 remain stale/non-mergeable and must not be merged as-is. PR #140 is stale against current main and must not be merged as-is. Any other open PR must be rechecked against current `main`, exact-head Security and Reliability, current safety invariants and current research-firewall constraints before integration.

## EXACT NEXT STEP
1. Inspect the live coordinator state/output for the first completed `adaptive-accuracy` experiment. Confirm hypothesis discovery used development rows only, the hypothesis was frozen before validation, and `oos_opened` is false unless every predeclared continuation gate passed.
2. Verify pure ACC-002 `InsufficientHistory` outcomes actually receive the six-hour recheck delay while adaptive-accuracy continues to receive the shared accuracy lane. Mixed source/software failures must remain immediately visible and fail closed.
3. Audit the first live 256-specialist refresh: exactly 256 logical specialists, one shared ledger read, zero normal-operation AI calls, no heavy-concurrency increase, and no trade/promotion/strategy-mutation authority. Treat their outputs as diagnostics/hypotheses only.
4. Confirm the PR #163 bridge admits only hypotheses whose scope can be preserved by the current evaluator; defer asset-specific/conjunctive hypotheses until a dedicated evaluator exists.
5. Feed conclusive adaptive results into bounded research memory and prevent consumed/disproven hypotheses from immediate repetition without materially more independent evidence or a changed mechanism.
6. Expand executable science one method at a time only with a defensible evaluator. Highest-value candidates remain regime-conditioned WAIT/abstention, calibration/selective precision, strategy-deterioration suppression, and execution/microstructure filters using timestamp-safe prospective data.
7. Keep ACC-002 fail-closed while aggregate failures remain natural-history blockers; keep 80% coverage, two-supported-subset, Top-N ordering and untouched-OOS requirements unchanged.
8. Allow PR #129 microstructure and PR #123 consensus evidence to accumulate naturally. Never reconstruct historical order books, infer hidden liquidity, or backfill consensus.
9. Monitor the authentic paper ledger without rewriting history. Paper results remain evidence only.
10. Preserve empty `live_promotions.json`, unused signing keys, broker-disconnected state, immutable $100k paper ledger, bounded heavy concurrency and the USD 30/month ceiling. Optimize genuine after-cost risk-adjusted realized performance with selective abstention and tail protection, never headline accuracy alone.
