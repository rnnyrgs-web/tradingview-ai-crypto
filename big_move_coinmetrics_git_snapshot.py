"""Deterministic Coin Metrics historical Git-snapshot value binding for Cohort 001.

This module binds a retained CSV to an exact upstream Git blob and selects a metric
value from a row strictly before the historical decision date. It deliberately does
not claim that an arbitrary commit timestamp alone proves public availability at that
time; capture/ingestion must separately prove the historical SHA resolved in the
original `coinmetrics/data` repository and preserve that provenance.

No outcomes, 2x labels, forecasts, broker code, or trading authority are touched.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import re
from typing import Any

UTC = timezone.utc
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_METRICS = frozenset({"CapMrktCurUSD", "SplyCur"})
EXPECTED_REPOSITORY = "coinmetrics/data"
EXPECTED_AUTHOR_LOGIN = "coinmetricsbot"
MAX_CSV_BYTES = 64 * 1024 * 1024


def git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def _utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def _metric_value(raw: str, *, metric: str, row_date: str) -> Decimal:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{metric} is blank on selected row {row_date}")
    try:
        value = Decimal(raw.strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{metric} is not decimal on selected row {row_date}") from exc
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{metric} must be finite and > 0 on selected row {row_date}")
    return value


def validate_snapshot_attestation(attestation: dict[str, Any], *, decision_at: str) -> None:
    """Validate immutable identifiers and chronology for a retained upstream snapshot.

    This is intentionally not sufficient by itself for authoritative PIT acceptance:
    a trusted capture process must establish that the commit SHA resolved in the
    original upstream repository. The attestation records what must be checked.
    """
    if not isinstance(attestation, dict):
        raise ValueError("attestation must be an object")
    if attestation.get("schema") != "coinmetrics_upstream_git_snapshot_proof.v1":
        raise ValueError("unexpected Coin Metrics Git snapshot proof schema")
    if attestation.get("repository") != EXPECTED_REPOSITORY:
        raise ValueError("Coin Metrics snapshot must resolve in original upstream repository")
    if attestation.get("author_login") != EXPECTED_AUTHOR_LOGIN:
        raise ValueError("Coin Metrics snapshot author login mismatch")
    for field in ("commit_sha", "tree_sha", "csv_blob_sha"):
        value = attestation.get(field)
        if not isinstance(value, str) or not SHA1_RE.fullmatch(value):
            raise ValueError(f"{field} must be lowercase Git SHA-1")
    commit_at = _utc(attestation.get("commit_at"), field="commit_at")
    cutoff = _utc(decision_at, field="decision_at")
    if commit_at >= cutoff:
        raise ValueError("Coin Metrics snapshot commit must predate decision cutoff")
    path = attestation.get("csv_path")
    if not isinstance(path, str) or not re.fullmatch(r"csv/[a-z0-9._-]+\.csv", path):
        raise ValueError("csv_path must be a simple Coin Metrics csv/<asset>.csv path")
    commit_url = attestation.get("upstream_commit_api_url")
    expected_commit_url = f"https://api.github.com/repos/{EXPECTED_REPOSITORY}/commits/{attestation['commit_sha']}"
    if commit_url != expected_commit_url:
        raise ValueError("upstream commit URL is not bound to original repository and commit SHA")
    contents_url = attestation.get("upstream_contents_api_url")
    expected_prefix = f"https://api.github.com/repos/{EXPECTED_REPOSITORY}/contents/{path}?ref={attestation['commit_sha']}"
    if contents_url != expected_prefix:
        raise ValueError("upstream contents URL is not bound to original repository/blob ref")
    if attestation.get("capture_verdict") != "UPSTREAM_RESOLUTION_VERIFIED":
        raise ValueError("trusted capture must verify historical SHA in original upstream repository")


def bind_metric_from_snapshot(
    csv_bytes: bytes,
    attestation: dict[str, Any],
    *,
    metric: str,
    decision_at: str,
) -> dict[str, Any]:
    """Bind an exact historical metric value to retained upstream CSV bytes."""
    validate_snapshot_attestation(attestation, decision_at=decision_at)
    if metric not in ALLOWED_METRICS:
        raise ValueError("metric is not predeclared for Cohort 001 Coin Metrics snapshot lane")
    if not isinstance(csv_bytes, (bytes, bytearray)):
        raise ValueError("csv_bytes must be bytes")
    raw = bytes(csv_bytes)
    if not raw or len(raw) > MAX_CSV_BYTES:
        raise ValueError("Coin Metrics CSV size is invalid")
    actual_blob = git_blob_sha(raw)
    if actual_blob != attestation["csv_blob_sha"]:
        raise ValueError("retained Coin Metrics CSV does not match upstream Git blob SHA")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Coin Metrics CSV must be UTF-8") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "time" not in reader.fieldnames:
        raise ValueError("Coin Metrics CSV is missing time column")
    if metric not in reader.fieldnames:
        raise ValueError(f"Coin Metrics CSV is missing metric column {metric}")

    cutoff_date = _utc(decision_at, field="decision_at").date()
    candidates: list[tuple[date, str]] = []
    seen_dates: set[date] = set()
    for line_number, row in enumerate(reader, start=2):
        raw_date = row.get("time")
        if not isinstance(raw_date, str):
            raise ValueError(f"Coin Metrics line {line_number} has no time")
        try:
            row_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise ValueError(f"Coin Metrics line {line_number} has invalid date") from exc
        if row_date in seen_dates:
            raise ValueError("Coin Metrics CSV contains duplicate date")
        seen_dates.add(row_date)
        if row_date >= cutoff_date:
            continue
        value = row.get(metric)
        if isinstance(value, str) and value.strip():
            candidates.append((row_date, value))

    if not candidates:
        raise ValueError(f"no nonblank {metric} row exists strictly before decision date")
    selected_date, selected_raw = max(candidates, key=lambda item: item[0])
    value = _metric_value(selected_raw, metric=metric, row_date=selected_date.isoformat())
    return {
        "schema": "coinmetrics_upstream_git_metric_binding.v1",
        "repository": EXPECTED_REPOSITORY,
        "commit_sha": attestation["commit_sha"],
        "tree_sha": attestation["tree_sha"],
        "csv_path": attestation["csv_path"],
        "csv_blob_sha": actual_blob,
        "commit_at": attestation["commit_at"],
        "decision_at": decision_at,
        "metric": metric,
        "row_date": selected_date.isoformat(),
        "value": str(value),
        "row_rule": "LATEST_NONBLANK_ROW_STRICTLY_BEFORE_DECISION_DATE",
        "fork_contents_used_as_evidence": False,
        "outcome_access": "SEALED",
        "prediction_authority": False,
        "trade_authority": False,
    }
