import combined_dashboard as combined


def test_combined_dashboard_defaults_to_unified_all_horizons(monkeypatch):
    monkeypatch.setattr(combined, "_authorized", lambda _request: True)
    monkeypatch.setattr(combined, "_unified_rows", lambda: [])

    response = combined.combined_dashboard_page(object())
    body = response.body.decode("utf-8")

    assert "unified opportunities" in body
    assert "All Signals" in body
    assert "/dashboard/signals?horizon=" not in body


def test_combined_dashboard_legacy_horizon_parameter_keeps_unified_view(monkeypatch):
    monkeypatch.setattr(combined, "_authorized", lambda _request: True)
    monkeypatch.setattr(combined, "_unified_rows", lambda: [])

    baseline = combined.combined_dashboard_page(object()).body
    for horizon in combined.OPPORTUNITY_HORIZONS:
        assert combined.combined_dashboard_page(object(), horizon).body == baseline


def test_combined_dashboard_invalid_horizon_parameter_keeps_unified_view(monkeypatch):
    monkeypatch.setattr(combined, "_authorized", lambda _request: True)
    monkeypatch.setattr(combined, "_unified_rows", lambda: [])

    assert combined.combined_dashboard_page(object(), "invalid").body == combined.combined_dashboard_page(object()).body
