# BTC Lead-Lag Cheap Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deterministically screen the frozen `DISC-BTC-LEADLAG-001-v1` contract on its immutable train/validation history while emitting truthful, reconciled economic evidence and never opening untouched OOS.

**Architecture:** Add one offline selection module that verifies the frozen contract and dataset before aligning bars, generates point-in-time signals, simulates the closed portfolio, applies every frozen gate, and seals a summary plus rich train/validation artifacts. Extend the profitability contract only enough to represent explicitly retrospective development evidence whose rule was frozen after the historical interval but before its outcomes were inspected.

**Tech Stack:** Python 3.12, standard library, pytest, existing `research_artifact` and `profitability_learning` packages.

**Spec:** `docs/research/btc_leadlag_001_preoutcome_contract_20260919.md`

## Global Constraints

- Exact fingerprint: `DISC-BTC-LEADLAG-001-v1`; frozen contract SHA-256 `8d991f723c65a583b1d3188aa7f4f77493d08cfd198ee6aa4be508294d770989`.
- Exact immutable dataset SHA-256 `047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f` and fixed BTC/ETH/SOL instruments only.
- Compute only purged 60% train and 20% chronological validation; untouched OOS and genuine-forward evidence stay unopened.
- Use the frozen through-origin 168-hour beta, next-open entry, six-hour hold, baseline, 35/50/65 bps gaps, cost stress, portfolio caps, and pass/fail gates without tuning.
- Research only; no trade, promotion, automatic execution, broker, paid-data, or paid-compute authority.

## Review Focus

- Future signal bars must not affect impulse, sigma, beta, gap, regime, or eligibility at decision time.
- Dataset timestamp gaps, duplicates, substitutions, identity mismatches, and invalid OHLC values must fail before outcomes are computed.
- Simultaneous ETH/SOL entries must share the BTC event and sizing NAV while respecting the two-position and 50% gross caps without resizing.
- Entry/exit costs and short/long P&L must reconcile exactly to hourly NAV and the rich experiment validator.
- Historical reused evidence must remain development-only and must never masquerade as pre-frozen forward/OOS evidence.

---

### Task 1: Truthful retrospective development contract

**Files:**
- Modify: `profitability_learning/contracts.py`
- Modify: `profitability_learning/experiment.schema.json`
- Test: `tests/test_profitability_learning.py`

**Interfaces:**
- Consumes: existing `validate_contract(contract)` and `DEVELOPMENT` split names.
- Produces: validated contracts with `retrospective_development_only=true`, `historical_outcomes_inspected_before_freeze=false`, and `historical_reuse_classification="EXPLORATORY_DEVELOPMENT_ONLY"` when `start < end <= frozen_at <= outcomes_observed_at`.

- [x] Add a failing test showing explicit retrospective TRAINING evidence is accepted but the same chronology is rejected for protected splits or without the disclosure fields.
- [x] Run `python -m pytest tests/test_profitability_learning.py -q` and verify the explicit retrospective case fails because the current chronology guard requires `frozen_at < start`.
- [x] Implement the narrow development-only chronology branch and matching JSON-schema properties/conditional requirements.
- [x] Re-run `python -m pytest tests/test_profitability_learning.py -q` and verify it passes.

### Task 2: Frozen lead-lag engine and reconciled artifacts

**Files:**
- Create: `btc_leadlag_selection.py`
- Create: `tests/test_btc_leadlag_selection.py`

**Interfaces:**
- Consumes: `orchestration/disc_btc_leadlag_001.json`, the immutable gzip dataset, `research_artifact.sha256_hex`, `seal_research_payload`, and `profitability_learning.analytics.analyze`.
- Produces: `evaluate_selection_from_histories(histories, contract, generated_at)`, `run(generated_at=None)`, and a CLI that writes a sealed JSON evidence envelope.

- [x] Write failing tests for exact contract/dataset validation, through-origin beta, future-bar isolation, next-open/six-hour execution, common event identity, NAV/cost reconciliation, capacity fail-closed behavior, and locked protected evidence.
- [x] Run `python -m pytest tests/test_btc_leadlag_selection.py -q` and verify failure because the module is absent.
- [x] Implement strict alignment/identity checks, point-in-time signal generation, closed-portfolio simulation, cost-stress metrics, frozen gates, and rich primary 3x train/validation experiments.
- [x] Re-run `python -m pytest tests/test_btc_leadlag_selection.py tests/test_profitability_learning.py -q` and verify all focused tests pass.

### Task 3: Execute and preserve the exploratory result

**Files:**
- Create: `orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz`
- Test: `tests/test_btc_leadlag_selection.py`

**Interfaces:**
- Consumes: `btc_leadlag_selection.run()`.
- Produces: sealed immutable evidence with dataset identity, gate results, rich train/validation economic artifacts, protected-evidence flags, scientific interpretation, and exact next action.

- [x] Run the offline frozen screen once with no network or parameter changes and write the sealed evidence file.
- [x] Add a regression test that replays the frozen screen and matches the committed evidence's scientific result and integrity hash.
- [x] Run `python -m pytest tests/test_btc_leadlag_selection.py tests/test_btc_leadlag_contract.py tests/test_profitability_learning.py -q`.
- [x] Run the complete `python -m pytest -q` suite and `git diff --check`; record exact results before publication.
