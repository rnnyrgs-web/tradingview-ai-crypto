"""Bounded research-only history collector for frozen DATA-FUNDING-001.

Uses only realized OKX funding observations at their actual ``fundingTime`` and
completed OKX index candles. It never assumes a fixed funding interval, repairs
missing observations, or grants signal/paper/promotion/broker authority.
"""

from basis_history_research import _collect_completed_price_history
from market_data import _normalized_history_points, okx_get

MAX_FUNDING_PAGES = 20
MAX_FUNDING_POINTS = 2000
MAX_INDEX_PAGES = 50
MAX_INDEX_POINTS = 5000


def _collect_realized_funding_history(inst_id, target_points, max_pages):
    points_by_ts = {}
    after = None
    previous_oldest = None
    pages = 0
    error_type = None

    while pages < max_pages and len(points_by_ts) < target_points:
        params = {"instId": inst_id, "limit": "100"}
        if after is not None:
            params["after"] = str(after)
        try:
            rows = okx_get("/api/v5/public/funding-rate-history", params)
        except Exception as exc:
            error_type = type(exc).__name__
            break
        pages += 1
        normalized = _normalized_history_points(rows, "fundingTime", "realizedRate")
        if not normalized:
            break
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


def collect_okx_funding_history(base="BTC", funding_target_points=1200,
                                index_target_points=4000,
                                funding_max_pages=15, index_max_pages=45):
    """Collect causal realized-funding inputs and completed index labels.

    Funding timestamps and intervals are accepted exactly as published. Price
    labels are completed 1H OKX index closes. Source errors or insufficient
    history fail closed; no interpolation/forward-fill/nearest matching occurs.
    """
    base = str(base or "").upper().strip()
    if not base or not base.replace("-", "").isalnum():
        raise ValueError("invalid base")
    funding_target = max(2, min(int(funding_target_points), MAX_FUNDING_POINTS))
    index_target = max(2, min(int(index_target_points), MAX_INDEX_POINTS))
    funding_pages_limit = max(1, min(int(funding_max_pages), MAX_FUNDING_PAGES))
    index_pages_limit = max(1, min(int(index_max_pages), MAX_INDEX_PAGES))

    funding, funding_pages, funding_error = _collect_realized_funding_history(
        f"{base}-USDT-SWAP", funding_target, funding_pages_limit
    )
    index, index_pages, index_error = _collect_completed_price_history(
        "/api/v5/market/history-index-candles",
        f"{base}-USDT",
        index_target,
        index_pages_limit,
    )

    source_error = bool(funding_error or index_error)
    # Do not require every requested funding point: funding schedules legitimately
    # vary. Adequacy for each horizon is decided later from causal examples.
    enough_raw_history = len(funding) >= 2 and len(index) >= 2
    if source_error:
        reason = "source_error"
    elif not enough_raw_history:
        reason = "insufficient_raw_history"
    else:
        reason = None

    return {
        "research_only": True,
        "candidate_id": "DATA-FUNDING-001",
        "source": "okx_realized_funding_plus_index",
        "available": bool(enough_raw_history and not source_error),
        "reason": reason,
        "funding_points": funding,
        "index_points": index,
        "funding_point_count": len(funding),
        "index_point_count": len(index),
        "funding_pages": funding_pages,
        "index_pages": index_pages,
        "source_errors": {"funding": funding_error, "index": index_error},
        "feature_window_hours": 24,
        "uses_actual_funding_timestamps": True,
        "assumed_fixed_funding_interval": False,
        "completed_price_candles_only": True,
        "interpolation_allowed": False,
        "forward_fill_allowed": False,
        "nearest_neighbor_matching": False,
        "trade_authority": False,
        "promotion_authority": False,
    }
