import uuid
from datetime import datetime, timedelta, timezone

import ffrizz_secondary_runner as runner
import research_adaptive_accuracy_runner as adaptive_runner


def _report(action="SHADOW_BUY", direction="LONG", horizon="6h"):
    return {
        "horizon_results": [
            {
                "horizon": horizon,
                "current_shadow_signals": [
                    {
                        "symbol": "BTC-USDT",
                        "action": action,
                        "direction": direction,
                        "entry_price": 100.0,
                        "score": 3.5,
                        "bar": "1H",
                        "independent_family_agreement": 3,
                        "available_family_count": 4,
                        "families": [{"family": "pb_ema", "score": 1.2}],
                    }
                ],
            }
        ]
    }


def test_forward_rows_use_exact_horizon_deadline_and_ffrizz_identity():
    now = datetime(2026, 9, 10, 3, 17, tzinfo=timezone.utc)
    rows = runner.build_forward_ledger_rows(_report(), generated_at=now)
    assert len(rows) == 1
    row = rows[0]
    assert datetime.fromisoformat(row["due_at"]) == now + timedelta(hours=6)
    assert row["strategy_identity"]["system"] == "FFRIZZ_SECONDARY_V1"
    assert row["action_at_forecast"] == "WAIT"
    assert row["direction"] == "LONG"
    assert row["calibration"]["shadow_action"] == "SHADOW_BUY"
    assert row["calibration"]["production_action_semantics"] == "WAIT"
    assert row["calibration"]["research_only"] is True
    assert row["calibration"]["trade_authority"] is False
    assert row["calibration"]["historical_oi_backfill_used"] is False


def test_wait_rows_are_never_persistable_forward_evidence():
    now = datetime(2026, 9, 10, 3, 17, tzinfo=timezone.utc)
    assert runner.build_forward_ledger_rows(_report(action="WAIT"), generated_at=now) == []


def test_same_full_horizon_bucket_has_stable_uuid_scan_id_but_next_bucket_changes():
    first = datetime(2026, 9, 10, 1, 0, tzinfo=timezone.utc)
    same_bucket = datetime(2026, 9, 10, 5, 59, tzinfo=timezone.utc)
    next_bucket = datetime(2026, 9, 10, 6, 1, tzinfo=timezone.utc)
    a = runner.build_forward_ledger_rows(_report(), generated_at=first)[0]
    b = runner.build_forward_ledger_rows(_report(), generated_at=same_bucket)[0]
    c = runner.build_forward_ledger_rows(_report(), generated_at=next_bucket)[0]
    assert str(uuid.UUID(a["scan_id"])) == a["scan_id"]
    assert a["scan_id"] == b["scan_id"]
    assert c["scan_id"] != a["scan_id"]


def test_runner_persists_only_eligible_rows(monkeypatch):
    candles = []
    price = 100.0
    for i in range(260):
        price += 0.2
        candles.append({"ts": (i + 1) * 3600000, "open": price - 0.2, "high": price + 0.5, "low": price - 0.5, "close": price, "volume": 1000 + i})
    monkeypatch.setattr(runner, "build_universe", lambda: [{"symbol": "BTC-USDT", "base": "BTC"}])
    monkeypatch.setattr(runner, "get_history", lambda *args, **kwargs: candles)
    monkeypatch.setattr(runner, "get_derivatives_history", lambda *args, **kwargs: {"open_interest_history": {"binance": []}})
    monkeypatch.setattr(runner, "chronological_backtest", lambda *args, **kwargs: {"signals": 0, "accuracy": None, "mean_net_pct": None})
    monkeypatch.setattr(runner, "score_shadow_signal", lambda candles, oi, horizon: {
        "system": "FFRIZZ_SECONDARY_V1", "horizon": horizon, "bar": "1H", "direction": "LONG",
        "action": "SHADOW_BUY", "score": 3.5, "independent_family_agreement": 3,
        "available_family_count": 3, "families": [], "research_only": True, "shadow_only": True,
        "trade_authority": False, "paper_trade_authority": False, "promotion_authority": False, "broker_authority": False,
    })
    captured = []
    monkeypatch.setattr(runner, "insert_prediction_ledger", lambda rows: captured.extend(rows))
    report = runner.run(persist=True, generated_at=datetime(2026, 9, 10, 3, 0, tzinfo=timezone.utc))
    assert len(captured) == 6
    assert {row["horizon"] for row in captured} == {"6h", "12h", "24h", "48h", "72h", "7d"}
    assert all(str(uuid.UUID(row["scan_id"])) == row["scan_id"] for row in captured)
    assert all(row["action_at_forecast"] == "WAIT" for row in captured)
    assert all(row["calibration"]["shadow_action"] == "SHADOW_BUY" for row in captured)
    assert report["forward_evidence"]["wait_rows_persisted"] is False
    assert report["trade_authority"] is False
    assert report["paper_trade_authority"] is False
    assert report["broker_authority"] is False


def test_adaptive_lane_collects_ffrizz_without_granting_authority(monkeypatch):
    monkeypatch.setattr(adaptive_runner, "run_ffrizz_secondary", lambda persist=True: {
        "system": "FFRIZZ_SECONDARY_V1",
        "generated_at": "2026-09-10T03:00:00+00:00",
        "forward_evidence": {
            "eligible_shadow_forecasts": 4,
            "non_overlapping_full_horizon_buckets": True,
            "wait_rows_persisted": False,
            "historical_oi_backfill_used": False,
        },
    })
    result = adaptive_runner._ffrizz_forward_collection()
    assert result["ok"] is True
    assert result["eligible_shadow_forecasts"] == 4
    assert result["non_overlapping_full_horizon_buckets"] is True
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
