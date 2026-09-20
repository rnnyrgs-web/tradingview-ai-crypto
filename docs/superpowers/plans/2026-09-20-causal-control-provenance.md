# Causal Control Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent confirmatory support when a planned observation ID is populated after outcomes with a different control source, metric, or selection provenance.

**Architecture:** Add an immutable per-pair observation selector to `FrozenHypothesis`, alongside ordered pair IDs and economic units. Require both future observations to match their frozen selectors before confirmatory evidence is admitted. Existing durable support without selectors becomes exploratory on replay; prospective synthetic acceptance freezes its deterministic selectors before outcomes.

**Tech Stack:** Python dataclasses, pytest, Supabase causal-memory document replay.

**Spec:** Phase-3 issue #462, PR #486 independent review at exact head `7b292102f9faece53eea101fdd2a487ae4583185` (Important post-outcome source/metric substitution reproduced and durably replayed).

## Global Constraints

- Work from main `361d110113700649dadf5d606456e8355945c17e` in an isolated branch.
- Preserve pre-outcome server-time freeze, project-wide alpha slots, exact pair identities, chronology and immutable replay.
- Leave market OOS/forward evidence unopened and broker, trading and promotion authority disabled.
- Require exact-head Security & Reliability, independent review and Lead-only integration.

## Review Focus

- Same frozen IDs with changed control metric or source must remain ineligible.
- Same frozen IDs with changed control provenance URI must remain ineligible.
- A changed outcome source or metric must remain ineligible.
- Restored historical support with no selector plan must lose confirmatory authority.
- A genuine prospective fixture with matching selectors must retain the research-only WAIT and later confirmation path.

---

### Task 1: Freeze and verify observation selectors

**Files:**
- Modify: `money_intelligence_causal_memory.py`
- Test: `tests/test_money_intelligence_causal_memory.py`
- Test: `tests/test_money_intelligence_causal_supabase.py`

**Interfaces:**
- Consumes: `FrozenHypothesis.evaluation_units` and `.evaluation_pairs`, `PointInTimeObservation`.
- Produces: `FrozenHypothesis.evaluation_selectors`, ordered one-for-one with pairs. Each pair holds two `(metric_name, source_id, provenance_uri)` tuples.

- [ ] **Step 1: Write failing adversarial tests.** Freeze six planned pair IDs and selector triples, then register observations under the exact IDs with a different control metric, source, and provenance URI. Assert `record_evidence` raises `CausalMemoryError` for each variation. Repeat after `to_document` / `from_document` and Supabase adapter restart. Assert a valid exact-selector case still confirms.
- [ ] **Step 2: Run the focused tests and observe the existing code admit the substituted controls.** Use `python -m pytest -q tests/test_money_intelligence_causal_memory.py tests/test_money_intelligence_causal_supabase.py` with the task's bundled Python and local dependency path.
- [ ] **Step 3: Implement the immutable contract.** Normalize nonblank selector strings in `FrozenHypothesis.__post_init__`, require selector count to equal the planned pair count, include selectors in `fingerprint` and `research_artifact`, and compare each actual outcome/control observation's `(metric_name, source_id, provenance_uri)` with its frozen selector before confirmatory support. Missing selectors must fail closed.
- [ ] **Step 4: Preserve replay and rejection semantics.** Parse selectors as tuples in `from_document`; demote historical support lacking selectors to exploratory; include selector-free variants in rejected-design checks, and reject a restored legacy-family marker that claims prospective selectors.
- [ ] **Step 5: Run causal-memory and Supabase tests; commit the code and regressions.**

### Task 2: Freeze selectors in synthetic acceptance

**Files:**
- Modify: `money_intelligence_causal_acceptance.py`
- Test: `tests/test_money_intelligence_causal_acceptance.py`
- Test: `tests/test_money_intelligence_mission_integration.py`

**Interfaces:**
- Consumes: `FrozenHypothesis.evaluation_selectors` from Task 1.
- Produces: an ordered prospective fixture selector for every dynamic 14–32 pair, generated from the same deterministic observation factory later used to register each pair.

- [ ] **Step 1: Add a regression** that checks all dynamically selected pairs have matching frozen selectors for slots 5 and 29 and that mismatch fails while the exact fixture passes.
- [ ] **Step 2: Run the acceptance tests and observe the red mismatch.**
- [ ] **Step 3: Generate selectors before plan registration** from each planned outcome/control observation ID using the fixed `matched_return` metric, `phase2-runtime-acceptance-fixture` source, and `acceptance://<observation-id>` provenance URI.
- [ ] **Step 4: Run focused causal/mission suites and `git diff --check`; commit.**

### Task 3: Integration gates

**Files:**
- Update only the bounded state or PR description needed to explain the reviewed scientific change.

**Interfaces:**
- Consumes: Tasks 1–2 exact branch head.
- Produces: reviewable PR with exact-head checks and explicit research-only limitation.

- [ ] **Step 1:** Run local focused tests and Linux Security & Reliability on the exact published head.
- [ ] **Step 2:** Request independent adversarial review of same-ID source/metric/URI substitution, replay, rejection and genuine prospective fixture.
- [ ] **Step 3:** Integrate only after no Important finding and green exact-head checks; verify exact merged-main SHA and postmerge Security & Reliability.

## Self-review

The plan covers the reproduced same-ID attack, replay, legacy demotion, rejected memory, dynamic fixture, exact-head gates and safety authority. Full source authenticity beyond the frozen selector contract remains a separately tracked scientific boundary and is not asserted by this fix.
