# AI DEVELOPMENT STATE
Last updated: 2026-09-09

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after every completed development/integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current runtime integration baseline after PR #158: `11555f75a24cf4c54074cfdafdc9d23c9c86b697`.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Parallel specialist development uses `AGENTS.md`, `docs/CHATGPT_SPECIALISTS.md`, `orchestration/specialist_coordination.json`, and the cost-bounded autonomous specialist runner. Specialists may create isolated candidate work only. They may not auto-merge, write directly to main, connect a broker, increase recurring cost, or weaken canonical evidence gates.

PR #149 integrates `UNIVERSAL_SIGNAL_DEVELOPMENT_V1`, a machine-readable research objective and scorecard. The optimization target is genuine forward 24h/7d BUY/SELL/WAIT quality with positive after-cost expectancy, never headline historical accuracy. Worker outputs must trace to that objective or to evidence-validity/safety work.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, historical promotion, observability metric, diagnostic, research-memory lesson, experiment priority, market-consensus provenance, microstructure snapshot, residual-momentum result, adaptive-accuracy result, shadow execution result, or paper result by itself may authorize live BUY/SELL.

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
- heavy research is ranked by `expected signal-quality impact × information/falsification value × probability of actionable evidence / compute/API cost`;
- repeated/disproven ideas receive a research-memory penalty rather than being blindly recycled;
- newly sealed research artifacts bind to `UNIVERSAL_SIGNAL_DEVELOPMENT_V1`, while legacy envelopes remain verifiable;
- historical/OOS and genuine-forward evidence remain separate and may not be pooled to inflate confidence;
- no experiment, scorecard, worker, or objective has trade/promotion authority.

PR #155 extends that loop with a deterministic quant-science factory. Resolved-error hypotheses receive a predeclared scientific method, primary/secondary/guardrail endpoints, a minimum effect to continue, a one-search predeclared budget, explicit no-parameter-mining/no-OOS-reuse/no-OOS-forward-pooling rules, and bounded per-method hypothesis breadth. The heavy experiment scheduler defers natural-history/prospective-evidence blockers and prefers restrictive abstention-first science when priorities tie.

PR #158 turns the factory from ranking-only into a bounded executable research loop for supported restrictive hypotheses:
- hypothesis discovery uses development data only;
- fixed hypotheses are frozen before validation;
- untouched OOS outcomes remain sealed unless the predeclared validation gate passes;
- initial executable methods are restrictive group-abstention experiments for score band, market regime, direction and strategy identity;
- horizon calibration remains design-only until a dedicated executor is implemented;
- continuation requires at least 2 percentage points absolute precision lift, positive after-cost expectancy, minimum evaluation samples and minimum actionable coverage;
- conclusive validation/OOS outcomes enter bounded research memory, and exact repeated hypotheses are deferred until materially more independent evidence exists;
- no OOS result is reused as fresh confirmation, and genuine-forward evidence remains separate.

No accuracy or profitability improvement is claimed from PR #149, #155 or #158 themselves. They improve evidence discipline, experiment execution and research allocation. Any signal-quality claim still requires genuine independent evidence through the canonical chain.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — FAIL-CLOSED before untouched OOS because the second predeclared liquidity subset is not yet defensibly supported.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE, including regime gating, champion/challenger, provenance, deterioration, robustness, genuine forward proof, portfolio/execution risk, size-aware execution, point-in-time universe safety, multiple-testing firewall, shadow comparison and chaos/failure gates.
- SELECTIVE PRECISION — research-only; independent non-overlapping full-horizon evidence required.
- FUTURE-ONLY AGREEMENT EVIDENCE — accumulating naturally from PR #123; no backfill or precision claim.
- KRAKEN PUBLIC-BOOK MICROSTRUCTURE — prospective research-only measurement from PR #129; stale/future/crossed/one-sided/malformed books fail closed; no historical reconstruction or hidden-liquidity inference.
- BETA-NEUTRAL RESIDUAL MOMENTUM — PR #131 challenger only; cannot bypass any canonical validation gate.
- UNIVERSAL SIGNAL-DEVELOPMENT / LEARNING LOOP — PR #149 active; research-only and information-gain aware.
- QUANT-SCIENCE RESEARCH FACTORY — PR #155 active; predeclared science design, bounded hypothesis breadth and blocker-aware scheduling.
- ADAPTIVE ACCURACY EXPERIMENT LANE — PR #158 active; supported restrictive hypotheses can now be evaluated development -> validation -> conditionally opened untouched OOS, with conclusive evidence remembered and no production authority.

### ACC-002 genuine bounded evidence
The underlying blocker remains natural history, not a source outage or failed strategy result. Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history merely to pass, fabricate/backfill history, or repeatedly spend scarce research cycles re-diagnosing collection failures while aggregate failure types remain purely `InsufficientHistory`.

Latest post-PR #158 live coordinator evidence:
- 24h: requested 30, resolved 27, supported subsets `[15]`, required coverage `0.80`, failed histories 3, `failure_type_counts={InsufficientHistory: 3}`.
- 7d: requested 30, resolved 17, supported subsets `[15]`, required coverage `0.80`, failed histories 13, `failure_type_counts={InsufficientHistory: 13}`.
- Both remain `insufficient_supported_liquidity_subsets`; untouched OOS remains unopened.

PR #158 therefore gives pure ACC-002 `InsufficientHistory` outcomes a bounded six-hour recheck instead of immediate repeat cycles. Mixed request/source/software failure classes do not receive that exemption. The existing one-slot accuracy lane is now shared with `adaptive-accuracy`; total heavy concurrency is unchanged.

## OPERATIONS / RELIABILITY
Prediction-ledger persistence issue from PR #98 remains fixed. Continuous observer rate-limit backoff from PR #100 remains bounded. Coordinator observability fixes #133/#135/#136 and aggregate cause classification #141 remain active.

PR #127 prevents new opposite-direction same-symbol 24h/7d paper entries from creating deterministic self-cancelling exposure and duplicate costs; existing paper history is untouched.

PR #147 integrated conservative Kraken Pro spot paper-execution assumptions. PR #157 (`3e5deb99533cf32bfadf6e9c776dcd48f3f8bcdb`) fixes paper P&L marking when a stable-quoted pair lacks a direct Kraken book by using the validated Kraken USD bridge path; paper history remains authentic and append-only.

PR #151 fixed initial queued-worker stale false positives. PR #153 completes the queue-state supervision fix: every bounded semaphore wait is explicitly `queued`; only `starting` and `queued` waits are exempt from heartbeat staleness, while `running`, `resting`, `error_backoff`, `crashed`, and crashed loop tasks remain fail-closed. PR #153 exact head `0f504ca7b66745a3c8288be9ceef068b18a30ce2` passed Security and Reliability #1130 before merge as `19938aaf3381f492ff01a179a89ef7aef580db08`.

PR #155 exact candidate head `01bfe7d2565ca48b55966167219695e1a57f1283` passed Security and Reliability #1143 before squash merge as `6a23c132b118180a9f42ef912cd90679c2892259`.

PR #158 was rebuilt on current main after PR #157 landed. Its first candidate exact-head run #1165 correctly failed with two regression findings: the synthetic positive-path validation split retained fewer than the predeclared eight actionable samples, and the new worker was not yet registered in the universal signal-worker binding. Both were fixed without weakening gates. Exact final head `8346da98019d959358ab5e045144d2a08df6fba2` then passed Security and Reliability #1169 before squash merge as `11555f75a24cf4c54074cfdafdc9d23c9c86b697`.

Post-merge Render evidence: production and coordinator both deployed `11555f75...` live. Coordinator canary reported `healthy`, `rollback_recommended=False`, `worker_failed=0`, `worker_timeouts=0`, `task_restarts=0`, no stale workers and no crashed workers. The post-deploy sample showed 238 completed worker jobs. This is operational evidence only, not an accuracy/profitability claim.

GitHub currently reports `main` branch protection disabled. Workflow-level exact-head/manual-review controls remain mandatory. Enable branch/ruleset protection for defense in depth when repository-admin access is available; do not weaken current controls in the meantime.

Cross-exchange/public-data collection may be unavailable at times. Never manufacture consensus, microstructure, history or agreement data when source evidence is unavailable.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

PR #158 increases the logical worker count from 19 to 20 by adding `adaptive-accuracy`, but it does not increase heavy semaphore concurrency or recurring infrastructure cost. The new worker shares the existing reserved accuracy lane with ACC-002 workers, and pure natural-history ACC-002 blockers back off for six hours so that lane can spend more time on currently falsifiable accuracy research.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, change source behavior, or cherry-pick thresholds merely to accelerate results.

## CURRENT OPEN DEVELOPMENT
Persistent specialist priorities live in `orchestration/specialist_coordination.json`. Specialists must follow current-main queue ownership/dependencies and may not use coordination state to bypass evidence gates.

PRs #120/#121/#141/#147/#149/#151/#153/#155/#157/#158 are integrated and must not be re-applied. PR #142 is closed/superseded. Old PRs #105, #34, #33 and #13 remain stale/non-mergeable and must not be merged as-is. PR #140 is stale against current main and must not be merged as-is. Any other open PR must be rechecked against current `main`, exact-head Security and Reliability, and current safety invariants before integration.

## EXACT NEXT STEP
1. Inspect the first completed `adaptive-accuracy` evidence on the live coordinator. Confirm the hypothesis came only from development rows, validation was frozen before inspection, and `oos_opened` is false unless all predeclared continuation gates passed.
2. Verify the pure `InsufficientHistory` ACC-002 workers now show the six-hour recheck delay while the `adaptive-accuracy` worker continues to receive the shared accuracy lane. Do not suppress or delay mixed source/software failures.
3. Feed each conclusive adaptive result into bounded research memory. Do not repeat a failed/consumed hypothesis until materially more independent evidence exists or its mechanism materially changes.
4. Expand executable science one method at a time only when there is a defensible evaluator: next highest-value candidates are regime-conditioned WAIT/abstention, calibration/selective precision, strategy-deterioration suppression, and execution/microstructure filters with timestamp-safe prospective data.
5. Keep ACC-002 as a natural-history blocker while aggregate failures remain purely `InsufficientHistory`; keep the 80% coverage, two-supported-subset, Top-N ordering and untouched-OOS requirements unchanged.
6. Allow PR #129 microstructure and PR #123 future-only consensus evidence to accumulate naturally. Never reconstruct historical order books, infer hidden liquidity, or backfill consensus.
7. Monitor the authentic paper ledger under PR #147/#157 execution marking and PR #127 conflict suppression without rewriting history. Paper results remain evidence only.
8. Preserve empty `live_promotions.json`, unused signing keys, broker-disconnected state, immutable $100k paper ledger, bounded heavy concurrency and the USD 30/month ceiling.
9. Keep exact-head Security and Reliability/manual compatibility review mandatory for every merge. Enable GitHub main branch/ruleset protection separately when repository-admin access is available.
10. Optimize genuine after-cost risk-adjusted realized performance with selective abstention and tail protection, never headline accuracy alone.
