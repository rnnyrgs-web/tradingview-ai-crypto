# COORD-DISC-TEST-003: discovery boundary audit

Role: testing-security. Branch: `auto/testing-security/coord-disc-test-003`.
Base main: `f62db7c45db2ee442dbc6bf4031c9559168bd46d`.

## Scope and DONE

The data-market source-resolution task DATA-004 already has its own claimed
branch. This independent audit does not duplicate it or change its archive
parser, scientific contract, cohort, outcomes, evidence or ownership.

DONE for this bounded subset: reproduce public discovery-boundary bypasses,
reject those inputs consistently, verify normal research routing and WAIT,
run focused/full/security checks, publish a PR and leave precise limitations
for independent Lead review. This is not completion of the entire TEST-003
scientific audit. No strategy outcome or protected OOS is inspected.

## Reproduced defects and root cause

1. `ranked_screens` and `snapshot` accepted in-memory payloads without calling
   `validate_queue`. A caller bypassing the loader, or mutating an already
   loaded queue, could route a rejected fingerprint or multiple deep candidates.
   `snapshot` could even report hard-coded broker-off/research-only flags while
   its supplied policy said otherwise. The normal CLI loaded and validated its
   queue first; no actual live trading, OOS access or production incident is
   established by this synthetic reproduction.
2. The validator enforced broker/trade/research booleans but ignored the
   existing frozen-selection-before-OOS, rejected-fingerprint and no-paid-API
   policy fields. Missing, false, string or numeric versions were accepted.
3. `int(max_active_deep_candidates)` silently accepted `True`, `"1"`, `1.0`
   and `1.5` as a valid one-candidate limit. `None` raised an incidental
   `TypeError` rather than the explicit validation error.

Fixes validate both public boundaries, require each existing policy flag to
be its exact safe boolean, and require the capacity field to be integer 1.
No ranking weight, scientific threshold, candidate identity or evidence gate
is relaxed. No protected coordination/configuration file is edited.

## Verification

The original tests used real in-memory queues copied from canonical state;
mutations were synthetic and never written back. The compatibility follow-up
below isolates unit fixtures from mutable candidate readiness. Before implementation, the new suite
reported **83 failed / 16 passed**. After the minimal fix:

- 99 new adversarial/positive-control cases passed.
- 134 focused tests passed, including existing discovery-transition and
  offline squeeze timestamp/sample-integrity tests with real Parquet replay.
- Full suite: **1,070 passed / 1 skipped**.

Commands (isolated Python 3.12 research environment):

```sh
python -m pytest -q tests/test_discovery_evidence_firewall.py tests/test_strategy_discovery_supervisor.py tests/test_strategy_discovery_queue_transition.py tests/test_data_market_squeeze_preflight.py
python -m pytest -q
bandit -q -r . -x ./tests
python security_secret_scan.py
PYTHONPATH=. python orchestration/specialist_coordination.py --validate
python strategy_discovery_supervisor.py --validate
git diff --check
```

Exact-head CI, remaining security checks and independent code-review results
are recorded in the PR, rather than implying that local tests authorize merge.
Dependencies, runtime services and spending are unchanged.

## Evidence limitations and exact next action

This closes a deterministic routing/validation weakness, not a profitable
strategy milestone. Checking a policy flag is not independent certification of
a selection artifact or permission to open OOS. Existing timestamp tests cover
the bounded sample/reference as-of guard, not an end-to-end signal constructor.

The full squeeze-retention contract and executable screen do not yet exist.
Therefore matched-control/search-breadth immutability and decision-time
publication/receipt joins still require adversarial tests against that eventual
implementation. Do not mark the full TEST-003 task DONE based on this PR.

Next: independent Lead reviews this exact head and green Security & Reliability;
the implementation worker does not merge its own PR. Continue DATA-004 source
resolution independently. Once a defensible source and pre-outcome scientific
contract exist, extend TEST-003 with future-row perturbation, publication-time
boundary, frozen-controls/search-breadth and OOS-open denial tests against the
actual screen. If the source is blocked, preserve the blocker and let the Lead
pivot without modifying rejected fingerprints. Broker/live remains disabled.

## Compatibility follow-up (2026-09-19)

Main advanced to `c51a59dbac604a2e0b2eefa2b68ae025d4c5b0e3`, recording
DATA-004's terminal source blocker. Pending Lead PR #435 at
`dc9533024122f23f5d8dbffb1c476e212927d0eb` correctly removes the old
candidate from screen-ready state. This supersedes the original DATA-004
continuation above: do not reopen the blocked source or its outcomes.

An isolated local combination of the original PR #432 head and pending #435
reproduced **3 failed / 96 passed** in this PR's new suite. Two rejection tests
raised `StopIteration` before exercising the guard; a positive-control test
assumed a real cheap-screen action existed. The production guard was correct;
the unit fixtures were incorrectly coupled to the evolving research queue.

The repair uses a fully explicit synthetic test-only queue for public-boundary
cases. A separate integration test still reads canonical state and checks safe
read-only behavior without assuming a candidate is ready. A valid synthetic
single-deep continuation positive control is now retained as a regression test.
No strategy state, production code or scientific rule is changed in this follow-up.

Verification after repair:

- Firewall suite: **101 passed**.
- Current-main plus PR #432 full suite: **1,078 passed / 1 skipped**.
- Pending #435 plus repaired PR #432 full suite: **1,079 passed / 1 skipped**.
- Both skips are the optional VectorBT test because VectorBT is not installed.
- The earlier exact-head CI success is historical, not authority for this new
  head. Updated exact-head CI and review results belong in the PR handoff.

Only the current-main integration is published in PR #432; #435 is tested in a
local compatibility branch, not merged or published by this worker. Independent
Lead should apply the pending coordination pivot through its review process and
select the new available-data hypothesis. This PR is generic guard hardening;
it does not make the blocked squeeze-retention TEST-003 task executable again.
