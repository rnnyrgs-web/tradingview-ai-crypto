# AI DEVELOPMENT STATE
Last updated: 2026-09-09

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after every completed development/integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current runtime integration baseline after PR #151: `015e6f034c88f703995426406cbd345cf28c6e3b`.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Parallel specialist development uses `AGENTS.md`, `docs/CHATGPT_SPECIALISTS.md`, `orchestration/specialist_coordination.json`, and the cost-bounded autonomous specialist runner. Specialists may create isolated candidate work only. They may not auto-merge, write directly to main, connect a broker, increase recurring cost, or weaken canonical evidence gates.

PR #149 integrates `UNIVERSAL_SIGNAL_DEVELOPMENT_V1`, a machine-readable research objective and scorecard. The optimization target is genuine forward 24h/7d BUY/SELL/WAIT quality with positive after-cost expectancy, never headline historical accuracy. Worker outputs must trace to that objective or to evidence-validity/safety work.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, historical promotion, observability metric, diagnostic, research-memory lesson, experiment priority, market-consensus provenance, microstructure snapshot, residual-momentum result, shadow execution result, or paper result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, identity-incomplete, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical evidence gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace, or manufacture its history. Paper performance is evidence only.

## VALIDATION / RESEARCH MEMORY
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress and false-discovery/search-breadth penalties. Forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

PR #116 prevents overlapping 15-minute forecast streams from inflating selective-precision readiness. PRs #122/#124 apply the same independence discipline to learning and experiment prioritization, reconstructing forecast origin from immutable `due_at - declared horizon` because production intentionally has no forecast-created column.

PR #123 records future-only timestamped preforecast market-consensus provenance. Historical rows are never backfilled. PR #125 fails closed on incomplete/unsupported strategy identities. PR #129 adds prospective timestamp-safe Kraken public-book microstructure research only. PR #131 adds the beta-neutral residual-momentum challenger as research-only, with future prices as labels and untouched OOS protected.

PR #149 adds the canonical research-development contract:
- resolved errors generate falsifiable hypotheses rather than direct tuning;
- each experiment must declare predicted mechanism, horizon, expected signal-quality effect, evidence needed, falsification criteria, chronological/OOS requirements, realistic costs, and independent-sample requirements;
- heavy research remains capped at one slot and is ranked by `expected signal-quality impact × information/falsification value × probability of actionable evidence / compute/API cost`;
- repeated/disproven ideas receive a research-memory penalty rather than being blindly recycled;
- newly sealed research artifacts bind to `UNIVERSAL_SIGNAL_DEVELOPMENT_V1`, while legacy envelopes remain verifiable;
- historical/OOS and genuine-forward evidence remain separate and may not be pooled to inflate confidence;
- no experiment, scorecard, worker, or objective has trade/promotion authority.

No accuracy or profitability improvement is claimed from PR #149 itself. It improves evidence discipline and research allocation, not production signal thresholds.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — FAIL-CLOSED before untouched OOS because the second predeclared liquidity subset is not yet defensibly supported.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE, including regime gating, champion/challenger, provenance, deterioration, robustness, genuine forward proof, portfolio/execution risk, size-aware execution, point-in-time universe safety, multiple-testing firewall, shadow comparison and chaos/failure gates.
- SELECTIVE PRECISION — research-only; independent non-overlapping full-horizon evidence required.
- FUTURE-ONLY AGREEMENT EVIDENCE — accumulating naturally from PR #123; no backfill or precision claim.
- KRAKEN PUBLIC-BOOK MICROSTRUCTURE — prospective research-only measurement from PR #129; stale/future/crossed/one-sided/malformed books fail closed; no historical reconstruction or hidden-liquidity inference.
- BETA-NEUTRAL RESIDUAL MOMENTUM — PR #131 challenger only; cannot bypass ACC-002 or any canonical validation gate.
- UNIVERSAL SIGNAL-DEVELOPMENT / LEARNING LOOP — PR #149 active; research-only and information-gain aware.

### ACC-002 genuine bounded evidence
Post-PR #141 aggregate failure diagnostics now answer the prior blocker question without exposing symbol identities or raw samples:
- 24h: requested 30, resolved 24, supported subsets `[15]`, required coverage `0.80`, unresolved histories 6, `failure_type_counts={InsufficientHistory: 6}`.
- 7d: requested 30, resolved 16, supported subsets `[15]`, required coverage `0.80`, unresolved histories 14, `failure_type_counts={InsufficientHistory: 14}`.
- Both remain `insufficient_supported_liquidity_subsets`; untouched OOS remains unopened.

This is genuine natural history insufficiency, not a request/source outage and not a failed strategy result. Do not lower the 80% requirement, remove the two-subset requirement, substitute lower-ranked assets, shorten required history merely to pass, fabricate/backfill history, or repeatedly spend scarce research cycles re-diagnosing collection failures while the aggregate failure types remain purely `InsufficientHistory`.

PR #149 therefore marks ACC-002 as `BLOCKED_NATURAL_HISTORY_ACCUMULATION` and reduces its immediate actionable-evidence priority. Periodic re-checks are valid when coverage materially changes; otherwise allocate scarce heavy research to other falsifiable high-information signal-quality experiments.

## OPERATIONS / RELIABILITY
Prediction-ledger persistence issue from PR #98 remains fixed. Continuous observer rate-limit backoff from PR #100 remains bounded. Coordinator observability fixes #133/#135/#136 and aggregate cause classification #141 remain active.

PR #127 prevents new opposite-direction same-symbol 24h/7d paper entries from creating deterministic self-cancelling exposure and duplicate costs; existing paper history is untouched.

PR #147 (`6d23e70b8d87ffdcd469bc64546c8505df7f8e79`) integrated conservative Kraken Pro spot paper-execution assumptions and tests before PR #149. PR #149 was rebuilt on top of that exact main baseline, not on its stale predecessor.

PR #149 exact candidate head `3f28245707b303ddcce5b3a744c83c77fe65b9a6` passed Security and Reliability run `34365409917` (#1110), including unit tests, dependency vulnerability audit, static security scan and committed-secret scan, before squash merge as `87ddac3364452eeb5bdfc46262976f96c5e57af7`.

PR #151 fixed a confirmed coordinator-supervision false positive. With the default single general-heavy semaphore lane, logical workers can legitimately remain in `starting` while queued longer than the normal stale-heartbeat threshold; the prior supervisor therefore intermittently marked healthy queued workers stale and emitted rollback recommendations despite continued completions and zero worker failures/timeouts/restarts. Exact head `635af4f5f96aed418d0fcc902ae2bd3db5b88b70` passed Security and Reliability run `34374345543` (#1119) before squash merge as `015e6f034c88f703995426406cbd345cf28c6e3b`. `starting` queue wait is no longer treated as stale; running/resting/error workers remain heartbeat-supervised, crashed loop tasks remain fail-closed and independently restarted. No concurrency, cost, signal, broker, promotion, OOS, chronology or paper-ledger behavior changed.

Pre-#151 live evidence showed intermittent stale-worker rollback recommendations while completed jobs continued increasing with `worker_failed=0`, `worker_timeouts=0`, `task_restarts=0` and no crashed workers. The same live window also showed ACC-002 still fail-closed with aggregate failures exclusively `InsufficientHistory`; do not infer a signal-quality change from this reliability fix. Post-deployment canary evidence must be monitored prospectively before declaring the false-positive symptom eliminated in live operation.

Stale PR #142 was closed as superseded after #149 passed exact-head CI and merged. Temporary isolated-branch integration PR #148 was used only to place the change set onto the latest main baseline; it did not merge directly to main.

GitHub currently reports `main` branch protection disabled. Workflow-level exact-head/manual-review controls remain mandatory. Enable branch/ruleset protection for defense in depth when repository-admin access is available; do not weaken current controls in the meantime.

Cross-exchange/public-data collection may be unavailable at times. Never manufacture consensus, microstructure, history or agreement data when source evidence is unavailable.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, change source behavior, or cherry-pick thresholds merely to accelerate results.

## CURRENT OPEN DEVELOPMENT
Persistent specialist priorities live in `orchestration/specialist_coordination.json`. Specialists must follow current-main queue ownership/dependencies and may not use coordination state to bypass evidence gates.

PRs #120/#121/#141/#147/#149/#151 are integrated and must not be re-applied. PR #142 is closed/superseded. Old PRs #105, #34, #33 and #13 remain stale/non-mergeable and must not be merged as-is. PR #140 is stale against current main and must not be merged as-is. Any other open PR must be rechecked against current `main`, exact-head Security and Reliability, and current safety invariants before integration.

## EXACT NEXT STEP
1. Verify PR #151 prospectively in coordinator canary/observability: queued `starting` workers must no longer trigger stale-worker rollback recommendations, while genuinely stale running/resting/error or crashed workers must remain fail-closed. Do not weaken watchdog semantics to make the canary green.
2. Treat ACC-002 as a natural-history accumulation blocker while aggregate failures remain purely `InsufficientHistory`. Keep `minimum_subset_coverage=0.80`, the two-supported-subset requirement, Top-N ordering and untouched OOS unchanged. Re-check only when genuine coverage materially changes.
3. Use the PR #149 learning/experiment contract to inspect genuinely resolved independent prediction errors and select the highest-information READY challenger by expected after-cost signal-quality impact, falsification value, actionable-evidence probability, compute/API cost and overfitting risk. Do not repeat a prior disproven experiment unless its conditions materially changed.
4. Prefer restrictive hypotheses that can plausibly improve genuine signal quality after costs: stricter WAIT/abstention, regime conditioning, cross-sectional/residual information, calibration, execution/microstructure filtering, or a predeclared challenger. Every candidate must keep chronology, untouched OOS, multiple-testing, point-in-time universe, cost stress, robustness and genuine-forward proof intact.
5. Allow PR #129 microstructure and PR #123 future-only consensus evidence to accumulate naturally. Do not reconstruct historical order books, infer hidden liquidity, or backfill consensus.
6. Monitor the authentic paper ledger under the PR #147 Kraken execution model and PR #127 cross-horizon conflict suppression without rewriting history. Paper results remain evidence only.
7. Preserve empty `live_promotions.json`, unused signing keys, broker-disconnected state, immutable $100k paper ledger, bounded heavy concurrency and the USD 30/month ceiling.
8. Keep exact-head Security and Reliability/manual compatibility review mandatory for every merge. Enable GitHub main branch/ruleset protection separately when repository-admin access is available.
9. Optimize genuine after-cost risk-adjusted realized performance with abstention and tail protection, never headline accuracy alone.
