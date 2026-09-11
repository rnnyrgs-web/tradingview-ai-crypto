import logging

import research_director_runtime as runtime


def _reset_probe_state():
    with runtime._lock:
        runtime._bybit_probe_ran = False
        runtime._bybit_probe_result = None


def test_director_bybit_probe_runs_once_and_strips_unbounded_fields(monkeypatch):
    calls = []

    def fake_probe():
        calls.append(1)
        return {
            "status": "available",
            "points_observed": 4,
            "symbol": "BTCUSDT",
            "url": "https://should-not-leak.invalid",
            "payload": {"raw": True},
            "trade_authority": True,
        }

    monkeypatch.setattr(runtime, "probe_bybit_oi_access", fake_probe)
    _reset_probe_state()

    first = runtime._ensure_bybit_probe()
    second = runtime._ensure_bybit_probe()

    assert len(calls) == 1
    assert first == second
    assert first["status"] == "available"
    assert first["points_observed"] == 4
    assert first["requests_attempted"] == 1
    assert first["diagnostic_only"] is True
    assert first["used_for_signal_scoring"] is False
    assert first["persistence_authority"] is False
    assert first["paper_trade_authority"] is False
    assert first["trade_authority"] is False
    assert first["promotion_authority"] is False
    assert first["broker_authority"] is False
    assert "symbol" not in first
    assert "url" not in first
    assert "payload" not in first


def test_director_bybit_probe_fail_closes_unknown_status_and_bad_points():
    compact = runtime._compact_bybit_probe(
        {"status": "unexpected", "points_observed": "5", "error": "secret detail"}
    )

    assert compact["status"] == "source_error"
    assert compact["points_observed"] == 0
    assert "error" not in compact
    assert compact["venue_substitution"] is False
    assert compact["trade_authority"] is False


def test_refresh_director_surfaces_only_bounded_probe_result(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "_STATE_PATH", tmp_path / "director.json")
    monkeypatch.setattr(
        runtime,
        "probe_bybit_oi_access",
        lambda: {"status": "valid_empty", "points_observed": 0, "response": "raw"},
    )
    _reset_probe_state()

    payload = runtime.refresh_director({"workers": {}, "supervisor": {}, "observability": {}})

    probe = payload["bybit_oi_access_probe"]
    assert probe["status"] == "valid_empty"
    assert probe["requests_attempted"] == 1
    assert "response" not in probe
    assert payload["research_only"] is True
    assert payload["trade_authority"] is False
    assert payload["promotion_authority"] is False


def test_director_logs_only_sanitized_probe_result(monkeypatch, caplog):
    monkeypatch.setattr(
        runtime,
        "probe_bybit_oi_access",
        lambda: {
            "status": "available",
            "points_observed": 5,
            "symbol": "SECRET_SYMBOL",
            "url": "https://secret.invalid/path",
            "payload": {"secret": True},
        },
    )
    _reset_probe_state()

    with caplog.at_level(logging.INFO, logger=runtime.__name__):
        runtime._ensure_bybit_probe()

    text = caplog.text
    assert "bybit_oi_access_probe" in text
    assert "'status': 'available'" in text
    assert "SECRET_SYMBOL" not in text
    assert "secret.invalid" not in text
    assert "payload" not in text
