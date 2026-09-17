"""Canonical economic result schema and fail-closed research lifecycle gates."""

from __future__ import annotations

from math import isfinite
from typing import Any


ECONOMIC_FIELDS = (
    "gross_return",
    "net_return",
    "net_expectancy_pct",
    "profit_factor",
    "sharpe",
    "sortino",
    "max_drawdown_pct",
    "calmar",
    "win_rate",
    "average_winner_pct",
    "average_loser_pct",
    "payoff_ratio",
    "trade_count",
    "turnover",
    "exposure",
    "cost_paid",
)
BREAKDOWN_FIELDS = (
    "long_short_breakdown",
    "asset_breakdown",
    "regime_breakdown",
    "monthly_returns",
    "rolling_expectancy",
    "rolling_sharpe",
)


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _trade_count(raw: dict) -> int | None:
    value = raw.get("trade_count", raw.get("trades"))
    number = _finite_float(value)
    if number is None or number < 0 or int(number) != number:
        return None
    return int(number)


def normalize_economic_result(raw: dict) -> dict:
    """Normalize every research engine into one stable, comparison-safe schema."""
    raw = raw if isinstance(raw, dict) else {}
    normalized = {field: None for field in ECONOMIC_FIELDS}
    for field in ECONOMIC_FIELDS:
        if field == "trade_count":
            normalized[field] = _trade_count(raw)
        else:
            normalized[field] = _finite_float(raw.get(field))
    for field in BREAKDOWN_FIELDS:
        value = raw.get(field)
        if field in {"rolling_expectancy", "rolling_sharpe"}:
            normalized[field] = list(value) if isinstance(value, list) else []
        else:
            normalized[field] = dict(value) if isinstance(value, dict) else {}
    return normalized


def _positive_stage(stage: Any) -> bool:
    if not isinstance(stage, dict):
        return False
    expectancy = _finite_float(stage.get("net_expectancy_pct"))
    profit_factor = _finite_float(stage.get("profit_factor"))
    trades = _trade_count(stage)
    return bool(
        expectancy is not None
        and expectancy > 0
        and profit_factor is not None
        and profit_factor > 1.0
        and trades is not None
        and trades > 0
    )


def _explicit_negative_stage(stage: Any) -> bool:
    if not isinstance(stage, dict):
        return False
    expectancy = _finite_float(stage.get("net_expectancy_pct"))
    profit_factor = _finite_float(stage.get("profit_factor"))
    return bool(
        expectancy is not None
        and expectancy <= 0
        or profit_factor is not None
        and profit_factor <= 1.0
    )


def evaluate_candidate_stage(evidence: dict) -> dict:
    """Evaluate a candidate monotonically through scientific gates without live authority."""
    evidence = evidence if isinstance(evidence, dict) else {}
    research = evidence.get("research")
    validation = evidence.get("validation")
    robustness = evidence.get("robustness")
    multiple_testing = evidence.get("multiple_testing")
    dataset = evidence.get("dataset")
    oos = evidence.get("oos")
    reproduction = evidence.get("independent_reproduction")
    forward = evidence.get("forward")

    rejection_reasons: list[str] = []
    blocking_gates: list[str] = []

    if not isinstance(dataset, dict) or dataset.get("certified") is not True:
        rejection_reasons.append("dataset_not_certified")

    for name, stage in (("research", research), ("validation", validation)):
        if isinstance(stage, dict) and stage.get("chronology_safe") is not True:
            rejection_reasons.append(f"{name}_chronology_unsafe")
        if _explicit_negative_stage(stage):
            rejection_reasons.append(f"{name}_economics_failed")

    if isinstance(oos, dict):
        if oos.get("opened") is True and oos.get("frozen_before_open") is not True:
            rejection_reasons.append("oos_opened_without_frozen_contract")
        if oos.get("opened") is True and _explicit_negative_stage(oos):
            rejection_reasons.append("oos_economics_failed")

    if isinstance(robustness, dict):
        for key in (
            "parameter_neighborhood_stable",
            "cost_2x_positive",
            "cost_3x_acceptable",
            "not_single_trade_dominated",
            "not_single_asset_dominated",
        ):
            if key in robustness and robustness.get(key) is not True:
                rejection_reasons.append(f"robustness:{key}")

    if isinstance(multiple_testing, dict) and "pass" in multiple_testing and multiple_testing.get("pass") is not True:
        rejection_reasons.append("multiple_testing_failed")

    if rejection_reasons:
        return {
            "state": "REJECTED",
            "blocking_gates": [],
            "rejection_reasons": rejection_reasons,
            "production_candidate": False,
            "real_money_trade_authority": False,
        }

    if not _positive_stage(research):
        blocking_gates.append("research")
        return {
            "state": "RESEARCH_PASS",
            "blocking_gates": blocking_gates,
            "rejection_reasons": [],
            "production_candidate": False,
            "real_money_trade_authority": False,
        }

    if not _positive_stage(validation) or not isinstance(validation, dict) or validation.get("chronology_safe") is not True:
        blocking_gates.append("validation")
        return {
            "state": "RESEARCH_PASS",
            "blocking_gates": blocking_gates,
            "rejection_reasons": [],
            "production_candidate": False,
            "real_money_trade_authority": False,
        }

    required_robustness = (
        "parameter_neighborhood_stable",
        "cost_2x_positive",
        "cost_3x_acceptable",
        "not_single_trade_dominated",
        "not_single_asset_dominated",
    )
    robustness_pass = isinstance(robustness, dict) and all(robustness.get(key) is True for key in required_robustness)
    multiple_testing_pass = isinstance(multiple_testing, dict) and multiple_testing.get("pass") is True
    if not robustness_pass or not multiple_testing_pass:
        if not robustness_pass:
            blocking_gates.append("robustness")
        if not multiple_testing_pass:
            blocking_gates.append("multiple_testing")
        return {
            "state": "VALIDATION_PASS",
            "blocking_gates": blocking_gates,
            "rejection_reasons": [],
            "production_candidate": False,
            "real_money_trade_authority": False,
        }

    if not isinstance(oos, dict) or oos.get("opened") is not True:
        blocking_gates.append("untouched_oos")
        return {
            "state": "ROBUSTNESS_PASS",
            "blocking_gates": blocking_gates,
            "rejection_reasons": [],
            "production_candidate": False,
            "real_money_trade_authority": False,
        }

    if not _positive_stage(oos) or oos.get("frozen_before_open") is not True:
        # Missing OOS economics is not silently promoted. Explicitly bad economics was
        # rejected above; incomplete evidence remains blocked at robustness.
        blocking_gates.append("untouched_oos")
        return {
            "state": "ROBUSTNESS_PASS",
            "blocking_gates": blocking_gates,
            "rejection_reasons": [],
            "production_candidate": False,
            "real_money_trade_authority": False,
        }

    if not isinstance(reproduction, dict) or reproduction.get("pass") is not True:
        blocking_gates.append("independent_reproduction")
        return {
            "state": "OOS_PASS",
            "blocking_gates": blocking_gates,
            "rejection_reasons": [],
            "production_candidate": False,
            "real_money_trade_authority": False,
        }

    if not isinstance(forward, dict) or forward.get("pass") is not True:
        blocking_gates.append("genuine_forward")
        return {
            "state": "FORWARD_PENDING",
            "blocking_gates": blocking_gates,
            "rejection_reasons": [],
            "production_candidate": False,
            "real_money_trade_authority": False,
        }

    return {
        "state": "FORWARD_PASS",
        "blocking_gates": [],
        "rejection_reasons": [],
        "production_candidate": True,
        "real_money_trade_authority": False,
    }
