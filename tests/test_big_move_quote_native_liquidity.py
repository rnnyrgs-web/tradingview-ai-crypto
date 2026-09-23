from datetime import datetime, timedelta

import pytest

from big_move_quote_native_liquidity import (
    SCHEMA,
    THRESHOLD_QUOTE_ASSET,
    TRANSFORM_ID,
    TRANSFORM_VERSION,
    compute_trailing_quote_asset_liquidity,
    frozen_parameters,
    passes_coarse_liquidity_gate,
    validate_derived_record,
)

DECISION_AT = "2021-02-01T00:00:00Z"
SYMBOL = "BTCUSDT"


def _rows(value=20_000_000.0):
    decision = datetime.fromisoformat(DECISION_AT.replace("Z", "+00:00"))
    return [
        {
            "date": (decision.date() - timedelta(days=offset)).isoformat(),
            "close": 30_000.0,
            "quote_asset_volume": value + offset,
        }
        for offset in range(30, 0, -1)
    ]


def _artifact(rows=None, *, schema=SCHEMA, symbol=SYMBOL):
    return {
        "schema": schema,
        "source_id": "BINANCE_PUBLIC_DATA_SPOT_RAW",
        "venue_symbol": symbol,
        "rows": _rows() if rows is None else rows,
    }


def _record(value):
    return {
        "source_id": TRANSFORM_ID,
        "unit": "USDT",
        "value": value,
        "derivation": {
            "transform_id": TRANSFORM_ID,
            "transform_version": TRANSFORM_VERSION,
            "parameters": frozen_parameters(),
            "inputs": [{"sha256": "0" * 64}],
        },
    }


def test_quote_native_liquidity_recomputes_exact_30d_median_in_usdt():
    artifact = _artifact()
    computed = compute_trailing_quote_asset_liquidity(
        artifact, decision_at=DECISION_AT, expected_symbol=SYMBOL
    )
    expected = (20_000_015.0 + 20_000_016.0) / 2
    assert computed == expected
    assert validate_derived_record(
        _record(expected), artifact, decision_at=DECISION_AT, expected_symbol=SYMBOL
    ) == expected
    assert passes_coarse_liquidity_gate(computed)
    assert THRESHOLD_QUOTE_ASSET == 10_000_000.0


def test_rejects_legacy_usd_labeled_normalized_schema():
    with pytest.raises(ValueError, match="must use"):
        compute_trailing_quote_asset_liquidity(
            _artifact(schema="binance_spot_daily_kline_rows.v1"),
            decision_at=DECISION_AT,
            expected_symbol=SYMBOL,
        )


def test_rejects_quote_volume_usd_alias_even_when_native_value_is_present():
    rows = _rows()
    rows[0]["quote_volume_usd"] = rows[0]["quote_asset_volume"]
    with pytest.raises(ValueError, match="USD-labelled"):
        compute_trailing_quote_asset_liquidity(
            _artifact(rows), decision_at=DECISION_AT, expected_symbol=SYMBOL
        )


def test_rejects_non_usdt_quote_asset_and_symbol_mismatch():
    with pytest.raises(ValueError, match="exactly USDT"):
        compute_trailing_quote_asset_liquidity(
            _artifact(),
            decision_at=DECISION_AT,
            expected_symbol=SYMBOL,
            expected_quote_asset="USD",
        )
    with pytest.raises(ValueError, match="venue_symbol mismatch"):
        compute_trailing_quote_asset_liquidity(
            _artifact(), decision_at=DECISION_AT, expected_symbol="ETHUSDT"
        )
    with pytest.raises(ValueError, match="frozen USDT"):
        compute_trailing_quote_asset_liquidity(
            _artifact(symbol="BTCUSD"), decision_at=DECISION_AT, expected_symbol="BTCUSD"
        )


def test_rejects_missing_duplicate_extra_and_post_decision_dates():
    missing = _rows()[:-1]
    with pytest.raises(ValueError, match="exactly the previous 30"):
        compute_trailing_quote_asset_liquidity(
            _artifact(missing), decision_at=DECISION_AT, expected_symbol=SYMBOL
        )

    duplicate = _rows()
    duplicate[-1] = dict(duplicate[-2])
    with pytest.raises(ValueError, match="duplicate UTC date"):
        compute_trailing_quote_asset_liquidity(
            _artifact(duplicate), decision_at=DECISION_AT, expected_symbol=SYMBOL
        )

    post = _rows()
    post[-1]["date"] = "2021-02-01"
    with pytest.raises(ValueError, match="decision/post-decision"):
        compute_trailing_quote_asset_liquidity(
            _artifact(post), decision_at=DECISION_AT, expected_symbol=SYMBOL
        )

    extra = _rows() + [{
        "date": "2021-01-01",
        "close": 30_000.0,
        "quote_asset_volume": 20_000_000.0,
    }]
    with pytest.raises(ValueError, match="exactly the previous 30"):
        compute_trailing_quote_asset_liquidity(
            _artifact(extra), decision_at=DECISION_AT, expected_symbol=SYMBOL
        )


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), float("-inf")])
def test_rejects_negative_or_nonfinite_quote_asset_volume(bad):
    rows = _rows()
    rows[0]["quote_asset_volume"] = bad
    with pytest.raises(ValueError, match="finite and nonnegative"):
        compute_trailing_quote_asset_liquidity(
            _artifact(rows), decision_at=DECISION_AT, expected_symbol=SYMBOL
        )


def test_rejects_wrong_transform_unit_parameters_and_claimed_value():
    artifact = _artifact()
    computed = compute_trailing_quote_asset_liquidity(
        artifact, decision_at=DECISION_AT, expected_symbol=SYMBOL
    )

    wrong_source = _record(computed)
    wrong_source["source_id"] = "TRAILING_30D_MEDIAN_QUOTE_VOLUME_USD_V1"
    with pytest.raises(ValueError, match="source_id"):
        validate_derived_record(
            wrong_source, artifact, decision_at=DECISION_AT, expected_symbol=SYMBOL
        )

    wrong_unit = _record(computed)
    wrong_unit["unit"] = "USD"
    with pytest.raises(ValueError, match="explicit USDT"):
        validate_derived_record(
            wrong_unit, artifact, decision_at=DECISION_AT, expected_symbol=SYMBOL
        )

    wrong_version = _record(computed)
    wrong_version["derivation"]["transform_version"] = "1"
    with pytest.raises(ValueError, match="transform_version"):
        validate_derived_record(
            wrong_version, artifact, decision_at=DECISION_AT, expected_symbol=SYMBOL
        )

    wrong_params = _record(computed)
    wrong_params["derivation"]["parameters"]["window_days"] = 29
    with pytest.raises(ValueError, match="parameters"):
        validate_derived_record(
            wrong_params, artifact, decision_at=DECISION_AT, expected_symbol=SYMBOL
        )

    wrong_value = _record(computed + 1)
    with pytest.raises(ValueError, match="does not equal"):
        validate_derived_record(
            wrong_value, artifact, decision_at=DECISION_AT, expected_symbol=SYMBOL
        )


def test_coarse_gate_is_usdt_not_strict_tradability_or_usd_equivalence():
    assert not passes_coarse_liquidity_gate(9_999_999.99)
    assert passes_coarse_liquidity_gate(10_000_000)
    with pytest.raises(ValueError):
        passes_coarse_liquidity_gate(float("nan"))
