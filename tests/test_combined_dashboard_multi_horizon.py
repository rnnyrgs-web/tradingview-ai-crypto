import combined_dashboard as combined


def test_combined_dashboard_defaults_to_all_horizons(monkeypatch):
    monkeypatch.setattr(combined, "_authorized", lambda _request: True)
    response = combined.combined_dashboard_page(object())
    body = response.body.decode("utf-8")
    assert '/dashboard/signals?horizon=all' in body


def test_combined_dashboard_accepts_each_multi_horizon_view(monkeypatch):
    monkeypatch.setattr(combined, "_authorized", lambda _request: True)
    for horizon in combined.OPPORTUNITY_HORIZONS:
        response = combined.combined_dashboard_page(object(), horizon)
        assert f'/dashboard/signals?horizon={horizon}' in response.body.decode("utf-8")


def test_combined_dashboard_invalid_view_fails_to_all(monkeypatch):
    monkeypatch.setattr(combined, "_authorized", lambda _request: True)
    response = combined.combined_dashboard_page(object(), "invalid")
    assert '/dashboard/signals?horizon=all' in response.body.decode("utf-8")
