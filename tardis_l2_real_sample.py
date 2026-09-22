"""Streaming qualification runner for the frozen free Tardis L2 sample.

This module is deliberately provider-adapter-only. It exists to prove that the exact
frozen provider sample can be consumed end-to-end without loading a full day of L2 data
into memory. It does not open 2x outcomes, establish historical tradability, rank a
candidate, fit a model, or grant broker/trading authority.

The full gzip is streamed and reconstruction semantics are checked message by message.
In addition, a bounded verbatim prefix containing the first reconstructable snapshot and
subsequent incremental messages is passed through ``tardis_l2_qualification`` itself, so
real provider rows exercise the exact PR #674 parser/reconstructor rather than a synthetic
lookalike only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import argparse
import csv
import gzip
import hashlib
import heapq
import json
from pathlib import Path
from typing import TextIO

from tardis_l2_qualification import (
    EXPECTED_COLUMNS,
    QUALIFICATION_AUTHORITY,
    parse_incremental_l2_csv,
    reconstruct_books,
)


RECEIPT_SCHEMA = "two_x_tardis_l2_real_sample_receipt.v1"
RUNNER_VERSION = "1"
PROVIDER_SAMPLE_RESULT = "QUALIFICATION_PROVIDER_SAMPLE_PASS"


@dataclass(frozen=True)
class StreamSummary:
    row_count: int
    message_count: int
    ignored_pre_snapshot_rows: int
    ignored_pre_snapshot_messages: int
    snapshot_message_count: int
    incremental_message_count: int
    reconstructed_state_count: int
    reset_count: int
    crossed_state_count: int
    gap_free_support_interval_count: int
    exact_instant_only_state_count: int
    first_event_timestamp_us: int
    last_event_timestamp_us: int
    first_local_timestamp_us: int
    last_local_timestamp_us: int
    max_bid_levels: int
    max_ask_levels: int
    canary_row_count: int
    canary_reconstructed_state_count: int


class _CapturingIterator:
    """Yield source lines unchanged while retaining only a bounded initial prefix."""

    def __init__(self, stream: TextIO) -> None:
        self._stream = iter(stream)
        self.capture = True
        self.lines: list[str] = []

    def __iter__(self) -> "_CapturingIterator":
        return self

    def __next__(self) -> str:
        line = next(self._stream)
        if self.capture:
            self.lines.append(line)
        return line


def _positive_int(value: str, *, field: str, row_index: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_index} {field} must be an integer") from exc
    if result <= 0:
        raise ValueError(f"row {row_index} {field} must be > 0")
    return result


def _decimal(value: str, *, field: str, row_index: int, allow_zero: bool = False) -> Decimal:
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"row {row_index} {field} must be a decimal") from exc
    if not result.is_finite():
        raise ValueError(f"row {row_index} {field} must be finite")
    if allow_zero:
        if result < 0:
            raise ValueError(f"row {row_index} {field} must be >= 0")
    elif result <= 0:
        raise ValueError(f"row {row_index} {field} must be > 0")
    return result


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _peek_bid(heap: list[Decimal], levels: dict[Decimal, Decimal], present: set[Decimal]) -> Decimal:
    while heap:
        price = -heap[0]
        if price in levels:
            return price
        heapq.heappop(heap)
        present.discard(price)
    raise ValueError("reconstructed book has no bid levels")


def _peek_ask(heap: list[Decimal], levels: dict[Decimal, Decimal], present: set[Decimal]) -> Decimal:
    while heap:
        price = heap[0]
        if price in levels:
            return price
        heapq.heappop(heap)
        present.discard(price)
    raise ValueError("reconstructed book has no ask levels")


def summarize_real_sample_stream(
    stream: TextIO,
    *,
    expected_exchange: str,
    expected_symbol: str,
    canary_min_reconstructed_states: int = 3,
) -> StreamSummary:
    """Validate and reconstruct a complete normalized incremental-L2 CSV as a stream.

    The algorithm preserves provider row order and groups one message by identical
    ``local_timestamp`` just like the bounded adapter. It keeps only the live book plus
    small heaps, so a full-day provider sample does not require retaining every historic
    book state in memory.
    """
    if canary_min_reconstructed_states < 1:
        raise ValueError("canary_min_reconstructed_states must be >= 1")

    source = _CapturingIterator(stream)
    reader = csv.DictReader(source)
    if reader.fieldnames is None or tuple(reader.fieldnames) != EXPECTED_COLUMNS:
        raise ValueError("unexpected Tardis incremental_book_L2 schema")

    row_count = 0
    message_count = 0
    ignored_pre_rows = 0
    ignored_pre_messages = 0
    snapshot_messages = 0
    incremental_messages = 0
    reconstructed_states = 0
    resets = 0
    crossed_states = 0
    support_intervals = 0
    exact_only_states = 0
    max_bid_levels = 0
    max_ask_levels = 0

    previous_local_row: int | None = None
    first_event: int | None = None
    last_event: int | None = None
    first_local: int | None = None
    last_local: int | None = None

    bids: dict[Decimal, Decimal] = {}
    asks: dict[Decimal, Decimal] = {}
    bid_heap: list[Decimal] = []
    ask_heap: list[Decimal] = []
    bid_heap_present: set[Decimal] = set()
    ask_heap_present: set[Decimal] = set()
    have_snapshot = False

    current_local: int | None = None
    current_event: int | None = None
    current_snapshot: bool | None = None
    current_rows: list[tuple[str, Decimal, Decimal]] = []
    current_source_row_count = 0

    previous_state_event: int | None = None
    previous_state_local: int | None = None

    canary_done = False

    def process_message() -> None:
        nonlocal message_count, ignored_pre_rows, ignored_pre_messages
        nonlocal snapshot_messages, incremental_messages, reconstructed_states, resets
        nonlocal crossed_states, support_intervals, exact_only_states
        nonlocal max_bid_levels, max_ask_levels, have_snapshot
        nonlocal previous_state_event, previous_state_local, canary_done

        if current_local is None or current_event is None or current_snapshot is None:
            return
        message_count += 1
        if not have_snapshot and not current_snapshot:
            ignored_pre_messages += 1
            ignored_pre_rows += current_source_row_count
            return

        if current_snapshot:
            bids.clear()
            asks.clear()
            bid_heap.clear()
            ask_heap.clear()
            bid_heap_present.clear()
            ask_heap_present.clear()
            have_snapshot = True
            resets += 1
            snapshot_messages += 1
        else:
            incremental_messages += 1

        for side, price, amount in current_rows:
            levels = bids if side == "bid" else asks
            heap = bid_heap if side == "bid" else ask_heap
            present = bid_heap_present if side == "bid" else ask_heap_present
            heap_value = -price if side == "bid" else price
            if amount == 0:
                levels.pop(price, None)
            else:
                if price not in present:
                    heapq.heappush(heap, heap_value)
                    present.add(price)
                levels[price] = amount

        if not bids or not asks:
            raise ValueError("reconstructed snapshot must contain both bid and ask sides")

        best_bid = _peek_bid(bid_heap, bids, bid_heap_present)
        best_ask = _peek_ask(ask_heap, asks, ask_heap_present)
        if best_bid >= best_ask:
            crossed_states += 1

        if previous_state_event is not None and previous_state_local is not None:
            if (
                not current_snapshot
                and current_event >= previous_state_event
                and current_local > previous_state_local
            ):
                support_intervals += 1
            else:
                exact_only_states += 1

        reconstructed_states += 1
        previous_state_event = current_event
        previous_state_local = current_local
        max_bid_levels = max(max_bid_levels, len(bids))
        max_ask_levels = max(max_ask_levels, len(asks))

        if not canary_done and reconstructed_states >= canary_min_reconstructed_states:
            source.capture = False
            canary_done = True

    for row_index, record in enumerate(reader, start=2):
        row_count += 1
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

        event_ts = _positive_int(record["timestamp"].strip(), field="timestamp", row_index=row_index)
        local_ts = _positive_int(
            record["local_timestamp"].strip(), field="local_timestamp", row_index=row_index
        )
        if previous_local_row is not None and local_ts < previous_local_row:
            raise ValueError("local_timestamp must be nondecreasing in source row order")
        previous_local_row = local_ts

        snapshot_text = record["is_snapshot"].strip().lower()
        if snapshot_text not in {"true", "false"}:
            raise ValueError(f"row {row_index} is_snapshot must be true/false")
        is_snapshot = snapshot_text == "true"
        side = record["side"].strip().lower()
        if side not in {"bid", "ask"}:
            raise ValueError(f"row {row_index} side must be bid/ask")
        price = _decimal(record["price"].strip(), field="price", row_index=row_index)
        amount = _decimal(
            record["amount"].strip(), field="amount", row_index=row_index, allow_zero=True
        )

        if first_event is None:
            first_event = event_ts
            first_local = local_ts
        last_event = event_ts
        last_local = local_ts

        if current_local is None:
            current_local = local_ts
            current_event = event_ts
            current_snapshot = is_snapshot
        elif local_ts != current_local:
            process_message()
            current_rows = []
            current_source_row_count = 0
            current_local = local_ts
            current_event = event_ts
            current_snapshot = is_snapshot
        else:
            if event_ts != current_event:
                raise ValueError("one local_timestamp message must have one provider event timestamp")
            if is_snapshot != current_snapshot:
                raise ValueError("one local_timestamp message cannot mix snapshot and incremental rows")

        current_rows.append((side, price, amount))
        current_source_row_count += 1

    process_message()
    if row_count == 0:
        raise ValueError("Tardis CSV contains no data rows")
    if reconstructed_states == 0:
        raise ValueError("no reconstructable state after an initial snapshot")
    exact_only_states += 1

    canary_text = "".join(source.lines)
    canary_rows = parse_incremental_l2_csv(
        canary_text,
        expected_exchange=expected_exchange,
        expected_symbol=expected_symbol,
    )
    canary_states = reconstruct_books(canary_rows)
    if len(canary_states) < canary_min_reconstructed_states:
        raise ValueError("real-sample canary did not produce enough reconstructed states")

    assert first_event is not None and last_event is not None
    assert first_local is not None and last_local is not None
    return StreamSummary(
        row_count=row_count,
        message_count=message_count,
        ignored_pre_snapshot_rows=ignored_pre_rows,
        ignored_pre_snapshot_messages=ignored_pre_messages,
        snapshot_message_count=snapshot_messages,
        incremental_message_count=incremental_messages,
        reconstructed_state_count=reconstructed_states,
        reset_count=resets,
        crossed_state_count=crossed_states,
        gap_free_support_interval_count=support_intervals,
        exact_instant_only_state_count=exact_only_states,
        first_event_timestamp_us=first_event,
        last_event_timestamp_us=last_event,
        first_local_timestamp_us=first_local,
        last_local_timestamp_us=last_local,
        max_bid_levels=max_bid_levels,
        max_ask_levels=max_ask_levels,
        canary_row_count=len(canary_rows),
        canary_reconstructed_state_count=len(canary_states),
    )


def qualify_gzip_sample(
    path: Path,
    *,
    source_url: str,
    expected_exchange: str,
    expected_symbol: str,
    retrieved_at: str,
    commit_sha: str,
) -> dict[str, object]:
    compressed_sha256 = _sha256_file(path)
    compressed_bytes = path.stat().st_size
    with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
        summary = summarize_real_sample_stream(
            stream,
            expected_exchange=expected_exchange,
            expected_symbol=expected_symbol,
        )

    return {
        "schema": RECEIPT_SCHEMA,
        "status": PROVIDER_SAMPLE_RESULT,
        "authority": QUALIFICATION_AUTHORITY,
        "runner_version": RUNNER_VERSION,
        "source_url": source_url,
        "expected_exchange": expected_exchange,
        "expected_symbol": expected_symbol,
        "retrieved_at": retrieved_at,
        "commit_sha": commit_sha,
        "compressed_sha256": compressed_sha256,
        "compressed_bytes": compressed_bytes,
        "summary": asdict(summary),
        "outcomes_opened": False,
        "strict_tradability_established": False,
        "candidate_authority": False,
        "model_fitting_authority": False,
        "broker_connected": False,
        "live_trading": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gzip-path", required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--expected-exchange", required=True)
    parser.add_argument("--expected-symbol", required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    receipt = qualify_gzip_sample(
        Path(args.gzip_path),
        source_url=args.source_url,
        expected_exchange=args.expected_exchange,
        expected_symbol=args.expected_symbol,
        retrieved_at=args.retrieved_at,
        commit_sha=args.commit_sha,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
