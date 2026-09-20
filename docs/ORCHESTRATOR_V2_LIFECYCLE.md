# Orchestrator V2-001 lifecycle contract

This milestone defines a deterministic control-plane contract and acceptance
harness for issue #472. It does not turn on another dispatcher or change the
V1 workflow. The task queue remains `specialist_coordination.json` plus
`specialist_coordination_overrides.json`, loaded through `load_state()`.
`AI_STATE.md`, the strategy-discovery queue, rejected-fingerprint registry,
model-routing policy, protected paths, and shared budget remain authoritative.
The V2 state value belongs under `v2` in V1's existing
`development_orchestrator_state.json` on `automation/specialist-runner-state`.
`GitHubStateStore.load/save` provides Contents API SHA compare-and-swap.

## State machine

`READY -> CLAIMED -> DISPATCHED -> RUNNING -> REVIEW_REQUIRED -> REVIEWING ->
REVISION_REQUIRED -> REPAIR -> REVIEW_REQUIRED -> READY_FOR_INTEGRATION -> DONE`

The canonical queue alone supplies `READY` and `DONE` for task selection;
V2 records the intervening attempt and evidence identities. A worker outcome
of `PR_CREATED` enters review. `NO_CHANGE`, `BLOCKED`, `TASK_MISMATCH`, and
`FAILED` block; `WAIT` and provider timeout require `retry_at`. CI failure
cannot enter review. Review must cite Security and independent reviewer lanes
and successful Security and Reliability CI on the exact PR head. Revisions
preserve exact findings and the existing owner, and are limited to two repair
cycles. A further revision blocks the task. A changed PR head returns to
`REVIEW_REQUIRED` and needs fresh CI and review. Main advancement blocks
further transitions until the branch is reconciled. A human Lead records the
integration decision and resulting main SHA; the reducer never merges.

`DONE` frees the worker. A successor event can then cite only the completed
task's canonical `next_task`, provided the Lead has updated the coordination
queue to mark that successor `READY`. The selection function evaluates
priority, dependencies, blockers, eligible engine and owner, claimed branches,
active PR branches, rejected fingerprints, retry time, and single deep-candidate
capacity. If none qualifies, it returns `None` (`WAIT`). Paid dispatch remains
subject to V1's local budget gate and `shared_budget.reserve_fleet_budget`;
the contract requires a reservation identity and cannot itself reserve funds.

Every event has a stable ID and content hash. Identical redelivery is a no-op;
conflicting redelivery raises. Task, attempt, engine, adapter, request, branch,
base SHA, PR, worker result, CI, review, repair, integration, and successor
identities are stored with the record. Callers must submit only verified GitHub
facts, persist the reduced value through `persist_event`, and reload after any
CAS conflict. No V2 event grants direct-main write, autonomous merge, broker,
trade, paper-ledger, strategy-promotion, or OOS authority.

## Adapter capability matrix

The machine-readable matrix is `ADAPTERS` in
`agents/development_orchestrator_v2.py`. Its `AUTOMATIC` flag means an
existing programmatic runner is accepted for the declared roles. V2-001
declares the existing Luna cloud specialist, Claude research runner, and Claude
Code testing runner as accepted; it does not invoke them. The deterministic
GitHub/Python lane is manual here because no general task dispatcher is
accepted. Terra, Sol, Codex, and Work/Astra are manual until a supported
adapter is verified. The independent reviewer and Lead are manual control
roles. Every specialist has `can_merge: false`; only the Lead capability can
merge, through the separate authorized integration process. `route_task`
returns `MANUAL_ADAPTER_REQUIRED` for unsupported/manual paths.

## User escalation

`USER_ACTION_REQUIRED` records blocked work, severity, Aron’s exact action,
work that can continue, and lane versus fleet scope. It covers credential,
plugin, spending, paid-resource, repeated-failure, manual-action, ambiguous
decision, and security-incident reasons. This contract records escalation;
no notification is sent by V2-001. Consumers should remain quiet otherwise.

## Acceptance scope

`tests/test_development_orchestrator_v2.py` uses synthetic control-plane
tasks and event identities only. It does not generate market outcomes or
research evidence. It exercises repair and exact-head re-review through Lead
integration, successor selection, duplicate delivery/claim suppression,
provider timeout, budget denial, unsupported adapters, stale head, main
advancement, CAS conflict, and human escalation. Existing V1 and safety
regressions remain required before integration.
