# Multi-Engine Coordination Protocol

This repository is developed by more than one AI engine plus a human Lead
Integrator, coordinating asynchronously through this repository's own
GitHub-hosted state rather than through the human relaying messages between
them. This document is the engine-agnostic counterpart to `AGENTS.md` (the
ChatGPT-specific historical protocol, still the authoritative reference for
the manual "paste a role assignment into a ChatGPT window" channel described
in `docs/CHATGPT_SPECIALISTS.md`) and to each engine's own runner
configuration.

## The four participants

1. **ChatGPT -- Lead Integrator / global coordinator.** Reviews candidate
   PRs (`agents/autonomous_orchestrator.py --reviewer lead` and
   `--reviewer security`), reconciles `AI_STATE.md` after integration
   (`agents/lead_state.py`), and resolves cross-role priority conflicts. Per
   the 2026-09-13 Lead Integrator amendment that introduced this document,
   ChatGPT's automated role is coordination and review, not production/test
   code authorship going forward.
2. **Claude -- deep scientific researcher and independent adversarial
   reviewer.** Two distinct, separately-implemented duties that must stay
   structurally independent of each other and of the engine being reviewed:
   - Research: `agents/claude_specialist_runner.py`, configured by
     `orchestration/autonomous_specialist_runner_claude.json`, owns
     research-only coordination tasks (currently `signal-accuracy` /
     `COORD-VAL-001`) and may only write research-design artifacts, never
     production or test code for strategy/signal/paper-ledger logic.
   - Adversarial review: `agents/autonomous_orchestrator.py
     --reviewer claude-adversarial`, called from `.github/workflows/autonomous_lead.yml`
     alongside (not instead of) the existing two OpenAI-backed reviews. It
     is instructed to actively try to falsify the claimed improvement
     against eleven named failure modes (see that function's docstring) and
     is documented, in its own system prompt, as never sufficient by itself
     to promote a strategy or authorize live trading.
3. **Claude Code -- implementation / engineering / testing agent.**
   `agents/claude_code_specialist_runner.py` plus the official
   [`anthropics/claude-code-action@v1`](https://code.claude.com/docs/en/github-actions),
   configured by `orchestration/autonomous_specialist_runner_claude_code.json`,
   owns implementation-flavored coordination tasks (currently
   `testing-security` / `COORD-TEST-001`). It is the engine this
   architecture designates for writing test/production code changes; running
   it and `agents/autonomous_cloud_runner.py`'s own code-writing path for
   the *same* coordination role at the same time would reintroduce the
   duplicate-work race this design avoids by construction (see "Task
   claiming" below) -- do not enable both for one role simultaneously.
4. **Existing research workers -- quantitative experiment/backtest/diagnostic
   factory.** `continuous_worker_army.py` and friends are unchanged by this
   document; they keep accumulating deterministic evidence that the other
   three participants read, and should consult
   `orchestration/rejected_fingerprints.json` before proposing a candidate
   that resembles a previously falsified one.

## Mandatory startup sequence (every engine, every cycle)

Every engine's `plan` step, before acting, must (this is enforced by the
shared functions in `agents/autonomous_cloud_runner.py` that every runner
imports, not merely documented as a convention):

1. Read current `AI_STATE.md` from `main` -- authoritative current project
   state.
2. Load `orchestration/specialist_coordination.json` with
   `orchestration/specialist_coordination_overrides.json` applied
   (`orchestration.specialist_coordination.load_state()`), never the base
   file alone.
3. Select at most one task via `next_task()` / `plan_decision()`. `None` /
   `Decision(run=False, ...)` is the correct WAIT outcome when nothing clean
   is READY -- never fabricate work to stay busy.
4. Check the candidate task's `fingerprint_id` (if any) against
   `orchestration/rejected_fingerprints.json`
   (`is_rejected_fingerprint()`) before opening untouched OOS on it.

## One canonical shared task/handoff state

`orchestration/specialist_coordination.json` (+ overrides) remains the
single canonical backlog. Two fields added for this multi-engine layer are
optional and additive, so every pre-existing task row is unaffected:

- `eligible_engines`: which engine kinds (`chatgpt`, `claude`, `claude-code`,
  `human`) may claim a task. Omitted means all are eligible.
- `engine_claim`: observability only, recording which engine claimed a task.
  The actual race-prevention mechanism is described below, not this field.

## Task claiming and duplicate-work prevention

A task is claimed the instant an engine successfully pushes the
deterministic branch `auto/<role>/<task_id>` (`agents.autonomous_cloud_runner.safe_branch`).
Git's own ref-creation atomicity is the race-prevention mechanism: a second
engine's pre-push `git ls-remote` check sees the branch already exists and
must treat that as "already claimed elsewhere," not an error to retry past.
Combined with `orchestration/specialist_coordination.py`'s existing
one-active-task-per-role invariant (`validate_state()`'s
`active_by_owner` check, unchanged by this layer) and this design's
non-overlapping role assignment per engine (see the four participants
above), no two engines can produce competing candidates for the same task.

## Protected paths (fail closed for every engine)

`orchestration/protected_paths.json` is the single canonical list every
engine's path allowlist check, `agents/autonomous_orchestrator.py`'s diff
review, and `.github/workflows/autonomous_lead.yml`'s pre-review guard all
load from -- previously these were three independently maintained lists
that had drifted out of sync with each other; see `BUG_REGRESSION_LEDGER.md`
entry `PROTECT-PATH-001`. It blocks `AI_STATE.md`, `AGENTS.md`, `agents/*`,
`orchestration/*`, `.github/workflows/*`, `requirements.txt`, `Dockerfile`,
`live_promotions.json`, `resource_recommendations_decisions.json`,
`BUG_REGRESSION_LEDGER.md`, and any `.env*` file for every engine
regardless of its own role allowlist.

## Fail-closed resource escalation

No engine may purchase, enable, or install a paid resource. An engine that
identifies one appends a proposal to `resource_recommendations_proposed.json`
(schema in that file) instead. Only a human/Lead-authored PR may append an
entry to `resource_recommendations_decisions.json` -- that file is itself a
protected path, so no autonomous engine's allowlist can include it. A
proposal existing is never itself an approval;
`orchestration.resource_recommendations.is_approved()` is the only function
that grants that meaning, and it can only return `True` from a decision
entry.

## Shared cost ceiling

Each engine's own runner config
(`orchestration/autonomous_specialist_runner*.json`) declares its own
conservative daily/monthly reserved-spend ceiling, individually enforced by
`agents.autonomous_cloud_runner.budget_gate()` exactly as before this
layer. Because those per-engine ceilings were each sized in isolation
against the one shared `project_monthly_ceiling_usd`, every engine's
workflow additionally runs `orchestration/shared_budget.py`'s fleet-wide
gate, which sums this engine's own recorded spend plus every sibling
engine's recorded spend (read from their state files on the shared
`automation/specialist-runner-state` branch) against that single ceiling
before executing. A missing sibling state file (an engine that has never
run) counts as zero spend, never as a failure.

## Safety invariants unchanged by this layer

Every invariant `AGENTS.md` and `orchestration/specialist_coordination.py`'s
`validate_state()` already enforce is unchanged: no engine may write `main`
directly, merge its own PR, enable automatic merge, connect the broker,
weaken chronological/OOS/robustness/multiple-testing/point-in-time
validation, or move the monthly infrastructure ceiling above 30 USD. This
layer adds engines to the existing pipeline; it does not add authority.
