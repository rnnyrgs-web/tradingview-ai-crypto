import httpx

import market_data as md


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {"code": "0", "data": [{"ok": True}]}


def test_okx_get_retries_bounded_transient_timeout(monkeypatch):
    calls = {"count": 0}

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] < 3:
            raise httpx.ReadTimeout("temporary")
        return _Response()

    monkeypatch.setattr(md.http, "get", fake_get)
    monkeypatch.setattr(md.time, "sleep", lambda _: None)
    assert md.okx_get("/test") == [{"ok": True}]
    assert calls["count"] == md.OKX_MAX_ATTEMPTS


def test_history_reuses_identical_deep_fetch_without_sharing_mutation(monkeypatch):
    md.clear_history_cache()
    calls = {"count": 0}
    page = [["1000", "1", "2", "0.5", "1.5", "10", "0", "15", "1"]]

    def fake_okx_get(*args, **kwargs):
        calls["count"] += 1
        return page

    monkeypatch.setattr(md, "okx_get", fake_okx_get)
    first = md.get_history("BTC-USDT", "1H", 100)
    first[0]["close"] = 999
    second = md.get_history("BTC-USDT", "1H", 100)
    assert calls["count"] == 1
    assert second[0]["close"] == 1.5
