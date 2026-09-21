from __future__ import annotations

from typing import Any

from orchestration.strategy_behavior_schema import BEHAVIOR_SCHEMAS

BEHAVIOR_DATA_PROJECTION_VERSION = 1

# Every reviewed behavior schema must partition its data_contract fields into:
# - behavior: data semantics that can change what the strategy actually trades;
# - evidence: dataset-instance/provenance/selection metadata that changes the
#   scientific evidence instance but not the executable strategy itself.
#
# The partition is import-time fail-closed: omitted/overlapping/unknown fields
# invalidate the registry instead of silently changing rejected-memory identity.
_OHLCV_BEHAVIOR_FIELDS = frozenset(
    {
        "source",
        "bar",
        "fixed_instruments",
        "point_in_time",
        "screen_may_read_protected_oos",
        "historical_universe",
    }
)
_OHLCV_EVIDENCE_FIELDS = frozenset(
    {
        "normalized_rows_sha256",
        "normalized_row_count",
        "coverage_start_utc",
        "coverage_end_utc",
        "selection_train_start_utc",
        "selection_train_end_utc",
        "selection_validation_start_utc",
        "selection_validation_end_utc",
        "protected_oos_start_utc",
        "protected_oos_end_utc",
    }
)

PRODUCTION_DATA_FIELD_PARTITIONS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "DISC_VOL_BREAKOUT_V1": (
        frozenset(
            {
                "venue",
                "instrument_type",
                "bar_interval",
                "completed_bars_only",
                "fixed_instruments",
                "asset_substitution_allowed",
            }
        ),
        frozenset(),
    ),
    "DISC_LIQUIDITY_MEANREV_V1": (
        frozenset(
            {
                "venue",
                "instrument_type",
                "bar_interval",
                "completed_bars_only",
                "fixed_instruments",
                "asset_substitution_allowed",
            }
        ),
        frozenset(),
    ),
    "DISC_BTC_LEADLAG_V1": (
        frozenset(
            {
                "venue",
                "instrument_type",
                "bar_interval",
                "completed_bars_only",
                "leader_instrument",
                "fixed_follower_instruments",
                "asset_substitution_allowed",
            }
        ),
        frozenset({"normalized_rows_sha256"}),
    ),
    "C101_BREADTH_PERSIST_V1": (_OHLCV_BEHAVIOR_FIELDS, _OHLCV_EVIDENCE_FIELDS),
    "C101_RESIDUAL_REV_V1": (_OHLCV_BEHAVIOR_FIELDS, _OHLCV_EVIDENCE_FIELDS),
    "C101_SIGNED_VOLUME_DRIFT_V1": (_OHLCV_BEHAVIOR_FIELDS, _OHLCV_EVIDENCE_FIELDS),
    "C101_LOWVOL_DRIFT_REV_V1": (_OHLCV_BEHAVIOR_FIELDS, _OHLCV_EVIDENCE_FIELDS),
    "C101_WEEKEND_NORMALIZE_V1": (_OHLCV_BEHAVIOR_FIELDS, _OHLCV_EVIDENCE_FIELDS),
    "C101_MODERATEVOL_AUTOCORR_V1": (_OHLCV_BEHAVIOR_FIELDS, _OHLCV_EVIDENCE_FIELDS),
    "C101_RANGE_AUCTION_REV_V1": (_OHLCV_BEHAVIOR_FIELDS, _OHLCV_EVIDENCE_FIELDS),
    "C101_DELTA_CARRY_V1": (
        frozenset(
            {
                "source",
                "bar",
                "fixed_instruments",
                "spot_hedges",
                "point_in_time",
                "historical_universe",
                "screen_may_read_protected_oos",
            }
        ),
        frozenset({"required_freeze_before_screen"}),
    ),
}

# Regression fixtures remain exact-shape semantics when an explicit test-only
# resolver context is active. They are never reachable from production admission.
TEST_DATA_FIELD_PARTITIONS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    schema_id: (schema["data_contract"], frozenset())
    for schema_id, schema in BEHAVIOR_SCHEMAS.items()
    if schema_id.startswith("TEST_")
}

DATA_FIELD_PARTITIONS = {
    **PRODUCTION_DATA_FIELD_PARTITIONS,
    **TEST_DATA_FIELD_PARTITIONS,
}


def _validate_partition_registry() -> None:
    if set(DATA_FIELD_PARTITIONS) != set(BEHAVIOR_SCHEMAS):
        missing = sorted(set(BEHAVIOR_SCHEMAS) - set(DATA_FIELD_PARTITIONS))
        extra = sorted(set(DATA_FIELD_PARTITIONS) - set(BEHAVIOR_SCHEMAS))
        raise RuntimeError(
            f"behavior data-projection schema coverage mismatch: missing={missing}, extra={extra}"
        )
    for schema_id, schema in BEHAVIOR_SCHEMAS.items():
        behavior_fields, evidence_fields = DATA_FIELD_PARTITIONS[schema_id]
        if behavior_fields & evidence_fields:
            raise RuntimeError(f"behavior data projection {schema_id} has overlapping fields")
        declared = schema["data_contract"]
        if behavior_fields | evidence_fields != declared:
            missing = sorted(declared - (behavior_fields | evidence_fields))
            extra = sorted((behavior_fields | evidence_fields) - declared)
            raise RuntimeError(
                f"behavior data projection {schema_id} field coverage mismatch: "
                f"missing={missing}, extra={extra}"
            )


_validate_partition_registry()


def project_behavior_data_contract(schema_id: str, data_contract: Any) -> dict[str, Any]:
    """Project one validated data contract onto executable data semantics only."""
    if schema_id not in DATA_FIELD_PARTITIONS:
        raise RuntimeError(f"behavior data projection is undeclared for schema {schema_id}")
    if not isinstance(data_contract, dict):
        raise RuntimeError("data_contract must be an object for behavior data projection")

    expected = BEHAVIOR_SCHEMAS[schema_id]["data_contract"]
    observed = frozenset(data_contract)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise RuntimeError(
            f"behavior data projection {schema_id} requires exact data_contract shape: "
            f"missing={missing}, extra={extra}"
        )

    behavior_fields, _ = DATA_FIELD_PARTITIONS[schema_id]
    return {field: data_contract[field] for field in sorted(behavior_fields)}
