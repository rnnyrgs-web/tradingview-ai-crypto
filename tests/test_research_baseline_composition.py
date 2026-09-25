"""Synthetic invariants for retrospective baseline comparisons; no new outcomes."""
import copy
import math
import gzip
import json
from pathlib import Path

import pytest

from research_baseline_composition import compare_trades
import research_baseline_composition as diagnostic


def trade(at, gross, *, instrument="BTC", duration=6):
    return {"instrument": instrument, "direction": "LONG", "signal_ts": at - 1,
            "entry_ts": at, "exit_ts": at + duration, "gross_bps": gross}


def test_identical_opportunities_have_zero_incremental_payoff():
    rows = [trade(10, 100), trade(30, -50)]
    report = compare_trades(rows, copy.deepcopy(rows), costs=(20, 60))
    assert report["common_labels"] == 2
    assert report["differing_temporal_components"] == 0
    for cost in report["costs"]:
        assert cost["mean_difference_bps"] == 0
        assert cost["common_payoff_difference_bps"] == 0
        assert cost["composition_mean_difference_bps"] == 0


def test_selection_composition_is_not_changed_shared_trade_payoff():
    common = trade(10, 100)
    p, b = [common, trade(30, 40)], [common, trade(50, -40)]
    r = compare_trades(p, b, costs=(20,))["costs"][0]
    assert r["primary_mean_net_bps"] == 50
    assert r["baseline_mean_net_bps"] == 10
    assert r["mean_difference_bps"] == 40
    assert r["common_payoff_difference_bps"] == 0
    assert r["composition_mean_difference_bps"] == 40
    assert sum(r["mean_decomposition_bps"].values()) == pytest.approx(40)
    assert sum(r["additive_decomposition_bps"].values()) == pytest.approx(80)


def test_different_sample_sizes_require_common_weight_term():
    p, b = [trade(10, 100)], [trade(10, 100), trade(30, -100)]
    r = compare_trades(p, b, costs=(20,))["costs"][0]
    assert r["mean_difference_bps"] == 100
    assert r["mean_decomposition_bps"]["common_reweighting"] == 40
    assert r["mean_decomposition_bps"]["minus_baseline_only"] == 60


def test_cross_asset_transitive_overlap_and_touching_endpoints_are_one_component():
    p = [trade(10, 100), trade(16, 20, instrument="ETH"), trade(22, -20, instrument="SOL")]
    b = [trade(10, 100)]
    r = compare_trades(p, b)
    assert r["union_labels"] == 3
    assert r["temporal_components"] == 1
    assert r["differing_temporal_components"] == 1
    assert r["costs"][0]["leave_one_differing_component_out"]["undefined_comparisons"] == 1


def test_component_removal_uses_both_arms_and_can_expose_single_episode_dependence():
    p = [trade(10, 10), trade(30, 200)]
    b = [trade(10, 10), trade(30, -100, instrument="ETH")]
    r = compare_trades(p, b, costs=(20,))["costs"][0]
    assert r["mean_difference_bps"] == 150
    sensitivity = r["leave_one_differing_component_out"]
    assert sensitivity["minimum_mean_difference_bps"] == 0
    assert sensitivity["nonpositive_comparisons"] == 1


@pytest.mark.parametrize("field,value", [
    ("gross_bps", float("nan")), ("gross_bps", float("inf")),
    ("gross_bps", True), ("entry_ts", 1.5), ("entry_ts", True),
    ("signal_ts", 11), ("exit_ts", 9), ("direction", "WAIT"),
    ("instrument", ""), ("instrument", " BTC "),
])
def test_invalid_rows_fail_closed(field, value):
    bad = trade(10, 1)
    bad[field] = value
    with pytest.raises(ValueError):
        compare_trades([bad], [trade(30, 1)])


def test_duplicate_and_conflicting_shared_evidence_fail_closed():
    row = trade(10, 100)
    with pytest.raises(ValueError, match="duplicate"):
        compare_trades([row, row], [row])
    bad = {**row, "gross_bps": 101}
    with pytest.raises(ValueError, match="shared"):
        compare_trades([row], [bad])


def test_same_signal_with_changed_execution_is_distinct_and_visible():
    p = trade(10, 100)
    b = {**p, "exit_ts": 17, "gross_bps": 101}
    r = compare_trades([p], [b])
    assert r["common_labels"] == 0
    assert r["primary_only_labels"] == r["baseline_only_labels"] == 1
    assert r["temporal_components"] == 1


@pytest.mark.parametrize("costs", [(math.nan,), (-1,), (True,), (), (20, 20)])
def test_invalid_cost_ladders_fail_closed(costs):
    with pytest.raises(ValueError):
        compare_trades([trade(10, 100)], [trade(10, 100)], costs=costs)


def test_empty_arm_is_unknown_not_zero_and_order_does_not_change_result():
    r = compare_trades([], [trade(10, 100)])
    assert r["costs"][0]["mean_difference_bps"] is None
    assert r["costs"][0]["primary_mean_net_bps"] is None
    rows = [trade(30, 50), trade(10, 100)]
    assert compare_trades(rows, rows) == compare_trades(rows[::-1], rows[::-1])


ARCHIVE = Path(__file__).resolve().parents[1] / "orchestration/evidence/liquidity_meanrev_001_cache/evidence.json.gz"


def test_pinned_loader_reads_only_consumed_trade_evidence(monkeypatch):
    reads = []
    original = Path.read_bytes
    def guarded(path):
        reads.append(path.resolve())
        if path.resolve() != ARCHIVE.resolve():
            raise AssertionError("unexpected source read: " + str(path))
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", guarded)
    assert hasattr(diagnostic, "audit_archive"), "consumed-only archive loader missing"
    result = diagnostic.audit_archive(ARCHIVE)
    assert reads == [ARCHIVE.resolve()]
    assert result["segments"]["train"]["primary_labels"] == 425
    assert result["segments"]["validation"]["primary_labels"] == 123
    assert result["untouched_oos_opened"] is False
    assert result["genuine_forward_opened"] is False
    assert result["analysis_type"] == "POST_SELECTION_BASELINE_COMPOSITION_NO_NEW_TEST"


def test_forged_archive_with_recomputed_self_hash_is_not_admitted(tmp_path):
    from research_artifact import sha256_hex
    forged = json.loads(gzip.decompress(ARCHIVE.read_bytes()))
    forged["payload"]["selection"]["primary"]["BTC-USDT-SWAP"]["train"]["trades"][0]["gross_bps"] += 1
    forged["integrity"]["payload_sha256"] = sha256_hex(forged["payload"])
    path = tmp_path / "forged.gz"
    path.write_bytes(gzip.compress(json.dumps(forged).encode()))
    assert hasattr(diagnostic, "audit_archive"), "consumed-only archive loader missing"
    with pytest.raises(ValueError, match="pinned"):
        diagnostic.audit_archive(path)
