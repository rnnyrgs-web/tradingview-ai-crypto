import json

import pytest

from big_move_commoncrawl_trusted_origin_v2 import (
    CONTRACT_ARTIFACT_ID,
    CONTRACT_GIT_BLOB_SHA,
    load_commoncrawl_selection_contract,
    select_commoncrawl_index_row,
)


URL = "https://example.org/original-document"
COLLECTION = "CC-MAIN-2026-39"


def _row(timestamp, *, filename_suffix="0001", offset="100", length="200", digest="A" * 32):
    return {
        "url": URL,
        "status": "200",
        "timestamp": timestamp,
        "filename": f"crawl-data/{COLLECTION}/segments/1/warc/CC-MAIN-{filename_suffix}.warc.gz",
        "offset": offset,
        "length": length,
        "digest": digest,
    }


def _raw(*rows):
    return b"".join(json.dumps(row, sort_keys=True).encode() + b"\n" for row in rows)


def test_capture_selection_contract_is_git_blob_pinned():
    contract = load_commoncrawl_selection_contract()
    assert contract["artifact_id"] == CONTRACT_ARTIFACT_ID
    assert len(CONTRACT_GIT_BLOB_SHA) == 40


def test_two_authentic_predecision_rows_select_latest_capture():
    older = _row("20260101000000", filename_suffix="older")
    latest = _row("20260801000000", filename_suffix="latest")
    selected = select_commoncrawl_index_row(
        _raw(older, latest),
        upstream_locator=URL,
        collection=COLLECTION,
        decision_at="2026-09-01T00:00:00Z",
    )
    assert selected == latest


def test_postdecision_only_rows_fail_closed():
    future = _row("20261001000000")
    with pytest.raises(ValueError, match="at or before decision_at"):
        select_commoncrawl_index_row(
            _raw(future),
            upstream_locator=URL,
            collection=COLLECTION,
            decision_at="2026-09-01T00:00:00Z",
        )


def test_caller_cannot_override_latest_with_older_declared_row():
    older = _row("20260101000000", filename_suffix="older")
    latest = _row("20260801000000", filename_suffix="latest")
    with pytest.raises(ValueError, match="does not equal deterministic selection"):
        select_commoncrawl_index_row(
            _raw(older, latest),
            upstream_locator=URL,
            collection=COLLECTION,
            decision_at="2026-09-01T00:00:00Z",
            declared_selection=older,
        )


def test_same_timestamp_tie_uses_frozen_tuple_order_and_ignores_row_order():
    lexical_first = _row("20260801000000", filename_suffix="aaa", offset="20", length="300", digest="B" * 32)
    lexical_second = _row("20260801000000", filename_suffix="zzz", offset="1", length="1", digest="A" * 32)
    selected_a = select_commoncrawl_index_row(
        _raw(lexical_second, lexical_first),
        upstream_locator=URL,
        collection=COLLECTION,
        decision_at="2026-09-01T00:00:00Z",
    )
    selected_b = select_commoncrawl_index_row(
        _raw(lexical_first, lexical_second),
        upstream_locator=URL,
        collection=COLLECTION,
        decision_at="2026-09-01T00:00:00Z",
    )
    assert selected_a == lexical_first
    assert selected_b == lexical_first


def test_identical_duplicate_rows_collapse_to_one_identity():
    row = _row("20260801000000")
    selected = select_commoncrawl_index_row(
        _raw(row, dict(row)),
        upstream_locator=URL,
        collection=COLLECTION,
        decision_at="2026-09-01T00:00:00Z",
        declared_selection=row,
    )
    assert selected == row
