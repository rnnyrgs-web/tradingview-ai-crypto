from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

import pytest

import kraken_eth_session_time_preflight as semantics


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "orchestration"
    / "external_replication"
    / "ext_eth_session_reversal_001_kraken_time_semantics_v1.json"
)


def test_contract_self_digest_and_authority_locks() -> None:
    payload = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    unsigned = dict(payload)
    claimed = unsigned.pop("artifact_sha256")
    canonical = json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == claimed
    assert claimed == semantics.CONTRACT_ARTIFACT_SHA256

    loaded = semantics.load_contract(ROOT)
    assert loaded["authority"]["timestamp_semantics_frozen_for_review"] is True
    for key, value in loaded["authority"].items():
        if key != "timestamp_semantics_frozen_for_review":
            assert value is False


def test_contract_binds_exact_parent_and_acquisition_sources() -> None:
    payload = semantics.load_contract(ROOT)
    assert payload["parent_replication"] == {
        "replication_id": "EXT-ETH-SESSION-REVERSAL-001-v1",
        "pr": 779,
        "exact_head_sha": "f3ae2ee6fd9ff648632ec3a557608af100902b08",
        "contract_path": "orchestration/external_replication/ext_eth_session_reversal_001_v1.json",
        "contract_git_blob_sha": "e27a19904130ceb0dcaff670b0eecb93b550103e",
        "contract_artifact_sha256": "fee604ea0e2f993cd109cadcc6717deedbb7bd02e044cf380de2ef80e91afcc3",
    }
    assert payload["acquisition_parent"]["exact_head_sha"] == (
        "6018652b2020db82ec3ede4ba51a4c3d22d853bd"
    )
    assert payload["acquisition_parent"]["helper_git_blob_sha"] == (
        "ea128e75bcc97ded30a600add865de7aff75dbbe"
    )
    assert payload["acquisition_parent"]["workflow_git_blob_sha"] == (
        "927f84720547c0c8a11b02807772313823e852d5"
    )


def test_kraken_close_is_available_only_at_interval_end() -> None:
    start = datetime(2026, 2, 3, 5, tzinfo=timezone.utc)
    assert semantics.close_available_at(start) == datetime(
        2026, 2, 3, 6, tzinfo=timezone.utc
    )
    assert semantics.source_bar_return_boundaries(start) == (
        datetime(2026, 2, 3, 5, tzinfo=timezone.utc),
        datetime(2026, 2, 3, 6, tzinfo=timezone.utc),
    )


def test_cutoff_five_source_labels_map_to_exact_economic_boundaries() -> None:
    d = date(2026, 2, 3)
    day = semantics.day_interval_begins(d)
    night = semantics.night_interval_begins(d)
    assert len(day) == 12
    assert len(night) == 12
    assert day[0] == datetime(2026, 2, 3, 5, tzinfo=timezone.utc)
    assert day[-1] == datetime(2026, 2, 3, 16, tzinfo=timezone.utc)
    assert semantics.day_economic_boundaries(d) == (
        datetime(2026, 2, 3, 5, tzinfo=timezone.utc),
        datetime(2026, 2, 3, 17, tzinfo=timezone.utc),
    )

    assert night[0] == datetime(2026, 2, 2, 17, tzinfo=timezone.utc)
    assert night[-1] == datetime(2026, 2, 3, 4, tzinfo=timezone.utc)
    assert semantics.night_economic_boundaries(d) == (
        datetime(2026, 2, 2, 17, tzinfo=timezone.utc),
        datetime(2026, 2, 3, 5, tzinfo=timezone.utc),
    )


def test_decision_boundary_uses_preceding_completed_candle_not_same_label_close() -> None:
    d = date(2026, 2, 3)
    five = semantics.day_decision_time(d)
    seventeen = semantics.day_exit_night_entry_time(d)

    assert semantics.boundary_source_interval_begin(five).hour == 4
    assert semantics.boundary_source_interval_begin(seventeen).hour == 16
    assert semantics.close_available_at(five) == five + timedelta(hours=1)
    assert semantics.close_available_at(seventeen) == seventeen + timedelta(hours=1)
    semantics.assert_no_future_close_at_decisions(d)


def test_previous_day_signal_is_completed_before_next_0500_decision() -> None:
    d = date(2026, 2, 3)
    assert semantics.previous_day_signal_available_at(d) == datetime(
        2026, 2, 2, 17, tzinfo=timezone.utc
    )
    assert semantics.previous_day_signal_available_at(d) < semantics.day_decision_time(d)


def test_frozen_window_contains_context_and_stops_before_sealed_tail() -> None:
    values = semantics.required_interval_begins()
    assert values[0] == datetime(2026, 1, 1, 4, tzinfo=timezone.utc)
    assert values[-1] == datetime(2026, 6, 30, 16, tzinfo=timezone.utc)
    assert all(b - a == timedelta(hours=1) for a, b in zip(values, values[1:]))
    assert semantics.frozen_window_is_contained() is True
    assert values[-1] < semantics.SEALED_HISTORICAL_TAIL_START
    assert values[-1] < semantics.GENUINE_FORWARD_SHADOW_START


def test_gap_detection_is_exact_and_never_interpolates() -> None:
    values = list(semantics.required_interval_begins())
    missing = values.pop(100)
    assert semantics.missing_required_interval_begins(values) == (missing,)


def test_duplicate_and_misaligned_timestamps_fail_closed() -> None:
    aligned = datetime(2026, 1, 2, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="duplicate"):
        semantics.missing_required_interval_begins([aligned, aligned])
    with pytest.raises(ValueError, match="whole UTC hour"):
        semantics.require_hour_aligned_utc(
            datetime(2026, 1, 2, 0, 1, tzinfo=timezone.utc)
        )
    with pytest.raises(ValueError, match="timezone-aware UTC"):
        semantics.require_hour_aligned_utc(datetime(2026, 1, 2, 0))


def test_out_of_window_timestamp_fails_closed() -> None:
    with pytest.raises(ValueError, match="escapes frozen"):
        semantics.missing_required_interval_begins(
            [datetime(2026, 7, 1, 0, tzinfo=timezone.utc)]
        )


def test_contract_keeps_pair_resolution_and_pnl_closed() -> None:
    payload = semantics.load_contract(ROOT)
    rules = payload["preflight_rules"]
    assert rules["archive_attestation_required"] is True
    assert rules["pair_resolution_required_before_row_normalization"] is True
    assert payload["authority"]["pair_resolution_authority"] is False
    assert payload["authority"]["normalized_rows_authority"] is False
    assert payload["authority"]["stage_1_screen_authority"] is False
    assert payload["authority"]["baseline_or_control_pnl_authority"] is False
    assert payload["authority"]["profitability_claim_authority"] is False
    assert payload["authority"]["broker_connected"] is False
    assert payload["authority"]["live_trading"] is False
