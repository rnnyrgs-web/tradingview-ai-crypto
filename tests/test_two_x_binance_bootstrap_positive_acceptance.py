from __future__ import annotations

import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import io
import json
import tarfile
import zipfile

import pytest

from two_x_binance_bootstrap_positive_acceptance import (
    ARCHIVE_SOURCE_KIND,
    ARCHIVE_URL,
    CHECKSUM_SOURCE_KIND,
    CHECKSUM_URL,
    CONTROL_PLANE_SCHEMA,
    EXPECTED_ARCHIVE_FILENAME,
    EXPECTED_MEMBER_FILENAME,
    PositiveAcceptanceError,
    REPOSITORY,
    RECEIPT_SCHEMA,
    ACQUISITION_SIGNER_WORKFLOW,
    accept_positive_canary,
    load_contract,
)

MAIN_SHA = "a" * 40


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _archive(*, start_day: int = 1, extra_member: bool = False) -> bytes:
    rows = []
    base = datetime(2021, 1, start_day, tzinfo=timezone.utc)
    for offset in range(31):
        open_at = base.timestamp() * 1000 + offset * 86_400_000
        open_ms = int(open_at)
        close_ms = open_ms + 86_400_000 - 1
        close = Decimal(10_000 + offset)
        rows.append(
            [
                str(open_ms),
                str(close - 5),
                str(close + 10),
                str(close - 10),
                str(close),
                "123.45",
                str(close_ms),
                "456789.12",
                "42",
                "61.0",
                "230000.0",
                "0",
            ]
        )
    csv_text = "\n".join(",".join(row) for row in rows) + "\n"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(EXPECTED_MEMBER_FILENAME, csv_text)
        if extra_member:
            zf.writestr("unexpected.csv", csv_text)
    return out.getvalue()


def _receipt(
    *,
    source_kind: str,
    url: str,
    response: bytes,
    run_id: int,
    contract_sha: str,
    main_sha: str = MAIN_SHA,
    provider_metadata: dict | None = None,
    extra: dict | None = None,
) -> dict:
    scientific = {
        "provenance_bound_price_consumer_possible_after_downstream_validation": True,
        "usd_liquidity_authority": False,
        "cohort_membership_authority": False,
        "historical_label_authority": False,
        "matched_control_authority": False,
        "prospective_candidate_authority": False,
        "prediction_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
        "live_trading": False,
    }
    payload = {
        "schema": RECEIPT_SCHEMA,
        "source_contract_id": "2X-BINANCE-COHORT-BOOTSTRAP-SLICE-001-v1",
        "source_contract_sha256": contract_sha,
        "consumer": "#705/#710 BTCUSDT Spot 1d Cohort-001 provenance canary",
        "source_kind": source_kind,
        "request": {"method": "GET", "url": url, "range_header": None},
        "response": {
            "status": 200,
            "sha256": _sha(response),
            "byte_count": len(response),
            "content_type": "application/octet-stream",
            "etag": None,
            "last_modified": None,
        },
        "provider_metadata": provider_metadata or {},
        "acquisition": {
            "started_at": "2026-09-23T18:00:00Z",
            "completed_at": "2026-09-23T18:00:01Z",
            "repository": REPOSITORY,
            "git_sha": main_sha,
            "git_ref": "refs/heads/main",
            "workflow_ref": f"{REPOSITORY}/.github/workflows/pit-trusted-remote-acquisition.yml@refs/heads/main",
            "run_id": run_id,
            "run_attempt": 1,
            "event_name": "workflow_dispatch",
        },
        "authority": "PROVIDER_BYTES_AUTHENTICATED_ONLY_AFTER_GITHUB_ATTESTATION_VERIFICATION",
        "scientific_authority": scientific,
    }
    if extra:
        payload.update(extra)
    payload["receipt_sha256"] = _sha(_canonical(payload))
    return payload


def _tar(receipt: dict, response: bytes, *, extra_member: bool = False) -> bytes:
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as tf:
        for name, raw in (("receipt.json", _canonical(receipt)), ("response.bin", response)):
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            info.mtime = 0
            tf.addfile(info, io.BytesIO(raw))
        if extra_member:
            raw = b"forbidden"
            info = tarfile.TarInfo("extra.txt")
            info.size = len(raw)
            tf.addfile(info, io.BytesIO(raw))
    return out.getvalue()


def _verification(bundle: bytes, *, subject_sha: str | None = None) -> bytes:
    digest = subject_sha or _sha(bundle)
    wrapped = {
        "schema": "gh_attestation_verify_output.v1",
        "results": [
            {
                "attestation": {},
                "verificationResult": {
                    "statement": {
                        "predicateType": "https://slsa.dev/provenance/v1",
                        "subject": [{"name": "trusted-acquisition.tar", "digest": {"sha256": digest}}],
                    }
                },
            }
        ],
    }
    return _canonical(wrapped)


def _control(bundle: bytes, verification: bytes, *, run_id: int, main_sha: str = MAIN_SHA) -> dict:
    return {
        "schema": CONTROL_PLANE_SCHEMA,
        "repository": REPOSITORY,
        "signer_workflow": ACQUISITION_SIGNER_WORKFLOW,
        "source_ref": "refs/heads/main",
        "source_digest": main_sha,
        "run_id": run_id,
        "run_attempt": 1,
        "artifact_name": f"trusted-remote-acquisition-{run_id}-1",
        "bundle_sha256": _sha(bundle),
        "gh_attestation_verification_sha256": _sha(verification),
        "gh_attestation_verify_exit_code": 0,
        "deny_self_hosted_runners": True,
    }


def _pair(*, archive: bytes | None = None, checksum: bytes | None = None):
    _, contract_sha = load_contract()
    archive = _archive() if archive is None else archive
    checksum = (
        f"{_sha(archive)}  {EXPECTED_ARCHIVE_FILENAME}\n".encode("ascii")
        if checksum is None
        else checksum
    )
    archive_receipt = _receipt(
        source_kind=ARCHIVE_SOURCE_KIND,
        url=ARCHIVE_URL,
        response=archive,
        run_id=100,
        contract_sha=contract_sha,
        provider_metadata={
            "declared_archive_sha256": None,
            "archive_filename": EXPECTED_ARCHIVE_FILENAME,
        },
    )
    checksum_receipt = _receipt(
        source_kind=CHECKSUM_SOURCE_KIND,
        url=CHECKSUM_URL,
        response=checksum,
        run_id=101,
        contract_sha=contract_sha,
        provider_metadata={
            "declared_archive_sha256": _sha(archive),
            "archive_filename": EXPECTED_ARCHIVE_FILENAME,
        },
    )
    archive_bundle = _tar(archive_receipt, archive)
    checksum_bundle = _tar(checksum_receipt, checksum)
    archive_verification = _verification(archive_bundle)
    checksum_verification = _verification(checksum_bundle)
    return {
        "archive_bundle_raw": archive_bundle,
        "checksum_bundle_raw": checksum_bundle,
        "archive_control_plane": _control(archive_bundle, archive_verification, run_id=100),
        "checksum_control_plane": _control(checksum_bundle, checksum_verification, run_id=101),
        "archive_verification_raw": archive_verification,
        "checksum_verification_raw": checksum_verification,
    }


def test_positive_pair_exposes_only_predeclared_decision_price() -> None:
    result = accept_positive_canary(**_pair())
    assert result["status"] == "PROVENANCE_BOOTSTRAP_SLICE_AUTHENTICATED_PRICE_ONLY"
    assert result["decision_bar_date"] == "2021-01-31"
    assert result["decision_price"] == "10030"
    assert result["source_native_binding"]["provider_native_close_times_before_decision_verified"] is True
    assert result["source_native_binding"]["caller_authored_event_time_authority"] is False
    assert result["trust_boundary"]["standalone_python_output_is_trusted"] is False
    assert result["scientific_authority"]["decision_price"] is True
    for key in (
        "historical_universe_membership",
        "listing_age",
        "usd_liquidity",
        "strict_tradability",
        "historical_2x_label",
        "matched_control",
        "precursor_or_graph_effect",
        "competing_risk_model",
        "prospective_candidate",
        "prediction",
        "promotion",
        "broker_connected",
        "live_trading",
    ):
        assert result["scientific_authority"][key] is False


def test_gh_verified_subject_must_bind_exact_bundle_bytes() -> None:
    pair = _pair()
    bad = _verification(pair["archive_bundle_raw"], subject_sha="0" * 64)
    pair["archive_verification_raw"] = bad
    pair["archive_control_plane"] = _control(pair["archive_bundle_raw"], bad, run_id=100)
    with pytest.raises(PositiveAcceptanceError, match="subject does not bind exact bundle SHA"):
        accept_positive_canary(**pair)


def test_control_plane_identity_cannot_change_repository_or_signer_or_ref() -> None:
    for field, value, match in (
        ("repository", "attacker/repo", "repository mismatch"),
        ("signer_workflow", "attacker/repo/.github/workflows/x.yml", "signer workflow mismatch"),
        ("source_ref", "refs/heads/feature", "source ref mismatch"),
    ):
        pair = _pair()
        pair["archive_control_plane"][field] = value
        with pytest.raises(PositiveAcceptanceError, match=match):
            accept_positive_canary(**pair)


def test_attestation_failure_or_self_hosted_allowance_fails_closed() -> None:
    pair = _pair()
    pair["archive_control_plane"]["gh_attestation_verify_exit_code"] = 1
    with pytest.raises(PositiveAcceptanceError, match="verification did not succeed"):
        accept_positive_canary(**pair)

    pair = _pair()
    pair["archive_control_plane"]["deny_self_hosted_runners"] = False
    with pytest.raises(PositiveAcceptanceError, match="must deny self-hosted"):
        accept_positive_canary(**pair)


def test_archive_and_checksum_must_be_independent_same_main_runs() -> None:
    pair = _pair()
    pair["checksum_control_plane"]["run_id"] = 100
    pair["checksum_control_plane"]["artifact_name"] = "trusted-remote-acquisition-100-1"
    with pytest.raises(PositiveAcceptanceError, match="independently acquired runs"):
        accept_positive_canary(**pair)

    pair = _pair()
    pair["checksum_control_plane"]["source_digest"] = "b" * 40
    with pytest.raises(PositiveAcceptanceError, match="same canonical main SHA"):
        accept_positive_canary(**pair)


def test_response_substitution_cannot_survive_receipt_and_attestation_binding() -> None:
    pair = _pair()
    _, contract_sha = load_contract()
    substituted = _archive(extra_member=True)
    # Keep the old receipt but rebuild/reattest the outer tar: the inner response hash
    # must still detect that the provider bytes no longer match the acquisition receipt.
    old_receipt_raw, _ = _extract_pair(pair["archive_bundle_raw"])
    old_receipt = json.loads(old_receipt_raw)
    tampered_bundle = _tar(old_receipt, substituted)
    verification = _verification(tampered_bundle)
    pair["archive_bundle_raw"] = tampered_bundle
    pair["archive_verification_raw"] = verification
    pair["archive_control_plane"] = _control(tampered_bundle, verification, run_id=100)
    with pytest.raises(PositiveAcceptanceError, match="retained response SHA mismatch"):
        accept_positive_canary(**pair)


def _extract_pair(bundle_raw: bytes) -> tuple[bytes, bytes]:
    with tarfile.open(fileobj=io.BytesIO(bundle_raw), mode="r:*") as tf:
        r = tf.extractfile("receipt.json")
        b = tf.extractfile("response.bin")
        assert r is not None and b is not None
        return r.read(), b.read()


def test_checksum_must_bind_exact_filename_and_archive_digest() -> None:
    archive = _archive()
    wrong_name = f"{_sha(archive)}  OTHER-1d-2021-01.zip\n".encode()
    with pytest.raises(PositiveAcceptanceError, match="checksum must bind exact archive filename"):
        accept_positive_canary(**_pair(archive=archive, checksum=wrong_name))

    wrong_digest = f"{'0' * 64}  {EXPECTED_ARCHIVE_FILENAME}\n".encode()
    with pytest.raises(PositiveAcceptanceError, match="checksum digest does not match"):
        accept_positive_canary(**_pair(archive=archive, checksum=wrong_digest))


def test_unsafe_or_multi_member_zip_is_rejected_after_provenance_binding() -> None:
    archive = _archive(extra_member=True)
    with pytest.raises(PositiveAcceptanceError, match="exactly one data member"):
        accept_positive_canary(**_pair(archive=archive))


def test_cross_period_or_post_decision_native_rows_fail_closed() -> None:
    archive = _archive(start_day=2)
    with pytest.raises(PositiveAcceptanceError, match="open-time coverage is not exactly"):
        accept_positive_canary(**_pair(archive=archive))


def test_legacy_or_extra_caller_chronology_cannot_enter_positive_path() -> None:
    pair = _pair()
    receipt_raw, response = _extract_pair(pair["archive_bundle_raw"])
    receipt = json.loads(receipt_raw)
    receipt["event_time_max"] = "2020-01-01T00:00:00Z"
    receipt["receipt_sha256"] = ""
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256")
    receipt["receipt_sha256"] = _sha(_canonical(unsigned))
    bundle = _tar(receipt, response)
    verification = _verification(bundle)
    pair["archive_bundle_raw"] = bundle
    pair["archive_verification_raw"] = verification
    pair["archive_control_plane"] = _control(bundle, verification, run_id=100)
    with pytest.raises(PositiveAcceptanceError, match="receipt shape mismatch"):
        accept_positive_canary(**pair)

    pair = _pair()
    receipt_raw, response = _extract_pair(pair["archive_bundle_raw"])
    receipt = json.loads(receipt_raw)
    receipt["schema"] = "binance_public_archive_proof.v1"
    receipt["receipt_sha256"] = ""
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256")
    receipt["receipt_sha256"] = _sha(_canonical(unsigned))
    bundle = _tar(receipt, response)
    verification = _verification(bundle)
    pair["archive_bundle_raw"] = bundle
    pair["archive_verification_raw"] = verification
    pair["archive_control_plane"] = _control(bundle, verification, run_id=100)
    with pytest.raises(PositiveAcceptanceError, match="not the trusted 2x bootstrap acquisition schema"):
        accept_positive_canary(**pair)


def test_outer_bundle_shape_is_fail_closed() -> None:
    pair = _pair()
    receipt_raw, response = _extract_pair(pair["archive_bundle_raw"])
    receipt = json.loads(receipt_raw)
    bundle = _tar(receipt, response, extra_member=True)
    verification = _verification(bundle)
    pair["archive_bundle_raw"] = bundle
    pair["archive_verification_raw"] = verification
    pair["archive_control_plane"] = _control(bundle, verification, run_id=100)
    with pytest.raises(PositiveAcceptanceError, match="exactly two files"):
        accept_positive_canary(**pair)
