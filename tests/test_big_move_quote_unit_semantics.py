import io
import zipfile

import pytest

from big_move_binance_archive_binding import (
    parse_spot_1d_kline_archive,
    verify_normalized_daily_rows,
)


def _zip(member: str, line: str) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, line + "\n")
    return stream.getvalue()


def _row(*, quote_asset_volume: str = "12345678.9") -> str:
    return ",".join(
        [
            "1704067200000",
            "100.0",
            "120.0",
            "90.0",
            "110.0",
            "1000.0",
            "1704153599999",
            quote_asset_volume,
            "42",
            "500.0",
            "6000000.0",
            "0",
        ]
    )


def test_binance_quote_asset_volume_is_not_labeled_usd_without_conversion():
    """Binance kline field 7 is quote-asset volume, not authenticated USD volume."""
    raw = _zip("BTCUSDT-1d-2024-01.csv", _row())

    parsed = parse_spot_1d_kline_archive(
        raw,
        decision_at="2024-01-03T00:00:00Z",
    )

    assert parsed[0]["quote_asset_volume"] == "12345678.9"
    assert "quote_volume_usd" not in parsed[0]


def test_normalized_binding_accepts_provider_native_quote_asset_volume():
    """The source-native binder should bind the provider unit before any USD transform."""
    raw = _zip("BTCUSDT-1d-2024-01.csv", _row())

    bound = verify_normalized_daily_rows(
        raw,
        [
            {
                "date": "2024-01-01",
                "close": "110.0",
                "quote_asset_volume": "12345678.9",
            }
        ],
        decision_at="2024-01-03T00:00:00Z",
    )

    assert bound[0]["quote_asset_volume"] == "12345678.9"
    assert "quote_volume_usd" not in bound[0]


def test_legacy_usd_labeled_row_fails_closed_without_explicit_conversion():
    """Raw BTCUSDT quote volume must not satisfy a field claiming USD semantics."""
    raw = _zip("BTCUSDT-1d-2024-01.csv", _row())

    with pytest.raises(ValueError):
        verify_normalized_daily_rows(
            raw,
            [
                {
                    "date": "2024-01-01",
                    "close": "110.0",
                    "quote_volume_usd": "12345678.9",
                }
            ],
            decision_at="2024-01-03T00:00:00Z",
        )
