# Permanent ChatGPT Specialist Protocol

This repository is the persistent shared brain for all ChatGPT development windows working on `rnnyrgs-web/tradingview-ai-crypto`.

As of the 2026-09-13 Lead Integrator multi-engine amendment, this repository is also developed by Claude (deep scientific research and independent adversarial review) and Claude Code (implementation/engineering/testing), coordinating through the same repository state rather than through a human relaying messages. Read `docs/MULTI_ENGINE_PROTOCOL.md` for the engine-agnostic rules shared by all engines (canonical task state, task claiming, protected paths, resource escalation, shared cost ceiling). This file remains authoritative for the ChatGPT-specific manual "paste a role assignment into a ChatGPT window" channel described below and in `docs/CHATGPT_SPECIALISTS.md`; its safety invariants apply to every engine, not only ChatGPT.

## Mandatory startup sequence
Every new or resumed ChatGPT development window must do this before development:

1. Read `AI_STATE.md` from `main` in full.
2. Treat `AI_STATE.md` on `main` as the authoritative current project state.
3. Read this `AGENTS.md` file in full.
4. Read `docs/CHATGPT_SPECIALISTS.md` and identify the assigned specialist role and branch.
5. Read `orchestration/specialist_coordination.json` **with canonical overrides applied** and locate the highest-priority active task owned by that specialist.
6. Read `orchestration/strategy_discovery_queue.json` and `orchestration/rejected_fingerprints.json` so the task is interpreted against the current ranked strategy-discovery objective and durable negative memory.
7. Validate/read the role queue with `python orchestration/specialist_coordination.py --role <role>` when working from a local checkout.
8. Inspect the latest relevant commits, open PRs, workflows, issues, and files for that role and coordination task.
9. Re-sync the assigned branch from current `main` before each new development cycle.
10. If `main`, the strategy-discovery queue, or the coordination state materially changes during work, stop, re-sync, and re-evaluate before continuing.

Never infer current project state from ChatGPT memory alone.

## Strategy-discovery / worker-queue relationship

`orchestration/strategy_discovery_queue.json` is the ranked scientific hypothesis queue. `orchestration/specialist_coordination.json` plus overrides is the execution queue that assigns bounded work to roles/engines. They are complementary, not competing sources of truth.

Rules:
- The Lead must keep worker assignments aligned with the highest-value current strategy-discovery milestone.
- A stale signal-era READY task must be blocked/superseded when it no longer materially advances the current strategy-discovery objective.
- Workers must not independently rewrite the ranked strategy queue or canonical coordination state; they return evidence/PRs and the Lead performs reconciliation.
- A failed candidate should cause durable learning and a pivot to the next materially distinct hypothesis, not dead-end inactivity.
- Waiting on one evidence stream does not prevent independent safe work on other hypothesis-generation or validation lanes.

## Shared coordination contract
`orchestration/specialist_coordination.json` is the persistent cross-specialist work queue. It records each specialist's highest-value current problem, ownership, status, dependencies/blockers, issue/branch/PR, evidence required for completion, and the next task after completion.

Rules:
- Prioritize by expected impact on genuine forward 24h/7d signal quality and after-cost profitability, not implementation ease or commit count.
- A specialist may have at most one task in `READY`, `IN_PROGRESS`, or `PR_OPEN` state at a time.
- `QUEUED` work is not started while a higher active task exists for that role.
- `BLOCKED` work stays blocked until the named evidence/dependency genuinely exists; never manufacture or backfill evidence to unblock it.
- When a task opens a PR, its coordination entry should identify the PR. After verified Lead integration, the Lead marks that task `DONE` and promotes the named `next_task` to `READY` only if its dependencies are actually satisfied.
- Specialists may propose coordination-state changes in their isolated PR when their own task state changes, but they must not rewrite another role's priorities or mark their own evidence complete without support in the PR/research artifacts.
- The Lead Integrator resolves cross-role priority conflicts and owns canonical multi-role handoffs after integration.
- The coordination file never authorizes live promotion, direct-main writes, merging, broker connectivity, extra compute, or weakening any canonical gate.
- Continuous Python research/experiment workers remain bounded by their existing heavy-concurrency and cost controls. Coordination should feed them high-information experiments and evidence accumulation, not increase infrastructure spend.

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

`SYNC -> READ STATE -> READ COORDINATION -> CHECK OWNERSHIP -> INSPECT CURRENT WORK -> DEVELOP -> TEST -> PR -> UPDATE OWN TASK STATE -> REPORT -> STOP`

At the end of each cycle, report:
- role
- coordination task ID
- branch
- base `main` SHA used
- commit SHA
- PR number/link
- tests and exact-head CI status
- what changed
- measured evidence, if any
- risks/unresolved issues
- whether the task is `PR_OPEN`, `BLOCKED`, or still `IN_PROGRESS`
- the named next task after successful Lead integration

## Objective
The objective is not maximal historical backtest performance. The objective is to improve genuine forward, after-cost predictive quality and profitability while minimizing overfitting, leakage, false discovery, execution illusion, and operational risk.
