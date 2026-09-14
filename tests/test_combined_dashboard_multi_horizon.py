import combined_dashboard as combined


def _empty_metrics():
    return combined._closed_metrics([])


def _stub_dashboard_sources(monkeypatch):
    monkeypatch.setattr(combined, "_authorized", lambda _request: True)
    monkeypatch.setattr(combined, "_crypto_rows", lambda: ([], 0))
    monkeypatch.setattr(combined, "fetch_cross_asset_leaders", lambda _limit=30: [])
    monkeypatch.setattr(
        combined,
        "_paper_snapshot",
        lambda: {
            "data_ok": True,
            "error": None,
            "status": {},
            "positions": [],
            "clean_closed": [],
            "audit_closed": [],
            "forward": _empty_metrics(),
            "legacy": _empty_metrics(),
            "unverified": _empty_metrics(),
            "forward_positions": [],
            "legacy_positions": [],
            "unverified_positions": [],
            "forward_open_pnl": 0.0,
            "legacy_open_pnl": 0.0,
            "unverified_open_pnl": 0.0,
            "forward_total_pnl": 0.0,
            "mark_failures": 0,
        },
    )


def _body(monkeypatch, horizon="all"):
    _stub_dashboard_sources(monkeypatch)
    return combined.combined_dashboard_page(object(), horizon).body.decode("utf-8")


def test_combined_dashboard_defaults_to_unified_all_markets(monkeypatch):
    body = _body(monkeypatch)
    assert "Current Trading System" in body
    assert "Current Opportunities &amp; Research" in body or "Current Opportunities & Research" in body
    assert "Open Paper Trades" in body
    assert "DATA INTEGRITY" in body
    assert "CUTOVER" in body
    assert "NOT VERIFIED" in body
    assert "/dashboard/signals?horizon=" not in body


def test_combined_dashboard_legacy_horizon_parameter_keeps_unified_view(monkeypatch):
    for horizon in combined.OPPORTUNITY_HORIZONS:
        body = _body(monkeypatch, horizon)
        assert "Current Opportunities &amp; Research" in body or "Current Opportunities & Research" in body
        assert f"horizon={horizon}" not in body


def test_combined_dashboard_invalid_horizon_parameter_keeps_unified_view(monkeypatch):
    body = _body(monkeypatch, "invalid")
    assert "Current Trading System" in body
    assert "DATA INTEGRITY" in body
