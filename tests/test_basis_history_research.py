import basis_history_research as bhr


def _row(ts, close, confirm="1"):
    return [str(ts), "0", "0", "0", str(close), confirm]


def test_paginated_basis_collection_uses_older_cursor_and_exact_overlap(monkeypatch):
    calls = []

    def fake_okx_get(endpoint, params):
        calls.append((endpoint, dict(params)))
        is_mark = "mark-price" in endpoint
        after = params.get("after")
        if after is None:
            return [_row(400, 101 if is_mark else 100), _row(300, 100.5 if is_mark else 100)]
        if after == "300":
            if is_mark:
                return [_row(200, 100.2), _row(100, 100.1)]
            return [_row(200, 100.0), _row(100, 100.0)]
        return []

    monkeypatch.setattr(bhr, "okx_get", fake_okx_get)
    out = bhr.collect_okx_basis_history("BTC", target_points=4, max_pages=3)

    assert out["available"] is True
    assert out["point_count"] == 4
    assert [p["ts"] for p in out["points"]] == [100, 200, 300, 400]
    assert [p["ts"] for p in out["index_points"]] == [100, 200, 300, 400]
    assert out["alignment"] == "exact_shared_timestamp_only"
    assert out["completed_candles_only"] is True
    assert out["interpolation_allowed"] is False
    assert out["trade_authority"] is False
    assert out["promotion_authority"] is False
    assert sum(1 for _, params in calls if params.get("after") == "300") == 2


def test_basis_collection_rejects_sparse_or_unfinished_overlap(monkeypatch):
    def fake_okx_get(endpoint, params):
        if params.get("after") is not None:
            return []
        if "mark-price" in endpoint:
            return [_row(300, 101), _row(200, 100.5, confirm="0"), _row(100, 100.1)]
        return [_row(300, 100), _row(200, 100), _row(50, 100)]

    monkeypatch.setattr(bhr, "okx_get", fake_okx_get)
    out = bhr.collect_okx_basis_history("ETH", target_points=3, max_pages=2)

    assert out["available"] is False
    assert out["reason"] == "insufficient_exact_timestamp_coverage"
    assert [p["ts"] for p in out["points"]] == [300]


def test_basis_collection_fails_closed_on_source_error(monkeypatch):
    def fake_okx_get(endpoint, params):
        if "mark-price" in endpoint:
            raise RuntimeError("blocked")
        return [_row(200, 100), _row(100, 100)]

    monkeypatch.setattr(bhr, "okx_get", fake_okx_get)
    out = bhr.collect_okx_basis_history("SOL", target_points=2, max_pages=1)

    assert out["available"] is False
    assert out["reason"] == "source_error"
    assert out["source_errors"]["mark"] == "RuntimeError"
    assert out["points"] == []


def test_basis_collection_bounds_requested_work(monkeypatch):
    seen = []

    def fake_okx_get(endpoint, params):
        seen.append(dict(params))
        return []

    monkeypatch.setattr(bhr, "okx_get", fake_okx_get)
    out = bhr.collect_okx_basis_history("XRP", target_points=999999, max_pages=999999)

    assert out["target_points"] == bhr.MAX_TARGET_POINTS
    assert out["mark_pages"] <= bhr.MAX_PAGES
    assert out["index_pages"] <= bhr.MAX_PAGES
    assert len(seen) == 2
