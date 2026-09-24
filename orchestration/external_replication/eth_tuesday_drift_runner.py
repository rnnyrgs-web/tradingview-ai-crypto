from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping, Sequence

UTC = timezone.utc
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
WEEK = timedelta(days=7)

ROOT = Path(__file__).resolve().parents[2]
PREDECLARATION_PATH = ROOT / "orchestration" / "external_replication" / "ext_eth_tuesday_drift_001_v1.json"
EXECUTION_CONTRACT_PATH = ROOT / "orchestration" / "external_replication" / "ext_eth_tuesday_drift_001_stage1_execution.json"
DATASET_PATH = ROOT / "orchestration" / "evidence" / "liquidity_meanrev_001_cache" / "dataset.json.gz"

REPLICATION_ID = "EXT-ETH-TUESDAY-DRIFT-001-v1"
PARENT_ARTIFACT_SHA256 = "6ddab16cbfbb846d0690dced9e2128244e2bc9ec6221243a02cb48fea4b5c98b"
DATASET_SHA256 = "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f"
DATASET_GIT_BLOB_SHA1 = "3a93beb4b1b4ef7f5d32b2936bf3119c692e7c15"
INSTRUMENT = "ETH-USDT-SWAP"
PROTECTED_OOS_START = datetime(2026, 9, 1, tzinfo=UTC)
SCREEN_START = datetime(2025, 5, 12, tzinfo=UTC)
HALF_2_START = datetime(2026, 1, 5, tzinfo=UTC)
SCREEN_WEEK_END_EXCLUSIVE = datetime(2026, 8, 31, tzinfo=UTC)
COSTS_BPS = (24.0, 48.0, 72.0)
PRIMARY_COST_BPS = 48.0
STRESS_COST_BPS = 72.0
MIN_SESSIONS_PER_HALF = 25


@dataclass(frozen=True)
class BoundaryBar:
    timestamp: datetime
    open: float


@dataclass(frozen=True)
class TuesdaySession:
    week_start: datetime
    half: str
    entry_timestamp: datetime
    exit_timestamp: datetime
    entry_open: float
    exit_open: float
    gross_bps: float


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _artifact_digest(document: Mapping[str, object], field: str) -> str:
    payload = dict(document)
    supplied = payload.pop(field, None)
    if not isinstance(supplied, str):
        raise RuntimeError(f"{field} missing")
    actual = hashlib.sha256(_canonical_json(payload)).hexdigest()
    if actual != supplied:
        raise RuntimeError(f"{field} mismatch")
    return supplied


def _parse_hour(value: object) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        seconds = float(value) / 1000.0
        dt = datetime.fromtimestamp(seconds, tz=UTC)
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise ValueError("timestamp must be UTC hour or epoch milliseconds")
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    dt = dt.astimezone(UTC)
    if dt.minute or dt.second or dt.microsecond:
        raise ValueError("timestamp must lie on exact UTC hourly grid")
    return dt


def load_and_validate_contracts(
    predeclaration_path: Path = PREDECLARATION_PATH,
    execution_contract_path: Path = EXECUTION_CONTRACT_PATH,
) -> tuple[dict, dict]:
    pre = json.loads(predeclaration_path.read_text(encoding="utf-8"))
    if _artifact_digest(pre, "artifact_sha256") != PARENT_ARTIFACT_SHA256:
        raise RuntimeError("unexpected predeclaration identity")
    if pre.get("replication_id") != REPLICATION_ID:
        raise RuntimeError("unexpected replication id")

    execution = json.loads(execution_contract_path.read_text(encoding="utf-8"))
    _artifact_digest(execution, "artifact_sha256")
    if execution.get("replication_id") != REPLICATION_ID:
        raise RuntimeError("execution contract replication mismatch")
    if execution.get("parent_artifact_sha256") != PARENT_ARTIFACT_SHA256:
        raise RuntimeError("execution contract parent mismatch")
    if execution.get("dataset_sha256") != DATASET_SHA256:
        raise RuntimeError("execution contract dataset mismatch")
    locks = execution.get("authority_locks", {})
    if any(locks.get(key) is not False for key in (
        "real_stage1_execution_before_independent_review",
        "baseline_pnl_opened",
        "protected_oos_opened",
        "genuine_forward_opened",
        "profitability_claim_allowed",
        "promotion_authority",
        "broker_connected",
        "trade_authority",
    )):
        raise RuntimeError("execution authority lock drift")
    return pre, execution


def _extract_boundary_bars(
    rows: Iterable[Mapping[str, object]],
    *,
    protected_oos_start: datetime = PROTECTED_OOS_START,
) -> tuple[BoundaryBar, ...]:
    bars: list[BoundaryBar] = []
    previous: datetime | None = None
    seen: set[datetime] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("history row must be an object")
        ts = _parse_hour(row.get("ts"))
        if previous is not None and ts <= previous:
            raise ValueError("history timestamps must be strictly increasing")
        previous = ts
        if ts in seen:
            raise ValueError("duplicate history timestamp")
        seen.add(ts)

        # The frozen artifact may physically contain an opaque protected tail.
        # Tail rows are provenance-only. Do not inspect price fields or return them.
        if ts >= protected_oos_start:
            continue

        try:
            value = float(row["open"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("development open must be present and numeric") from exc
        if not isfinite(value) or value <= 0:
            raise ValueError("development open must be finite and positive")
        bars.append(BoundaryBar(timestamp=ts, open=value))
    return tuple(bars)


def build_frozen_schedule(
    rows: Iterable[Mapping[str, object]],
) -> tuple[tuple[TuesdaySession, ...], tuple[dict, ...]]:
    bars = _extract_boundary_bars(rows)
    by_ts = {bar.timestamp: bar for bar in bars}
    sessions: list[TuesdaySession] = []
    missing: list[dict] = []

    week = SCREEN_START
    while week < SCREEN_WEEK_END_EXCLUSIVE:
        entry_ts = week + DAY  # Monday 00 -> Tuesday 00.
        exit_ts = entry_ts + DAY
        half = "half_1" if week < HALF_2_START else "half_2"
        entry = by_ts.get(entry_ts)
        exit_bar = by_ts.get(exit_ts)
        absent = []
        if entry is None:
            absent.append(entry_ts.isoformat())
        if exit_bar is None:
            absent.append(exit_ts.isoformat())
        if absent:
            missing.append({
                "week_start": week.isoformat(),
                "half": half,
                "reason": "DATA/PIT_INCONCLUSIVE_SESSION",
                "missing_required_boundaries": absent,
            })
        else:
            gross_bps = (exit_bar.open / entry.open - 1.0) * 10_000.0
            sessions.append(TuesdaySession(
                week_start=week,
                half=half,
                entry_timestamp=entry_ts,
                exit_timestamp=exit_ts,
                entry_open=entry.open,
                exit_open=exit_bar.open,
                gross_bps=gross_bps,
            ))
        week += WEEK

    if len(sessions) + len(missing) != 68:
        raise RuntimeError("frozen schedule must contain exactly 68 predeclared weeks")
    return tuple(sessions), tuple(missing)


def _profit_factor(net_bps: Sequence[float]) -> tuple[float | None, bool]:
    gains = sum(value for value in net_bps if value > 0)
    losses = -sum(value for value in net_bps if value < 0)
    if losses == 0:
        if gains > 0:
            return None, True
        return None, False
    return gains / losses, False


def _metrics(sessions: Sequence[TuesdaySession], cost_bps: float) -> dict:
    net = [s.gross_bps - cost_bps for s in sessions]
    pf, infinite = _profit_factor(net)
    positive_total = sum(value for value in net if value > 0)
    max_positive_share = None
    if positive_total > 0:
        max_positive_share = max((value for value in net if value > 0), default=0.0) / positive_total
    return {
        "sessions": len(sessions),
        "mean_gross_bps": mean([s.gross_bps for s in sessions]) if sessions else None,
        "mean_net_bps": mean(net) if net else None,
        "profit_factor": pf,
        "profit_factor_is_infinite": infinite,
        "max_positive_pnl_share": max_positive_share,
    }


def _pf_above_one(metrics: Mapping[str, object]) -> bool:
    return bool(metrics["profit_factor_is_infinite"]) or (
        isinstance(metrics["profit_factor"], (int, float))
        and float(metrics["profit_factor"]) > 1.0
    )


def _classify_failure(
    full_raw: Mapping[str, object],
    full_primary: Mapping[str, object],
    half_1: Mapping[str, object],
    half_2: Mapping[str, object],
    full_stress: Mapping[str, object],
    *,
    power_ok: bool,
    concentration_ok: bool,
) -> str:
    if not power_ok:
        return "INCONCLUSIVE_POWER"
    if full_raw["mean_gross_bps"] is None or float(full_raw["mean_gross_bps"]) <= 0:
        return "NO_GROSS_EDGE"
    if full_primary["mean_net_bps"] is None or float(full_primary["mean_net_bps"]) <= 0:
        return "COST_ERASED_EDGE"
    if (
        half_1["mean_net_bps"] is None
        or half_2["mean_net_bps"] is None
        or float(half_1["mean_net_bps"]) <= 0
        or float(half_2["mean_net_bps"]) <= 0
    ):
        return "REGIME_OR_CHRONOLOGY_INSTABILITY"
    if full_stress["mean_net_bps"] is None or float(full_stress["mean_net_bps"]) <= 0:
        return "COST_STRESS_ERASED_EDGE"
    if not concentration_ok:
        return "WINNER_CONCENTRATION"
    if not _pf_above_one(full_primary):
        return "PROFIT_FACTOR_FAILURE"
    return "UNCLASSIFIED_STAGE1_FAILURE"


def evaluate_stage1(rows: Iterable[Mapping[str, object]]) -> dict:
    sessions, missing = build_frozen_schedule(rows)
    half_1_sessions = [s for s in sessions if s.half == "half_1"]
    half_2_sessions = [s for s in sessions if s.half == "half_2"]

    full_by_cost = {str(int(cost)): _metrics(sessions, cost) for cost in COSTS_BPS}
    h1_primary = _metrics(half_1_sessions, PRIMARY_COST_BPS)
    h2_primary = _metrics(half_2_sessions, PRIMARY_COST_BPS)
    raw = _metrics(sessions, 0.0)
    primary = full_by_cost[str(int(PRIMARY_COST_BPS))]
    stress = full_by_cost[str(int(STRESS_COST_BPS))]

    power_ok = (
        len(half_1_sessions) >= MIN_SESSIONS_PER_HALF
        and len(half_2_sessions) >= MIN_SESSIONS_PER_HALF
    )
    concentration = primary["max_positive_pnl_share"]
    concentration_ok = concentration is not None and float(concentration) <= 0.5
    gates = {
        "minimum_sessions_per_half": power_ok,
        "full_mean_net_positive_48bps": primary["mean_net_bps"] is not None and float(primary["mean_net_bps"]) > 0,
        "half_1_mean_net_positive_48bps": h1_primary["mean_net_bps"] is not None and float(h1_primary["mean_net_bps"]) > 0,
        "half_2_mean_net_positive_48bps": h2_primary["mean_net_bps"] is not None and float(h2_primary["mean_net_bps"]) > 0,
        "full_profit_factor_above_1_48bps": _pf_above_one(primary),
        "full_mean_net_positive_72bps": stress["mean_net_bps"] is not None and float(stress["mean_net_bps"]) > 0,
        "max_positive_pnl_share_le_50pct_48bps": concentration_ok,
        "data_pit_contract_valid": True,
    }
    survived = all(gates.values())
    if survived:
        status = "STAGE1_SURVIVOR_ONLY"
        failure_classification = None
    elif not power_ok:
        status = "INCONCLUSIVE_POWER"
        failure_classification = "INCONCLUSIVE_POWER"
    else:
        status = "REJECT_PRE_OOS"
        failure_classification = _classify_failure(
            raw, primary, h1_primary, h2_primary, stress,
            power_ok=power_ok,
            concentration_ok=concentration_ok,
        )

    return {
        "replication_id": REPLICATION_ID,
        "screen_stage": "STAGE1_CHEAP_FALSIFICATION_ONLY",
        "status": status,
        "failure_classification": failure_classification,
        "expected_sessions": 68,
        "scored_sessions": len(sessions),
        "missing_sessions": list(missing),
        "metrics": {
            "full": full_by_cost,
            "half_1_48bps": h1_primary,
            "half_2_48bps": h2_primary,
            "raw_gross": raw,
        },
        "gates": gates,
        "survived_stage1_economic_gates": survived,
        "evidence_authority": "TEST_ONLY_UNTRUSTED_CALLER_ROWS",
        "authority": {
            "stage2_baseline_execution_allowed": False,
            "profitability_claim_allowed": False,
            "deep_promotion_allowed": False,
            "protected_oos_opened": False,
            "genuine_forward_opened": False,
            "broker_connected": False,
            "trade_authority": False,
        },
    }


def load_frozen_eth_rows(dataset_path: Path = DATASET_PATH) -> tuple[dict, ...]:
    # Identity checking the complete frozen object is a provenance operation only.
    # Economics are computed solely after _extract_boundary_bars drops the protected tail
    # without inspecting protected price fields.
    from liquidity_mean_reversion_selection import _load_frozen_cache

    if dataset_path.resolve() != DATASET_PATH.resolve():
        raise RuntimeError("fresh-history or alternate dataset substitution is forbidden")
    raw = dataset_path.read_bytes()
    raw_git_blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    if raw_git_blob != DATASET_GIT_BLOB_SHA1:
        raise RuntimeError("frozen compressed dataset git-blob identity mismatch")
    _, dataset = _load_frozen_cache(dataset_path.parent)
    histories = dataset.get("histories")
    if not isinstance(histories, Mapping):
        raise RuntimeError("frozen dataset histories missing")
    rows = histories.get(INSTRUMENT)
    if not isinstance(rows, list):
        raise RuntimeError("exact ETH-USDT-SWAP history missing")
    return tuple(rows)


def run_canonical_stage1() -> dict:
    """Score only the exact frozen dataset after static contracts are authenticated.

    Legitimate scientific authority still depends on the external exact-head
    CI/independent-review/integration gate. This function deliberately does not
    mint Stage-2, profitability, promotion, broker or trading authority.
    """
    load_and_validate_contracts()
    rows = load_frozen_eth_rows()
    result = evaluate_stage1(rows)
    result["evidence_authority"] = "FROZEN_DATASET_VERIFIED_REVIEW_AUTHORITY_EXTERNAL"
    result["authority"]["stage2_baseline_execution_allowed"] = False
    return result
