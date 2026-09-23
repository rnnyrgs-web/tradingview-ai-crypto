# Exact-Head Review Control-Plane Break-Glass Procedure

## Purpose

This procedure exists only to restore the liveness of the exact-head review control plane if the canonical reviewer runtime itself is reproducibly unable to evaluate any repair. It is **not** a scientific approval path, a candidate-merge override, or a way to erase prior review evidence.

Repository-owner/admin mutation of GitHub state is already the explicit trusted control-plane boundary. This document narrows how that trust may be used during a genuine reviewer-runtime deadlock.

## Normal recovery comes first

Do not use break-glass for an ordinary transient provider failure, a scientific rejection, a missing secondary approval receipt, stale CI, a moved candidate head, or an ambiguous candidate state.

In particular, an already-finalized current-context approved source attempt whose secondary approval receipt failed to persist must use the deterministic **Exact-Head Approval Receipt Recovery** path. That path recreates only the missing receipt from the validated source attempt and never reruns scientific reviewers.

## Genuine break-glass trigger

Break-glass is allowed only when all of the following are true:

1. the canonical reviewer/control-state implementation has a reproducible defect that prevents legitimate exact-head review requests or control-plane repairs from being evaluated;
2. the failure occurs before a new independent scientific judgment can be trusted;
3. the defect cannot be repaired through the normal reviewed path because the defective gate itself blocks that path;
4. the incident is recorded durably with the failing canonical-main SHA, workflow run/error evidence, and the minimal repair scope.

A scientific `approve:false`, a durable `REJECTED`, or an authenticated interrupted `STARTED` attempt is never a break-glass trigger. Those remain terminal for that candidate SHA.

## Allowed repair authority

Break-glass authority is **control-plane-liveness only**. The repository owner/admin may manually integrate the smallest reviewer-runtime repair needed to restore the normal exact-head gate when the normal gate is itself impossible to use.

The repair must:

- touch only reviewer/control-plane paths required for liveness;
- preserve exact candidate SHA/repository identity, rejection dominance, interrupted-attempt nonretryability, protected scientific evidence, and zero autonomous merge/trading authority;
- pass full Security & Reliability and focused deterministic control-state regressions before manual integration;
- include a durable incident/repair receipt identifying the exact repair commit and why normal exact-head review was impossible;
- keep broker/live trading OFF.

Break-glass must **not**:

- create or synthesize an approval for any strategy, 2x candidate, research result, or scientific PR;
- delete, rewrite, or downgrade a prior rejection/interrupted-attempt record;
- declare a strategy profitable or a 2x predictor validated;
- open protected OOS/genuine-forward evidence;
- enable autonomous merge, broker connectivity, or trading;
- bypass a functioning reviewer gate merely for speed.

## After liveness is restored

1. Re-enable the normal exact-head review path immediately.
2. Treat every candidate PR as unapproved unless its positive approval is valid under the restored current reviewer context.
3. Preserve all prior exact-SHA negative scientific memory.
4. Re-run any positive-context validation required by the restored runtime; do not grandfather stale approval authority.
5. Independently review the break-glass repair itself through the restored gate as an after-the-fact control-plane audit. Any Important/Critical finding requires another bounded repair.
6. Close the incident only after the normal gate is demonstrably operational again.

## Principle

Break-glass may restore the **ability to ask independent reviewers a trustworthy question**. It may never decide the scientific answer on their behalf.
