"""Outcome-blind Binance spot trade-flow features for 2x Cohort 001.

The feature contract is frozen in
``money_intelligence/2x_spot_trade_flow_contract_v1.json``.  This module consumes
checksum-verified *daily SPOT trades* archives for the fourteen complete UTC days
before a decision timestamp and deterministically derives two adjacent seven-day
participation/aggressor windows.

It intentionally does **not** infer bid/ask spread, order-book depth, strict
tradability, a 2x label, candidate status, or trading authority.  Missing daily raw
archives fail closed instead of being interpreted as zero activity.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import io
from pathlib import PurePosixPath
from typing import Any
import zipfile

from big_move_binance_archive_binding import verify_checksum_sidecar

UTC = timezone.utc
TRADE_COLUMNS = 7
MAX_MEMBER_BYTES = 1024 * 1024 * 1024
MILLISECONDS_THRESHOLD = 10**14
MICROSECONDS_THRESHOLD = 10**15
WINDOW_DAYS = 7
TOTAL_DAYS = WINDOW_DAYS * 2


def _utc_midnight(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("decision_at must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("decision_at must be valid RFC3339 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("decision_at must be UTC")
    if parsed.timetz().replace(tzinfo=None) != time(0, 0):
        raise ValueError("decision_at must be exactly 00:00:00 UTC")
    return parsed


def _event_time(raw: str) -> datetime:
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("trade timestamp must be integer epoch milliseconds/microseconds") from exc
    if value >= MICROSECONDS_THRESHOLD:
        seconds = value / 1_000_000
    elif value >= MILLISECONDS_THRESHOLD:
        raise ValueError("trade timestamp has ambiguous epoch precision")
    else:
        seconds = value / 1_000
    try:
        return datetime.fromtimestamp(seconds, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise ValueError("trade timestamp is outside supported epoch range") from exc


def _positive_decimal(raw: str, *, field: str) -> Decimal:
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f"{field} must be decimal") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{field} must be finite and > 0")
    return value


def _bool(raw: str, *, field: str) -> bool:
    normalized = str(raw).strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{field} must be true/false")


def _symbol(value: str) -> str:
    if not isinstance(value, str) or not value or value != value.upper() or not value.isalnum():
        raise ValueError("symbol must be uppercase alphanumeric")
    if not value.endswith("USDT") or len(value) <= 4:
        raise ValueError("Cohort 001 spot-flow source requires a USDT-quoted symbol")
    return value


def _safe_member(archive_bytes: bytes, *, expected_member: str) -> bytes:
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes), "r") as archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            if len(members) != 1:
                raise ValueError("Binance trades archive must contain exactly one data member")
            info = members[0]
            path = PurePosixPath(info.filename)
            if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
                raise ValueError("Binance trades archive member path is unsafe")
            if info.filename != expected_member:
                raise ValueError("Binance trades archive member name mismatch")
            if info.flag_bits & 0x1:
                raise ValueError("encrypted Binance archive members are unsupported")
            if info.file_size <= 0 or info.file_size > MAX_MEMBER_BYTES:
                raise ValueError("Binance trades archive member size is invalid")
            return archive.read(info)
    except zipfile.BadZipFile as exc:
        raise ValueError("Binance trades archive is not a valid ZIP") from exc


def _parse_daily_archive(
    *,
    symbol: str,
    archive_date: date,
    archive_name: str,
    archive_bytes: bytes,
    checksum_bytes: bytes,
) -> tuple[list[dict[str, Any]], str]:
    expected_archive = f"{symbol}-trades-{archive_date.isoformat()}.zip"
    if archive_name != expected_archive:
        raise ValueError(f"archive name mismatch for {archive_date.isoformat()}")
    digest = verify_checksum_sidecar(archive_bytes, checksum_bytes, expected_archive)
    expected_member = expected_archive[:-4] + ".csv"
    csv_bytes = _safe_member(archive_bytes, expected_member=expected_member)
    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Binance trades CSV must be UTF-8") from exc

    day_start = datetime.combine(archive_date, time(0, 0), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    rows: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    prior_id: int | None = None
    prior_time: datetime | None = None
    for line_number, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != TRADE_COLUMNS:
            raise ValueError(f"Binance trades CSV line {line_number} must have 7 columns")
        try:
            trade_id = int(row[0])
        except ValueError as exc:
            raise ValueError(f"Binance trades CSV line {line_number} has invalid trade id") from exc
        if trade_id < 0 or trade_id in seen_ids:
            raise ValueError("Binance trades archive contains invalid/duplicate trade id")
        if prior_id is not None and trade_id <= prior_id:
            raise ValueError("Binance trades archive trade ids must be strictly increasing")
        seen_ids.add(trade_id)
        event_at = _event_time(row[4])
        if not day_start <= event_at < day_end:
            raise ValueError("trade timestamp is outside the archive UTC date")
        if prior_time is not None and event_at < prior_time:
            raise ValueError("Binance trades archive timestamps must be nondecreasing")
        price = _positive_decimal(row[1], field="price")
        quantity = _positive_decimal(row[2], field="quantity")
        quote_quantity = _positive_decimal(row[3], field="quote_quantity")
        buyer_maker = _bool(row[5], field="is_buyer_maker")
        best_match = _bool(row[6], field="is_best_match")
        rows.append(
            {
                "trade_id": trade_id,
                "price": price,
                "quantity": quantity,
                "quote_quantity": quote_quantity,
                "timestamp": event_at,
                "is_buyer_maker": buyer_maker,
                "is_best_match": best_match,
            }
        )
        prior_id = trade_id
        prior_time = event_at
    if not rows:
        raise ValueError("Binance trades archive must contain at least one trade")
    return rows, digest


def _window_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("feature window cannot be empty")
    with localcontext() as ctx:
        ctx.prec = 50
        total_quote = sum((row["quote_quantity"] for row in rows), Decimal(0))
        aggressive_buy = sum(
            (row["quote_quantity"] for row in rows if not row["is_buyer_maker"]),
            Decimal(0),
        )
        aggressive_sell = total_quote - aggressive_buy
        if total_quote <= 0:
            raise ValueError("feature window quote notional must be > 0")
        buy_share = aggressive_buy / total_quote
        net_quote = aggressive_buy - aggressive_sell
        net_share = net_quote / total_quote
        first_price = rows[0]["price"]
        last_price = rows[-1]["price"]
        window_return = last_price / first_price - Decimal(1)
    return {
        "quote_notional": total_quote,
        "trade_count": len(rows),
        "aggressive_buy_quote": aggressive_buy,
        "aggressive_sell_quote": aggressive_sell,
        "aggressive_buy_share": buy_share,
        "net_aggressive_quote": net_quote,
        "net_aggressive_share": net_share,
        "first_trade_price": first_price,
        "last_trade_price": last_price,
        "window_return": window_return,
    }


def _ratio_change(current: Decimal, previous: Decimal, *, field: str) -> Decimal:
    if previous <= 0:
        raise ValueError(f"previous {field} must be > 0")
    with localcontext() as ctx:
        ctx.prec = 50
        return current / previous - Decimal(1)


def _decimal_text(value: Decimal) -> str:
    return format(value, "f")


def build_spot_trade_flow_features(
    *,
    symbol: str,
    decision_at: str,
    daily_archives: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the frozen 14d->7d/7d PIT spot-flow feature artifact.

    Each daily archive item must contain ``date`` (YYYY-MM-DD), ``archive_name``,
    ``archive_bytes`` and ``checksum_bytes``.  Exactly the fourteen expected dates are
    required.  The bytes remain the source of truth; caller-normalized trade rows are
    never accepted here.
    """
    symbol = _symbol(symbol)
    cutoff = _utc_midnight(decision_at)
    if not isinstance(daily_archives, list) or len(daily_archives) != TOTAL_DAYS:
        raise ValueError("exactly 14 daily trades archives are required")

    expected_dates = [cutoff.date() - timedelta(days=offset) for offset in range(TOTAL_DAYS, 0, -1)]
    by_date: dict[date, dict[str, Any]] = {}
    for index, item in enumerate(daily_archives):
        if not isinstance(item, dict):
            raise ValueError(f"daily_archives[{index}] must be an object")
        raw_date = item.get("date")
        try:
            parsed_date = date.fromisoformat(raw_date)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"daily_archives[{index}].date must be YYYY-MM-DD") from exc
        if parsed_date in by_date:
            raise ValueError("duplicate daily trades archive date")
        by_date[parsed_date] = item
    if set(by_date) != set(expected_dates):
        raise ValueError("daily trades coverage must exactly match the frozen 14 UTC dates")

    all_rows: list[dict[str, Any]] = []
    archive_digests: list[tuple[str, str]] = []
    seen_global_ids: set[int] = set()
    for archive_date in expected_dates:
        item = by_date[archive_date]
        archive_name = item.get("archive_name")
        archive_bytes = item.get("archive_bytes")
        checksum_bytes = item.get("checksum_bytes")
        if not isinstance(archive_name, str) or not isinstance(archive_bytes, bytes) or not isinstance(checksum_bytes, bytes):
            raise ValueError("daily archive requires archive_name string plus archive/checksum bytes")
        rows, digest = _parse_daily_archive(
            symbol=symbol,
            archive_date=archive_date,
            archive_name=archive_name,
            archive_bytes=archive_bytes,
            checksum_bytes=checksum_bytes,
        )
        ids = {row["trade_id"] for row in rows}
        if seen_global_ids.intersection(ids):
            raise ValueError("trade id is duplicated across daily archives")
        seen_global_ids.update(ids)
        all_rows.extend(rows)
        archive_digests.append((archive_date.isoformat(), digest))

    all_rows.sort(key=lambda row: (row["timestamp"], row["trade_id"]))
    previous_start = cutoff - timedelta(days=14)
    current_start = cutoff - timedelta(days=7)
    previous_rows = [row for row in all_rows if previous_start <= row["timestamp"] < current_start]
    current_rows = [row for row in all_rows if current_start <= row["timestamp"] < cutoff]
    previous = _window_summary(previous_rows)
    current = _window_summary(current_rows)

    with localcontext() as ctx:
        ctx.prec = 50
        quote_acceleration = _ratio_change(current["quote_notional"], previous["quote_notional"], field="quote_notional")
        trade_count_acceleration = Decimal(current["trade_count"]) / Decimal(previous["trade_count"]) - Decimal(1)
        buy_share_change = current["aggressive_buy_share"] - previous["aggressive_buy_share"]
        net_share_change = current["net_aggressive_share"] - previous["net_aggressive_share"]

    digest_material = "\n".join(f"{day}:{digest}" for day, digest in archive_digests).encode("ascii")
    source_set_digest = hashlib.sha256(digest_material).hexdigest()

    def public_summary(summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "quote_notional_usdt": _decimal_text(summary["quote_notional"]),
            "trade_count": summary["trade_count"],
            "aggressive_buy_quote_usdt": _decimal_text(summary["aggressive_buy_quote"]),
            "aggressive_sell_quote_usdt": _decimal_text(summary["aggressive_sell_quote"]),
            "aggressive_buy_share": _decimal_text(summary["aggressive_buy_share"]),
            "net_aggressive_quote_usdt": _decimal_text(summary["net_aggressive_quote"]),
            "net_aggressive_share": _decimal_text(summary["net_aggressive_share"]),
            "first_trade_price": _decimal_text(summary["first_trade_price"]),
            "last_trade_price": _decimal_text(summary["last_trade_price"]),
            "window_return": _decimal_text(summary["window_return"]),
        }

    return {
        "schema": "two_x_spot_trade_flow_features.v1",
        "contract_id": "2X-SPOT-FLOW-001-v1",
        "symbol": symbol,
        "decision_at": cutoff.isoformat().replace("+00:00", "Z"),
        "coverage": {
            "first_date": expected_dates[0].isoformat(),
            "last_date": expected_dates[-1].isoformat(),
            "days": TOTAL_DAYS,
            "archive_sha256_by_date": [
                {"date": day, "sha256": digest} for day, digest in archive_digests
            ],
            "source_set_sha256": source_set_digest,
        },
        "previous_7d": public_summary(previous),
        "current_7d": public_summary(current),
        "changes": {
            "quote_notional_acceleration": _decimal_text(quote_acceleration),
            "trade_count_acceleration": _decimal_text(trade_count_acceleration),
            "aggressive_buy_share_change": _decimal_text(buy_share_change),
            "net_aggressive_share_change": _decimal_text(net_share_change),
        },
        "strict_tradability_established": False,
        "outcome_label_attached": False,
        "prediction_authority": False,
    }
