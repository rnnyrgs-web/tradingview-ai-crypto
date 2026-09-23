"""Positive trusted-attested Binance PIT acceptance for the frozen Cohort-001 canary.

This module is intentionally narrow.  It consumes the *already acquired* archive and
checksum bundles for ``2X-BINANCE-COHORT-BOOTSTRAP-SLICE-001-v1`` only after a
canonical GitHub control-plane workflow has cryptographically verified each bundle's
GitHub artifact attestation.  It then binds the attested bundle bytes to the exact
acquisition receipt, exact provider response bytes, exact Binance object identities,
and source-native daily-kline chronology.

Important trust boundary
------------------------
Candidate-controlled Python cannot manufacture its own artifact-attestation authority.
The ``control_plane`` records accepted here are therefore policy inputs, not signatures.
A result from this module gains scientific provenance authority only when the result
artifact itself is produced and attested by the canonical verifier workflow on
``main``.  Running this module locally, or fabricating a control-plane JSON document,
grants no scientific authority.

A successful result exposes one thing only: the frozen 2021-01-31 BTCUSDT Spot 1d
close that was fully closed before 2021-02-01T00:00:00Z.  It grants no historical
universe membership, listing-age, USD-liquidity, strict-tradability, outcome, matched
control, model, prospective-candidate, promotion, broker, or live-trading authority.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
from typing import Any
import zipfile

CONTRACT_PATH = "money_intelligence/2x_binance_cohort_bootstrap_slice_v1.json"
CONTRACT_ID = "2X-BINANCE-COHORT-BOOTSTRAP-SLICE-001-v1"
RESULT_SCHEMA = "two_x_binance_bootstrap_positive_acceptance.v1"
CONTROL_PLANE_SCHEMA = "two_x_github_attestation_control_plane.v1"
REPOSITORY = "rnnyrgs-web/tradingview-ai-crypto"
ACQUISITION_WORKFLOW_PATH = ".github/workflows/pit-trusted-remote-acquisition.yml"
ACQUISITION_WORKFLOW_REF = f"{REPOSITORY}/{ACQUISITION_WORKFLOW_PATH}@refs/heads/main"
ACQUISITION_SIGNER_WORKFLOW = f"{REPOSITORY}/{ACQUISITION_WORKFLOW_PATH}"
VERIFIER_WORKFLOW_PATH = ".github/workflows/2x-binance-bootstrap-positive-verify.yml"
VERIFIER_WORKFLOW_REF = f"{REPOSITORY}/{VERIFIER_WORKFLOW_PATH}@refs/heads/main"
EXPECTED_REF = "refs/heads/main"
EXPECTED_EVENT = "workflow_dispatch"
DECISION_AT = "2021-02-01T00:00:00Z"
EXPECTED_BAR_DATE = "2021-01-31"
EXPECTED_ARCHIVE_FILENAME = "BTCUSDT-1d-2021-01.zip"
EXPECTED_MEMBER_FILENAME = "BTCUSDT-1d-2021-01.csv"
ARCHIVE_SOURCE_KIND = "BINANCE_2X_COHORT_BOOTSTRAP_ARCHIVE"
CHECKSUM_SOURCE_KIND = "BINANCE_2X_COHORT_BOOTSTRAP_CHECKSUM"
ARCHIVE_URL = (
    "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1d/"
    "BTCUSDT-1d-2021-01.zip"
)
CHECKSUM_URL = ARCHIVE_URL + ".CHECKSUM"
RECEIPT_SCHEMA = "two_x_binance_bootstrap_direct_acquisition_receipt.v1"
MAX_BUNDLE_BYTES = 70 * 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_CHECKSUM_BYTES = 4096
MAX_CSV_BYTES = 64 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
CHECKSUM_RE = re.compile(
    rf"^(?P<sha>[0-9a-f]{{64}})[ \t]+\*?(?P<filename>{re.escape(EXPECTED_ARCHIVE_FILENAME)})\r?\n?$"
)
UTC = timezone.utc


class PositiveAcceptanceError(ValueError):
    """Raised when any provenance, identity, or source-native PIT gate fails."""


def _reject_duplicate_object_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PositiveAcceptanceError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _reject_nonstandard_constant(value: str) -> Any:
    raise PositiveAcceptanceError(f"non-standard JSON numeric constant: {value}")


def _strict_json_bytes(raw: bytes, *, field: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PositiveAcceptanceError(f"{field} must be UTF-8 JSON") from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_object_keys,
            parse_constant=_reject_nonstandard_constant,
        )
    except (json.JSONDecodeError, PositiveAcceptanceError) as exc:
        raise PositiveAcceptanceError(f"{field} rejected: {exc}") from exc
    if not isinstance(value, dict):
        raise PositiveAcceptanceError(f"{field} JSON root must be an object")
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _require_sha(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise PositiveAcceptanceError(f"{field} must be lowercase SHA-256")
    return value


def _require_positive_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PositiveAcceptanceError(f"{field} must be a positive integer")
    return value


def _utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PositiveAcceptanceError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise PositiveAcceptanceError(f"{field} must be valid RFC3339 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise PositiveAcceptanceError(f"{field} must be UTC")
    return parsed.astimezone(UTC)


def load_contract(repo_root: str | Path | None = None) -> tuple[dict[str, Any], str]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    raw = (root / CONTRACT_PATH).resolve().read_bytes()
    contract = _strict_json_bytes(raw, field="bootstrap contract")
    if contract.get("artifact_id") != CONTRACT_ID:
        raise PositiveAcceptanceError("bootstrap contract identity mismatch")
    selection = contract.get("selection")
    if not isinstance(selection, dict) or selection.get("decision_at") != DECISION_AT:
        raise PositiveAcceptanceError("bootstrap decision timestamp drifted")
    subject = selection.get("subject")
    if not isinstance(subject, dict) or subject != {
        "venue": "BINANCE_SPOT",
        "symbol": "BTCUSDT",
        "base_asset": "BTC",
        "quote_asset": "USDT",
        "dataset": "klines",
        "cadence": "1d",
        "archive_period": "2021-01",
    }:
        raise PositiveAcceptanceError("bootstrap subject identity drifted")
    objects = contract.get("provider_objects")
    if not isinstance(objects, dict):
        raise PositiveAcceptanceError("bootstrap provider object contract missing")
    archive = objects.get("archive")
    checksum = objects.get("checksum")
    if not isinstance(archive, dict) or not isinstance(checksum, dict):
        raise PositiveAcceptanceError("bootstrap provider object contract malformed")
    if archive.get("source_kind") != ARCHIVE_SOURCE_KIND or archive.get("url") != ARCHIVE_URL:
        raise PositiveAcceptanceError("bootstrap archive identity drifted")
    if checksum.get("source_kind") != CHECKSUM_SOURCE_KIND or checksum.get("url") != CHECKSUM_URL:
        raise PositiveAcceptanceError("bootstrap checksum identity drifted")
    allowed = contract.get("allowed_scientific_consumers")
    if not isinstance(allowed, dict) or set(allowed) != {"decision_price"}:
        raise PositiveAcceptanceError("bootstrap must remain decision-price only")
    if contract.get("broker_live_trading") != "OFF":
        raise PositiveAcceptanceError("broker/live trading must remain OFF")
    return contract, _sha256(raw)


def _safe_bundle_members(bundle_raw: bytes, *, field: str) -> tuple[bytes, bytes]:
    if not isinstance(bundle_raw, bytes) or not bundle_raw:
        raise PositiveAcceptanceError(f"{field} bundle must be non-empty bytes")
    if len(bundle_raw) > MAX_BUNDLE_BYTES:
        raise PositiveAcceptanceError(f"{field} bundle exceeds frozen size limit")
    try:
        with tarfile.open(fileobj=io.BytesIO(bundle_raw), mode="r:*") as bundle:
            members = bundle.getmembers()
            if len(members) != 2:
                raise PositiveAcceptanceError(f"{field} bundle must contain exactly two files")
            expected = {"receipt.json", "response.bin"}
            names = {member.name for member in members}
            if names != expected:
                raise PositiveAcceptanceError(f"{field} bundle members must be exactly {sorted(expected)}")
            for member in members:
                path = PurePosixPath(member.name)
                if path.is_absolute() or ".." in path.parts or len(path.parts) != 1:
                    raise PositiveAcceptanceError(f"{field} bundle member path is unsafe")
                if not member.isfile() or member.issym() or member.islnk():
                    raise PositiveAcceptanceError(f"{field} bundle members must be regular files")
                if member.size < 0 or member.size > MAX_ARCHIVE_BYTES + 1_000_000:
                    raise PositiveAcceptanceError(f"{field} bundle member size is unsafe")
            receipt_handle = bundle.extractfile("receipt.json")
            response_handle = bundle.extractfile("response.bin")
            if receipt_handle is None or response_handle is None:
                raise PositiveAcceptanceError(f"{field} bundle members could not be read")
            receipt_raw = receipt_handle.read(1_000_001)
            response_raw = response_handle.read(MAX_ARCHIVE_BYTES + 1)
    except (tarfile.TarError, OSError) as exc:
        raise PositiveAcceptanceError(f"{field} bundle is not a valid safe tar") from exc
    if len(receipt_raw) > 1_000_000:
        raise PositiveAcceptanceError(f"{field} receipt exceeds size limit")
    if len(response_raw) > MAX_ARCHIVE_BYTES:
        raise PositiveAcceptanceError(f"{field} response exceeds size limit")
    return receipt_raw, response_raw


def _validate_control_plane(
    control: dict[str, Any],
    verification_raw: bytes,
    bundle_raw: bytes,
    *,
    field: str,
) -> dict[str, Any]:
    expected_keys = {
        "schema",
        "repository",
        "signer_workflow",
        "source_ref",
        "source_digest",
        "run_id",
        "run_attempt",
        "artifact_name",
        "bundle_sha256",
        "gh_attestation_verification_sha256",
        "gh_attestation_verify_exit_code",
        "deny_self_hosted_runners",
    }
    if set(control) != expected_keys:
        raise PositiveAcceptanceError(f"{field} control-plane shape mismatch")
    if control.get("schema") != CONTROL_PLANE_SCHEMA:
        raise PositiveAcceptanceError(f"{field} control-plane schema mismatch")
    if control.get("repository") != REPOSITORY:
        raise PositiveAcceptanceError(f"{field} control-plane repository mismatch")
    if control.get("signer_workflow") != ACQUISITION_SIGNER_WORKFLOW:
        raise PositiveAcceptanceError(f"{field} control-plane signer workflow mismatch")
    if control.get("source_ref") != EXPECTED_REF:
        raise PositiveAcceptanceError(f"{field} control-plane source ref mismatch")
    source_digest = control.get("source_digest")
    if not isinstance(source_digest, str) or re.fullmatch(r"[0-9a-f]{40}", source_digest) is None:
        raise PositiveAcceptanceError(f"{field} source_digest must be a full Git commit SHA")
    run_id = _require_positive_int(control.get("run_id"), field=f"{field}.run_id")
    run_attempt = _require_positive_int(control.get("run_attempt"), field=f"{field}.run_attempt")
    expected_artifact_name = f"trusted-remote-acquisition-{run_id}-{run_attempt}"
    if control.get("artifact_name") != expected_artifact_name:
        raise PositiveAcceptanceError(f"{field} artifact name does not bind run/attempt")
    if control.get("bundle_sha256") != _sha256(bundle_raw):
        raise PositiveAcceptanceError(f"{field} bundle SHA does not match verified control-plane input")
    if control.get("gh_attestation_verification_sha256") != _sha256(verification_raw):
        raise PositiveAcceptanceError(f"{field} gh verification output SHA mismatch")
    if control.get("gh_attestation_verify_exit_code") != 0:
        raise PositiveAcceptanceError(f"{field} GitHub attestation verification did not succeed")
    if control.get("deny_self_hosted_runners") is not True:
        raise PositiveAcceptanceError(f"{field} must deny self-hosted attestation signers")

    verification = _strict_json_bytes(verification_raw, field=f"{field} gh attestation verification")
    # `gh attestation verify --format json` emits an array.  For deterministic unit
    # tests and future CLI-shape compatibility, the control-plane workflow stores the
    # selected verified result as an object with the raw CLI array under `results`.
    if verification.get("schema") != "gh_attestation_verify_output.v1":
        raise PositiveAcceptanceError(f"{field} verification wrapper schema mismatch")
    results = verification.get("results")
    if not isinstance(results, list) or not results:
        raise PositiveAcceptanceError(f"{field} has no verified attestation result")
    bundle_sha = _sha256(bundle_raw)
    subject_match = False
    for item in results:
        if not isinstance(item, dict):
            continue
        vr = item.get("verificationResult")
        statement = vr.get("statement") if isinstance(vr, dict) else None
        subjects = statement.get("subject") if isinstance(statement, dict) else None
        if not isinstance(subjects, list):
            continue
        for subject in subjects:
            digest = subject.get("digest") if isinstance(subject, dict) else None
            if isinstance(digest, dict) and digest.get("sha256") == bundle_sha:
                subject_match = True
    if not subject_match:
        raise PositiveAcceptanceError(f"{field} verified attestation subject does not bind exact bundle SHA")
    return {
        "source_digest": source_digest,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "artifact_name": expected_artifact_name,
        "bundle_sha256": bundle_sha,
        "verification_sha256": _sha256(verification_raw),
    }


def _validate_receipt(
    receipt_raw: bytes,
    response_raw: bytes,
    control: dict[str, Any],
    contract_sha256: str,
    *,
    source_kind: str,
    url: str,
    field: str,
) -> dict[str, Any]:
    receipt = _strict_json_bytes(receipt_raw, field=f"{field} acquisition receipt")
    expected_top = {
        "schema",
        "source_contract_id",
        "source_contract_sha256",
        "consumer",
        "source_kind",
        "request",
        "response",
        "provider_metadata",
        "acquisition",
        "authority",
        "scientific_authority",
        "receipt_sha256",
    }
    if set(receipt) != expected_top:
        raise PositiveAcceptanceError(f"{field} acquisition receipt shape mismatch")
    if receipt.get("schema") != RECEIPT_SCHEMA:
        raise PositiveAcceptanceError(f"{field} receipt is not the trusted 2x bootstrap acquisition schema")
    if receipt.get("source_contract_id") != CONTRACT_ID:
        raise PositiveAcceptanceError(f"{field} receipt source contract mismatch")
    if receipt.get("source_contract_sha256") != contract_sha256:
        raise PositiveAcceptanceError(f"{field} receipt source contract digest mismatch")
    if receipt.get("source_kind") != source_kind:
        raise PositiveAcceptanceError(f"{field} receipt source kind mismatch")
    request = receipt.get("request")
    if not isinstance(request, dict) or set(request) != {"method", "url", "range_header"}:
        raise PositiveAcceptanceError(f"{field} request shape mismatch")
    if request != {"method": "GET", "url": url, "range_header": None}:
        raise PositiveAcceptanceError(f"{field} request identity mismatch")
    response = receipt.get("response")
    if not isinstance(response, dict):
        raise PositiveAcceptanceError(f"{field} response metadata missing")
    required_response = {"status", "sha256", "byte_count", "content_type", "etag", "last_modified"}
    if set(response) != required_response:
        raise PositiveAcceptanceError(f"{field} response metadata shape mismatch")
    if response.get("status") != 200:
        raise PositiveAcceptanceError(f"{field} provider response was not HTTP 200")
    if response.get("sha256") != _sha256(response_raw):
        raise PositiveAcceptanceError(f"{field} retained response SHA mismatch")
    if response.get("byte_count") != len(response_raw):
        raise PositiveAcceptanceError(f"{field} retained response byte count mismatch")

    acquisition = receipt.get("acquisition")
    if not isinstance(acquisition, dict):
        raise PositiveAcceptanceError(f"{field} acquisition identity missing")
    required_acquisition = {
        "started_at", "completed_at", "repository", "git_sha", "git_ref",
        "workflow_ref", "run_id", "run_attempt", "event_name",
    }
    if set(acquisition) != required_acquisition:
        raise PositiveAcceptanceError(f"{field} acquisition identity shape mismatch")
    started = _utc(acquisition.get("started_at"), field=f"{field}.started_at")
    completed = _utc(acquisition.get("completed_at"), field=f"{field}.completed_at")
    if completed < started:
        raise PositiveAcceptanceError(f"{field} acquisition completed before it started")
    if acquisition.get("repository") != REPOSITORY:
        raise PositiveAcceptanceError(f"{field} acquisition repository mismatch")
    if acquisition.get("git_ref") != EXPECTED_REF:
        raise PositiveAcceptanceError(f"{field} acquisition ref mismatch")
    if acquisition.get("workflow_ref") != ACQUISITION_WORKFLOW_REF:
        raise PositiveAcceptanceError(f"{field} acquisition workflow mismatch")
    if acquisition.get("event_name") != EXPECTED_EVENT:
        raise PositiveAcceptanceError(f"{field} acquisition event mismatch")
    if acquisition.get("git_sha") != control["source_digest"]:
        raise PositiveAcceptanceError(f"{field} acquisition SHA is not the attestation-enforced source digest")
    if acquisition.get("run_id") != control["run_id"] or acquisition.get("run_attempt") != control["run_attempt"]:
        raise PositiveAcceptanceError(f"{field} acquisition run identity mismatch")

    if receipt.get("authority") != "PROVIDER_BYTES_AUTHENTICATED_ONLY_AFTER_GITHUB_ATTESTATION_VERIFICATION":
        raise PositiveAcceptanceError(f"{field} receipt authority marker mismatch")
    scientific = receipt.get("scientific_authority")
    if not isinstance(scientific, dict):
        raise PositiveAcceptanceError(f"{field} scientific authority block missing")
    forbidden_true = {
        "usd_liquidity_authority",
        "cohort_membership_authority",
        "historical_label_authority",
        "matched_control_authority",
        "prospective_candidate_authority",
        "prediction_authority",
        "promotion_authority",
        "broker_connected",
        "live_trading",
    }
    if any(scientific.get(key) is not False for key in forbidden_true):
        raise PositiveAcceptanceError(f"{field} acquisition receipt attempts to broaden scientific authority")
    if scientific.get("provenance_bound_price_consumer_possible_after_downstream_validation") is not True:
        raise PositiveAcceptanceError(f"{field} receipt does not authorize the bounded price consumer")

    stored_fingerprint = _require_sha(receipt.get("receipt_sha256"), field=f"{field}.receipt_sha256")
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256")
    if _sha256(_canonical_bytes(unsigned)) != stored_fingerprint:
        raise PositiveAcceptanceError(f"{field} receipt fingerprint mismatch")
    return receipt


def _verify_checksum(archive_raw: bytes, checksum_raw: bytes) -> str:
    if len(checksum_raw) > MAX_CHECKSUM_BYTES:
        raise PositiveAcceptanceError("checksum response exceeds frozen size limit")
    try:
        text = checksum_raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise PositiveAcceptanceError("checksum response must be ASCII") from exc
    match = CHECKSUM_RE.fullmatch(text)
    if match is None:
        raise PositiveAcceptanceError("checksum must bind exact archive filename and lowercase SHA-256")
    actual = _sha256(archive_raw)
    if match.group("sha") != actual:
        raise PositiveAcceptanceError("checksum digest does not match exact attested archive bytes")
    return actual


def _parse_exact_january_archive(archive_raw: bytes) -> dict[str, Any]:
    if len(archive_raw) > MAX_ARCHIVE_BYTES:
        raise PositiveAcceptanceError("archive response exceeds frozen size limit")
    try:
        with zipfile.ZipFile(io.BytesIO(archive_raw), "r") as archive:
            members = archive.infolist()
            data_members = [member for member in members if not member.is_dir()]
            if len(data_members) != 1:
                raise PositiveAcceptanceError("Binance archive must contain exactly one data member")
            info = data_members[0]
            path = PurePosixPath(info.filename)
            if (
                info.filename != EXPECTED_MEMBER_FILENAME
                or path.is_absolute()
                or ".." in path.parts
                or len(path.parts) != 1
            ):
                raise PositiveAcceptanceError("Binance archive member identity/path mismatch")
            if info.flag_bits & 0x1:
                raise PositiveAcceptanceError("encrypted Binance archive is unsupported")
            if info.file_size <= 0 or info.file_size > MAX_CSV_BYTES:
                raise PositiveAcceptanceError("Binance archive member size is unsafe")
            csv_raw = archive.read(info)
    except zipfile.BadZipFile as exc:
        raise PositiveAcceptanceError("archive response is not a valid ZIP") from exc
    try:
        text = csv_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PositiveAcceptanceError("Binance kline CSV must be UTF-8") from exc

    expected_opens = [
        datetime(2021, 1, day, tzinfo=UTC) for day in range(1, 32)
    ]
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for line_no, row in enumerate(csv.reader(io.StringIO(text)), start=1):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) != 12:
            raise PositiveAcceptanceError(f"Binance kline line {line_no} must have exactly 12 columns")
        try:
            open_ms = int(row[0])
            close_ms = int(row[6])
            trade_count = int(row[8])
        except ValueError as exc:
            raise PositiveAcceptanceError(f"Binance kline line {line_no} has invalid integer fields") from exc
        if open_ms in seen:
            raise PositiveAcceptanceError("Binance kline archive contains duplicate open time")
        seen.add(open_ms)
        try:
            open_at = datetime.fromtimestamp(open_ms / 1000, tz=UTC)
            close_at = datetime.fromtimestamp(close_ms / 1000, tz=UTC)
        except (OverflowError, OSError, ValueError) as exc:
            raise PositiveAcceptanceError("Binance kline timestamp is outside supported range") from exc
        if close_ms != open_ms + 86_400_000 - 1:
            raise PositiveAcceptanceError("Binance 1d kline close time does not match one UTC day")
        if trade_count < 0:
            raise PositiveAcceptanceError("Binance kline trade count must be nonnegative")
        try:
            close = Decimal(row[4])
        except InvalidOperation as exc:
            raise PositiveAcceptanceError("Binance kline close must be decimal") from exc
        if not close.is_finite() or close <= 0:
            raise PositiveAcceptanceError("Binance kline close must be finite and positive")
        rows.append({"open_at": open_at, "close_at": close_at, "close": close})
    if len(rows) != 31:
        raise PositiveAcceptanceError("frozen January archive must contain exactly 31 daily rows")
    rows.sort(key=lambda item: item["open_at"])
    if [item["open_at"] for item in rows] != expected_opens:
        raise PositiveAcceptanceError("frozen archive open-time coverage is not exactly 2021-01-01..31 UTC")
    cutoff = _utc(DECISION_AT, field="decision_at")
    if any(item["close_at"] >= cutoff for item in rows):
        raise PositiveAcceptanceError("frozen archive contains a row not fully closed before decision_at")
    last = rows[-1]
    if last["open_at"].date().isoformat() != EXPECTED_BAR_DATE:
        raise PositiveAcceptanceError("decision-price bar date mismatch")
    return {
        "decision_bar_date": EXPECTED_BAR_DATE,
        "decision_bar_open_time": last["open_at"].isoformat().replace("+00:00", "Z"),
        "decision_bar_close_time": last["close_at"].isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "decision_price": str(last["close"]),
        "row_count": len(rows),
    }


def accept_positive_canary(
    *,
    archive_bundle_raw: bytes,
    checksum_bundle_raw: bytes,
    archive_control_plane: dict[str, Any],
    checksum_control_plane: dict[str, Any],
    archive_verification_raw: bytes,
    checksum_verification_raw: bytes,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Validate both independently attested acquisitions and expose price only.

    The returned object is not, by itself, a trusted scientific receipt.  It becomes a
    trusted positive-control receipt only when the canonical verifier workflow on main
    emits and attests the exact result bytes.
    """
    _, contract_sha = load_contract(repo_root)
    archive_cp = _validate_control_plane(
        archive_control_plane,
        archive_verification_raw,
        archive_bundle_raw,
        field="archive",
    )
    checksum_cp = _validate_control_plane(
        checksum_control_plane,
        checksum_verification_raw,
        checksum_bundle_raw,
        field="checksum",
    )
    if archive_cp["run_id"] == checksum_cp["run_id"]:
        raise PositiveAcceptanceError("archive and checksum must be independently acquired runs")
    if archive_cp["source_digest"] != checksum_cp["source_digest"]:
        raise PositiveAcceptanceError("archive and checksum acquisitions must use the same canonical main SHA")

    archive_receipt_raw, archive_response = _safe_bundle_members(archive_bundle_raw, field="archive")
    checksum_receipt_raw, checksum_response = _safe_bundle_members(checksum_bundle_raw, field="checksum")
    archive_receipt = _validate_receipt(
        archive_receipt_raw,
        archive_response,
        archive_cp,
        contract_sha,
        source_kind=ARCHIVE_SOURCE_KIND,
        url=ARCHIVE_URL,
        field="archive",
    )
    checksum_receipt = _validate_receipt(
        checksum_receipt_raw,
        checksum_response,
        checksum_cp,
        contract_sha,
        source_kind=CHECKSUM_SOURCE_KIND,
        url=CHECKSUM_URL,
        field="checksum",
    )
    archive_digest = _verify_checksum(archive_response, checksum_response)
    parsed = _parse_exact_january_archive(archive_response)

    provider_archive = archive_receipt.get("provider_metadata")
    provider_checksum = checksum_receipt.get("provider_metadata")
    if not isinstance(provider_archive, dict) or provider_archive.get("archive_filename") != EXPECTED_ARCHIVE_FILENAME:
        raise PositiveAcceptanceError("archive provider metadata filename mismatch")
    if provider_archive.get("declared_archive_sha256") is not None:
        raise PositiveAcceptanceError("archive receipt must not self-declare its own checksum digest")
    if not isinstance(provider_checksum, dict):
        raise PositiveAcceptanceError("checksum provider metadata missing")
    if provider_checksum.get("archive_filename") != EXPECTED_ARCHIVE_FILENAME:
        raise PositiveAcceptanceError("checksum provider metadata filename mismatch")
    if provider_checksum.get("declared_archive_sha256") != archive_digest:
        raise PositiveAcceptanceError("checksum provider metadata digest mismatch")

    result: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "contract_sha256": contract_sha,
        "status": "PROVENANCE_BOOTSTRAP_SLICE_AUTHENTICATED_PRICE_ONLY",
        "subject": {
            "venue": "BINANCE_SPOT",
            "symbol": "BTCUSDT",
            "quote_asset": "USDT",
            "cadence": "1d",
            "archive_period": "2021-01",
        },
        "decision_at": DECISION_AT,
        **parsed,
        "archive": {
            "run_id": archive_cp["run_id"],
            "run_attempt": archive_cp["run_attempt"],
            "acquisition_main_sha": archive_cp["source_digest"],
            "bundle_sha256": archive_cp["bundle_sha256"],
            "attestation_verification_sha256": archive_cp["verification_sha256"],
            "response_sha256": _sha256(archive_response),
            "receipt_sha256": archive_receipt["receipt_sha256"],
            "request_url": ARCHIVE_URL,
        },
        "checksum": {
            "run_id": checksum_cp["run_id"],
            "run_attempt": checksum_cp["run_attempt"],
            "acquisition_main_sha": checksum_cp["source_digest"],
            "bundle_sha256": checksum_cp["bundle_sha256"],
            "attestation_verification_sha256": checksum_cp["verification_sha256"],
            "response_sha256": _sha256(checksum_response),
            "receipt_sha256": checksum_receipt["receipt_sha256"],
            "request_url": CHECKSUM_URL,
        },
        "source_native_binding": {
            "checksum_exact_filename_and_digest_verified": True,
            "zip_single_exact_member_verified": True,
            "exact_january_2021_daily_coverage_verified": True,
            "provider_native_close_times_before_decision_verified": True,
            "caller_authored_event_time_authority": False,
        },
        "trust_boundary": {
            "standalone_python_output_is_trusted": False,
            "required_result_attestation_signer_workflow": f"{REPOSITORY}/{VERIFIER_WORKFLOW_PATH}",
            "required_result_source_ref": EXPECTED_REF,
            "reason": "control-plane gh attestation verification must be bound by the canonical verifier workflow result attestation",
        },
        "scientific_authority": {
            "decision_price": True,
            "historical_universe_membership": False,
            "listing_age": False,
            "usd_liquidity": False,
            "strict_tradability": False,
            "historical_2x_label": False,
            "matched_control": False,
            "precursor_or_graph_effect": False,
            "competing_risk_model": False,
            "prospective_candidate": False,
            "prediction": False,
            "promotion": False,
            "broker_connected": False,
            "live_trading": False,
        },
    }
    result["result_fingerprint"] = _sha256(_canonical_bytes(result))
    return result


def _load_json_file(path: str, *, field: str) -> tuple[dict[str, Any], bytes]:
    raw = Path(path).read_bytes()
    return _strict_json_bytes(raw, field=field), raw


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive-bundle", required=True)
    parser.add_argument("--checksum-bundle", required=True)
    parser.add_argument("--archive-control-plane", required=True)
    parser.add_argument("--checksum-control-plane", required=True)
    parser.add_argument("--archive-verification", required=True)
    parser.add_argument("--checksum-verification", required=True)
    parser.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    archive_control, _ = _load_json_file(args.archive_control_plane, field="archive control plane")
    checksum_control, _ = _load_json_file(args.checksum_control_plane, field="checksum control plane")
    archive_verification = Path(args.archive_verification).read_bytes()
    checksum_verification = Path(args.checksum_verification).read_bytes()
    result = accept_positive_canary(
        archive_bundle_raw=Path(args.archive_bundle).read_bytes(),
        checksum_bundle_raw=Path(args.checksum_bundle).read_bytes(),
        archive_control_plane=archive_control,
        checksum_control_plane=checksum_control,
        archive_verification_raw=archive_verification,
        checksum_verification_raw=checksum_verification,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "decision_price": result["decision_price"],
        "result_fingerprint": result["result_fingerprint"],
        "standalone_python_output_is_trusted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
