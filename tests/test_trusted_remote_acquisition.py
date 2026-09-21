from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import tarfile

import pytest

from trusted_remote_acquisition import (
    CONTRACT_ID,
    FetchResult,
    canonical_receipt,
    freeze_binance_listobjects_request,
    freeze_commoncrawl_index_request,
    freeze_commoncrawl_warc_request,
    load_contract,
    trusted_github_context,
    verify_receipt_bytes,
    write_bundle,
)


GOOD_CONTEXT = {
    "GITHUB_REPOSITORY": "rnnyrgs-web/tradingview-ai-crypto",
    "GITHUB_REF": "refs/heads/main",
    "GITHUB_EVENT_NAME": "workflow_dispatch",
    "GITHUB_SHA": "a" * 40,
    "GITHUB_WORKFLOW_REF": (
        "rnnyrgs-web/tradingview-ai-crypto/.github/workflows/"
        "pit-trusted-remote-acquisition.yml@refs/heads/main"
    ),
    "GITHUB_RUN_ID": "123456",
    "GITHUB_RUN_ATTEMPT": "1",
}


def _result(body: bytes = b"provider bytes", *, status: int = 200) -> FetchResult:
    return FetchResult(
        status=status,
        headers={"content-type": "application/octet-stream", "etag": '"abc"'},
        body=body,
        started_at="2026-09-21T10:00:00Z",
        completed_at="2026-09-21T10:00:01Z",
    )


def test_binance_request_is_built_from_frozen_host_path_and_query():
    request = freeze_binance_listobjects_request(
        prefix="data/spot/monthly/klines/BTCUSDT/1d/"
    )
    assert request.host == "s3-ap-northeast-1.amazonaws.com"
    assert request.target.startswith("/data.binance.vision?list-type=2&prefix=")
    assert "BTCUSDT" in request.url
    assert request.range_header is None


def test_binance_prefix_cannot_escape_frozen_archive_family():
    with pytest.raises(ValueError, match="frozen spot"):
        freeze_binance_listobjects_request(prefix="data/futures/um/monthly/klines/")
    with pytest.raises(ValueError, match="forbidden"):
        freeze_binance_listobjects_request(
            prefix="data/spot/monthly/klines/../secret/"
        )


def test_binance_pagination_requires_receipt_chain():
    with pytest.raises(ValueError, match="predecessor"):
        freeze_binance_listobjects_request(
            prefix="data/spot/monthly/klines/",
            continuation_token="next-page",
        )
    predecessor = "b" * 64
    request = freeze_binance_listobjects_request(
        prefix="data/spot/monthly/klines/",
        continuation_token="opaque+/=",
        predecessor_receipt_sha256=predecessor,
    )
    assert request.predecessor_receipt_sha256 == predecessor
    assert "continuation-token=opaque%2B%2F%3D" in request.url


def test_commoncrawl_index_freezes_collection_and_exact_target_url():
    request = freeze_commoncrawl_index_request(
        collection="CC-MAIN-2026-34",
        target_url="https://example.org/project/docs?a=1",
    )
    assert request.host == "index.commoncrawl.org"
    assert request.target.startswith("/CC-MAIN-2026-34-index?")
    assert "output=json" in request.target
    assert "example.org" in request.target

    with pytest.raises(ValueError, match="clean HTTPS"):
        freeze_commoncrawl_index_request(
            collection="CC-MAIN-2026-34",
            target_url="http://example.org/docs",
        )


def test_commoncrawl_warc_range_is_bounded_and_collection_bound():
    request = freeze_commoncrawl_warc_request(
        collection="CC-MAIN-2026-34",
        filename=(
            "crawl-data/CC-MAIN-2026-34/segments/123.0/warc/"
            "CC-MAIN-20260901000000-00000.warc.gz"
        ),
        offset=100,
        length=250,
    )
    assert request.host == "data.commoncrawl.org"
    assert request.range_header == "bytes=100-349"
    assert request.max_response_bytes == 250

    with pytest.raises(ValueError, match="filename/collection mismatch"):
        freeze_commoncrawl_warc_request(
            collection="CC-MAIN-2026-34",
            filename="crawl-data/CC-MAIN-2025-30/segments/123/warc/x.warc.gz",
            offset=0,
            length=100,
        )


def test_trusted_context_fails_closed_outside_canonical_main_dispatch():
    parsed = trusted_github_context(GOOD_CONTEXT)
    assert parsed["repository"] == "rnnyrgs-web/tradingview-ai-crypto"
    assert parsed["run_id"] == 123456

    for key, bad in (
        ("GITHUB_REF", "refs/heads/feature"),
        ("GITHUB_EVENT_NAME", "pull_request"),
        ("GITHUB_REPOSITORY", "attacker/fork"),
        ("GITHUB_SHA", "short"),
        ("GITHUB_WORKFLOW_REF", "attacker/workflow@refs/heads/main"),
    ):
        modified = dict(GOOD_CONTEXT)
        modified[key] = bad
        with pytest.raises(ValueError):
            trusted_github_context(modified)


def test_trusted_context_rejects_sibling_workflow_on_same_repo_main():
    modified = dict(GOOD_CONTEXT)
    modified["GITHUB_WORKFLOW_REF"] = (
        "rnnyrgs-web/tradingview-ai-crypto/.github/workflows/"
        "sibling.yml@refs/heads/main"
    )
    with pytest.raises(ValueError, match="exact trusted acquisition workflow"):
        trusted_github_context(modified)


def test_receipt_binds_exact_response_bytes_and_runner_identity():
    request = freeze_binance_listobjects_request(
        prefix="data/spot/monthly/klines/BTCUSDT/1d/"
    )
    context = trusted_github_context(GOOD_CONTEXT)
    receipt = canonical_receipt(request, _result(b"real response"), github_context=context)
    assert receipt["source_contract_id"] == CONTRACT_ID
    assert receipt["response"]["sha256"] == hashlib.sha256(b"real response").hexdigest()
    assert receipt["acquisition"]["git_sha"] == "a" * 40
    verify_receipt_bytes(receipt, b"real response")
    with pytest.raises(ValueError, match="response bytes"):
        verify_receipt_bytes(receipt, b"fabricated response")


def test_receipt_fingerprint_detects_metadata_tamper():
    request = freeze_binance_listobjects_request(
        prefix="data/spot/monthly/klines/BTCUSDT/1d/"
    )
    receipt = canonical_receipt(
        request, _result(), github_context=trusted_github_context(GOOD_CONTEXT)
    )
    receipt["request"]["url"] = "https://example.org/fabricated"
    with pytest.raises(ValueError, match="fingerprint"):
        verify_receipt_bytes(receipt, b"provider bytes")


def test_bundle_is_deterministic_for_identical_receipt_and_response(tmp_path: Path):
    request = freeze_binance_listobjects_request(
        prefix="data/spot/monthly/klines/BTCUSDT/1d/"
    )
    context = trusted_github_context(GOOD_CONTEXT)
    result = _result()
    first = write_bundle(request, result, output_dir=tmp_path / "a", github_context=context)
    second = write_bundle(request, result, output_dir=tmp_path / "b", github_context=context)
    assert first["bundle_sha256"] == second["bundle_sha256"]

    bundle = (tmp_path / "a" / "trusted-acquisition.tar").read_bytes()
    with tarfile.open(fileobj=io.BytesIO(bundle), mode="r:") as archive:
        assert sorted(archive.getnames()) == ["receipt.json", "response.bin"]
        receipt = json.loads(archive.extractfile("receipt.json").read())
        response = archive.extractfile("response.bin").read()
    verify_receipt_bytes(receipt, response)


def test_caller_backdated_available_at_has_no_input_surface():
    request = freeze_commoncrawl_index_request(
        collection="CC-MAIN-2026-34",
        target_url="https://example.org/docs",
    )
    receipt = canonical_receipt(
        request, _result(), github_context=trusted_github_context(GOOD_CONTEXT)
    )
    serialized = json.dumps(receipt, sort_keys=True)
    assert "available_at" not in serialized
    assert "published_at" not in serialized


def test_frozen_contract_bytes_match_code_pin(tmp_path: Path):
    root = tmp_path
    (root / "money_intelligence").mkdir()
    source = (
        Path(__file__).resolve().parents[1]
        / "money_intelligence"
        / "trusted_remote_acquisition_contract_v1.json"
    )
    target = root / "money_intelligence" / "trusted_remote_acquisition_contract_v1.json"
    target.write_bytes(source.read_bytes())
    assert load_contract(root)["artifact_id"] == CONTRACT_ID
    target.write_text(target.read_text() + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        load_contract(root)
