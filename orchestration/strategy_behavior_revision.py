from __future__ import annotations

from orchestration.strategy_behavior_schema import (
    BEHAVIOR_SCHEMAS,
    PRODUCTION_BEHAVIOR_SCHEMAS,
)

DEFAULT_EXECUTABLE_CONTRACT_REVISION = 1

# The seven non-carry Cohort-001 OHLCV schemas changed executable cost semantics
# from a daily funding placeholder to an adverse per-completed-trade allowance.
# Keep the global schema/value registry domains stable for canonical rejected
# memory and version only this bounded executable-contract transition.
COHORT_001_OHLCV_REVISION_2_SCHEMAS = frozenset(
    {
        "C101_BREADTH_PERSIST_V1",
        "C101_RESIDUAL_REV_V1",
        "C101_SIGNED_VOLUME_DRIFT_V1",
        "C101_LOWVOL_DRIFT_REV_V1",
        "C101_WEEKEND_NORMALIZE_V1",
        "C101_MODERATEVOL_AUTOCORR_V1",
        "C101_RANGE_AUCTION_REV_V1",
    }
)

_SCHEMA_EXECUTABLE_CONTRACT_REVISIONS: dict[str, int] = {
    schema_id: 2 for schema_id in COHORT_001_OHLCV_REVISION_2_SCHEMAS
}


def _validate_revision_registry() -> None:
    if set(_SCHEMA_EXECUTABLE_CONTRACT_REVISIONS) != set(COHORT_001_OHLCV_REVISION_2_SCHEMAS):
        raise RuntimeError("behavior executable-contract revision registry coverage mismatch")
    for schema_id, revision in _SCHEMA_EXECUTABLE_CONTRACT_REVISIONS.items():
        if schema_id not in PRODUCTION_BEHAVIOR_SCHEMAS:
            raise RuntimeError(
                f"behavior executable-contract revision references non-production schema {schema_id}"
            )
        if schema_id.startswith("TEST_"):
            raise RuntimeError("test-only behavior schemas cannot receive production revisions")
        if isinstance(revision, bool) or not isinstance(revision, int) or revision <= 1:
            raise RuntimeError(
                f"behavior executable-contract revision for {schema_id} must be an integer > 1"
            )


_validate_revision_registry()


def behavior_schema_executable_contract_revision(schema_id: str) -> int:
    """Return the reviewed executable-contract revision for one resolved schema.

    Revision 1 is the historical/default domain and is intentionally omitted from
    behavior projections so existing rejected semantic digests remain byte-for-byte
    stable. Only explicitly reviewed transitions receive a higher revision.
    """
    if not isinstance(schema_id, str) or not schema_id:
        raise RuntimeError("behavior schema id must be a non-empty string")
    if schema_id not in BEHAVIOR_SCHEMAS:
        raise RuntimeError(f"unknown behavior schema id {schema_id!r}")
    revision = _SCHEMA_EXECUTABLE_CONTRACT_REVISIONS.get(
        schema_id,
        DEFAULT_EXECUTABLE_CONTRACT_REVISION,
    )
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise RuntimeError(f"invalid executable-contract revision for {schema_id}")
    return revision
