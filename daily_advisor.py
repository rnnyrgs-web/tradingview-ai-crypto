from collections import Counter

from news_engine import for_base


def _base(symbol):
    text = str(symbol or "").upper()
    return text.split("-")[0].split("/")[0].strip()


def _pct(a, b):
    try:
        a, b = float(a), float(b)
        return (b / a - 1.0) * 100.0 if a else None
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _item(row, news):
    entry = row.get("entry_price")
    t1 = row.get("target_1")
    t2 = row.get("target_2")
    stop = row.get("stop_loss")
    action = str(row.get("action") or "WAIT").upper()
    live_validated = action == "TRADE"
    base = _base(row.get("symbol"))
    headlines = for_base(base, news)[:5] if base else []
    return {
        "rank": row.get("rank"),
        "symbol": row.get("symbol"),
        "horizon": row.get("horizon"),
        "direction": row.get("direction"),
        "advice": "BUY" if live_validated and row.get("direction") == "LONG" else "SELL" if live_validated and row.get("direction") == "SHORT" else "WAIT",
        "status": "LIVE_VALIDATED" if live_validated else "RESEARCH_ONLY",
        "entry_price": entry,
        "entry_zone": [row.get("entry_low"), row.get("entry_high")],
        "stop_loss": stop,
        "targets": [t1, t2],
        "expected_move_pct": {
            "target_1": _pct(entry, t1),
            "target_2": _pct(entry, t2),
            "invalidation": _pct(entry, stop),
        },
        "evidence_score": row.get("evidence_score"),
        "quant_score": row.get("quant_score"),
        "market_regime": row.get("market_regime"),
        "risk_reward": row.get("risk_reward"),
        "reasoning": row.get("reasoning"),
        "calibration": row.get("calibration"),
        "news": headlines,
    }


def build_daily_advice(opportunities_by_horizon, news, max_items=20):
    """Build a daily market brief without creating a second trade-approval path.

    Existing opportunity rows are already fail-closed by production validation.
    This layer may explain/rank them, but it never upgrades WAIT to BUY/SELL.
    """
    rows = []
    for horizon in ("24h", "7d"):
        rows.extend(opportunities_by_horizon.get(horizon) or [])

    items = [_item(row, news or []) for row in rows]
    items.sort(key=lambda x: (x.get("evidence_score") or 0.0), reverse=True)
    items = items[: max(1, min(int(max_items), 40))]

    regimes = Counter(str(x.get("market_regime") or "UNKNOWN") for x in items)
    directions = Counter(str(x.get("direction") or "UNKNOWN") for x in items)
    live_count = sum(1 for x in items if x["status"] == "LIVE_VALIDATED")
    return {
        "ok": True,
        "scope": "broad-market-ranked-opportunities",
        "safety": {
            "fail_closed": True,
            "can_upgrade_wait": False,
            "live_advice_requires_existing_validated_trade": True,
        },
        "market_summary": {
            "items": len(items),
            "live_validated": live_count,
            "research_only": len(items) - live_count,
            "dominant_regime": regimes.most_common(1)[0][0] if regimes else "UNKNOWN",
            "long_bias_count": directions.get("LONG", 0),
            "short_bias_count": directions.get("SHORT", 0),
            "news_headlines_scanned": len(news or []),
        },
        "advice": items,
    }
