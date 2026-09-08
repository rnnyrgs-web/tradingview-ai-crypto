import json

from point_in_time_universe import (
    assess_symbol_set,
    filter_histories,
    load_manifest,
    membership_at,
)


def _write_manifest(tmp_path, snapshots, provenance=True):
    payload = {"snapshots": snapshots}
    if provenance:
        payload["provenance"] = {"source": "test historical snapshot archive", "captured_at": "2026-01-01T00:00:00Z"}
    path = tmp_path / "universe.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_missing_manifest_fails_closed():
    manifest = load_manifest(None)
    assert not manifest["valid"]
    gate = assess_symbol_set(manifest, ["BTC-USDT"])
    assert not gate["promotion_allowed"]


def test_missing_provenance_fails_closed(tmp_path):
    path = _write_manifest(tmp_path, [{"effective_from":"2024-01-01T00:00:00Z","effective_to":None,"symbols":["BTC-USDT"]}], provenance=False)
    manifest = load_manifest(path)
    assert not manifest["valid"]
    assert "provenance" in manifest["reason"]


def test_overlapping_snapshot_intervals_are_rejected(tmp_path):
    path = _write_manifest(tmp_path, [
        {"effective_from":"2024-01-01T00:00:00Z","effective_to":"2024-07-01T00:00:00Z","symbols":["BTC-USDT"]},
        {"effective_from":"2024-06-01T00:00:00Z","effective_to":None,"symbols":["BTC-USDT","OLD-USDT"]},
    ])
    assert not load_manifest(path)["valid"]


def test_membership_respects_historical_snapshot(tmp_path):
    path = _write_manifest(tmp_path, [
        {"effective_from":"2024-01-01T00:00:00Z","effective_to":"2024-06-01T00:00:00Z","symbols":["BTC-USDT","OLD-USDT"]},
        {"effective_from":"2024-06-01T00:00:00Z","effective_to":None,"symbols":["BTC-USDT","NEW-USDT"]},
    ])
    manifest = load_manifest(path)
    assert membership_at(manifest, "OLD-USDT", "2024-05-01T00:00:00Z")
    assert not membership_at(manifest, "OLD-USDT", "2024-07-01T00:00:00Z")
    assert membership_at(manifest, "NEW-USDT", "2024-07-01T00:00:00Z")


def test_current_survivors_cannot_hide_historical_member(tmp_path):
    path = _write_manifest(tmp_path, [
        {"effective_from":"2024-01-01T00:00:00Z","effective_to":None,"symbols":["BTC-USDT","DEAD-USDT"]},
    ])
    gate = assess_symbol_set(load_manifest(path), ["BTC-USDT"])
    assert not gate["survivorship_safe"]
    assert gate["missing_historical_member_symbols"] == ["DEAD-USDT"]


def test_complete_historical_member_set_can_pass_symbol_gate(tmp_path):
    path = _write_manifest(tmp_path, [
        {"effective_from":"2024-01-01T00:00:00Z","effective_to":None,"symbols":["BTC-USDT","DEAD-USDT"]},
    ])
    gate = assess_symbol_set(load_manifest(path), ["BTC-USDT", "DEAD-USDT"])
    assert gate["survivorship_safe"]
    assert gate["promotion_allowed"]
    assert not gate["can_authorize_by_itself"]


def test_filter_excludes_asset_outside_snapshot_but_preserves_real_history(tmp_path):
    path = _write_manifest(tmp_path, [
        {"effective_from":"2024-01-01T00:00:00Z","effective_to":"2024-06-01T00:00:00Z","symbols":["BTC-USDT","OLD-USDT"]},
        {"effective_from":"2024-06-01T00:00:00Z","effective_to":None,"symbols":["BTC-USDT","NEW-USDT"]},
    ])
    histories = {
        "BTC-USDT": [{"ts":"2024-05-01T00:00:00Z"}, {"ts":"2024-07-01T00:00:00Z"}],
        "OLD-USDT": [{"ts":"2024-05-01T00:00:00Z"}, {"ts":"2024-07-01T00:00:00Z"}],
        "NEW-USDT": [{"ts":"2024-05-01T00:00:00Z"}, {"ts":"2024-07-01T00:00:00Z"}],
    }
    filtered, gate = filter_histories(load_manifest(path), histories)
    assert gate["survivorship_safe"]
    assert len(filtered["OLD-USDT"]) == 1
    assert len(filtered["NEW-USDT"]) == 1
    assert gate["excluded_nonmember_observations"] == 2


def test_filter_fails_closed_when_manifest_member_was_never_fetched(tmp_path):
    path = _write_manifest(tmp_path, [
        {"effective_from":"2024-01-01T00:00:00Z","effective_to":None,"symbols":["BTC-USDT","DEAD-USDT"]},
    ])
    histories = {"BTC-USDT": [{"ts":"2024-05-01T00:00:00Z"}]}
    filtered, gate = filter_histories(load_manifest(path), histories)
    assert not gate["promotion_allowed"]
    assert gate["missing_historical_member_symbols"] == ["DEAD-USDT"]
    assert filtered == histories


def test_filter_fails_closed_on_uncovered_history_timestamp(tmp_path):
    path = _write_manifest(tmp_path, [
        {"effective_from":"2024-06-01T00:00:00Z","effective_to":None,"symbols":["BTC-USDT"]},
    ])
    histories = {"BTC-USDT": [{"ts":"2024-05-01T00:00:00Z"}, {"ts":"2024-07-01T00:00:00Z"}]}
    _, gate = filter_histories(load_manifest(path), histories)
    assert not gate["promotion_allowed"]
    assert gate["uncovered_observations"] == 1
