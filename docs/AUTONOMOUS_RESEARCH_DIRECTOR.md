# Autonomous Research Director

This document defines the persistent 24/7 research-management layer that coordinates signal-accuracy work without requiring a human to continuously open and direct ChatGPT windows.

## Objective

Continuously improve genuine forward BUY / SELL / WAIT quality for the 24h and 7d horizons while preserving all existing scientific, execution, safety, cost, and promotion gates.

The Director is a coordination layer, not a bypass. It never weakens untouched-OOS rules, never fabricates evidence, never auto-promotes a strategy that has not passed the repository's canonical gates, and never places real broker orders.

## Continuous loop

1. Ingest fresh resolved predictions, paper-trade outcomes, research diagnostics, worker health, blockers, and experiment results.
2. Maintain a shared mission board keyed by horizon, direction, regime, failure mode, and experiment family.
3. Rank candidate missions by expected information gain, expected signal-quality impact, evidence freshness, blocker state, and compute cost.
4. Assign each mission to exactly one specialist lane using a claim/lease so duplicate work is suppressed.
5. Run supported research-only experiments using the existing development -> validation -> untouched-OOS process.
6. Record rejected, blocked, exhausted, disproven, and successful experiments in durable research memory.
7. Re-rank remaining missions immediately after every material result or newly resolved signal.
8. Emit a concise daily Lead report with completed work, failed hypotheses, newly supported candidates, blockers, forward performance, and recommended next actions.

## Specialist lanes

The mission board should distinguish at least:

- 24h BUY
- 24h SELL
- 7d BUY
- 7d SELL
- WAIT / abstention
- regime selection
- confidence calibration
- false-positive suppression
- feature discovery
- derivatives / market intelligence
- microstructure / liquidity
- execution realism
- strategy deterioration
- validation / leakage defense
- forward performance

A lane may be research-only even when production execution is unavailable. For example, bearish/SELL predictive research may continue while authentic short execution remains fail-closed.

## Mission ranking

Each mission should be scored using a deterministic priority function. The exact weights may evolve, but the inputs must remain inspectable and timestamp-safe:

- expected information gain
- estimated improvement to forward precision / after-cost expectancy
- sample availability
- evidence freshness
- uncertainty reduction
- novelty versus consumed experiments
- blocker severity and expected unblock time
- heavy-compute cost
- risk of redundant testing

Blocked missions should not monopolize scarce heavy slots. A mission blocked only by natural history should receive a future recheck time and yield the lane to experiments that can teach us something now.

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

This is the primary mechanism preventing multiple workers or future ChatGPT specialist sessions from unknowingly duplicating the same research task.

## Promotion safety

The Director may autonomously create, rank, run, reject, and remember research experiments. It may not weaken or skip the canonical validation process. Production-facing changes remain subject to repository CI, untouched-OOS requirements, forward evidence where required, execution realism, and the existing integration / promotion policy.

## Lead report

A daily Lead report should summarize, at minimum:

- jobs considered / started / completed
- worker failures, timeouts, stale workers, and restarts
- experiments tested and rejected
- experiments blocked and their blocker classes
- candidates that passed validation
- candidates that opened untouched OOS
- 24h BUY / SELL and 7d BUY / SELL precision and coverage where supported
- WAIT / abstention findings
- after-cost expectancy changes
- material execution / liquidity findings
- highest-priority next missions
- explicit statement of whether any production promotion occurred

The report must distinguish genuine measured evidence from hypotheses and from insufficient-history states.

## Human / ChatGPT integration

Normal ChatGPT sessions are optional accelerators rather than required schedulers. A specialist session should read the shared state, claim a mission, work on a separate branch, record findings, and submit a PR. The persistent cloud Director and Python worker army continue when all ChatGPT browser windows are closed.
