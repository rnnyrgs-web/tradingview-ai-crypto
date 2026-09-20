"""Issue #456 owner dashboard safety regressions."""

import json
import ast
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import httpx
import pytest

import db

from promising_results_dashboard import build_results_snapshot, render_results_html


NOW = datetime(2026, 9, 19, 20, tzinfo=timezone.utc)


def _write(root: Path, name: str, value: dict) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _strategy(fingerprint="STRAT-1"):
    return {
        "fingerprint_id": fingerprint,
        "stage": "CHEAP_SCREEN_PASS",
        "economic_mechanism": "Persistent spot demand can survive a brief squeeze.",
        "target_markets": ["BTC-USDT-SWAP"],
        "target_timeframes": ["1h"],
        "evidence_ref": f"orchestration/evidence/{fingerprint}.json",
    }


def _evidence(fingerprint="STRAT-1"):
    return {
        "fingerprint_id": fingerprint,
        "generated_at": "2026-09-19T18:00:00Z",
        "status": "CHEAP_SCREEN_PASS",
        "contract_sha256": "a" * 64,
        "dataset": {
            "source": "Timestamped exchange candles",
            "coverage_start_utc": "2025-01-01T00:00:00Z",
            "coverage_end_utc": "2026-09-18T00:00:00Z",
            "normalized_rows_sha256": "b" * 64,
        },
        "selection": {
            "screen_status": "PRE_OOS_PASS",
            "economic_pre_oos_pass": True,
            "eligible_for_deep_freeze": True,
            "data_integrity_ok": True,
            "robustness_pass": True,
            "multiple_testing_pass": True,
            "pooled_train": {"trades": 80, "mean_net_bps": 18, "profit_factor": 1.4},
            "pooled_validation": {"trades": 40, "mean_net_bps": 12, "profit_factor": 1.25},
            "validation_halves_mean_net_bps": [10, 14],
            "max_stress_round_trip_cost_bps": 60,
            "stressed_validation_mean_net_bps": 5,
            "untouched_oos_opened": False,
            "genuine_forward_opened": False,
            "pooled_failure_reasons": [],
        },
    }


def _base(root: Path, candidates=None, evidence=None, rejected=None, cycle=None, lab=None):
    candidates = candidates or []
    _write(root, "orchestration/strategy_discovery_queue.json", {"candidates": candidates})
    _write(root, "orchestration/rejected_fingerprints.json", {"entries": rejected or []})
    _write(root, "orchestration/specialist_coordination.json", {"tasks": []})
    for item in evidence or []:
        _write(root, f"orchestration/evidence/{item['fingerprint_id']}.json", item)
    _write(root, "money_intelligence/big_move_lab.json", lab or {"forward_candidates": []})
    if cycle is not None:
        _write(root, "money_intelligence/research_cycles/2026-09-19T1842Z-cycle.json", cycle)


def _snapshot(root: Path):
    return build_results_snapshot(root, now=NOW)


def test_rejected_strategy_never_appears_as_promising(tmp_path):
    _base(tmp_path, [_strategy()], [_evidence()], [{"fingerprint_id": "STRAT-1"}])
    assert _snapshot(tmp_path)["strategies"] == []


def test_wait_or_no_edge_never_enters_strict_lists(tmp_path):
    evidence = _evidence()
    evidence["selection"]["screen_status"] = "WAIT"
    _base(tmp_path, [_strategy()], [evidence], lab={"forward_candidates": [
        {"asset": "ENA", "status": "WAIT", "reference_price": 1, "observed_at": "2026-09-19T19:00:00Z"}
    ]})
    snapshot = _snapshot(tmp_path)
    assert snapshot["strategies"] == []
    assert snapshot["candidates_2x"] == []


def test_retrospective_big_mover_cannot_be_a_prior_forecast(tmp_path):
    _base(tmp_path, lab={"cases": [{"asset": "ZEC", "observed_move": "+200%", "decision_support": "WAIT"}]})
    assert _snapshot(tmp_path)["candidates_2x"] == []


def test_stale_and_malformed_evidence_fail_closed(tmp_path):
    evidence = _evidence()
    evidence["generated_at"] = "2026-09-10T18:00:00Z"
    _base(tmp_path, [_strategy()], [evidence])
    assert _snapshot(tmp_path)["strategies"] == []
    path = tmp_path / "orchestration/evidence/STRAT-1.json"
    path.write_text("{bad", encoding="utf-8")
    assert _snapshot(tmp_path)["strategies"] == []


def test_strict_strategy_requires_stressed_cost_and_robustness(tmp_path):
    evidence = _evidence()
    evidence["selection"]["stressed_validation_mean_net_bps"] = -1
    _base(tmp_path, [_strategy()], [evidence])
    assert _snapshot(tmp_path)["strategies"] == []
    evidence["selection"]["stressed_validation_mean_net_bps"] = 5
    evidence["selection"]["robustness_pass"] = False
    _write(tmp_path, "orchestration/evidence/STRAT-1.json", evidence)
    assert _snapshot(tmp_path)["strategies"] == []


def test_unfrozen_or_unverifiable_strategy_evidence_fails_closed(tmp_path):
    evidence = _evidence()
    evidence.pop("contract_sha256")
    _base(tmp_path, [_strategy()], [evidence])
    assert _snapshot(tmp_path)["strategies"] == []
    evidence["contract_sha256"] = "a" * 64
    evidence["dataset"].pop("normalized_rows_sha256")
    _write(tmp_path, "orchestration/evidence/STRAT-1.json", evidence)
    assert _snapshot(tmp_path)["strategies"] == []


def test_candidate_caps_and_unavailable_visuals(tmp_path):
    strategies = [_strategy(f"STRAT-{i}") for i in range(6)]
    evidence = [_evidence(f"STRAT-{i}") for i in range(6)]
    _base(tmp_path, strategies, evidence)
    snapshot = _snapshot(tmp_path)
    assert len(snapshot["strategies"]) == 3
    body = render_results_html(snapshot)
    assert "DATA NOT YET AVAILABLE" in body
    assert "RESEARCH ONLY / NOT LIVE" in body
    assert "Validation funnel" in body


def test_zero_promising_lists_render_and_navigation_is_valid(tmp_path):
    _base(tmp_path)
    body = render_results_html(_snapshot(tmp_path))
    assert "No promising strategies currently clear the evidence bar" in body
    assert "No promising 90-day 2x+ candidates currently clear the evidence bar" in body
    assert 'href="/dashboard"' in body
    assert 'href="/dashboard/results"' in body
    assert 'href="/dashboard/money"' in body


def test_closest_research_is_separate_fresh_and_research_only(tmp_path):
    cycle = {
        "information_cutoff": "2026-09-19T18:42:17Z",
        "fresh_validated_observations": [{
            "topic": "ENA/StablecoinX event",
            "label": "BIG-MOVE CAUSAL LAB / WAIT",
            "observed_facts": ["A timestamped filing was published."],
            "inference": "Treasury flexibility may reprice.",
            "transmission_mechanism": "Filing -> treasury optionality -> price response",
            "alternative_explanations": ["Broad risk-on"],
            "unknowns": ["Marginal buyer unknown"],
            "decision_support": "WAIT / NO CLEAN EDGE",
        }],
        "next_research": ["Freeze ENA venue-level spot and leverage data around the filing."],
        "source_log": [{"publisher": "SEC", "url": "https://www.sec.gov/example", "topic": "ENA filing"}],
        "prediction_ledger": {"frozen_new": 0},
    }
    _base(tmp_path, cycle=cycle)
    snapshot = _snapshot(tmp_path)
    assert snapshot["strategies"] == []
    assert snapshot["candidates_2x"] == []
    assert len(snapshot["closest_research"]) == 1
    body = render_results_html(snapshot)
    assert "NOT YET PROMISING — RESEARCH ONLY" in body
    assert "RETROSPECTIVE CASE" in body
    assert "FACTS" in body and "EVIDENCE AGAINST" in body and "NEXT TEST" in body
    cycle["information_cutoff"] = "2026-09-15T18:42:17Z"
    _write(tmp_path, "money_intelligence/research_cycles/2026-09-19T1842Z-cycle.json", cycle)
    assert _snapshot(tmp_path)["closest_research"] == []


def _forward_candidate(index):
    source = {"source_id": "exchange-quote", "publisher": "Example Exchange",
              "url": "https://example.org/market/quote", "published_at": "2026-09-19T17:58:00Z",
              "available_at": "2026-09-19T17:58:00Z", "captured_at": "2026-09-19T17:59:00Z",
              "observed_at": "2026-09-19T17:58:00Z", "reference_price": 2.5}
    return {
        "asset": f"ASSET-{index}", "status": "PROMISING_RESEARCH", "reference_price": 2.5,
        "forecast_id": index + 1, "scan_id": str(UUID(int=index + 1)),
        "observed_at": "2026-09-19T17:58:00Z", "frozen_at": "2026-09-19T18:00:00Z",
        "information_cutoff": "2026-09-19T17:59:00Z",
        "horizon_days": 90, "causal_mechanism": "Documented supply shock may affect marginal demand.",
        "evidence": {"pit_provenance_verified": True, "matched_controls_pass": True,
                     "base_rate_documented": True, "spot_leverage_decomposed": True},
        "evidence_for": ["Timestamped flow"], "evidence_against": ["Leverage may explain the move"],
        "invalidation": "Flow reverses", "next_test": "Observe independent forward cohort",
        "sources": [source],
    }


def _immutable_ledger_row(candidate):
    cutoff = candidate["information_cutoff"]
    evidence_rows = {flag: {"recorded_at": cutoff, "summary": f"Frozen {flag} evidence",
                            "source_ids": ["exchange-quote"]} for flag in candidate["evidence"]}
    return {
        "id": candidate["forecast_id"], "scan_id": candidate["scan_id"],
        "symbol": candidate["asset"], "horizon": "90d", "direction": "LONG",
        "entry_price": 2.5, "created_at": "2026-09-19T18:00:00Z",
        "due_at": "2026-12-18T18:00:00Z",
        "calibration": {"big_move_2x": {
            "information_cutoff": cutoff, "reference_observed_at": candidate["observed_at"],
            "evidence_captured_at": cutoff, "reference_price": 2.5,
            "reference_price_source_id": "exchange-quote", "target_multiplier": 2,
            "target_price": 5.0,
            "target_definition": "at_least_2x_frozen_reference_within_90_days",
            "evidence": deepcopy(candidate["evidence"]), "evidence_rows": evidence_rows,
            "causal_mechanism": candidate["causal_mechanism"],
            "evidence_for": deepcopy(candidate["evidence_for"]),
            "evidence_against": deepcopy(candidate["evidence_against"]),
            "invalidation": candidate["invalidation"], "next_test": candidate["next_test"],
            "sources": deepcopy(candidate["sources"]),
        }},
    }


def _serve_ledger(monkeypatch, rows):
    ledger = {row["id"]: row for row in rows}
    monkeypatch.setattr(db, "fetch_prediction_by_id", lambda identity: ledger.get(identity))


def test_2x_candidates_are_capped_and_reference_price_is_computed(tmp_path, monkeypatch):
    candidates = [_forward_candidate(i) for i in range(9)]
    _serve_ledger(monkeypatch, [_immutable_ledger_row(x) for x in candidates])
    _base(tmp_path, lab={"forward_candidates": candidates})
    candidates = _snapshot(tmp_path)["candidates_2x"]
    assert len(candidates) == 5
    assert all(x["two_x_price"] == 5 for x in candidates)
    assert "VALIDATED_FORECAST" not in render_results_html(_snapshot(tmp_path))


def test_2x_stale_malformed_and_unfrozen_cases_fail_closed(tmp_path, monkeypatch):
    stale = _forward_candidate(1)
    stale["observed_at"] = "2026-09-17T19:00:00Z"
    malformed = _forward_candidate(2)
    malformed["reference_price"] = "NaN"
    unfrozen = _forward_candidate(3)
    unfrozen["frozen_at"] = "2026-09-19T19:30:00Z"
    claimed_validated = _forward_candidate(4)
    claimed_validated["status"] = "VALIDATED_FORECAST"
    _serve_ledger(monkeypatch, [_immutable_ledger_row(_forward_candidate(i)) for i in (1, 2, 3, 4)])
    _base(tmp_path, lab={"forward_candidates": [stale, malformed, unfrozen, claimed_validated]})
    assert _snapshot(tmp_path)["candidates_2x"] == []


def test_forged_backdated_candidate_cannot_enter_without_ledger_row(tmp_path, monkeypatch):
    candidate = _forward_candidate(0)
    candidate["frozen_at"] = "2026-09-01T00:00:00Z"
    _serve_ledger(monkeypatch, [])
    _base(tmp_path, lab={"forward_candidates": [candidate]})
    assert _snapshot(tmp_path)["candidates_2x"] == []


def test_candidate_without_immutable_forecast_identity_cannot_enter(tmp_path, monkeypatch):
    candidate = _forward_candidate(0)
    candidate.pop("forecast_id")
    monkeypatch.setattr(db, "fetch_prediction_by_id", lambda _: pytest.fail("ledger must not be fetched"))
    _base(tmp_path, lab={"forward_candidates": [candidate]})
    assert _snapshot(tmp_path)["candidates_2x"] == []


@pytest.mark.parametrize("mutation", ["id", "scan_id", "asset", "price", "horizon", "cutoff", "target"])
def test_mismatched_immutable_identity_or_target_cannot_enter(tmp_path, monkeypatch, mutation):
    candidate = _forward_candidate(0)
    row = _immutable_ledger_row(candidate)
    if mutation == "id":
        row["id"] += 1
    elif mutation == "scan_id":
        row["scan_id"] = str(UUID(int=50))
    elif mutation == "asset":
        row["symbol"] = "OTHER"
    elif mutation == "price":
        row["entry_price"] = 3.0
    elif mutation == "horizon":
        row["horizon"] = "7d"
    elif mutation == "cutoff":
        row["calibration"]["big_move_2x"]["information_cutoff"] = "2026-09-19T19:00:00Z"
    else:
        row["calibration"]["big_move_2x"]["target_definition"] = "unclear target"
    monkeypatch.setattr(db, "fetch_prediction_by_id", lambda _: row)
    _base(tmp_path, lab={"forward_candidates": [candidate]})
    assert _snapshot(tmp_path)["candidates_2x"] == []


@pytest.mark.parametrize("mutation", ["late_publication", "unknown_availability", "http_url",
                                      "malformed_url", "malformed_host", "late_evidence",
                                      "missing_evidence_row", "malformed_evidence_source",
                                      "late_ledger_creation", "missing_ledger_creation",
                                      "already_resolved"])
def test_unsafe_provenance_or_late_evidence_cannot_enter(tmp_path, monkeypatch, mutation):
    candidate = _forward_candidate(0)
    row = _immutable_ledger_row(candidate)
    manifest = row["calibration"]["big_move_2x"]
    source = manifest["sources"][0]
    if mutation == "late_publication":
        source["published_at"] = "2026-09-19T18:01:00Z"
    elif mutation == "unknown_availability":
        source.pop("available_at")
    elif mutation == "http_url":
        source["url"] = "http://example.org/market/quote"
    elif mutation == "malformed_url":
        source["url"] = "https://user:pass@example.org/market/quote"
    elif mutation == "malformed_host":
        source["url"] = "https://example..org/market/quote"
    elif mutation == "late_evidence":
        manifest["evidence_rows"]["matched_controls_pass"]["recorded_at"] = "2026-09-19T18:01:00Z"
    elif mutation == "missing_evidence_row":
        manifest["evidence_rows"].pop("base_rate_documented")
    elif mutation == "malformed_evidence_source":
        manifest["evidence_rows"]["base_rate_documented"]["source_ids"] = [{"fake": True}]
    elif mutation == "late_ledger_creation":
        row["created_at"] = "2026-09-19T19:00:00Z"
    elif mutation == "missing_ledger_creation":
        row.pop("created_at")
    else:
        row["resolved_at"] = "2026-09-19T19:00:00Z"
    candidate["sources"] = deepcopy(manifest["sources"])
    _serve_ledger(monkeypatch, [row])
    _base(tmp_path, lab={"forward_candidates": [candidate]})
    assert _snapshot(tmp_path)["candidates_2x"] == []


def test_mutable_lab_flags_alone_cannot_qualify(tmp_path, monkeypatch):
    candidate = _forward_candidate(0)
    row = _immutable_ledger_row(candidate)
    row["calibration"]["big_move_2x"]["evidence"]["pit_provenance_verified"] = False
    _serve_ledger(monkeypatch, [row])
    _base(tmp_path, lab={"forward_candidates": [candidate]})
    assert _snapshot(tmp_path)["candidates_2x"] == []


def test_already_moved_retrospective_candidate_stays_outside_forward_list(tmp_path, monkeypatch):
    candidate = _forward_candidate(0)
    candidate["retrospective"] = True
    _serve_ledger(monkeypatch, [_immutable_ledger_row(candidate)])
    _base(tmp_path, lab={"forward_candidates": [candidate],
                         "cases": [{"asset": candidate["asset"], "observed_move": "+200%"}]})
    assert _snapshot(tmp_path)["candidates_2x"] == []


def test_valid_immutable_timestamp_safe_candidate_qualifies(tmp_path, monkeypatch):
    candidate = _forward_candidate(0)
    row = _immutable_ledger_row(candidate)
    _serve_ledger(monkeypatch, [row])
    _base(tmp_path, lab={"forward_candidates": [candidate]})
    result = _snapshot(tmp_path)["candidates_2x"]
    assert len(result) == 1
    assert result[0]["forecast_id"] == row["id"]
    assert result[0]["two_x_price"] == 5
    assert "https://example.org/market/quote" in render_results_html(_snapshot(tmp_path))


def test_strategy_display_logic_is_independent_of_2x_ledger_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "fetch_prediction_by_id", lambda _: (_ for _ in ()).throw(RuntimeError("offline")))
    _base(tmp_path, [_strategy()], [_evidence()], lab={"forward_candidates": [_forward_candidate(0)]})
    snapshot = _snapshot(tmp_path)
    assert len(snapshot["strategies"]) == 1
    assert snapshot["candidates_2x"] == []


@pytest.mark.parametrize("transport_error", [httpx.ConnectError, httpx.TimeoutException])
def test_2x_transport_failure_preserves_independent_results(tmp_path, monkeypatch, transport_error):
    cycle = {
        "information_cutoff": "2026-09-19T18:42:17Z",
        "fresh_validated_observations": [{
            "topic": "ENA/StablecoinX event", "observed_facts": ["Timestamped filing"],
            "inference": "Possible repricing", "unknowns": ["Marginal buyer unknown"],
            "decision_support": "WAIT",
        }],
        "next_research": ["Freeze ENA spot flow"],
        "source_log": [{"url": "https://www.sec.gov/example", "topic": "ENA filing"}],
    }
    _base(tmp_path, [_strategy()], [_evidence()], cycle=cycle,
          lab={"forward_candidates": [_forward_candidate(0)]})

    def fail_lookup(request):
        raise transport_error("Supabase unavailable", request=request)

    with httpx.Client(transport=httpx.MockTransport(fail_lookup)) as client:
        monkeypatch.setattr(db, "configured", lambda: True)
        monkeypatch.setattr(db, "SUPABASE_URL", "https://supabase.example")
        monkeypatch.setattr(db, "SUPABASE_SECRET_KEY", "test")
        monkeypatch.setattr(db, "http", client)
        snapshot = _snapshot(tmp_path)
        body = render_results_html(snapshot)

    assert snapshot["candidates_2x"] == []
    assert len(snapshot["strategies"]) == 1
    assert snapshot["strategies"][0]["fingerprint"] == "STRAT-1"
    assert len(snapshot["closest_research"]) == 1
    assert "STRAT-1" in body
    assert "ENA/StablecoinX" in body
    assert "No promising 90-day 2x+ candidates currently clear the evidence bar" in body


def test_2x_lookup_programming_error_is_not_swallowed(tmp_path, monkeypatch):
    _base(tmp_path, lab={"forward_candidates": [_forward_candidate(0)]})

    def fail_lookup(_identity):
        raise AssertionError("unrelated programming error")

    monkeypatch.setattr(db, "fetch_prediction_by_id", fail_lookup)
    with pytest.raises(AssertionError, match="unrelated programming error"):
        _snapshot(tmp_path)


def test_app_declares_results_route_and_all_three_pages_link_it():
    root = Path(__file__).parents[1]
    tree = ast.parse((root / "app.py").read_text(encoding="utf-8"))
    routes = [d.args[0].value for fn in tree.body if isinstance(fn, ast.FunctionDef)
              for d in fn.decorator_list if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute)
              and d.func.attr == "get" and d.args and isinstance(d.args[0], ast.Constant)]
    assert "/dashboard/results" in routes
    for file in ("strategy_mission_dashboard.py", "money_intelligence_dashboard.py", "promising_results_dashboard.py"):
        assert "/dashboard/results" in (root / file).read_text(encoding="utf-8")


def test_visuals_only_render_from_canonical_numeric_inputs(tmp_path):
    evidence = _evidence()
    evidence["mechanism_steps"] = ["Observed flow", "Frozen entry rule", "Risk exit"]
    evidence["visuals"] = {
        "after_cost_equity": {"train": [100, 101, 103], "validation": [100, 102, 104]},
        "drawdown": [0, -1, -0.5],
        "trade_returns_bps": list(range(-10, 10)),
        "cost_sensitivity": [{"round_trip_bps": 20, "mean_net_bps": 15},
                             {"round_trip_bps": 60, "mean_net_bps": 5}],
        "asset_regime_breakdown": [{"label": "BTC bull", "independent_trades": 22, "mean_net_bps": 4}],
    }
    _base(tmp_path, [_strategy()], [evidence])
    body = render_results_html(_snapshot(tmp_path))
    assert "Trade-return distribution" in body
    assert "20 bps cost" in body and "60 bps cost" in body
    assert "BTC bull" in body
    assert body.count("<svg") >= 4


def test_newest_malformed_cycle_blocks_older_research_fallback(tmp_path):
    cycle = {
        "information_cutoff": "2026-09-19T18:42:17Z",
        "fresh_validated_observations": [{"topic": "ENA/StablecoinX event", "observed_facts": ["Filed"],
                                          "inference": "Repricing", "unknowns": ["Buyer unknown"],
                                          "decision_support": "WAIT"}],
        "next_research": ["Freeze ENA spot flow"],
        "source_log": [{"url": "https://www.sec.gov/example", "topic": "ENA filing"}],
    }
    _base(tmp_path, cycle=cycle)
    newer = tmp_path / "money_intelligence/research_cycles/2026-09-19T1900Z-cycle.json"
    newer.write_text("{broken", encoding="utf-8")
    assert _snapshot(tmp_path)["closest_research"] == []


def test_untrusted_research_text_is_escaped(tmp_path):
    evidence = _evidence()
    candidate = _strategy()
    candidate["economic_mechanism"] = "<script>alert(1)</script>"
    _base(tmp_path, [candidate], [evidence])
    body = render_results_html(_snapshot(tmp_path))
    assert "<script>" not in body
    assert "&lt;script&gt;" in body
