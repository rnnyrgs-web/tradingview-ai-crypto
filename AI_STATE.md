# AI_STATE.md

Last reconciled: 2026-09-12
Last updated: 2026-09-12

This file is the authoritative compact handoff for future agents working on `rnnyrgs-web/tradingview-ai-crypto`. Read it before changing the system. When this file conflicts with an older chat summary, branch note, or stale base coordination row, this file plus the repository's canonical coordination loader state wins.

## PRIMARY OBJECTIVE

1. Maximize **genuine sustainable after-cost profitability** first.
2. Maximize **genuine forward BUY/SELL precision/accuracy** second.
3. Never improve reported results by weakening chronology, untouched OOS/forward gates, multiple-testing controls, point-in-time universe safety, realistic execution/risk assumptions, abstention, or fail-closed behavior.

Profitability means net expectancy after realistic fees, spread, slippage, funding/carry, adverse selection, missed fills, market impact, and drawdown/risk. Headline accuracy and trade count are not objectives by themselves.

## CURRENT MAIN / DEPLOYMENT STATE

- Latest runtime-affecting GitHub `main` verified during this reconciliation: `b95f81459fe8bd4bdcc4b283f8d65f31363da660` (PR #328, retired funding observability made explicitly inactive).
- PR #328 changed observability/control-plane semantics only; no strategy rules, thresholds, OOS/forward gates, paper ledger, broker state, promotions, concurrency, budget, or deployment authority changed.
- PR #328 exact candidate head `ba3a240f0e1d0f44be392d2f411b8a498a3a2451` passed **Security and Reliability #2245**.
- Production Render service `srv-dadliegu01pc73bc7t50` is live on `b95f81459fe8bd4bdcc4b283f8d65f31363da660`.
- Research-coordinator Render service `srv-dafgtead0e5s73cc7ekg` is live on the same commit.
- There were no open GitHub PRs before this state-reconciliation branch was created.

Do not confuse a later state-only commit with a new trading/runtime strategy baseline. State-only reconciliations can advance `main` without changing trading behavior.

## SAFETY INVARIANTS

- `live_promotions.json` remains empty unless genuine forward profitability evidence and every canonical promotion gate authorize otherwise.
- Broker remains disconnected. Research, shadow execution, and paper trading have no real-order authority.
- Never reset, rewrite, reseed, or cosmetically improve the authentic paper ledger. The canonical starting account is the existing **$100,000** paper account; history remains append-only/authentic.
- Monthly infrastructure ceiling remains **$30 USD**. Add no paid service without explicit user approval.
- Code changes only on isolated branches.
- Confirmed defects require regression coverage where practical.
- Require exact-head **Security and Reliability** green before merge.
- Verify deployment health after runtime-affecting merges.
- Missing, stale, malformed, future, ambiguous, or scientifically insufficient evidence fails closed to WAIT / RESEARCH_ONLY.
- No candidate gets production, broker, paper-authority, or promotion authority merely from one promising research result.

## CANONICAL COORDINATION STATE — IMPORTANT OVERRIDE RULE

The canonical specialist state is produced by the coordination loader using:

- `orchestration/specialist_coordination.json` as the durable base; and
- `orchestration/specialist_coordination_overrides.json` as the later append-only reconciliation layer.

Do **not** read only the base JSON and conclude that `COORD-DATA-005` is still READY. That was the control-plane drift corrected by this reconciliation.

Current data-market handoff:

- `COORD-DATA-005`: **DONE**. DATA-BREADTH-001 was predeclared before outcome inspection in PR #300 and its bounded chronological falsifier was integrated in PR #301 (`40e9737e0e1dbdee7a25c48788b2d55b963db8d4`).
- `COORD-DATA-006`: **DONE**. Prospective point-in-time universe capture was integrated in PR #306 and independently verified live in PR #309. Verified evidence recorded by the override includes scan `7d886310-0854-41bf-b2b7-650a3c6f81c9`, captured `2026-09-12T14:07:50.146607+00:00`, forecast `2026-09-12T14:09:46.056333+00:00`, 79 members, no historical backfill, no future data, and zero trading authority.
- `COORD-DATA-007`: **BLOCKED**. It must remain blocked until genuinely prospective point-in-time universe cohorts mature into enough independent, non-overlapping 24h and 7d outcomes. **Never backfill or reconstruct missing historical membership from current survivors.**

DATA-BREADTH-001 remains frozen and research-only. Its next evaluation requires at least eight independent matured OOS observations per primary horizon, separate 24h/7d scoring, the frozen feature/sign/baseline, incremental after-cost expectancy, 1x/2x/3x cost stress, OOS-half/liquidity/regime stability, and no threshold mining or untouched-OOS reuse. Negative or insufficient evidence remains WAIT / RESEARCH_ONLY.

## EXACT NEXT STEP

**Do not select another data candidate while DATA-BREADTH-001 is awaiting the prospectively captured evidence required by COORD-DATA-007.** Let authentic point-in-time cohorts mature and run the frozen falsification only after its predeclared sample floor is satisfied. Never backfill or reconstruct missing historical membership from current survivors.

While that evidence matures, the event-driven supervisor may assign at most one independent, non-contaminating CHANGE task from the profitability-first READY backlog. Prefer work on genuine 24h after-cost profitability, execution/microstructure, resolved-signal error attribution, regime-conditioned abstention, or reliability defects only when it does not duplicate, tune on, or contaminate DATA-BREADTH-001 evidence. All other specialists remain AUDIT-only under the existing supervisor contract. If no clean independent work is justified, waiting is the correct action.

## DURABLE NEGATIVE DATA RESULTS — DO NOT RESCUE

### DATA-BASIS-001 — REJECTED CURRENT FINGERPRINT

The predeclared 8,000-hour chronological evidence window falsified both primary horizons after realistic costs:

- 24h OOS: **134** independent samples; average net **-8.490253160921695 bps**.
- 7d OOS: **19** independent samples; average net **-51.210226000078 bps**.

Do not tune, rescue, reopen untouched OOS, or reintroduce the same fingerprint under a new name merely to increase feature count.

### DATA-FUNDING-001 — REJECTED CURRENT FINGERPRINT

- 24h OOS: **38** samples; directional hit rate **0.50**; average net **+43.56917973482839 bps**, but **0.0 bps incremental expectancy versus its frozen training-only baseline**.
- 24h OOS halves were unstable: approximately **+91.5426 bps** then **-4.4042 bps**.
- 7d OOS had only **6** samples versus the predeclared minimum **8** and therefore failed the evidence floor.

The headline positive 24h return is not evidence of incremental alpha. Keep this fingerprint rejected.

### Historical OI routes already blocked

- Unchanged Binance historical-OI access from the deployed environment returned HTTP 451.
- Unchanged Bybit historical-OI access returned HTTP 403.

Do not waste research capacity retrying the same blocked routes unless the access conditions materially change. Do not substitute unverifiable or timestamp-unsafe data.

## PROFITABILITY-FIRST CONTROL PLANE

Recent integrations deliberately changed research prioritization, not production trading rules:

- PR #319 made independent after-cost economic harm outrank wrong-signal rate when allocating research attention.
- PR #320 made expected incremental after-cost profitability the research director's primary impact term, with forward signal quality secondary.
- PR #321 removed the permanently rejected DATA-BASIS/DATA-FUNDING compatibility job from the always-on heavy lane.
- PR #328 made the retained legacy funding observability projection explicitly inactive/retired so rejected evidence cannot masquerade as an active candidate.

After PR #321 the active layout is **20 logical workers: 18 heavy + 2 lightweight research-brain workers**. Physical heavy concurrency/cost controls remain bounded; no paid infrastructure increase was authorized.

Experiment ranking should continue to favor, in order:

1. expected incremental after-cost profitability / dollars per unit risk;
2. genuine forward precision and information gain;
3. low compute and implementation cost;
4. low overfitting / multiple-testing risk.

Repeatedly falsified features or strategies should be removed or deprioritized rather than endlessly tuned.

## EXECUTION / MICROSTRUCTURE LESSONS

The public Kraken order-book research path is timestamp-safe and research-only. `kraken_microstructure.py` measures spread, visible depth, top-level/depth imbalance, and microprice deviation from genuine snapshots and fails closed on stale, future, crossed, malformed, or one-sided books. It assumes no hidden liquidity and grants no order/trade/promotion authority.

Recent corrections:

- Direction-aware imbalance was required so LONG and SHORT do not interpret the same raw imbalance identically.
- A suspected execution condition must be compared against a sufficiently sampled normal-execution baseline; negative expectancy alone is not enough to blame execution.
- 24h and 7d execution economics must remain separated; one horizon may not hide the other's losses.

Earlier paper observations suggested worse measured entry slippage among some 7d stop-outs than target winners, but sample size was too small to authorize a veto. Continue prospective measurement; do not turn it into a threshold until independent evidence passes the canonical gates.

## ACC-002 / SIGNAL-EVIDENCE STATUS

At the last authoritative profitability-first state before this reconciliation:

- 24h ACC-002 history was close to data-ready (roughly 28–29/30 histories) with supported Top-15/30 liquidity evidence.
- 7d remained history-limited (roughly 19/30) and must stay blocked rather than borrowing 24h evidence.
- Horizon evidence is never pooled merely to meet sample counts.
- Untouched holdout / forward evidence is not reusable tuning data.

Use the latest authentic repository/runtime artifacts if these counts have advanced. Never copy an older count forward as if it were fresh evidence.

## PAPER / PROFITABILITY INTERPRETATION

Paper P&L is evidence, not truth. Always study expectancy per trade, profit factor, payoff ratio, win rate, max drawdown, calibration, BUY/SELL/WAIT precision, horizon/regime breakdowns, false positives/negatives, execution costs, and sample uncertainty together.

A higher hit rate is not an improvement if net expectancy or risk-adjusted return falls. A lower-hit-rate strategy may be valid only when chronological OOS plus genuine forward evidence demonstrates superior after-cost expectancy with controlled drawdown/risk.

Do not claim improved profitability or accuracy from process/control-plane fixes alone.

## RESEARCH DISCIPLINE

For every proposed experiment:

- state the economic mechanism before inspecting outcomes;
- freeze the candidate fingerprint and training-only decision rules;
- use chronological splits and non-overlapping full-horizon observations;
- keep 24h and 7d evidence separate;
- use a defensible point-in-time universe;
- compare against a frozen baseline and report incremental after-cost value;
- stress realistic costs and execution assumptions;
- measure stability across OOS halves, assets/liquidity buckets, and regimes where sample size permits;
- account for multiple testing/search breadth;
- preserve negative results and avoid repeating disproven ideas unless conditions materially change;
- require genuine forward evidence before promotion.

Missed profitable opportunities and losing trades should become falsifiable hypotheses, not ad-hoc threshold changes.

## CURRENT SAFE DEVELOPMENT PRIORITIES

While DATA-BREADTH-001 naturally matures, independent lanes may continue bounded work on:

- resolving 24h ACC-002 profitability hypotheses once canonical data gates permit;
- diagnosing genuine resolved-signal errors and missed opportunities without reusing holdout evidence;
- execution/microstructure hypotheses that test incremental after-cost value rather than raw correlation;
- regime-conditioned abstention/demotion where evidence is genuinely independent;
- portfolio interaction, concentration, and contradictory 24h/7d signal suppression;
- reliability/adversarial validation for leakage, overlap, timestamp, ledger, cost, and fail-closed defects.

Do not create work merely to keep workers busy. Waiting for clean prospective evidence is preferable to contaminating the experiment.

## MERGE / DEPLOYMENT CONTRACT

Before merging any code/runtime change:

1. Work on an isolated branch.
2. Add or update regression tests for confirmed defects.
3. Run/obtain exact-head Security and Reliability and require success.
4. Merge only after the exact candidate SHA is green.
5. Confirm both deployment services reach the intended merged commit and remain healthy.
6. Preserve `live_promotions.json`, broker-disconnected state, paper-ledger authenticity, and the cost ceiling unless independently authorized by the canonical gates/user.

If a safe cycle cannot complete, leave the system fail-closed and record the precise blocker and next experiment. Never fabricate evidence or report a profitability/accuracy gain that has not actually been demonstrated.