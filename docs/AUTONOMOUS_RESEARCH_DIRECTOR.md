# Autonomous Research Director

This document defines the persistent 24/7 research-management layer that coordinates profitability and signal-quality work without requiring a human to continuously open and direct ChatGPT windows.

## Objective

Continuously improve genuine sustainable after-cost profitability first and genuine forward BUY / SELL / WAIT quality second, while preserving all existing scientific, execution, safety, cost, and promotion gates.

The Director must not be constrained to only fixed 24h and 7d opportunities. Those horizons remain benchmark and validation anchors, while research may also investigate materially tradeable abnormal moves on adaptive horizons from roughly 5 minutes through multi-week periods. Adaptive-horizon selection must itself remain frozen, chronological, multiple-testing controlled, untouched-OOS evaluated, and prospectively validated before any production-facing use.

The Director is a coordination layer, not a bypass. It never weakens untouched-OOS rules, never fabricates evidence, never auto-promotes a strategy that has not passed the repository's canonical gates, and never places real broker orders.

See `docs/EXTREME_MOVE_RESEARCH_FACTORY.md` for the dedicated Big Move / Crash research mission.

## Continuous loop

1. Ingest fresh resolved predictions, paper-trade outcomes, research diagnostics, worker health, blockers, experiment results, abnormal-move candidates, and extreme-event research results.
2. Maintain a shared mission board keyed by horizon or adaptive-horizon family, direction, regime, failure mode, event family, and experiment family.
3. Rank candidate missions primarily by expected genuine after-cost profitability impact, then expected information gain / signal-quality impact, evidence freshness, blocker state, and compute cost.
4. Assign each mission to exactly one specialist lane using a claim/lease so duplicate work is suppressed.
5. Run supported research-only experiments using the existing development -> validation -> untouched-OOS process.
6. Record rejected, blocked, exhausted, disproven, null, and successful experiments in durable research memory.
7. Re-rank remaining missions immediately after every material result, newly resolved signal, or materially new abnormal-move event.
8. Emit a concise daily Lead report with completed work, failed hypotheses, newly supported candidates, blockers, forward performance, extreme-move research progress, and recommended next actions.

## Specialist lanes

The mission board should distinguish at least:

- 24h BUY
- 24h SELL
- 7d BUY
- 7d SELL
- WAIT / abstention
- adaptive-horizon opportunity detection
- Big Move Radar
- Extreme Move Watch
- Early Warning
- upside 2x+ historical-event research
- severe-crash historical-event research
- event-vs-matched-control cohort construction
- magnitude prediction
- time-to-event / duration prediction
- tail-probability calibration
- regime selection
- confidence calibration
- false-positive suppression
- feature discovery
- derivatives / market intelligence
- microstructure / liquidity
- execution realism
- strategy deterioration
- validation / leakage defense
- precursor falsification
- forward performance

A lane may be research-only even when production execution is unavailable. For example, bearish/SELL predictive research may continue while authentic short execution remains fail-closed. Likewise, Extreme Move Watch and Early Warning remain research-only until canonical evidence and promotion requirements are satisfied.

## Mission ranking

Each mission should be scored using a deterministic priority function. The exact weights may evolve, but the inputs must remain inspectable and timestamp-safe:

- expected incremental after-cost profitability impact
- expected information gain
- estimated improvement to forward precision / after-cost expectancy
- sample availability
- evidence freshness
- uncertainty reduction
- novelty versus consumed experiments
- blocker severity and expected unblock time
- heavy-compute cost
- risk of redundant testing
- risk of winner-selection / retrospective narrative bias for extreme-event research
- tradeability / liquidity relevance

Blocked missions should not monopolize scarce heavy slots. A mission blocked only by natural history should receive a future recheck time and yield the lane to experiments that can teach us something now.

## Extreme-move research requirements

The Director should continuously coordinate the dedicated `EXTREME_MOVE_RESEARCH_FACTORY` mission without allowing it to become a retrospective storytelling engine.

For every extreme-event research family it should require:

- broad point-in-time historical universe construction
- retention of failed, delisted, illiquid, and non-winning assets when historically eligible
- matched controls that looked similar before the event but did not make the extreme move
- reconstruction of only information genuinely available before the event
- explicit event de-duplication / non-overlap rules
- frozen hypotheses and horizon-selection logic before OOS evaluation
- realistic cost, spread, slippage, funding, liquidity, and capacity treatment
- multiple-testing protection
- untouched OOS and prospective/forward validation
- durable preservation of negative and null findings

No single famous winner or crash may justify a general production claim.

## Claim / lease semantics

Every active mission receives an owner and lease expiration. A worker may claim only an unclaimed or expired mission. The Director renews leases for healthy running workers and safely releases leases for stale, crashed, cancelled, or completed work.

The claim record should include:

- mission_id
- owner_lane
- worker_id
- claimed_at
- lease_expires_at
- state
- experiment_id, when applicable
- last_progress_at

This is the primary mechanism preventing multiple workers or future ChatGPT / Claude / Claude Code specialist sessions from unknowingly duplicating the same research task.

## Promotion safety

The Director may autonomously create, rank, run, reject, and remember research experiments. It may not weaken or skip the canonical validation process. Production-facing changes remain subject to repository CI, untouched-OOS requirements, forward evidence where required, execution realism, and the existing integration / promotion policy.

Big Move Radar, Extreme Move Watch, and Early Warning outputs do not receive special promotion authority. Missing, stale, malformed, future, ambiguous, or scientifically insufficient evidence must fail closed.

## Lead report

A daily Lead report should summarize, at minimum:

- jobs considered / started / completed
- worker failures, timeouts, stale workers, and restarts
- experiments tested and rejected
- experiments blocked and their blocker classes
- candidates that passed validation
- candidates that opened untouched OOS
- 24h BUY / SELL and 7d BUY / SELL precision and coverage where supported
- adaptive-horizon research progress
- Big Move Radar / Extreme Move Watch / Early Warning research status
- new extreme-event cohorts and matched-control findings
- WAIT / abstention findings
- after-cost expectancy changes
- material execution / liquidity findings
- highest-priority next missions
- explicit statement of whether any production promotion occurred

The report must distinguish genuine measured evidence from hypotheses and from insufficient-history states.

## Human / multi-engine integration

Normal ChatGPT sessions are optional accelerators rather than required schedulers. The persistent cloud Director and Python worker army continue when browser windows are closed.

The intended division of labor is:

- ChatGPT Lead Integrator: profitability-first prioritization, coordination, integration, anti-duplication, evidence synthesis
- Claude: deep research, mechanism discovery, extreme-event / matched-control analysis, falsifiable hypothesis design
- Claude adversarial reviewer: independent falsification, especially winner-selection bias, leakage, horizon mining, control mismatch, and execution realism
- Claude Code: implementation, data pipelines, frozen experiment code, tests, and research artifacts
- deterministic workers: broad scans, cohort construction, backtests, robustness checks, diagnostics, and evidence accumulation

A specialist session should read the shared state, claim a mission, work on a separate branch, record findings, and submit a PR. No engine may authorize real-money trading, merge its own unsafe work, or raise the shared paid-resource ceiling without explicit approval.
