# Permanent ChatGPT Specialist Protocol

This repository is the persistent shared brain for all ChatGPT development windows working on `rnnyrgs-web/tradingview-ai-crypto`.

## Mandatory startup sequence
Every new or resumed ChatGPT development window must do this before development:

1. Read `AI_STATE.md` from `main` in full.
2. Treat `AI_STATE.md` on `main` as the authoritative current project state.
3. Read this `AGENTS.md` file in full.
4. Read `docs/CHATGPT_SPECIALISTS.md` and identify the assigned specialist role and branch.
5. Inspect the latest relevant commits, open PRs, workflows, and files for that role.
6. Re-sync the assigned branch from current `main` before each new development cycle.
7. If `main` materially changes during work, stop, re-sync, and re-evaluate before continuing.

Never infer current project state from ChatGPT memory alone.

## Shared safety invariants
- Never develop directly on `main` unless acting as the designated Lead Integrator in an explicit integration cycle.
- Specialists must never merge their own PRs.
- Specialists must never edit canonical `AI_STATE.md`; the Lead Integrator owns canonical state updates after successful integration.
- Use isolated specialist branches listed in `docs/CHATGPT_SPECIALISTS.md`.
- Do not duplicate another specialist's active work. If overlap is detected, stop and report it.
- Require exact-head Security and Reliability success before merge.
- Preserve chronological validation, untouched OOS, robustness/stability, multiple-testing protection, point-in-time universe safety, genuine forward proof, realistic fees/spread/slippage, and restrictive risk gates.
- Missing, stale, contradictory, statistically weak, execution-unsafe, or otherwise unreliable evidence must fail closed to `WAIT / NO TRADE / RESEARCH_ONLY`.
- Never weaken validation or safety gates merely to increase signal frequency, reported accuracy, or paper P&L.
- Never fabricate missing data or historical fields.
- Never count overlapping forecasts as independent.
- Never select a threshold using untouched/forward results and then reuse the same evidence as confirmation.
- Preserve exact strategy fingerprints when evidence is accumulating; behavior-changing challengers need a new fingerprint.
- Preserve the authentic forward-only paper ledger. Starting capital remains exactly $100,000 from the canonical baseline in `AI_STATE.md`; never reset or rewrite it.
- Keep the broker disconnected and do not add credentials or real-order capability without explicit user approval and all canonical gates.
- Preserve the recurring infrastructure ceiling of USD 30/month unless the user explicitly changes it.

## Development cycle
Use this loop:

`SYNC -> READ STATE -> CHECK OWNERSHIP -> INSPECT CURRENT WORK -> DEVELOP -> TEST -> PR -> REPORT -> STOP`

At the end of each cycle, report:
- role
- branch
- base `main` SHA used
- commit SHA
- PR number/link
- tests and exact-head CI status
- what changed
- measured evidence, if any
- risks/unresolved issues
- recommended next action

## Objective
The objective is not maximal historical backtest performance. The objective is to improve genuine forward, after-cost predictive quality and profitability while minimizing overfitting, leakage, false discovery, execution illusion, and operational risk.
