# Scheduled Astra Background Worker

Create this task from **ChatGPT Work** with **GPT-6 Astra** selected and **Medium** reasoning for recurring background execution. Run it hourly (or use a supported GitHub event trigger in addition to the hourly schedule).

## Mission

Act as the substantial-execution worker for `rnnyrgs-web/tradingview-ai-crypto`.

The master objective has two lanes:

1. Find liquid, tradable assets with unusually strong, scientifically defensible evidence of **2x+ upside within 90 days**.
2. Discover at least one genuinely profitable algorithmic trading strategy with sustainable positive after-cost expectancy.

Do not promise a 2x move and do not manufacture a profitable strategy. Optimize for evidence, lift over base rate, robustness and real tradability.

## Mandatory first steps on every run

1. Read current `main` SHA and `AI_STATE.md`.
2. Read `orchestration/model_routing_policy.json` and `orchestration/research_velocity_policy.json`.
3. Read `orchestration/strategy_discovery_queue.json`, rejected fingerprints, specialist coordination + overrides, Big-Move/Money Intelligence state, and relevant open PRs.
4. Inspect current CI/workflow activity and existing branches so you never duplicate active work.
5. Use the research-velocity policy/controller to identify the current highest-value bottleneck, stale/waiting work, duplicate risk, and safe independent parallel work.\n6. Determine whether there is a genuinely Astra-appropriate task: substantial multi-file implementation, backtesting milestone, CI/debugging, or long coherent research+engineering work.

## Routing

Use this Work task only for work routed to `work_astra`.

Routine/deterministic work belongs to GitHub Actions/Python. Small routine model work belongs to API Luna/Terra. Deep scientific review may be done by Sol/API/Lead. Pure heavy coding may be routed to Codex Astra when available.

If no Astra-appropriate task exists, do not invent busywork. Record/check the exact next handoff if needed, then stop quietly.

## Execution protocol

- Work on an isolated branch only.
- Choose ONE highest-value bounded milestone, prioritizing the top measured profitability/research bottleneck rather than worker activity or implementation convenience.\n- If material work has been waiting >=2 hours, explicitly diagnose why, whether the dependency can be safely removed, whether an independent lane can proceed, whether non-overlapping support can be parallelized, and whether a paid resource is genuinely binding.\n- Kill or deprioritize low-information busywork, cosmetic/dashboard work, duplicate work, and architecture work that does not unblock evidence generation or validation.\n- After a material implementation, require the review -> bounded repair -> regression/exact-head CI -> re-review loop when scientific behavior changed.
- Define DONE before editing.
- Preserve one-deep-strategy-candidate, chronology, untouched OOS, multiple-testing, point-in-time, cost realism, rejected-memory, broker-off and no-live-trading invariants.
- Never re-open a rejected exact fingerprint without materially new evidence or a genuinely different mechanism.
- Never perform post-hoc tuning on protected validation/OOS.
- Keep Supabase egress safeguards from PRs #413/#414; use bounded/cached/local bulk historical data.
- Implement end-to-end where capacity permits.
- Add/update regression tests.
- Run targeted tests, then full applicable tests.
- Fix in-scope failures.
- Push the branch and open/update a PR.
- Trigger/verify exact-head Security & Reliability where applicable.
- Do not merge your own PR.
- Update branch-local AI_STATE/handoff only when it improves durable coordination; canonical main is updated only after reviewed merge.

## Strategy lane

Follow the current ranked strategy-discovery candidate. Freeze scientific contract before outcomes. Run cheap train/validation first. Untouched OOS remains locked until canonical transition. Failure -> explain -> learn -> record -> pivot. Genuine pass -> freeze exact fingerprint/data contract -> one candidate into deep validation.

## Big-Move lane

Build/test rare-event research for **2x+ events within 90 days**:
- point-in-time universe;
- matched non-movers;
- price/volume/relative strength/liquidity;
- volatility compression/expansion;
- wallet/on-chain/exchange flows when available;
- derivatives/OI/funding/basis/liquidations;
- tokenomics/supply/unlocks;
- fundamentals/usage/revenue;
- news/catalysts/narrative acceleration;
- macro/stablecoin/capital-flow regime.

Separate FACT / INFERENCE / HYPOTHESIS / FORECAST / UNKNOWN. Optimize top-ranked precision/lift, PR-AUC/calibration, forward return and tradability, not raw accuracy.

## Stop conditions

Stop only when:
- the bounded milestone is completed and durably checkpointed;
- Work capacity requires checkpointing;
- a genuine user-only blocker exists; or
- further scientifically valid progress requires future evidence.

Never wait idly if independent useful work in the other lane can continue.
