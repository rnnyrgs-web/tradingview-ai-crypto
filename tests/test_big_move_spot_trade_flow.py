from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import io
import zipfile

import pytest

from big_move_spot_trade_flow import build_spot_trade_flow_features


UTC = timezone.utc
DECISION = datetime(2026, 1, 15, tzinfo=UTC)


def _zip_csv(member_name: str, rows: list[list[str]]) -> bytes:
    body = "\n".join(",".join(row) for row in rows) + "\n"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member_name, body.encode("utf-8"))
    return buffer.getvalue()


def _epoch_us(dt: datetime) -> str:
    return str(int(dt.timestamp() * 1_000_000))


def _archive(day: date, day_index: int, *, symbol: str = "AAAUSDT"):
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    if day_index < 7:
        specs = [
            (100 + day_index, "1", "1000", False),
            (101 + day_index, "1", "1000", True),
        ]
    else:
        specs = [
            (100 + day_index, "1", "2000", False),
            (101 + day_index, "1", "1000", False),
            (102 + day_index, "1", "1000", True),
        ]
    rows = []
    for offset, (price, qty, quote_qty, buyer_maker) in enumerate(specs):
        trade_id = day_index * 100 + offset + 1
        event_at = start + timedelta(hours=1 + offset)
        rows.append(
            [
                str(trade_id),
                str(price),
                qty,
                quote_qty,
                _epoch_us(event_at),
                "true" if buyer_maker else "false",
                "true",
            ]
        )
    archive_name = f"{symbol}-trades-{day.isoformat()}.zip"
    member_name = archive_name[:-4] + ".csv"
    raw = _zip_csv(member_name, rows)
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "date": day.isoformat(),
        "archive_name": archive_name,
        "archive_bytes": raw,
        "checksum_bytes": f"{digest}  {archive_name}\n".encode("utf-8"),
    }


def _archives():
    first = DECISION.date() - timedelta(days=14)
    return [_archive(first + timedelta(days=index), index) for index in range(14)]


def test_builds_frozen_two_window_spot_flow_features_from_raw_archives():
    result = build_spot_trade_flow_features(
        symbol="AAAUSDT",
        decision_at="2026-01-15T00:00:00Z",
        daily_archives=_archives(),
    )

    assert result["schema"] == "two_x_spot_trade_flow_features.v1"
    assert result["contract_id"] == "2X-SPOT-FLOW-001-v1"
    assert result["coverage"]["days"] == 14
    assert len(result["coverage"]["archive_sha256_by_date"]) == 14
    assert len(result["coverage"]["source_set_sha256"]) == 64

    assert result["previous_7d"]["quote_notional_usdt"] == "14000"
    assert result["current_7d"]["quote_notional_usdt"] == "28000"
    assert result["previous_7d"]["trade_count"] == 14
    assert result["current_7d"]["trade_count"] == 21
    assert result["previous_7d"]["aggressive_buy_share"] == "0.5"
    assert result["current_7d"]["aggressive_buy_share"] == "0.75"
    assert result["current_7d"]["net_aggressive_share"] == "0.5"
    assert result["changes"]["quote_notional_acceleration"] == "1"
    assert result["changes"]["trade_count_acceleration"] == "0.5"
    assert result["changes"]["aggressive_buy_share_change"] == "0.25"
    assert result["changes"]["net_aggressive_share_change"] == "0.5"

    assert result["strict_tradability_established"] is False
    assert result["outcome_label_attached"] is False
    assert result["prediction_authority"] is False


def test_missing_day_fails_closed_instead_of_becoming_zero_flow():
    archives = _archives()
    archives.pop(5)
    with pytest.raises(ValueError, match="exactly 14"):
        build_spot_trade_flow_features(
            symbol="AAAUSDT",
            decision_at="2026-01-15T00:00:00Z",
            daily_archives=archives,
        )


def test_wrong_coverage_date_fails_closed():
    archives = _archives()
    archives[-1] = _archive(date(2025, 12, 31), 99)
    with pytest.raises(ValueError, match="coverage must exactly match"):
        build_spot_trade_flow_features(
            symbol="AAAUSDT",
            decision_at="2026-01-15T00:00:00Z",
            daily_archives=archives,
        )


def test_checksum_mismatch_is_rejected():
    archives = _archives()
    archives[0]["checksum_bytes"] = ("0" * 64 + "  " + archives[0]["archive_name"] + "\n").encode()
    with pytest.raises(ValueError, match="digest does not match"):
        build_spot_trade_flow_features(
            symbol="AAAUSDT",
            decision_at="2026-01-15T00:00:00Z",
            daily_archives=archives,
        )


def test_archive_trade_timestamp_must_belong_to_its_utc_date():
    archives = _archives()
    day = date(2026, 1, 1)
    archive_name = f"AAAUSDT-trades-{day.isoformat()}.zip"
    member = archive_name[:-4] + ".csv"
    outside = datetime(2026, 1, 2, 1, tzinfo=UTC)
    raw = _zip_csv(member, [["1", "100", "1", "100", _epoch_us(outside), "false", "true"]])
    digest = hashlib.sha256(raw).hexdigest()
    archives[0] = {
        "date": day.isoformat(),
        "archive_name": archive_name,
        "archive_bytes": raw,
        "checksum_bytes": f"{digest}  {archive_name}\n".encode(),
    }
    with pytest.raises(ValueError, match="outside the archive UTC date"):
        build_spot_trade_flow_features(
            symbol="AAAUSDT",
            decision_at="2026-01-15T00:00:00Z",
            daily_archives=archives,
        )


def test_non_midnight_decision_is_rejected_to_avoid_partial_day_ambiguity():
    with pytest.raises(ValueError, match="exactly 00:00:00 UTC"):
        build_spot_trade_flow_features(
            symbol="AAAUSDT",
            decision_at="2026-01-15T12:00:00Z",
            daily_archives=_archives(),
        )


def test_non_usdt_or_unsafe_symbol_is_rejected():
    with pytest.raises(ValueError, match="USDT-quoted"):
        build_spot_trade_flow_features(
            symbol="AAAUSD",
            decision_at="2026-01-15T00:00:00Z",
            daily_archives=_archives(),
        )
    with pytest.raises(ValueError, match="uppercase alphanumeric"):
        build_spot_trade_flow_features(
            symbol="../AAAUSDT",
            decision_at="2026-01-15T00:00:00Z",
            daily_archives=_archives(),
        )


def test_duplicate_trade_id_across_days_is_rejected():
    archives = _archives()
    second = date(2026, 1, 2)
    archive_name = f"AAAUSDT-trades-{second.isoformat()}.zip"
    member = archive_name[:-4] + ".csv"
    # Reuse trade id 1 from the first day while retaining a valid second-day timestamp.
    raw = _zip_csv(member, [["1", "101", "1", "100", _epoch_us(datetime(2026, 1, 2, 1, tzinfo=UTC)), "false", "true"]])
    digest = hashlib.sha256(raw).hexdigest()
    archives[1] = {
        "date": second.isoformat(),
        "archive_name": archive_name,
        "archive_bytes": raw,
        "checksum_bytes": f"{digest}  {archive_name}\n".encode(),
    }
    with pytest.raises(ValueError, match="duplicated across daily archives"):
        build_spot_trade_flow_features(
            symbol="AAAUSDT",
            decision_at="2026-01-15T00:00:00Z",
            daily_archives=archives,
        )
