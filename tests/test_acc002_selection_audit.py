import copy

import pytest

import cross_asset_runner as runner
from acc002_selection_audit import build_selection_audit
from cross_asset_rank import CrossAssetConfig, build_cross_section_panel, evaluate_pre_oos
from research_artifact import seal_research_payload


def _rows(symbol_index: int, count: int = 260):
    base = 100.0 + symbol_index * 7.0
    rows = []
    for i in range(count):
        close = base * (1.0 + 0.0007 * i + 0.00003 * symbol_index * (i % 11))
        rows.append({
            "ts": 1_700_000_000_000 + i * 3_600_000,
            "open": close * 0.999,
            "high": close * 1.002,
            "low": close * 0.998,
            "close": close,
            "volume": 1000.0 + i + symbol_index,
            "quote_volume": (1000.0 + i + symbol_index) * close,
        })
    return rows


def _fixture():
    ranked = [f"ASSET{i:02d}-USDT" for i in range(15)]
    histories = {symbol: _rows(i) for i, symbol in enumerate(ranked[:12])}
    config = CrossAssetConfig(lookbacks=(4, 16, 64), forward_bars=24, round_trip_cost_bps=12.0, min_assets=8)
    panel = build_cross_section_panel(histories, config)
    pre = evaluate_pre_oos(panel, config)
    subset_ok = runner._pre_oos_candidate_ok(pre)
    fingerprint = runner._candidate_fingerprint(
        horizon="24h",
        bar="1H",
        config=config,
        primary_liquidity_subset=15,
    )
    candidate = {
        "index": 0,
        "lookbacks": [4, 16, 64],
        "candidate_fingerprint": fingerprint,
        "pre_oos": pre,
        "eligible_pre_oos": False,
        "liquidity_stability": {
            "minimum_passing_subsets": 2,
            "passing_subset_count": int(subset_ok),
            "passes": False,
        },
        "liquidity_subsets": {
            "15": {
                "requested_assets": 15,
                "resolved_assets": 12,
                "pre_oos": pre,
                "eligible_pre_oos": subset_ok,
            }
        },
    }
    payload = {
        "generated_at": "2026-09-18T23:30:00+00:00",
        "acc": "ACC-002",
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "selection_mode": True,
        "history_provenance": {"policy": "OKX only", "no_rank_substitution": True},
        "point_in_time_universe": {
            "mode": "current_universe_only",
            "promotion_allowed": False,
            "reason": "historical point-in-time membership unavailable",
        },
        "parameter_stability": {
            "minimum_eligible_candidates": 2,
            "eligible_candidate_count": 0,
            "passes": False,
        },
        "liquidity_stability_policy": {
            "predeclared_subsets": [15, 30, 45],
            "supported_subsets": [15],
            "minimum_subset_coverage": 0.80,
            "minimum_passing_subsets_per_candidate": 2,
            "primary_oos_subset": 15,
            "oos_subset_count": 0,
            "coverage_diagnostics": {},
        },
        "untouched_oos_opened_for_candidate_count": 0,
        "candidate_count": 1,
        "candidates": [candidate],
        "selected_evaluation": None,
        "universe_requested": 15,
        "universe_resolved": 12,
        "symbols": sorted(histories),
        "failed_symbols": [],
        "bar": "1H",
        "horizon": "24h",
        "bars_requested_env": 260,
        "bars_effective": 260,
        "minimum_history_bars": 100,
        "minimum_independent_oos_samples": 20,
    }
    captured = {
        "ranked_symbols": ranked,
        "research_histories": copy.deepcopy(histories),
        "liquidity_histories": {15: copy.deepcopy(histories)},
        "survivorship": copy.deepcopy(payload["point_in_time_universe"]),
    }
    return seal_research_payload(payload), captured


def test_audit_binds_exact_dataset_predicate_and_locked_oos_boundaries():
    envelope, captured = _fixture()
    audit = build_selection_audit(envelope, captured)
    payload = audit["payload"]

    assert payload["artifact_type"] == "ACC002_SELECTION_EVIDENCE_AUDIT"
    assert payload["dataset_manifest"]["dataset_sha256"]
    assert payload["dataset_manifest"]["ranked_symbol_count"] == 15
    assert payload["dataset_manifest"]["scored_symbol_count"] == 12
    assert len(payload["dataset_manifest"]["missing_ranked_symbols"]) == 3
    assert payload["dataset_manifest"]["survivorship_safe"] is False
    assert payload["scientific_limitations"]["promotion_grade"] is False
    assert payload["scientific_limitations"]["pre_oos_reproduced_from_captured_rows"] is True
    assert payload["selection_result"]["untouched_oos_status"] == "LOCKED_UNTOUCHED_OOS"
    assert payload["selection_result"]["untouched_oos_opened_for_candidate_count"] == 0
    assert payload["selection_result"]["eligible_for_promotion_review"] is False
    assert payload["trade_authority"] is False

    subset = payload["candidates"][0]["liquidity_subsets"]["15"]
    assert subset["selection_predicate"]["passes_all"] is runner._pre_oos_candidate_ok(
        envelope["payload"]["candidates"][0]["liquidity_subsets"]["15"]["pre_oos"]
    )
    assert subset["pre_oos_reproduced_from_dataset"] is True
    assert subset["split_boundaries"]["train"]["first_ts"] < subset["split_boundaries"]["validation"]["first_ts"]
    assert subset["split_boundaries"]["validation"]["last_ts"] < subset["split_boundaries"]["untouched_oos"]["first_ts"]
    assert subset["untouched_oos_scored"] is False


def test_audit_refuses_when_exact_scored_row_no_longer_matches_sealed_pre_oos():
    envelope, captured = _fixture()
    changed = copy.deepcopy(captured)
    changed["research_histories"]["ASSET00-USDT"][64]["close"] += 0.01
    changed["liquidity_histories"][15]["ASSET00-USDT"][64]["close"] += 0.01

    with pytest.raises(RuntimeError, match="does not reproduce"):
        build_selection_audit(envelope, changed)


def test_audit_refuses_opened_untouched_oos():
    envelope, captured = _fixture()
    payload = copy.deepcopy(envelope["payload"])
    payload["untouched_oos_opened_for_candidate_count"] = 1
    opened = seal_research_payload(payload)
    with pytest.raises(RuntimeError, match="untouched OOS"):
        build_selection_audit(opened, captured)


def test_audit_refuses_non_selection_mode():
    envelope, captured = _fixture()
    payload = copy.deepcopy(envelope["payload"])
    payload["selection_mode"] = False
    not_selection = seal_research_payload(payload)
    with pytest.raises(RuntimeError, match="SELECTION"):
        build_selection_audit(not_selection, captured)
