# One Verified Edge Research System Design

**Date:** 2026-09-16
**Status:** Approved for implementation

## Mission

The system has one primary research objective: **find one independently validated, sustainable after-cost algorithmic edge**. Broad research, UI work, money-intelligence work, and additional strategy families are subordinate unless they directly improve the validity, speed, or observability of that mission.

The system must remain research/paper only. No change in this design grants real-money trade authority.

## Existing architecture to preserve

This design extends the current repository rather than creating a parallel stack. Preserve the current single-strategy focus, untouched OOS/forward-evidence firewall, rejected-fingerprint memory, $100k append-only paper ledger, $30/month recurring ceiling, isolated-branch workflow, 20-worker logical fleet, and fail-closed production/risk gates.

The current worker separation remains authoritative:

- ChatGPT/Astra: research lead and integrator.
- Claude Research: economic hypothesis generation and scientific falsification.
- Claude adversarial reviewer: attack apparently good evidence.
- Claude Code / GitHub implementation lane: implement one frozen change contract at a time.
- Deterministic Python workers: data preparation, backtests, robustness, diagnostics and forward evidence.
- GitHub Actions: objective test/validation judge.
- Sentry/Render: production/runtime truth only; neither may claim alpha.

## 1. Universal immutable experiment contract

Create one canonical `StrategyContract` representation used by research identity, research artifacts, experiment factory, validation gates, forward proof and paper evidence. A frozen contract contains at minimum:

- strategy family and version
- feature names and feature-calculation parameters
- lookbacks
- point-in-time universe and selection rules
- entry, exit, stop and position-sizing rules
- holding logic and horizon/timeframes
- fee, spread, slippage, funding/carry and execution-delay assumptions
- train, validation and untouched-OOS ranges
- Git SHA/research-code SHA
- dataset ID and dataset snapshot SHA
- hypothesis ID and experiment ID

The fingerprint is the SHA-256 of the normalized contract. Any material change creates a new fingerprint. After untouched OOS is opened, the fingerprint is immutable; mutation attempts fail closed.

## 2. Certified dataset contract

Each experiment references a deterministic dataset manifest containing source, venue, symbol, timestamps, available market fields, missing-period diagnostics, point-in-time universe declaration, timezone, quality status and snapshot SHA.

Certification fails closed on future leakage, duplicate/out-of-order timestamps, impossible OHLC, missing required intervals, stale data, future universe membership, timezone inconsistencies, or future-bar feature use when those checks are applicable to the supplied manifest.

Parquet + DuckDB is the preferred high-volume research representation. It is an optional research dependency and must not become a runtime requirement for the production web path.

## 3. Canonical economic result and gatekeeper

All strategies must emit one normalized result schema containing gross/net return, net expectancy/trade, profit factor, Sharpe, Sortino, max drawdown, Calmar, win rate, average winner/loser, payoff ratio, trade count, turnover, exposure, cost paid, long/short, asset, regime and rolling/segment breakdowns when available.

One central gatekeeper returns exactly one lifecycle state:

`RESEARCH_PASS`, `VALIDATION_PASS`, `ROBUSTNESS_PASS`, `OOS_PASS`, `FORWARD_PENDING`, `FORWARD_PASS`, or `REJECTED`.

Promotion requires positive after-cost evidence, chronology/leakage safety, reasonable sample size, parameter-neighborhood stability, non-concentration in one lucky trade/asset, cost stress, multiple-testing control, independent reproduction and finally genuine forward evidence. Missing evidence remains pending or rejected; it never becomes a pass by inference.

## 4. Experiment tracking

Add an MLflow adapter for deterministic experiment logging. It records experiment ID, hypothesis ID, fingerprint, Git SHA, dataset SHA, parameters, normalized metrics, plots/artifacts, result state and rejection reason.

MLflow is optional at runtime: if not configured, research remains functional and the adapter reports `tracking_disabled`; it must never silently claim successful logging.

## 5. Independent reproduction

Add an independent vectorized reproduction adapter using VectorBT for candidates that reach the reproduction gate. It must not call the canonical strategy execution implementation internally. If VectorBT is unavailable, the result is `INDEPENDENT_REPRODUCTION_UNAVAILABLE`, not a pass.

A material disagreement between canonical and independent economics returns `VALIDATION_BLOCKED` until explained.

## 6. Research-director focus

The experiment factory and research director rank work primarily by expected information gain toward after-cost alpha and falsification value per bounded compute/API cost. Signal precision remains secondary. Rejected fingerprints and duplicate hypotheses cannot be automatically resurfaced.

Only one deep candidate and one implementation/change lane may be active at a time. Other agents can work in parallel only on non-conflicting review, falsification, testing, data certification, or prospective evidence for that same mission.

## 7. Forward proof and paper evidence

Only a frozen `OOS_PASS` contract may enter shadow forward testing. The decision record is written immutably at decision time with strategy fingerprint, signal/experiment IDs, timestamp, entry reference, horizon, expected move, stop/exit rule, Git SHA and dataset SHA. Outcome fields are appended later; historical signals are never reconstructed.

Every paper trade links to its immutable strategy fingerprint, signal ID and experiment ID. The $100k paper ledger is never reset or edited to remove losses.

## 8. Mission Control

Extend the existing `strategy_mission_dashboard.py` / combined dashboard rather than creating another dashboard. The first screen must expose scientific truth:

- whether any strategy passed every gate
- closest candidate and current lifecycle state
- explicit blocker / missing evidence
- champion funnel counts
- today’s completed/rejected/promoted/insufficient-evidence experiments
- worker and system health
- cost/parameter-stability, multiple-testing and independent-reproduction status
- negative knowledge / rejected fingerprints
- latest forward/paper evidence

Pre-OOS ranking uses train/validation evidence. OOS must never be repeatedly reused to choose parameter tweaks.

## 9. Dependency and rollout policy

Add MLflow, VectorBT and DuckDB/Parquet support as research-only optional dependencies. Do not add Prefect, another chatbot/orchestrator, QuantConnect paid infrastructure, or real-money execution in this phase.

Roll out in independently reviewable increments: immutable contract and gatekeeper first; dataset certification; canonical result schema; tracking and independent reproduction; director/factory focus; Mission Control; forward/paper integration; adversarial audit.

Every increment uses TDD, isolated branches, exact-head CI and fail-closed behavior. No increment may weaken existing safety, chronology, OOS, forward-proof, cost, budget, or paper-ledger invariants.