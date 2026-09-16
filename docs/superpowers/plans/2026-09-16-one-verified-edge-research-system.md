# One Verified Edge Research System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing single-strategy research stack into one auditable funnel where every candidate is immutable, dataset-bound, economically normalized, centrally gated, independently reproducible, forward-proofed and visible in Mission Control.

**Architecture:** Extend the repository’s existing `strategy_identity`, research artifact, experiment factory, validation, forward-proof and dashboard modules instead of creating a parallel platform. Introduce focused modules for immutable contracts, dataset certification, normalized economic results, validation gates, optional experiment tracking and independent reproduction; then wire those interfaces into the existing director, forward/paper and dashboard paths.

**Tech Stack:** Python 3.12, pytest, FastAPI, existing deterministic research stack; optional research-only MLflow, VectorBT, DuckDB and PyArrow/Parquet.

**Spec:** `docs/superpowers/specs/2026-09-16-one-verified-edge-research-system-design.md`

## Global Constraints

- Primary objective: find one independently validated sustainable after-cost algorithmic edge.
- Maximum active deep candidates: 1.
- Maximum implementation/change lane: 1.
- Real-money trading authority remains false.
- Untouched OOS cannot be used for tuning or candidate search.
- Missing/ambiguous evidence fails closed.
- Rejected fingerprints cannot be silently resurrected.
- $100,000 paper evidence remains append-only and cannot be reset to improve results.
- Monthly recurring project ceiling remains USD 30.
- Research-only dependencies must not become mandatory imports in the production web path.

---

### Task 1: Universal immutable strategy contract

**Files:**
- Create: `strategy_contract.py`
- Modify: `strategy_identity.py`
- Test: `tests/test_strategy_contract.py`

**Interfaces:**
- Produces: `StrategyContract.from_mapping(payload: dict) -> StrategyContract`
- Produces: `StrategyContract.canonical_payload() -> dict`
- Produces: `StrategyContract.fingerprint() -> str`
- Produces: `freeze_strategy_contract(payload: dict) -> dict`
- Produces: `assert_contract_unchanged(frozen: dict, proposed: dict) -> None`
- `strategy_identity.build_strategy_identity(...)` remains backward compatible and adds optional `contract` support.

- [ ] **Step 1: Write failing contract tests**

```python
from dataclasses import replace
import pytest
from strategy_contract import StrategyContract, assert_contract_unchanged, freeze_strategy_contract


def base_payload():
    return {
        "strategy_family": "momentum", "strategy_version": "v1",
        "features": {"residual_momentum": {"lookback": 24}},
        "universe": ["BTC", "ETH"], "universe_selection_rules": {"top_n": 2},
        "entry_rules": {"rank_lte": 1}, "exit_rules": {"horizon_hours": 24},
        "stop_rules": {"max_loss_pct": 2.0}, "position_sizing": {"equal_weight": True},
        "holding_logic": {"max_hours": 24}, "timeframes": ["1h"], "horizon": "24h",
        "costs": {"fees_bps": 20, "spread_bps": 4, "slippage_bps": 6, "funding_bps": 0, "execution_delay_bars": 1},
        "train_range": ["2024-01-01", "2024-12-31"],
        "validation_range": ["2025-01-01", "2025-06-30"],
        "untouched_oos_range": ["2025-07-01", "2025-12-31"],
        "git_sha": "abc123", "research_code_sha256": "code-sha",
        "dataset_id": "kraken-1h-v1", "dataset_sha256": "data-sha",
        "hypothesis_id": "H-001", "experiment_id": "EXP-001",
    }


def test_contract_fingerprint_is_deterministic_and_sensitive():
    first = StrategyContract.from_mapping(base_payload())
    second = StrategyContract.from_mapping(dict(reversed(list(base_payload().items()))))
    assert first.fingerprint() == second.fingerprint()
    changed = base_payload(); changed["stop_rules"] = {"max_loss_pct": 2.5}
    assert StrategyContract.from_mapping(changed).fingerprint() != first.fingerprint()


def test_frozen_contract_rejects_mutation():
    frozen = freeze_strategy_contract(base_payload())
    proposed = base_payload(); proposed["entry_rules"] = {"rank_lte": 2}
    with pytest.raises(RuntimeError, match="immutable strategy contract changed"):
        assert_contract_unchanged(frozen, proposed)
```

- [ ] **Step 2: Run `pytest tests/test_strategy_contract.py -v` and verify failure because module does not exist.**

- [ ] **Step 3: Implement normalized dataclass contract and SHA-256 fingerprint**

Use JSON canonicalization with sorted keys and compact separators. Reject missing required fields, empty identifiers, non-dict rule/cost blocks, and empty timeframes/universe.

- [ ] **Step 4: Extend `build_strategy_identity`**

Add keyword-only `contract: dict | None = None`; when supplied, use `StrategyContract.from_mapping(contract).fingerprint()` as the authoritative fingerprint and expose `contract_schema_version`. Existing callers without a contract retain current behavior.

- [ ] **Step 5: Run `pytest tests/test_strategy_contract.py tests/test_strategy_families.py tests/test_single_strategy_focus.py -v`.**

- [ ] **Step 6: Commit `feat: add immutable strategy contract`.**

---

### Task 2: Certified dataset manifest

**Files:**
- Create: `dataset_certification.py`
- Test: `tests/test_dataset_certification.py`

**Interfaces:**
- Produces: `certify_dataset_manifest(manifest: dict) -> dict`
- Produces keys: `certified: bool`, `dataset_sha256: str`, `checks: dict`, `failures: list[str]`.

- [ ] **Step 1: Write failing tests**

```python
from dataset_certification import certify_dataset_manifest


def manifest():
    return {
        "dataset_id": "kraken-btc-1h-v1", "source": "kraken", "venue": "spot",
        "symbol": "BTC/USD", "timezone": "UTC", "start_timestamp": "2025-01-01T00:00:00+00:00",
        "end_timestamp": "2025-12-31T23:00:00+00:00", "received_timestamp_available": False,
        "fields": ["open", "high", "low", "close", "volume"], "missing_periods": [],
        "duplicate_timestamps": 0, "out_of_order_records": 0, "impossible_ohlc_records": 0,
        "stale_records": 0, "future_universe_membership": False, "future_feature_use": False,
        "point_in_time_universe": True, "content_sha256": "abc123",
    }


def test_good_manifest_certifies_and_hashes():
    result = certify_dataset_manifest(manifest())
    assert result["certified"] is True
    assert len(result["dataset_sha256"]) == 64
    assert result["failures"] == []


def test_future_feature_use_fails_closed():
    value = manifest(); value["future_feature_use"] = True
    result = certify_dataset_manifest(value)
    assert result["certified"] is False
    assert "future_feature_use" in result["failures"]
```

- [ ] **Step 2: Run the test and confirm import failure.**
- [ ] **Step 3: Implement deterministic certification and fail-closed checks for duplicate/out-of-order timestamps, impossible OHLC, stale records, future membership/use, missing UTC timezone, missing point-in-time universe and empty content hash.**
- [ ] **Step 4: Run `pytest tests/test_dataset_certification.py tests/test_historical_cache.py tests/test_point_in_time_universe.py -v`.**
- [ ] **Step 5: Commit `feat: certify research dataset manifests`.**

---

### Task 3: Canonical economic result schema and central validation gatekeeper

**Files:**
- Create: `research_validation.py`
- Test: `tests/test_research_validation.py`

**Interfaces:**
- Produces: `normalize_economic_result(raw: dict) -> dict`
- Produces: `evaluate_candidate_stage(evidence: dict) -> dict`
- State values: `RESEARCH_PASS`, `VALIDATION_PASS`, `ROBUSTNESS_PASS`, `OOS_PASS`, `FORWARD_PENDING`, `FORWARD_PASS`, `REJECTED`.

- [ ] **Step 1: Write failing tests**

```python
from research_validation import evaluate_candidate_stage


def complete_evidence():
    return {
        "research": {"net_expectancy_pct": 0.2, "profit_factor": 1.2, "trades": 120, "chronology_safe": True},
        "validation": {"net_expectancy_pct": 0.15, "profit_factor": 1.15, "trades": 50, "chronology_safe": True},
        "robustness": {"parameter_neighborhood_stable": True, "cost_2x_positive": True, "cost_3x_acceptable": True, "not_single_trade_dominated": True, "not_single_asset_dominated": True},
        "multiple_testing": {"pass": True}, "dataset": {"certified": True},
        "oos": {"opened": True, "frozen_before_open": True, "net_expectancy_pct": 0.1, "profit_factor": 1.1, "trades": 40},
        "independent_reproduction": {"pass": True},
        "forward": {"observations": 0, "pass": False},
    }


def test_oos_survivor_waits_for_forward():
    result = evaluate_candidate_stage(complete_evidence())
    assert result["state"] == "FORWARD_PENDING"
    assert result["production_candidate"] is False


def test_negative_oos_is_rejected():
    evidence = complete_evidence(); evidence["oos"]["net_expectancy_pct"] = -0.01
    assert evaluate_candidate_stage(evidence)["state"] == "REJECTED"


def test_missing_independent_reproduction_fails_closed():
    evidence = complete_evidence(); evidence["independent_reproduction"] = {"pass": False, "status": "UNAVAILABLE"}
    result = evaluate_candidate_stage(evidence)
    assert result["state"] == "OOS_PASS"
    assert "independent_reproduction" in result["blocking_gates"]
```

- [ ] **Step 2: Run and verify failure.**
- [ ] **Step 3: Implement normalization for the standard economic fields and a monotonic fail-closed gate evaluation.**
- [ ] **Step 4: Ensure no state ever implies live trade authority; return `production_candidate=False` until forward passes and still return `real_money_trade_authority=False` after it passes.**
- [ ] **Step 5: Run `pytest tests/test_research_validation.py tests/test_robustness.py tests/test_multiple_testing.py tests/test_execution_oos.py -v`.**
- [ ] **Step 6: Commit `feat: centralize research validation gates`.**

---

### Task 4: Bind experiments and research artifacts to immutable contracts

**Files:**
- Modify: `research_artifact.py`
- Modify: `research_experiment_factory.py`
- Modify: `orchestration/rejected_fingerprints.py`
- Test: `tests/test_research_contract_binding.py`

**Interfaces:**
- Research envelopes schema version becomes 3 when a strategy contract is supplied.
- Experiment specs expose `hypothesis_id`, `experiment_id`, `strategy_fingerprint`, `dataset_sha256` and `contract_frozen`.

- [ ] **Step 1: Add tests asserting a supplied contract is frozen, its fingerprint is inside the sealed payload, and tampering fails envelope verification.**
- [ ] **Step 2: Add tests asserting a fingerprint present in rejected memory cannot be automatically queued again.**
- [ ] **Step 3: Implement contract binding while keeping schema v1/v2 verification backward compatible.**
- [ ] **Step 4: Run `pytest tests/test_research_contract_binding.py tests/test_research_experiment_factory.py tests/test_rejected_fingerprints.py tests/test_research_artifact_audit.py -v`.**
- [ ] **Step 5: Commit `feat: bind experiments to frozen strategy identity`.**

---

### Task 5: Optional MLflow tracking and research data dependencies

**Files:**
- Create: `research_tracking.py`
- Create: `requirements-research.txt`
- Test: `tests/test_research_tracking.py`

**Interfaces:**
- Produces: `log_experiment(run: dict, *, tracking_uri: str | None = None) -> dict`.
- Status values: `LOGGED`, `TRACKING_DISABLED`, `TRACKING_UNAVAILABLE`, `TRACKING_FAILED`.

- [ ] **Step 1: Test that no configured URI returns `TRACKING_DISABLED` without importing MLflow.**
- [ ] **Step 2: Test a fake injected/imported MLflow module receives fingerprint, Git SHA, dataset SHA, parameters and metrics.**
- [ ] **Step 3: Implement lazy MLflow import; never import it on production web module import paths.**
- [ ] **Step 4: Create `requirements-research.txt` with bounded research dependencies: `mlflow>=3,<4`, `vectorbt>=0.28,<1`, `duckdb>=1.4,<2`, `pyarrow>=18,<25`. Keep `requirements.txt` unchanged.**
- [ ] **Step 5: Run `pytest tests/test_research_tracking.py -v`.**
- [ ] **Step 6: Commit `feat: add optional research experiment tracking`.**

---

### Task 6: Independent VectorBT reproduction adapter

**Files:**
- Create: `independent_reproduction.py`
- Test: `tests/test_independent_reproduction.py`

**Interfaces:**
- Produces: `reproduce_vectorized(spec: dict, price_rows: list[dict]) -> dict`.
- Result status values: `PASS`, `DISAGREE`, `INDEPENDENT_REPRODUCTION_UNAVAILABLE`, `INVALID_INPUT`.

- [ ] **Step 1: Test that absent VectorBT produces `INDEPENDENT_REPRODUCTION_UNAVAILABLE` and `pass=False`.**
- [ ] **Step 2: Test that normalized independent metrics within declared tolerance of canonical metrics produce `PASS`.**
- [ ] **Step 3: Test that material net-expectancy/profit-factor disagreement produces `DISAGREE`.**
- [ ] **Step 4: Implement lazy VectorBT import and comparison logic; adapter must not import/call `backtest.py` or `execution_simulator.py`.**
- [ ] **Step 5: Run `pytest tests/test_independent_reproduction.py tests/test_backtest_execution_realism.py -v`.**
- [ ] **Step 6: Commit `feat: add independent vectorized reproduction gate`.**

---

### Task 7: Refocus research director and worker coordination on the single funnel

**Files:**
- Modify: `research_director.py`
- Modify: `research_experiment_factory.py`
- Modify: `orchestration/specialist_coordination.json`
- Test: `tests/test_one_edge_research_coordination.py`

**Interfaces:**
- Mission ranking rejects/penalizes duplicate hypothesis/fingerprint work and explicitly emits `candidate_fingerprint` when deep validation begins.
- Coordination has exactly one `CHANGE` owner; other lanes are `REVIEW`, `FALSIFICATION`, `DATA_CERTIFICATION`, or `EVIDENCE_COLLECTION` for the same mission.

- [ ] **Step 1: Add tests proving two change-lane claims cannot coexist and rejected/duplicate work cannot outrank the active candidate.**
- [ ] **Step 2: Add tests proving review/falsification/evidence missions can coexist without receiving strategy-mutation authority.**
- [ ] **Step 3: Implement the smallest coordination changes required; preserve existing worker-count and budget caps.**
- [ ] **Step 4: Run `pytest tests/test_one_edge_research_coordination.py tests/test_research_director.py tests/test_specialist_coordination.py tests/test_single_strategy_focus.py -v`.**
- [ ] **Step 5: Commit `feat: focus research fleet on one verified edge`.**

---

### Task 8: Forward-proof and paper-trade provenance

**Files:**
- Modify: `forward_proof.py`
- Modify: `paper_db.py`
- Modify: `paper_trading.py`
- Add migration only if schema inspection proves current columns cannot store the required IDs.
- Test: `tests/test_strategy_forward_provenance.py`

**Interfaces:**
- Forward decision record requires `strategy_fingerprint`, `signal_id`, `experiment_id`, `git_sha`, `dataset_sha256` before acceptance.
- Only central gate state `OOS_PASS` may start forward collection.
- Paper records link immutable provenance and reject conflicting rewrites.

- [ ] **Step 1: Write tests proving a non-OOS-pass contract cannot create a new forward decision.**
- [ ] **Step 2: Write tests proving provenance identifiers are immutable after decision time while outcome fields may be appended.**
- [ ] **Step 3: Write tests proving duplicate/conflicting paper decisions fail closed and losses cannot be deleted/reset through this path.**
- [ ] **Step 4: Implement backward-compatible provenance enforcement.**
- [ ] **Step 5: Run `pytest tests/test_strategy_forward_provenance.py tests/test_forward_proof.py tests/test_paper_db_integrity.py tests/test_paper_decision_idempotency.py tests/test_paper_trading.py -v`.**
- [ ] **Step 6: Commit `feat: bind forward and paper evidence to frozen strategies`.**

---

### Task 9: Mission Control scientific funnel

**Files:**
- Modify: `strategy_mission_dashboard.py`
- Modify: `combined_dashboard.py` only for navigation/integration if needed.
- Test: `tests/test_strategy_mission_dashboard.py`

**Interfaces:**
- `build_mission_snapshot` adds `funnel`, `closest_candidate`, `missing_evidence`, `negative_knowledge`, `experiment_activity`, `independent_reproduction`, `cost_stress`, `parameter_stability`, `multiple_testing`, `forward_evidence`.

- [ ] **Step 1: Extend snapshot tests for explicit fail-closed funnel data and no-production-qualified-strategy state.**
- [ ] **Step 2: Extend HTML assertions for mission, closest candidate, lifecycle stage, blocker, funnel counts, rejected knowledge, cost/reproduction/multiple-testing/forward status and system health.**
- [ ] **Step 3: Implement the UI using existing objective/coordinator/rejected-memory sources; never fabricate missing counts or results—display `UNVERIFIED`/`INSUFFICIENT EVIDENCE`.**
- [ ] **Step 4: Run `pytest tests/test_strategy_mission_dashboard.py tests/test_combined_dashboard_current_system.py tests/test_dashboard_authenticity.py -v`.**
- [ ] **Step 5: Commit `feat: make mission control show research truth`.**

---

### Task 10: Full adversarial and regression audit

**Files:**
- Modify only defects discovered by the audit.
- Document: `docs/integration/one_verified_edge_validation.md`

**Interfaces:**
- Audit conclusion is one of `PASS`, `BLOCKED`, `REJECTED`; never infer success from partial checks.

- [ ] **Step 1: Run targeted tests from Tasks 1-9.**
- [ ] **Step 2: Run full `pytest -q`.**
- [ ] **Step 3: Run repository security/reliability workflow against the exact branch head.**
- [ ] **Step 4: Review specifically for leakage, survivorship bias, overlapping samples, data snooping, parameter mining, cost assumptions, regime concentration, single-asset/trade dependency, execution illusion, small samples and timestamp errors.**
- [ ] **Step 5: Record exact head SHA, test counts, failures/waivers and remaining blockers in `docs/integration/one_verified_edge_validation.md`.**
- [ ] **Step 6: Open a PR from `agent/one-verified-edge-foundation` to `main`; do not merge while any required check is pending/failing or while review finds unresolved scientific risk.**
