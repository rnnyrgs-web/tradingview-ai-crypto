"""Source-native authenticity checks for the Cohort 001 pre-label gate.

A local digest proves only that retained bytes stopped changing after capture. It does
not prove that the bytes came from the claimed provider or that the information was
available at the historical decision time. This module adds the second boundary:
provider/archive-specific proof plus a pinned source-policy artifact.

The checks are intentionally conservative. Unsupported or unverifiable evidence is
missing evidence; it must not be converted into a value just to increase coverage.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from big_move_primary_historical_availability import (
    validate_primary_document_historical_availability,
)

SOURCE_POLICY_PATH = "money_intelligence/2x_source_provenance_preflight_v1.json"
SOURCE_POLICY_GIT_BLOB_SHA = "f0c9048228dac566def31f5872406d3437d114c7"
SOURCE_POLICY_ARTIFACT_ID = "2X-SOURCE-PREFLIGHT-001-v1"
MAX_PROOF_BYTES = 16_000_000

BINANCE_SOURCES = {"BINANCE_PUBLIC_DATA_SPOT_RAW"}
# Only asset metrics whose Community response exposes a provider-native review status
# and status-time are eligible here. Catalog/candle coverage is useful for audits but
# does not by itself establish historical value availability.
COINMETRICS_STATUS_SOURCES = {
    "COINMETRICS_COMMUNITY_CAP_MRKT_CUR_USD": "CapMrktCurUSD",
    "COINMETRICS_COMMUNITY_SPLY_CUR": "SplyCur",
}
PRIMARY_DOCUMENT_SOURCES = {
    "PRIMARY_CONTRACT_OR_GENESIS_DOC",
    "TIMESTAMPED_PRIMARY_SUPPLY_DISCLOSURE",
}
DERIVED_SOURCES = {
    "TRAILING_30D_MEDIAN_QUOTE_VOLUME_USD_V1",
    "DERIVED_BINANCE_LISTING_AGE_DAYS_V1",
    "DERIVED_PRE_CUTOFF_VENUE_BARS_V1",
    "PIT_PRIMARY_FUNCTIONAL_CLASSIFIER_V1",
    "DERIVED_BTC_MARKET_REGIME_V1",
    "DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1",
}
BLOCKED_DIRECT_SOURCES = {
    "COINGECKO_EXISTING_AUTHORIZED_MARKET_CHART",
    "COINMETRICS_COMMUNITY_MARKET_CANDLE",
    "COINMETRICS_COMMUNITY_ASSET_CATALOG",
}


def _utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an RFC3339 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def _decision_at_text(value: datetime) -> str:
    """Serialize only an explicitly UTC decision clock for trusted PIT validators."""

    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("decision_at must be a timezone-aware UTC datetime")
    if value.utcoffset() != timezone.utc.utcoffset(value):
        raise ValueError("decision_at must be UTC")
    return value.isoformat().replace("+00:00", "Z")


def _same_value(left: Any, right: Any) -> bool:
    if type(left) is bool or type(right) is bool:
        return left is right
    try:
        lnum = float(left)
        rnum = float(right)
    except (TypeError, ValueError):
        return left == right
    return math.isfinite(lnum) and math.isfinite(rnum) and math.isclose(
        lnum, rnum, rel_tol=1e-12, abs_tol=1e-12
    )


def _safe_path(root: Path, relpath: Any, *, field: str) -> Path:
    if not isinstance(relpath, str) or not relpath.strip():
        raise ValueError(f"{field}.artifact_relpath missing")
    relative = Path(relpath)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{field}.artifact_relpath must stay inside retained artifact root")
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"{field}.artifact_relpath escapes retained artifact root")
    return path


def _verified_bytes(root: Path, relpath: Any, expected_sha256: Any, *, field: str) -> bytes:
    if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256")
    try:
        int(expected_sha256, 16)
    except ValueError as exc:
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256") from exc
    if expected_sha256.lower() != expected_sha256:
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256")
    path = _safe_path(root, relpath, field=field)
    try:
        if path.stat().st_size > MAX_PROOF_BYTES:
            raise ValueError(f"{field} retained proof is too large")
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{field} retained proof is unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError(f"{field} retained proof SHA-256 mismatch")
    return raw


def _unique_json_object(pairs: list[tuple[str, Any]], *, field: str) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"{field} contains duplicate JSON object key {key!r}")
        value[key] = item
    return value


def _reject_nonstandard_json_constant(value: str, *, field: str) -> Any:
    raise ValueError(f"{field} contains non-standard JSON numeric constant {value}")


def _strict_json_loads(raw: bytes, *, field: str, json_error: str) -> Any:
    """Parse authenticated JSON with one deterministic semantic interpretation."""

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(json_error) from exc
    try:
        return json.loads(
            text,
            object_pairs_hook=lambda pairs: _unique_json_object(pairs, field=field),
            parse_constant=lambda constant: _reject_nonstandard_json_constant(
                constant, field=field
            ),
        )
    except json.JSONDecodeError as exc:
        raise ValueError(json_error) from exc


def _verified_json(root: Path, ref: Any, *, field: str) -> dict[str, Any]:
    if not isinstance(ref, dict):
        raise ValueError(f"{field} source_proof missing")
    raw = _verified_bytes(root, ref.get("artifact_relpath"), ref.get("sha256"), field=field)
    value = _strict_json_loads(
        raw,
        field=field,
        json_error=f"{field} source proof must be JSON",
    )
    if not isinstance(value, dict):
        raise ValueError(f"{field} source proof must be an object")
    return value


def _https_locator(value: Any, *, field: str, required_host: str | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} upstream locator missing")
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError(f"{field} upstream locator must be a clean HTTPS URL")
    host = parts.hostname.lower()
    if required_host is not None and host != required_host and not host.endswith("." + required_host):
        raise ValueError(f"{field} upstream locator host is not approved")
    return value


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def verify_source_policy_pin(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / SOURCE_POLICY_PATH).resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("pinned 2x source/provenance policy artifact is unavailable") from exc
    if _git_blob_sha(raw) != SOURCE_POLICY_GIT_BLOB_SHA:
        raise ValueError("2x source/provenance policy drifted from frozen Git blob")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("pinned 2x source/provenance policy is malformed") from exc
    if not isinstance(value, dict) or value.get("artifact_id") != SOURCE_POLICY_ARTIFACT_ID:
        raise ValueError("unexpected pinned 2x source/provenance policy identity")
    return value


def is_derived_source(source_id: str) -> bool:
    return source_id in DERIVED_SOURCES


def _validate_binance_proof(
    proof: dict[str, Any], root: Path, decision_at: datetime, *, field: str
) -> None:
    if proof.get("schema") != "binance_public_archive_proof.v1":
        raise ValueError(f"{field} requires binance_public_archive_proof.v1")
    _https_locator(proof.get("upstream_locator"), field=field, required_host="data.binance.vision")
    archive_raw = _verified_bytes(
        root,
        proof.get("archive_relpath"),
        proof.get("archive_sha256"),
        field=f"{field}.archive",
    )
    checksum_raw = _verified_bytes(
        root,
        proof.get("checksum_relpath"),
        proof.get("checksum_sha256"),
        field=f"{field}.checksum",
    )
    archive_sha = hashlib.sha256(archive_raw).hexdigest()
    try:
        checksum_text = checksum_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{field} Binance checksum must be UTF-8 text") from exc
    if archive_sha not in checksum_text:
        raise ValueError(f"{field} Binance checksum sidecar does not authenticate archive digest")
    event_time_max = _utc(proof.get("event_time_max"), field=f"{field}.event_time_max")
    if event_time_max > decision_at:
        raise ValueError(f"{field} Binance proof includes post-decision events")


def _validate_coinmetrics_proof(
    proof: dict[str, Any],
    root: Path,
    source_id: str,
    record: dict[str, Any],
    decision_at: datetime,
    *,
    field: str,
) -> None:
    if proof.get("schema") != "coinmetrics_raw_response_proof.v1":
        raise ValueError(f"{field} requires coinmetrics_raw_response_proof.v1")
    locator = _https_locator(
        proof.get("upstream_locator"),
        field=field,
        required_host="community-api.coinmetrics.io",
    )
    if proof.get("source_id") != source_id:
        raise ValueError(f"{field} Coin Metrics proof source mismatch")
    metric = COINMETRICS_STATUS_SOURCES[source_id]
    if proof.get("metric") != metric:
        raise ValueError(f"{field} Coin Metrics metric mismatch")
    asset = proof.get("asset")
    frequency = proof.get("frequency")
    record_time = proof.get("record_time")
    if not isinstance(asset, str) or not asset.strip():
        raise ValueError(f"{field} Coin Metrics asset missing")
    if not isinstance(frequency, str) or not frequency.strip():
        raise ValueError(f"{field} Coin Metrics frequency missing")
    _utc(record_time, field=f"{field}.record_time")

    parsed = urlsplit(locator)
    params = parse_qs(parsed.query)
    if asset not in ",".join(params.get("assets", [])).split(","):
        raise ValueError(f"{field} Coin Metrics locator asset mismatch")
    if metric not in ",".join(params.get("metrics", [])).split(","):
        raise ValueError(f"{field} Coin Metrics locator metric mismatch")
    if params.get("frequency") != [frequency]:
        raise ValueError(f"{field} Coin Metrics locator frequency mismatch")

    raw = _verified_bytes(
        root,
        proof.get("raw_response_relpath"),
        proof.get("raw_response_sha256"),
        field=f"{field}.coinmetrics_raw_response",
    )
    response = _strict_json_loads(
        raw,
        field=f"{field}.coinmetrics_raw_response",
        json_error=f"{field} Coin Metrics raw response must be JSON",
    )
    rows = response.get("data") if isinstance(response, dict) else None
    if not isinstance(rows, list):
        raise ValueError(f"{field} Coin Metrics raw response data missing")
    matches = [
        row for row in rows
        if isinstance(row, dict)
        and row.get("asset") == asset
        and row.get("time") == record_time
        and metric in row
    ]
    if len(matches) != 1:
        raise ValueError(f"{field} Coin Metrics record identity is not unique")
    row = matches[0]
    status_key = f"{metric}-status"
    status_time_key = f"{metric}-status-time"
    if row.get(status_key) not in {"reviewed", "revised"}:
        raise ValueError(f"{field} Coin Metrics raw metric must be reviewed or revised")
    status_time = _utc(row.get(status_time_key), field=f"{field}.status_time")
    if status_time > decision_at:
        raise ValueError(f"{field} Coin Metrics status_time is after decision_at")
    if _utc(record_time, field=f"{field}.record_time") != _utc(
        record.get("observed_at"), field=f"{field}.observed_at"
    ):
        raise ValueError(f"{field} Coin Metrics observation time mismatch")
    if not _same_value(row.get(metric), record.get("value")):
        raise ValueError(f"{field} Coin Metrics raw value mismatch")


def _validate_primary_document_proof(
    proof: dict[str, Any], root: Path, source_id: str, record: dict[str, Any], decision_at: datetime, *, field: str
) -> None:
    if proof.get("schema") != "primary_document_proof.v1":
        raise ValueError(f"{field} requires primary_document_proof.v1")
    if proof.get("source_id") != source_id:
        raise ValueError(f"{field} primary-document proof source mismatch")
    _https_locator(proof.get("upstream_locator"), field=field)
    published_at = _utc(proof.get("published_at"), field=f"{field}.published_at")
    if published_at > decision_at:
        raise ValueError(f"{field} primary document was published after decision_at")
    effective_raw = proof.get("effective_at")
    if effective_raw is not None and _utc(effective_raw, field=f"{field}.effective_at") > decision_at:
        raise ValueError(f"{field} primary document was not effective by decision_at")
    _verified_bytes(
        root,
        proof.get("document_relpath"),
        proof.get("document_sha256"),
        field=f"{field}.document",
    )
    if "claim_value" not in proof or proof.get("claim_value") != record.get("value"):
        raise ValueError(f"{field} primary-document claim does not match evidence value")

    # Caller-authored publication/effective clocks are semantic constraints only. They
    # do not establish that these exact retained bytes were knowable at decision_at.
    # Reuse the trusted Common Crawl acquisition + WARC binding boundary so both direct
    # and derived primary evidence require an independently authenticated pre-decision
    # capture of the same locator and document bytes.
    try:
        validate_primary_document_historical_availability(
            record,
            decision_at=_decision_at_text(decision_at),
            artifact_root=root,
        )
    except ValueError as exc:
        raise ValueError(
            f"{field} primary document lacks trusted historical capture: {exc}"
        ) from exc


def _validate_input_authenticity(
    artifact: dict[str, Any], root: Path, decision_at: datetime, *, field: str
) -> None:
    source_id = artifact.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError(f"{field} derived input source_id missing")
    proof = _verified_json(root, artifact.get("source_proof"), field=f"{field}.source_proof")
    if source_id in BINANCE_SOURCES:
        _validate_binance_proof(proof, root, decision_at, field=field)
    elif source_id in COINMETRICS_STATUS_SOURCES:
        _validate_coinmetrics_proof(proof, root, source_id, artifact, decision_at, field=field)
    elif source_id in PRIMARY_DOCUMENT_SOURCES:
        _validate_primary_document_proof(proof, root, source_id, artifact, decision_at, field=field)
    else:
        raise ValueError(f"{field} derived input source has no authenticity verifier")


def validate_record_authenticity(
    record: dict[str, Any],
    *,
    artifact_root: Path | None,
    decision_at: datetime,
    field: str,
) -> None:
    if artifact_root is None:
        raise ValueError(f"{field} cannot verify source authenticity without retained artifact root")
    source_id = record.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError(f"{field}.source_id missing")

    if source_id in BLOCKED_DIRECT_SOURCES:
        raise ValueError(f"{field} source lacks independently timestamped PIT authenticity proof")

    if source_id in DERIVED_SOURCES:
        derivation = record.get("derivation")
        if not isinstance(derivation, dict):
            raise ValueError(f"{field} derived evidence must declare derivation")
        inputs = derivation.get("inputs")
        if not isinstance(inputs, list) or not inputs:
            raise ValueError(f"{field} derived evidence must bind authenticated inputs")
        for index, ref in enumerate(inputs):
            if not isinstance(ref, dict):
                raise ValueError(f"{field}.derivation.inputs[{index}] malformed")
            input_field = f"{field}.derivation.inputs[{index}]"
            raw = _verified_bytes(
                artifact_root,
                ref.get("artifact_relpath"),
                ref.get("sha256"),
                field=input_field,
            )
            artifact = _strict_json_loads(
                raw,
                field=input_field,
                json_error=f"{input_field} must be JSON",
            )
            if not isinstance(artifact, dict):
                raise ValueError(f"{input_field} must be an object")
            _validate_input_authenticity(
                artifact,
                artifact_root,
                decision_at,
                field=input_field,
            )
        return

    proof = _verified_json(artifact_root, record.get("source_proof"), field=f"{field}.source_proof")
    if source_id in BINANCE_SOURCES:
        _validate_binance_proof(proof, artifact_root, decision_at, field=field)
    elif source_id in COINMETRICS_STATUS_SOURCES:
        _validate_coinmetrics_proof(proof, artifact_root, source_id, record, decision_at, field=field)
    elif source_id in PRIMARY_DOCUMENT_SOURCES:
        _validate_primary_document_proof(
            proof, artifact_root, source_id, record, decision_at, field=field
        )
    else:
        raise ValueError(f"{field} source has no source-native authenticity verifier")