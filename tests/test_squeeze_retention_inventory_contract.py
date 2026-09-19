import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from squeeze_retention_inventory_contract import audit_inventory


UTC = timezone.utc
START = datetime(2026, 8, 20, tzinfo=UTC)
END = START + timedelta(hours=2)
SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
SHA256 = "a" * 64


def object_entry(hour, symbol, family, **updates):
    entry = {
        "object_path": (
            f"binance_futures/{hour:%Y-%m-%d}/{hour:%H}/"
            f"{symbol}_{family}.parquet"
        ),
        "size_bytes": 100,
        "sha256": SHA256,
    }
    entry.update(updates)
    return entry


def complete_two_hour_inventory():
    entries = []
    for offset in range(2):
        hour = START + timedelta(hours=offset)
        for symbol in SYMBOLS:
            entries.append(object_entry(hour, symbol, "open_interest"))
            entries.append(object_entry(hour, symbol, "mark_price"))
            if offset == 0:
                entries.append(object_entry(hour, symbol, "liquidations"))
    return entries


def audit(entries, **overrides):
    options = {
        "start": START,
        "end": END,
        "listing_complete": True,
        "receipt_semantics_verified": True,
        "contract_units_verified": True,
    }
    options.update(overrides)
    return audit_inventory(entries, **options)


def test_complete_inventory_allows_sparse_liquidation_files_without_calling_them_zero():
    report = audit(complete_two_hour_inventory())

    assert report["status"] == "READY_FOR_PREOUTCOME_QUANT"
    assert report["blockers"] == []
    assert report["dense_expected"] == 12
    assert report["dense_verified"] == 12
    assert report["liquidation_files_verified"] == 3
    assert report["no_published_liquidation_file_hours"] == 3
    assert report["collection_unknown_liquidation_hours"] == 0
    assert report["missing_liquidation_means_zero_notional"] is False
    assert report["outcomes_inspected"] is False


def test_dense_gap_prevents_absent_liquidation_from_being_called_no_publication():
    entries = complete_two_hour_inventory()
    missing_hour = START + timedelta(hours=1)
    entries = [
        entry for entry in entries
        if entry["object_path"] != object_entry(
            missing_hour, "BTCUSDT", "open_interest"
        )["object_path"]
    ]

    report = audit(entries)

    assert report["status"] == "TERMINAL_DATA_BLOCKER"
    assert "dense_coverage_incomplete" in report["blockers"]
    assert report["dense_verified"] == 11
    assert report["collection_unknown_liquidation_hours"] == 1
    assert report["no_published_liquidation_file_hours"] == 2


def test_listing_hash_suffix_and_identity_fail_closed():
    entries = complete_two_hour_inventory()
    entries[0].pop("sha256")
    entries[0]["etag"] = "not-a-sha256"
    entries[1]["object_path"] += ".zst"  # wrong after 2026-08-19
    entries.append(dict(entries[2]))

    report = audit(entries)

    assert report["status"] == "TERMINAL_DATA_BLOCKER"
    assert "inventory_integrity_failed" in report["blockers"]
    assert report["invalid_objects"] == 2
    assert report["duplicate_objects"] == 1


def test_unproved_listing_receipts_or_units_each_block_quant_use():
    entries = complete_two_hour_inventory()
    assert "complete_prefix_inventory_unavailable" in audit(
        entries, listing_complete=False
    )["blockers"]
    assert "historical_receipt_semantics_unverified" in audit(
        entries, receipt_semantics_verified=False
    )["blockers"]
    assert "contract_and_notional_units_unverified" in audit(
        entries, contract_units_verified=False
    )["blockers"]


def test_pre_august_19_objects_require_legacy_zst_key_suffix():
    hour = datetime(2026, 8, 18, tzinfo=UTC)
    good = object_entry(hour, "BTCUSDT", "open_interest")
    good["object_path"] += ".zst"
    bad = object_entry(hour, "ETHUSDT", "open_interest")

    report = audit_inventory(
        [good, bad],
        start=hour,
        end=hour + timedelta(hours=1),
        symbols=("BTCUSDT", "ETHUSDT"),
        listing_complete=False,
        receipt_semantics_verified=False,
        contract_units_verified=False,
    )

    assert report["valid_objects"] == 1
    assert report["invalid_objects"] == 1


def test_committed_resolution_freezes_interval_and_keeps_all_outcomes_closed():
    evidence = Path(__file__).resolve().parents[1] / (
        "research_data/squeeze_preflight/data004_source_resolution.json"
    )
    report = json.loads(evidence.read_text())

    assert report["task_id"] == "COORD-DISC-DATA-004"
    assert report["decision"] == "TERMINAL_NO_ZERO_COST_TIMESTAMP_SAFE_SOURCE"
    assert report["frozen_interval"] == {
        "start_inclusive": "2025-07-01T00:00:00Z",
        "end_exclusive": "2026-09-01T00:00:00Z",
    }
    assert report["symbols"] == list(SYMBOLS)
    assert report["families"] == ["liquidations", "open_interest", "mark_price"]
    assert report["strategy_outcomes_inspected"] is False
    assert report["untouched_oos_opened"] is False
    assert report["new_paid_service_authorized"] is False
    assert report["broker_or_live_authority"] is False
    assert report["next_action"] == "LEAD_PIVOT_TO_DISTINCT_AVAILABLE_DATA_HYPOTHESIS"
