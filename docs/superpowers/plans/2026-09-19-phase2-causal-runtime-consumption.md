# Phase 2 Causal Runtime Consumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the real autonomous research director consume deployment-durable Money Intelligence causal memory and prove that qualified evidence changes Big-Move and strategy-component mission eligibility/ranking without opening OOS or trading authority.

**Architecture:** Add a fail-closed adapter over `SupabaseCausalMemory` that produces provenance-bound `ResearchMission` rows only through the existing frozen-hypothesis/evidence gate. Integrate those rows into `research_director_runtime.refresh_director`, then add a sealed, secret-protected deployment acceptance path that writes deterministic acceptance evidence to the same append-only store and verifies support, contradiction, decay, replay, and restart behavior from durable state.

**Tech Stack:** Python 3.12, FastAPI, existing Supabase REST/RPC adapter, pytest, GitHub Actions.

**Spec:** `AI_STATE.md` Phase 2 / `COORD-MI-CAUSAL-002`, issue #451, and `orchestration/lead_coordination_overrides.json`.

## Global Constraints

- Research-only; `trade_authority`, `promotion_authority`, `broker_connected`, and `oos_opening_authority` remain false.
- Read and write only the approved service-role Supabase causal-memory version store; no empty or local fallback.
- Narrative-only claims, exploratory support, stale evidence, unresolved contradictions, and rejected exact fingerprints cannot enter mission eligibility.
- Preserve point-in-time chronology, matched controls, frozen methods, Bonferroni family controls, replay idempotency, and canonical rejected memory.
- Do not alter strategy outcomes, thresholds, OOS/forward state, or the approximately $30/month resource ceiling.

## Review Focus

- Configured backend missing/corrupt/outage: causal missions must be empty with explicit fail-closed status.
- Narrative-only or exploratory evidence: no mission may appear.
- Canonically rejected exact ID/design/effective fingerprint: no mission may appear after restart.
- Contradiction at or after latest support and long staleness decay: prior mission must disappear.
- Repeated acceptance and concurrent stale-writer replay: no duplicate evidence or mission identity drift.

---

### Task 1: Durable causal mission adapter

**Files:**
- Create: `money_intelligence_causal_runtime.py`
- Test: `tests/test_money_intelligence_causal_runtime.py`

**Interfaces:**
- Consumes: `SupabaseCausalMemory.load()`, `CausalRepricingMemory.research_artifact()`, canonical rejected-fingerprint registry.
- Produces: `causal_mission_feedback(*, as_of=None, store=None) -> dict` with deterministic mission rows, durable digest, status, and immutable safety fields.

- [ ] Write failing tests for qualified support, narrative/exploratory exclusion, rejected exact identity, contradiction, decay, restart, and backend failure.
- [ ] Run the focused tests and confirm the adapter import/behavior fails for the intended reason.
- [ ] Implement the minimal adapter and deterministic mission mapping.
- [ ] Run the focused tests to green and commit.

### Task 2: Default autonomous director consumption

**Files:**
- Modify: `research_director_runtime.py`
- Test: `tests/test_money_intelligence_causal_director.py`

**Interfaces:**
- Consumes: `causal_mission_feedback()` mission dictionaries.
- Produces: `refresh_director()` payload containing `money_intelligence_causal_memory`, combined visible/runnable rankings, and auditable evidence attribution.

- [ ] Write failing tests proving durable evidence changes eligibility/ranking while outage and narrative-only state do not.
- [ ] Run the focused tests and confirm the new payload/ranking assertions fail.
- [ ] Integrate causal missions without disturbing active claims or existing profitability-learning vetoes.
- [ ] Run director, profitability-learning, and causal-memory tests to green and commit.

### Task 3: Exact-deployed-SHA acceptance

**Files:**
- Create: `money_intelligence_causal_acceptance.py`
- Modify: `app.py`
- Create: `.github/workflows/money-intelligence-causal-runtime-acceptance.yml`
- Test: `tests/test_money_intelligence_causal_acceptance.py`
- Test: `tests/test_money_intelligence_causal_workflow.py`

**Interfaces:**
- Consumes: sealed in-repository acceptance contract, `SupabaseCausalMemory.transact()`, and the production causal director adapter.
- Produces: secret-protected POST result proving exact deployed SHA, support-stage admission/ranking, contradiction removal, decay removal, durable replay idempotency, restart equality, and all authority flags false.

- [ ] Write failing endpoint, replay, transition, workflow, and sanitized-diagnostics tests.
- [ ] Run them and confirm the new module/route/workflow is absent.
- [ ] Implement deterministic acceptance mutations and the automatic post-main deployment workflow.
- [ ] Run focused tests, full suite, dependency/static/secret/diff checks, then commit and publish a reviewable PR.
