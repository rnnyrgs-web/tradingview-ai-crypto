# Phase 1: learning feedback reaches research admission

Task: PHASE1-DISPATCH-FEEDBACK-001, bounded acceptance subtask of issue #438.
Role: implementation worker. Base main: `17fbcd14b4131db768f62631ce7d18df647008e0`.
Branch: `auto/profitability-learning/phase1-dispatch-feedback-001`.

## Root cause and DONE

PR #437 persisted economic/component learning and modified factory information
priority, but the heavy scheduler sorted by unchanged economic priority factors.
Its actual admission therefore ignored learned evidence. An exact rejected
fingerprint received zero information priority yet remained eligible, including
as the only candidate. The director likewise offered a zero-priority rejected
mission. Reapplying queue feedback also compounded the same display penalty.

DONE for this subtask: real completion/persistence/feedback changes actual bounded
research admission; exact rejection is a veto; repeated application is stable;
meaningful regressions and full tests pass; separate PR with exact-head Security
and Reliability, independent review and Lead handoff. This is not acceptance of
the complete deployed Phase-1 loop.

## Implementation

- Multiply the existing economic scheduler score by validated learning feedback.
  Do not replace economic priority with information score or win rate. Expose
  base and adjusted economics plus the feedback explanation in selected work.
- Absent feedback preserves legacy behavior. Present malformed, nonfinite,
  out-of-bounds or authority-unsafe feedback fails closed. The maximum factor is
  1.5, above the existing family/component maximum of 1.3 * 1.15 = 1.495.
- Exact remembered rejection removes heavy eligibility and the director's next
  mission recommendation, including its daily-report surface. Existing active
  claims are retained, not canceled.
- Keep an unadjusted information-priority baseline so re-entry cannot count the
  same learning twice. Persistent event replay already remains idempotent.
- No strategy evaluator, canonical state, contracts, datasets, OOS release,
  search breadth, promotion gates, paid services or broker capability changed.

## Verification

The initial regression set against base main had 12 failures and 2 passes:
ignored economic/legacy feedback, rejected heavy/director recommendation,
invalid numerical feedback and absent adjusted economics. The completed suite
adds a real factory-report integration (no mocked queue/scheduler), ablation
consumption, re-entry and protected-partition controls.

- `pytest -q tests/test_profitability_learning_dispatch.py`: 27 passed.
- Full `pytest -q`: 1082 passed, 1 skipped (optional vectorbt).
- Targeted Bandit, committed-secret scan and `git diff --check`: clean.
- Exact published head, independent review and CI are recorded in the PR and
  issue #438 checkpoint rather than guessed before publication.

Independent review identified two additional boundary gaps: non-string feedback
reasons could abort scheduling, and the daily director report retained a rejected
recommendation. Three regression cases reproduced these failures before fixes;
malformed rows now leave healthy alternatives usable and the daily report mirrors
the filtered recommendations.

All economics in these tests are explicitly synthetic. No new market outcomes
were inspected, no strategy was validated and no profitability claim is made.

## Limitations and exact next action

This remains research admission/planning, not automatic execution authority.
Learned successor missions still require a fresh contract and independent review;
they are not automatically inserted into a heavy queue. Existing canonical
eligibility, one-deep-candidate and scientific gates remain required. This patch
does not enable any retired legacy worker or deploy a service.

Independent Lead: review exact PR head/CI and integrate if acceptable; do not
mark issue #438 complete. Then continue the separate candidate-evaluator path
(PR #436), emit actual frozen-contract/trade/NAV evidence, select an already
approved durable state transport, and verify the deployed SHA's completion ->
immutable memory -> consumed ranked-mission path. Phase 2 remains gated on that
acceptance or an explicit documented dependency decision.
