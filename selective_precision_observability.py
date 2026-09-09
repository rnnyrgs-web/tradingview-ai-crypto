"""Read-only bridge from resolved prediction-ledger rows to selective precision research.

This layer is descriptive research only. It cannot select production thresholds,
change signal behavior, promote strategies, or authorize trades.
"""

from __future__ import annotations

from db import fetch_resolved_predictions
from selective_precision import selective_precision_summary


def resolved_selective_precision_snapshot(limit: int = 5000) -> dict:
    rows = fetch_resolved_predictions(limit=limit)
    result = selective_precision_summary(rows)
    return {
        **result,
        "resolved_rows_observed": len(rows),
        "source": "prediction_ledger_resolved_only",
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "threshold_selection_authority": False,
    }
