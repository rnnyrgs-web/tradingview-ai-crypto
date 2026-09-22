from decimal import Decimal
import json
from pathlib import Path

import pytest

from tardis_l2_qualification import (
    EXPECTED_COLUMNS,
    QUALIFICATION_AUTHORITY,
    parse_incremental_l2_csv,
    qualify_bid_exit,
    reconstruct_books,
    select_cotemporal_state,
)


ARTIFACT = Path("money_intelligence/2x_tardis_l2_qualification_v1.json")
HEADER = ",".join(EXPECTED_COLUMNS)


def _csv(*rows: str) -> str:
    return HEADER + "\n" + "\n".join(rows) + "\n"


def _fixture() -> str:
    return _csv(
        # Buffered update before the initial snapshot: must be ignored.
        "binance,BTCUSDT,900,100,false,bid,99,9",
        # Initial snapshot message.
        "binance,BTCUSDT,1000,110,true,bid,100,2",
        "binance,BTCUSDT,1000,110,true,bid,99,3",
        "binance,BTCUSDT,1000,110,true,ask,101,4",
        "binance,BTCUSDT,1000,110,true,ask,102,5",
        # Ordinary incremental update; amount is absolute and zero removes a level.
        "binance,BTCUSDT,1020,120,false,bid,100,4",
        "binance,BTCUSDT,1020,120,false,ask,101,0",
        # Another incremental message.
        "binance,BTCUSDT,1030,130,false,bid,98,6",
        "binance,BTCUSDT,1030,130,false,ask,103,7",
        # Restart/new snapshot: previous book must be discarded.
        "binance,BTCUSDT,2000,200,true,bid,110,1",
        "binance,BTCUSDT,2000,200,true,ask,111,1",
    )


def test_committed_contract_is_zero_spend_and_adapter_only():
    contract = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert contract["status"] == "FREE_SAMPLE_QUALIFICATION_PASS"
    assert contract["authority"] == "PROVIDER_ADAPTER_ONLY"
    assert contract["spend_authorized_usd"] == 0
    assert contract["outcomes_opened"] is False
    assert contract["candidate_authority"] is False
    assert contract["model_fitting_authority"] is False
    assert contract["strict_tradability_established"] is False
    assert contract["broker_connected"] is False
    assert contract["live_trading"] is False
    assert contract["current_blocker"] == "EVENT_DATE_HISTORICAL_L2_BYTES_NOT_ACQUIRED_OR_AUTHORIZED"
    receipt = contract["provider_pass_receipt"]
    assert receipt["compressed_sha256"] == "f7daa040dc33fc7328ff8468b198731fd5add90bc8cef434aab86726268e8a34"
    assert receipt["row_count"] == 6486542
    assert receipt["message_count"] == 815980
    assert receipt["reconstructed_state_count"] == 815980
    assert receipt["crossed_state_count"] == 0


def test_parser_enforces_exact_schema_and_provider_identity():
    rows = parse_incremental_l2_csv(
        _fixture(), expected_exchange="binance", expected_symbol="BTCUSDT"
    )
    assert len(rows) == 11
    assert rows[0].row_index == 2
    assert rows[0].local_timestamp_us == 100

    bad_header = _fixture().replace("exchange,symbol", "symbol,exchange", 1)
    with pytest.raises(ValueError, match="unexpected Tardis"):
        parse_incremental_l2_csv(
            bad_header, expected_exchange="binance", expected_symbol="BTCUSDT"
        )

    with pytest.raises(ValueError, match="symbol mismatch"):
        parse_incremental_l2_csv(
            _fixture(), expected_exchange="binance", expected_symbol="ETHUSDT"
        )


def test_parser_rejects_out_of_order_local_capture_time():
    raw = _csv(
        "binance,BTCUSDT,1000,110,true,bid,100,1",
        "binance,BTCUSDT,1000,110,true,ask,101,1",
        "binance,BTCUSDT,1010,109,false,bid,100,2",
    )
    with pytest.raises(ValueError, match="nondecreasing"):
        parse_incremental_l2_csv(raw, expected_exchange="binance", expected_symbol="BTCUSDT")


def test_pre_snapshot_rows_are_ignored_and_snapshot_reset_discards_old_book():
    rows = parse_incremental_l2_csv(
        _fixture(), expected_exchange="binance", expected_symbol="BTCUSDT"
    )
    states = reconstruct_books(rows)

    assert len(states) == 4
    initial = states[0]
    assert initial.reset_sequence == 1
    assert initial.bids == ((Decimal("100"), Decimal("2")), (Decimal("99"), Decimal("3")))
    assert (Decimal("99"), Decimal("9")) not in initial.bids

    after_update = states[1]
    assert after_update.bids[0] == (Decimal("100"), Decimal("4"))
    assert all(price != Decimal("101") for price, _ in after_update.asks)

    restarted = states[-1]
    assert restarted.reset_sequence == 2
    assert restarted.bids == ((Decimal("110"), Decimal("1")),)
    assert restarted.asks == ((Decimal("111"), Decimal("1")),)
    assert all(price not in {Decimal("100"), Decimal("99"), Decimal("98")} for price, _ in restarted.bids)


def test_mixed_snapshot_and_incremental_rows_in_one_message_fail_closed():
    raw = _csv(
        "binance,BTCUSDT,1000,110,true,bid,100,1",
        "binance,BTCUSDT,1000,110,false,ask,101,1",
    )
    rows = parse_incremental_l2_csv(raw, expected_exchange="binance", expected_symbol="BTCUSDT")
    with pytest.raises(ValueError, match="cannot mix"):
        reconstruct_books(rows)


def test_cotemporal_selection_requires_both_clocks_and_never_bridges_restart():
    rows = parse_incremental_l2_csv(
        _fixture(), expected_exchange="binance", expected_symbol="BTCUSDT"
    )
    states = reconstruct_books(rows)

    # State after local=120 is valid until the next ordinary incremental message.
    selected = select_cotemporal_state(
        states, crossing_timestamp_us=1025, crossing_local_timestamp_us=125
    )
    assert selected is not None
    assert selected.local_timestamp_us == 120

    # Matching only one clock is insufficient.
    assert (
        select_cotemporal_state(
            states, crossing_timestamp_us=1025, crossing_local_timestamp_us=150
        )
        is None
    )

    # The state at local=130 is followed by a new snapshot/restart. It cannot be
    # stretched across the unobserved interval to the new snapshot.
    assert (
        select_cotemporal_state(
            states, crossing_timestamp_us=1500, crossing_local_timestamp_us=160
        )
        is None
    )

    # Exact message-time evidence remains admissible for provider qualification.
    exact = select_cotemporal_state(
        states, crossing_timestamp_us=1030, crossing_local_timestamp_us=130
    )
    assert exact is not None
    assert exact.local_timestamp_us == 130


def test_bid_exit_vwap_requires_full_reference_quantity_at_target_or_better():
    raw = _csv(
        "binance,BTCUSDT,1000,110,true,bid,105,1",
        "binance,BTCUSDT,1000,110,true,bid,104,2",
        "binance,BTCUSDT,1000,110,true,bid,99,10",
        "binance,BTCUSDT,1000,110,true,ask,106,5",
    )
    rows = parse_incremental_l2_csv(raw, expected_exchange="binance", expected_symbol="BTCUSDT")
    state = reconstruct_books(rows)[0]

    result = qualify_bid_exit(state, reference_quantity="2.5", target_price="100")
    assert result.status == "QUALIFICATION_EXECUTABLE_AT_TARGET_OR_BETTER"
    assert result.authority == QUALIFICATION_AUTHORITY
    assert result.filled_quantity == Decimal("2.5")
    assert result.proceeds == Decimal("261.0")
    assert result.vwap == Decimal("104.4")
    assert result.worst_fill_price == Decimal("104")

    insufficient = qualify_bid_exit(state, reference_quantity="3.5", target_price="100")
    assert insufficient.status == "QUALIFICATION_INSUFFICIENT_TARGET_DEPTH"
    assert insufficient.filled_quantity == Decimal("3")
    assert insufficient.proceeds == Decimal("313")
    assert insufficient.vwap == Decimal("313") / Decimal("3")


def test_crossed_or_missing_alignment_cannot_be_called_executable():
    raw = _csv(
        "binance,BTCUSDT,1000,110,true,bid,101,1",
        "binance,BTCUSDT,1000,110,true,ask,100,1",
    )
    rows = parse_incremental_l2_csv(raw, expected_exchange="binance", expected_symbol="BTCUSDT")
    state = reconstruct_books(rows)[0]
    result = qualify_bid_exit(state, reference_quantity="1", target_price="100")
    assert result.status == "QUALIFICATION_UNKNOWN_ALIGNMENT"

    missing = qualify_bid_exit(None, reference_quantity="1", target_price="100")
    assert missing.status == "QUALIFICATION_UNKNOWN_ALIGNMENT"


def test_adapter_never_emits_factory_authority_labels():
    forbidden = {
        "TRADABLE_2X_HIT_AT_BAND",
        "PRICE_HIT_TRADABILITY_UNKNOWN",
        "ILLIQUID_2X_RESEARCH_ONLY",
    }
    raw = _csv(
        "binance,BTCUSDT,1000,110,true,bid,105,1",
        "binance,BTCUSDT,1000,110,true,ask,106,1",
    )
    rows = parse_incremental_l2_csv(raw, expected_exchange="binance", expected_symbol="BTCUSDT")
    state = reconstruct_books(rows)[0]
    result = qualify_bid_exit(state, reference_quantity="1", target_price="100")
    assert result.status not in forbidden
    assert result.authority == "PROVIDER_ADAPTER_ONLY"
