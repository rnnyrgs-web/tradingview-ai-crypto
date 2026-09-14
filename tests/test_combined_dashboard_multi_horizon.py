import combined_dashboard as combined


def _stub_dashboard_sources(monkeypatch):
    monkeypatch.setattr(combined, "_authorized", lambda _request: True)
    monkeypatch.setattr(combined, "_crypto_rows", lambda: [])
    monkeypatch.setattr(combined, "fetch_cross_asset_leaders", lambda _limit=30: [])
    monkeypatch.setattr(
        combined,
        "_paper_snapshot",
        lambda: {
            "status": {},
            "positions": [],
            "closed": [],
            "open_pnl": 0.0,
            "total_pnl": 0.0,
            "equity": 100000.0,
            "win_rate": None,
        },
    )


def test_combined_dashboard_defaults_to_unified_all_markets(monkeypatch):
    _stub_dashboard_sources(monkeypatch)

    response = combined.combined_dashboard_page(object())
    body = response.body.decode("utf-8")

    assert "Market Opportunity Engine" in body
    assert "Top Expected Moves Across Markets" in body
    assert "Open System Trades &amp; P&amp;L" in body or "Open System Trades & P&L" in body
    assert "/dashboard/signals?horizon=" not in body


def test_combined_dashboard_legacy_horizon_parameter_keeps_unified_view(monkeypatch):
    _stub_dashboard_sources(monkeypatch)

    baseline = combined.combined_dashboard_page(object()).body
    for horizon in combined.OPPORTUNITY_HORIZONS:
        assert combined.combined_dashboard_page(object(), horizon).body == baseline


def test_combined_dashboard_invalid_horizon_parameter_keeps_unified_view(monkeypatch):
    _stub_dashboard_sources(monkeypatch)

    assert combined.combined_dashboard_page(object(), "invalid").body == combined.combined_dashboard_page(object()).body
