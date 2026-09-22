"""Deterministic, outcome-blind qualification helpers for Tardis incremental L2 data.

This module exists only to qualify provider/schema/chronology mechanics for the frozen
2x tradability research contracts. It does not fetch data, open historical labels,
form candidates, establish strict tradability, or grant model/broker/trading authority.

The implementation follows Tardis' documented ``incremental_book_L2`` semantics:
- rows are ordered by local capture chronology;
- multiple level updates belonging to one message share ``local_timestamp``;
- pre-snapshot updates are ignored until an initial snapshot is observed;
- entering a new snapshot discards the previous book;
- ``amount`` is an absolute level amount, and zero removes a level.

For co-temporal qualification, a reconstructed state receives an interval only when the
next captured message is an ordinary incremental update. A following snapshot marks a
restart/reset boundary, so the preceding state is exact-instant-only. A crossing may use
an interval only when *both* exchange-event time and local-capture time fall inside the
same support interval. This deliberately forbids nearest-neighbour depth borrowing.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import csv
import io
from typing import Iterable, Sequence


EXPECTED_COLUMNS = (
    "exchange",
    "symbol",
    "timestamp",
    "local_timestamp",
    "is_snapshot",
    "side",
    "price",
    "amount",
)
QUALIFICATION_AUTHORITY = "PROVIDER_ADAPTER_ONLY"


@dataclass(frozen=True)
class L2Row:
    exchange: str
    symbol: str
    timestamp_us: int
    local_timestamp_us: int
    is_snapshot: bool
    side: str
    price: Decimal
    amount: Decimal
    row_index: int


@dataclass(frozen=True)
class BookState:
    exchange: str
    symbol: str
    timestamp_us: int
    local_timestamp_us: int
    bids: tuple[tuple[Decimal, Decimal], ...]
    asks: tuple[tuple[Decimal, Decimal], ...]
    reset_sequence: int
    support_end_timestamp_us: int | None
    support_end_local_timestamp_us: int | None
    crossed: bool


@dataclass(frozen=True)
class ExecutionQualification:
    status: str
    reference_quantity: Decimal
    filled_quantity: Decimal
    proceeds: Decimal
    vwap: Decimal | None
    worst_fill_price: Decimal | None
    authority: str = QUALIFICATION_AUTHORITY


def _positive_decimal(value: str, *, field: str, allow_zero: bool = False) -> Decimal:
    try:
        number = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a decimal") from exc
    if not number.is_finite():
        raise ValueError(f"{field} must be finite")
    if allow_zero:
        if number < 0:
            raise ValueError(f"{field} must be >= 0")
    elif number <= 0:
        raise ValueError(f"{field} must be > 0")
    return number


def _positive_int(value: str, *, field: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc
    if number <= 0:
        raise ValueError(f"{field} must be > 0")
    return number


def parse_incremental_l2_csv(
    raw: bytes | str,
    *,
    expected_exchange: str,
    expected_symbol: str,
) -> list[L2Row]:
    """Parse one normalized Tardis incremental-L2 CSV fail-closed.

    Exact column identity is intentional for this qualification slice. If the provider
    schema changes, the adapter must be versioned and re-qualified rather than silently
    accepting a new representation.
    """
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Tardis CSV must be UTF-8") from exc
    elif isinstance(raw, str):
        text = raw
    else:
        raise ValueError("Tardis CSV must be bytes or text")

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None or tuple(reader.fieldnames) != EXPECTED_COLUMNS:
        raise ValueError("unexpected Tardis incremental_book_L2 schema")

    rows: list[L2Row] = []
    previous_local: int | None = None
    for row_index, record in enumerate(reader, start=2):
        if None in record or any(value is None for value in record.values()):
            raise ValueError(f"row {row_index} is malformed")
        exchange = record["exchange"].strip()
        symbol = record["symbol"].strip()
        if exchange != expected_exchange:
            raise ValueError(f"row {row_index} exchange mismatch")
        if symbol != expected_symbol:
            raise ValueError(f"row {row_index} symbol mismatch")
        if symbol != symbol.upper():
            raise ValueError(f"row {row_index} symbol must preserve provider uppercase identity")

        timestamp_us = _positive_int(record["timestamp"].strip(), field="timestamp")
        local_timestamp_us = _positive_int(
            record["local_timestamp"].strip(), field="local_timestamp"
        )
        if previous_local is not None and local_timestamp_us < previous_local:
            raise ValueError("local_timestamp must be nondecreasing in source row order")
        previous_local = local_timestamp_us

        snapshot_text = record["is_snapshot"].strip().lower()
        if snapshot_text not in {"true", "false"}:
            raise ValueError(f"row {row_index} is_snapshot must be true/false")
        side = record["side"].strip().lower()
        if side not in {"bid", "ask"}:
            raise ValueError(f"row {row_index} side must be bid/ask")

        rows.append(
            L2Row(
                exchange=exchange,
                symbol=symbol,
                timestamp_us=timestamp_us,
                local_timestamp_us=local_timestamp_us,
                is_snapshot=snapshot_text == "true",
                side=side,
                price=_positive_decimal(record["price"].strip(), field="price"),
                amount=_positive_decimal(
                    record["amount"].strip(), field="amount", allow_zero=True
                ),
                row_index=row_index,
            )
        )
    if not rows:
        raise ValueError("Tardis CSV contains no data rows")
    return rows


def _group_messages(rows: Sequence[L2Row]) -> list[list[L2Row]]:
    messages: list[list[L2Row]] = []
    current: list[L2Row] = []
    current_local: int | None = None
    for row in rows:
        if current_local is None or row.local_timestamp_us == current_local:
            current.append(row)
            current_local = row.local_timestamp_us
            continue
        messages.append(current)
        current = [row]
        current_local = row.local_timestamp_us
    if current:
        messages.append(current)
    return messages


def reconstruct_books(rows: Sequence[L2Row]) -> list[BookState]:
    """Reconstruct post-message L2 states without carrying a book across resets."""
    if not rows:
        raise ValueError("rows cannot be empty")
    exchange = rows[0].exchange
    symbol = rows[0].symbol
    if any(row.exchange != exchange or row.symbol != symbol for row in rows):
        raise ValueError("all L2 rows must share one provider instrument identity")

    messages = _group_messages(rows)
    normalized: list[tuple[list[L2Row], bool, int]] = []
    for message in messages:
        snapshot_flags = {row.is_snapshot for row in message}
        if len(snapshot_flags) != 1:
            raise ValueError("one local_timestamp message cannot mix snapshot and incremental rows")
        event_times = {row.timestamp_us for row in message}
        if len(event_times) != 1:
            raise ValueError("one local_timestamp message must have one provider event timestamp")
        normalized.append((message, next(iter(snapshot_flags)), next(iter(event_times))))

    bids: dict[Decimal, Decimal] = {}
    asks: dict[Decimal, Decimal] = {}
    have_snapshot = False
    reset_sequence = 0
    interim: list[dict[str, object]] = []

    for message, is_snapshot, event_time in normalized:
        if not have_snapshot and not is_snapshot:
            # Tardis explicitly documents buffered non-snapshot updates before the
            # first initial snapshot; they are not a reconstructable book state.
            continue
        if is_snapshot:
            bids.clear()
            asks.clear()
            have_snapshot = True
            reset_sequence += 1

        for row in message:
            side_book = bids if row.side == "bid" else asks
            if row.amount == 0:
                side_book.pop(row.price, None)
            else:
                side_book[row.price] = row.amount

        if not bids or not asks:
            raise ValueError("reconstructed snapshot must contain both bid and ask sides")
        bid_levels = tuple(sorted(bids.items(), key=lambda item: item[0], reverse=True))
        ask_levels = tuple(sorted(asks.items(), key=lambda item: item[0]))
        interim.append(
            {
                "exchange": exchange,
                "symbol": symbol,
                "timestamp_us": event_time,
                "local_timestamp_us": message[0].local_timestamp_us,
                "bids": bid_levels,
                "asks": ask_levels,
                "reset_sequence": reset_sequence,
                "crossed": bid_levels[0][0] >= ask_levels[0][0],
                "is_snapshot": is_snapshot,
            }
        )

    if not interim:
        raise ValueError("no reconstructable state after an initial snapshot")

    states: list[BookState] = []
    for index, state in enumerate(interim):
        support_end_timestamp_us: int | None = None
        support_end_local_timestamp_us: int | None = None
        if index + 1 < len(interim):
            nxt = interim[index + 1]
            # A following snapshot is a restart/reset boundary. Do not claim that the
            # prior state remained valid through the unobserved interval leading to it.
            if nxt["is_snapshot"] is False:
                next_event = int(nxt["timestamp_us"])
                next_local = int(nxt["local_timestamp_us"])
                current_event = int(state["timestamp_us"])
                current_local = int(state["local_timestamp_us"])
                if next_event >= current_event and next_local > current_local:
                    support_end_timestamp_us = next_event
                    support_end_local_timestamp_us = next_local

        states.append(
            BookState(
                exchange=str(state["exchange"]),
                symbol=str(state["symbol"]),
                timestamp_us=int(state["timestamp_us"]),
                local_timestamp_us=int(state["local_timestamp_us"]),
                bids=state["bids"],  # type: ignore[arg-type]
                asks=state["asks"],  # type: ignore[arg-type]
                reset_sequence=int(state["reset_sequence"]),
                support_end_timestamp_us=support_end_timestamp_us,
                support_end_local_timestamp_us=support_end_local_timestamp_us,
                crossed=bool(state["crossed"]),
            )
        )
    return states


def state_supports_crossing(
    state: BookState,
    *,
    crossing_timestamp_us: int,
    crossing_local_timestamp_us: int,
) -> bool:
    """Return true only for exact/co-temporal evidence on both provider clocks."""
    if state.crossed:
        return False
    if crossing_timestamp_us == state.timestamp_us and crossing_local_timestamp_us == state.local_timestamp_us:
        return True
    if state.support_end_timestamp_us is None or state.support_end_local_timestamp_us is None:
        return False
    return (
        state.timestamp_us <= crossing_timestamp_us < state.support_end_timestamp_us
        and state.local_timestamp_us
        <= crossing_local_timestamp_us
        < state.support_end_local_timestamp_us
    )


def select_cotemporal_state(
    states: Iterable[BookState],
    *,
    crossing_timestamp_us: int,
    crossing_local_timestamp_us: int,
) -> BookState | None:
    matches = [
        state
        for state in states
        if state_supports_crossing(
            state,
            crossing_timestamp_us=crossing_timestamp_us,
            crossing_local_timestamp_us=crossing_local_timestamp_us,
        )
    ]
    if len(matches) > 1:
        raise ValueError("crossing maps to more than one L2 support interval")
    return matches[0] if matches else None


def qualify_bid_exit(
    state: BookState | None,
    *,
    reference_quantity: Decimal | str,
    target_price: Decimal | str,
) -> ExecutionQualification:
    """Test bid-side full-quantity target-or-better executability for adapter QA only."""
    quantity = _positive_decimal(str(reference_quantity), field="reference_quantity")
    target = _positive_decimal(str(target_price), field="target_price")
    if state is None or state.crossed:
        return ExecutionQualification(
            status="QUALIFICATION_UNKNOWN_ALIGNMENT",
            reference_quantity=quantity,
            filled_quantity=Decimal("0"),
            proceeds=Decimal("0"),
            vwap=None,
            worst_fill_price=None,
        )

    remaining = quantity
    filled = Decimal("0")
    proceeds = Decimal("0")
    worst: Decimal | None = None
    for price, amount in state.bids:
        if price < target:
            break
        take = min(remaining, amount)
        if take <= 0:
            continue
        filled += take
        proceeds += take * price
        remaining -= take
        worst = price
        if remaining == 0:
            break

    if filled < quantity:
        return ExecutionQualification(
            status="QUALIFICATION_INSUFFICIENT_TARGET_DEPTH",
            reference_quantity=quantity,
            filled_quantity=filled,
            proceeds=proceeds,
            vwap=proceeds / filled if filled else None,
            worst_fill_price=worst,
        )
    return ExecutionQualification(
        status="QUALIFICATION_EXECUTABLE_AT_TARGET_OR_BETTER",
        reference_quantity=quantity,
        filled_quantity=filled,
        proceeds=proceeds,
        vwap=proceeds / filled,
        worst_fill_price=worst,
    )
