from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from trusted_remote_acquisition import FetchResult
from two_x_binance_bootstrap_direct_acquisition import (
    ARCHIVE_OBJECT_PATH,
    ARCHIVE_SOURCE_KIND,
    CHECKSUM_OBJECT_PATH,
    CHECKSUM_SOURCE_KIND,
    CONTRACT_ID,
    _validate_provider_body,
    canonical_receipt,
    contract_sha256,
    freeze_binance_2x_bootstrap_request,
    load_contract,
)


GOOD_CONTEXT = {
    "repository": "rnnyrgs-web/tradingview-ai-crypto",
    "git_sha": "a" * 40,
    "git_ref": "refs/heads/main",
    "workflow_ref": (
        "rnnyrgs-web/tradingview-ai-crypto/.github/workflows/"
        "pit-trusted-remote-acquisition.yml@refs/heads/main"
    ),
    "run_id": 123,
    "run_attempt": 1,
    "event_name": "workflow_dispatch",
}


def _result(body: bytes) -> FetchResult:
    return FetchResult(
        status=200,
        headers={"content-type": "application/octet-stream"},
        body=body,
        started_at="2026-09-23T16:00:00Z",
        completed_at="2026-09-23T16:00:01Z",
    )


def test_accepts_only_exact_frozen_archive_and_checksum_objects():
    archive = freeze_binance_2x_bootstrap_request(
        source_kind=ARCHIVE_SOURCE_KIND,
        object_path=ARCHIVE_OBJECT_PATH,
    )
    checksum = freeze_binance_2x_bootstrap_request(
        source_kind=CHECKSUM_SOURCE_KIND,
        object_path=CHECKSUM_OBJECT_PATH,
    )
    assert archive.url == "https://data.binance.vision/" + ARCHIVE_OBJECT_PATH
    assert checksum.url == "https://data.binance.vision/" + CHECKSUM_OBJECT_PATH
    assert archive.range_header is None
    assert checksum.range_header is None


@pytest.mark.parametrize(
    "source_kind,object_path",
    [
        (ARCHIVE_SOURCE_KIND, "data/spot/monthly/klines/ETHUSDT/1d/ETHUSDT-1d-2021-01.zip"),
        (ARCHIVE_SOURCE_KIND, "data/spot/monthly/klines/BTCUSDT/1h/BTCUSDT-1h-2021-01.zip"),
        (ARCHIVE_SOURCE_KIND, "data/spot/monthly/klines/BTCUSDT/1d/BTCUSDT-1d-2021-02.zip"),
        (CHECKSUM_SOURCE_KIND, ARCHIVE_OBJECT_PATH),
        (ARCHIVE_SOURCE_KIND, CHECKSUM_OBJECT_PATH),
        ("BINANCE_C101H_ARCHIVE", ARCHIVE_OBJECT_PATH),
        (ARCHIVE_SOURCE_KIND, ARCHIVE_OBJECT_PATH + "?x=1"),
        (ARCHIVE_SOURCE_KIND, "data/spot/monthly/klines/BTCUSDT/1d/../BTCUSDT-1d-2021-01.zip"),
    ],
)
def test_cross_subject_period_cadence_kind_and_path_substitution_fail_closed(source_kind: str, object_path: str):
    with pytest.raises(ValueError):
        freeze_binance_2x_bootstrap_request(source_kind=source_kind, object_path=object_path)


def test_checksum_must_bind_exact_frozen_archive_filename():
    request = freeze_binance_2x_bootstrap_request(
        source_kind=CHECKSUM_SOURCE_KIND,
        object_path=CHECKSUM_OBJECT_PATH,
    )
    digest = "a" * 64
    metadata = _validate_provider_body(
        request,
        f"{digest}  BTCUSDT-1d-2021-01.zip\n".encode("ascii"),
    )
    assert metadata["declared_archive_sha256"] == digest
    assert metadata["archive_filename"] == "BTCUSDT-1d-2021-01.zip"

    with pytest.raises(ValueError, match="filename"):
        _validate_provider_body(
            request,
            f"{digest}  ETHUSDT-1d-2021-01.zip\n".encode("ascii"),
        )


def test_archive_response_must_be_zip_stream():
    request = freeze_binance_2x_bootstrap_request(
        source_kind=ARCHIVE_SOURCE_KIND,
        object_path=ARCHIVE_OBJECT_PATH,
    )
    assert _validate_provider_body(request, b"PK\x03\x04payload")["declared_archive_sha256"] is None
    with pytest.raises(ValueError, match="ZIP"):
        _validate_provider_body(request, b"not-a-zip")


def test_receipt_binds_bytes_contract_and_price_only_authority():
    request = freeze_binance_2x_bootstrap_request(
        source_kind=ARCHIVE_SOURCE_KIND,
        object_path=ARCHIVE_OBJECT_PATH,
    )
    result = _result(b"PK\x03\x04payload")
    metadata = _validate_provider_body(request, result.body)
    receipt = canonical_receipt(
        request,
        result,
        github_context=GOOD_CONTEXT,
        provider_metadata=metadata,
        source_contract_sha256="b" * 64,
    )
    assert receipt["source_contract_id"] == CONTRACT_ID
    assert receipt["source_contract_sha256"] == "b" * 64
    assert receipt["response"]["sha256"] == hashlib.sha256(result.body).hexdigest()
    authority = receipt["scientific_authority"]
    assert authority["provenance_bound_price_consumer_possible_after_downstream_validation"] is True
    assert authority["usd_liquidity_authority"] is False
    assert authority["cohort_membership_authority"] is False
    assert authority["historical_label_authority"] is False
    assert authority["matched_control_authority"] is False
    assert authority["prospective_candidate_authority"] is False
    assert authority["prediction_authority"] is False
    assert authority["promotion_authority"] is False
    assert authority["broker_connected"] is False
    assert authority["live_trading"] is False


def test_contract_loader_binds_exact_price_only_slice_and_rejects_semantic_drift(tmp_path: Path):
    source = Path(__file__).resolve().parents[1] / "money_intelligence" / "2x_binance_cohort_bootstrap_slice_v1.json"
    target_dir = tmp_path / "money_intelligence"
    target_dir.mkdir(parents=True)
    target = target_dir / source.name
    target.write_bytes(source.read_bytes())

    payload = load_contract(tmp_path)
    assert payload["artifact_id"] == CONTRACT_ID
    assert set(payload["allowed_scientific_consumers"]) == {"decision_price"}
    assert "trailing_30d_median_quote_volume_usd" in payload["blocked_scientific_consumers"]
    assert contract_sha256(tmp_path) == hashlib.sha256(target.read_bytes()).hexdigest()

    mutated = json.loads(target.read_text())
    mutated["allowed_scientific_consumers"]["trailing_30d_median_quote_volume_usd"] = {
        "semantics": "forbidden test mutation"
    }
    target.write_text(json.dumps(mutated), encoding="utf-8")
    with pytest.raises(ValueError, match="price-only"):
        load_contract(tmp_path)


def test_contract_loader_rejects_c101h_authority_laundering(tmp_path: Path):
    source = Path(__file__).resolve().parents[1] / "money_intelligence" / "2x_binance_cohort_bootstrap_slice_v1.json"
    target_dir = tmp_path / "money_intelligence"
    target_dir.mkdir(parents=True)
    target = target_dir / source.name
    payload = json.loads(source.read_text())
    payload["trusted_acquisition_requirements"]["c101h_source_kind_reuse_forbidden"] = False
    target.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="C101-H source-kind reuse"):
        load_contract(tmp_path)
