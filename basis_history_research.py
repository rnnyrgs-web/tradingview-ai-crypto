"""Research-only OKX mark/index basis history collection for DATA-BASIS-001.

This module exists only to make the frozen COORD-DATA-003 falsification executable
with enough chronological history. It has no production, paper, promotion, broker,
or signal authority.
"""

from market_data import _aligned_basis_history, _normalized_price_candles, okx_get


# The current 7d result has only 10 non-overlapping OOS samples. Permit a larger
# but still hard-bounded window so the next rejection-oriented run can nearly
# double independent 7d OOS evidence without changing the feature, split, or
# thresholds. With OKX's 100-row pages, 85 pages safely covers an 8,000-point
# target plus the existing one-page completed-candle slack.
MAX_PAGES = 85
MAX_TARGET_POINTS = 8000


def _collect_completed_price_history(endpoint, inst_id, target_points, max_pages):
    points_by_ts = {}
    after = None
    previous_oldest = None
    pages = 0
    error_type = None
    completion_slack_pages = 0

    while pages < min(MAX_PAGES, max_pages + completion_slack_pages) and len(points_by_ts) < target_points:
        params = {"instId": inst_id, "bar": "1H", "limit": "100"}
        if after is not None:
            params["after"] = str(after)
        try:
            rows = okx_get(endpoint, params)
        except Exception as exc:
            error_type = type(exc).__name__
            break

        pages += 1
        normalized = _normalized_price_candles(rows)
        if not normalized:
            break
        # The newest OKX history page can contain the still-open 1H candle. Our
        # normalizer correctly removes it, which otherwise leaves an exact
        # N*100-page collection one completed candle short forever. Permit one
        # additional bounded page only when source rows were filtered. This does
        # not interpolate, forward-fill, relax exact timestamp matching, or alter
        # the requested completed-point target.
        if len(normalized) < len(rows):
            completion_slack_pages = 1
        for point in normalized:
            points_by_ts[point["ts"]] = point["value"]

        oldest = min(point["ts"] for point in normalized)
        if previous_oldest is not None and oldest >= previous_oldest:
            break
        previous_oldest = oldest
        after = oldest

    points = [{"ts": ts, "value": points_by_ts[ts]} for ts in sorted(points_by_ts)]
    if len(points) > target_points:
        points = points[-target_points:]
    return points, pages, error_type


def collect_okx_basis_history(base, target_points=1000, max_pages=20):
    """Collect exact-timestamp completed 1H OKX mark/index basis history.

    Pagination is bounded and uses OKX's ``after`` cursor to request older data.
    Mark and index candles are never interpolated, forward-filled, or nearest-
    neighbour matched. A source error or insufficient exact overlap fails closed.

    ``index_points`` are returned only so a separate research-only falsifier can
    form timestamp-exact future-return labels. They are targets, not features,
    and this collector itself performs no outcome inspection or signal selection.
    """
    base = str(base or "").upper().strip()
    if not base or not base.replace("-", "").isalnum():
        raise ValueError("invalid base")
    target = max(2, min(int(target_points), MAX_TARGET_POINTS))
    pages_limit = max(1, min(int(max_pages), MAX_PAGES))

    mark_points, mark_pages, mark_error = _collect_completed_price_history(
        "/api/v5/market/history-mark-price-candles",
        f"{base}-USDT-SWAP",
        target,
        pages_limit,
    )
    index_points, index_pages, index_error = _collect_completed_price_history(
        "/api/v5/market/history-index-candles",
        f"{base}-USDT",
        target,
        pages_limit,
    )
    basis_points = _aligned_basis_history(mark_points, index_points)
    if len(basis_points) > target:
        basis_points = basis_points[-target:]

    source_error = bool(mark_error or index_error)
    enough_overlap = len(basis_points) >= target
    if source_error:
        reason = "source_error"
    elif not enough_overlap:
        reason = "insufficient_exact_timestamp_coverage"
    else:
        reason = None

    return {
        "research_only": True,
        "candidate_id": "DATA-BASIS-001",
        "source": "okx_mark_vs_index",
        "bar": "1H",
        "available": bool(enough_overlap and not source_error),
        "reason": reason,
        "target_points": target,
        "point_count": len(basis_points),
        "mark_point_count": len(mark_points),
        "index_point_count": len(index_points),
        "mark_pages": mark_pages,
        "index_pages": index_pages,
        "source_errors": {
            "mark": mark_error,
            "index": index_error,
        },
        "points": basis_points,
        "index_points": index_points,
        "alignment": "exact_shared_timestamp_only",
        "completed_candles_only": True,
        "interpolation_allowed": False,
        "trade_authority": False,
        "promotion_authority": False,
    }
