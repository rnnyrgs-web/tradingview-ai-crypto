# Exact-head review control migration evidence

Status: **review infrastructure only**. This document grants no strategy, OOS/forward, promotion, broker, trading, merge, or integration authority.

## Why the migration is fail-closed

The legacy exact-head queue used title-oriented approval/retry bookkeeping. The repaired control plane requires trusted GitHub Actions authorship plus exact PR, exact candidate SHA, workflow-main SHA, source attempt/run, outcome, repository identity, and `Integration authority: NONE` bindings.

A trusted historical control title is no longer silently ignored when its body cannot satisfy the structured contract. `orchestration.exact_head_control_state` exposes it in `invalid_trusted_control_issues` and forces `ambiguous_control_state=true`. The workflow therefore cannot invoke another paid reviewer or treat the old title as approval; the exact head must have its durable control evidence repaired or move to a new SHA with fresh CI/review. This is the migration path for legacy or partially persisted evidence.

## Live pre-migration approval audit

Immediately before this repair on 2026-09-22, a repository issue search for exact-head approval titles:

`repo:rnnyrgs-web/tradingview-ai-crypto in:title "exact-head-review-approved:"`

returned **zero issues**. Therefore the stricter structured approval receipt contract is not silently revoking a currently existing approval receipt in this repository. This observation is supporting migration evidence only; the runtime invalid-control blocker above remains authoritative if control state changes later.

## Monotone terminal rejection

The decision rule is predeclared and exhaustively regression-tested over all 27 combinations of three reviewer states (approve / reject / non-verdict), with and without controlled WAIT:

1. any valid independent rejection => `REJECTED`;
2. otherwise an acknowledged transient provider/runtime gap => `WAIT_RETRYABLE`;
3. otherwise exactly three valid approvals => the review-only approval outcome;
4. everything else => `FAILED`.

The control state retains the issue numbers of both validated approval receipts and validated rejection attempts/receipts. If a later validated rejection is added after an earlier approval receipt, `approved` becomes false while both evidence sets remain visible and `terminal_precedence` is `REJECTION_DOMINATES_APPROVAL`. Rejection therefore changes authority monotonically toward a safer terminal state rather than erasing history.

## Concurrency and API failure boundary

The workflow has one repository-wide `concurrency` group with `cancel-in-progress: false`, so only one exact-head review control-plane writer executes at a time. Issue enumeration uses complete `gh api --paginate` calls under `set -euo pipefail`; duplicate issue identities in a snapshot raise a hard control-state error. Repository owner/admin mutation remains the explicit trusted control-plane boundary and is not claimed to be cryptographically impossible.

This evidence does not convert green CI into approval. The final candidate head still requires exact-head Security & Reliability and genuine independent all-reviewer clearance before Lead integration is allowed.
