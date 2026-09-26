from __future__ import annotations

from contextlib import nullcontext
import hashlib
from pathlib import Path

import pytest

from orchestration.strategy_behavior_schema import allow_test_behavior_schemas

# Only regression modules that intentionally exercise synthetic TEST_* behavior
# contracts receive the explicit test-only resolver context. Production-boundary
# tests are deliberately absent from this allowlist so the default production
# resolver is exercised there.
_TEST_BEHAVIOR_SCHEMA_MODULES = {
    "test_scientific_design_identity.py",
    "test_strategy_behavior_field_semantics.py",
    "test_strategy_behavior_identity.py",
    "test_strategy_predeclaration.py",
    "test_strategy_predeclaration_scalar_representation_guard.py",
}

# Cohort-preflight regressions intentionally use tiny local Binance fixtures to test
# downstream coverage, threshold, duplicate, chronology, and derivation semantics.
# Those fixtures are not provider-authenticated evidence and must never regain
# production authority after #705. The dedicated trusted-origin regressions exercise
# the real production boundary without this test-only override.
_TEST_SYNTHETIC_BINANCE_FIXTURE_MODULES = {"test_big_move_cohort_preflight.py"}
_SYNTHETIC_BINANCE_LOCATOR = (
    "https://data.binance.vision/data/spot/daily/trades/TEST/TEST.zip"
)


def _validated_synthetic_binance_fixture(proof, root: Path, decision_at, *, field: str) -> None:
    """Verify local fixture integrity only; grant zero provider/PIT authority."""
    if proof.get("schema") != "binance_public_archive_proof.v1":
        raise ValueError(f"{field} requires binance_public_archive_proof.v1")
    if proof.get("source_id") != "BINANCE_PUBLIC_DATA_SPOT_RAW":
        raise ValueError(f"{field} synthetic Binance fixture source mismatch")
    if proof.get("upstream_locator") != _SYNTHETIC_BINANCE_LOCATOR:
        raise ValueError(f"{field} synthetic Binance fixture locator mismatch")

    def _verified_local_bytes(relpath, expected_sha256, *, label: str) -> bytes:
        if not isinstance(relpath, str) or not relpath:
            raise ValueError(f"{field} synthetic {label} path missing")
        candidate = Path(relpath)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ValueError(f"{field} synthetic {label} path unsafe")
        path = (root / candidate).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError(f"{field} synthetic {label} path escapes fixture root")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha256:
            raise ValueError(f"{field} synthetic {label} digest mismatch")
        return raw

    archive_raw = _verified_local_bytes(
        proof.get("archive_relpath"), proof.get("archive_sha256"), label="archive"
    )
    checksum_raw = _verified_local_bytes(
        proof.get("checksum_relpath"), proof.get("checksum_sha256"), label="checksum"
    )
    archive_sha = hashlib.sha256(archive_raw).hexdigest()
    archive_name = Path(proof["archive_relpath"]).name
    try:
        checksum_text = checksum_raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{field} synthetic checksum must be ASCII") from exc
    if checksum_text != f"{archive_sha}  {archive_name}\n":
        raise ValueError(f"{field} synthetic checksum does not exactly bind archive fixture")
    expected_event_time = decision_at.isoformat().replace("+00:00", "Z")
    if proof.get("event_time_max") != expected_event_time:
        raise ValueError(f"{field} synthetic event clock must equal fixture decision time")


@pytest.fixture(autouse=True)
def _explicit_test_behavior_schema_context(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
):
    filename = Path(str(request.node.path)).name
    context = (
        allow_test_behavior_schemas()
        if filename in _TEST_BEHAVIOR_SCHEMA_MODULES
        else nullcontext()
    )
    if filename in _TEST_SYNTHETIC_BINANCE_FIXTURE_MODULES:
        import big_move_source_authenticity as source_authenticity

        monkeypatch.setattr(
            source_authenticity,
            "_validate_binance_proof",
            _validated_synthetic_binance_fixture,
        )
    with context:
        yield
