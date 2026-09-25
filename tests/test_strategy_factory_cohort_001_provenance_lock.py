from __future__ import annotations

import hashlib
import fnmatch
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from orchestration.strategy_factory_cohort_001_provenance import (
    LOCK_RELATIVE_PATH,
    REQUIRED_SOURCE_PATHS,
    verify_admission_provenance_lock,
)


ROOT = Path(__file__).resolve().parents[1]

# Explicit scientific dependencies: do not derive coverage from the verifier's
# own registry, because an omitted dependency must itself fail this regression.
ADMISSION_INPUT_PATHS = {
    "btc_leadlag_selection.py",
    "research_artifact.py",
    "signal_development.py",
    "volatility_breakout_selection.py",
    "profitability_learning/__init__.py",
    "profitability_learning/analytics.py",
    "profitability_learning/contracts.py",
    "orchestration/rejected_fingerprints.py",
    "orchestration/rejected_fingerprints.json",
    "orchestration/rejected_semantic_designs.json",
    "orchestration/disc_btc_leadlag_001.json",
    "orchestration/disc_liquidity_meanrev_001.json",
    "orchestration/disc_vol_breakout_001.json",
    "orchestration/evidence/liquidity_meanrev_001_cache/dataset.json.gz",
    "orchestration/strategy_behavior_data_projection.py",
    "orchestration/scientific_design_identity.py",
    "orchestration/strategy_predeclaration.py",
    "orchestration/strategy_behavior_revision.py",
    "orchestration/strategy_behavior_schema.py",
    "orchestration/strategy_behavior_value_contract.py",
    "orchestration/strategy_factory_cohort_001_admission.py",
    "orchestration/strategy_factory_cohort_001_provenance.py",
    "strategy_dataset_preflight.py",
}


def test_admission_workflow_does_not_persist_checkout_credentials() -> None:
    workflow = (ROOT / ".github/workflows/strategy_factory_cohort_001_admission.yml").read_text()
    checkout = workflow.split("uses: actions/checkout@", 1)[1].split("- name:", 1)[0]
    assert "persist-credentials: false" in checkout


def test_admission_workflow_pins_action_code_and_test_dependencies() -> None:
    workflow = (ROOT / ".github/workflows/strategy_factory_cohort_001_admission.yml").read_text()
    actions = re.findall(r"uses:\s*([^\s]+)", workflow)
    assert actions
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", action) for action in actions)
    assert "--require-hashes -r requirements-cohort001-admission.txt" in workflow
    lock = ROOT / "requirements-cohort001-admission.txt"
    requirements = [line.strip() for line in lock.read_text().splitlines() if line.strip() and not line.startswith("#")]
    assert requirements
    assert all(re.fullmatch(r"[\w-]+==[\d.]+ --hash=sha256:[0-9a-f]{64}", line) for line in requirements)
    assert lock.name in REQUIRED_SOURCE_PATHS


def test_admission_workflow_runs_existing_protected_dataset_regressions() -> None:
    workflow = (ROOT / ".github/workflows/strategy_factory_cohort_001_admission.yml").read_text()
    assert "tests/test_strategy_dataset_preflight.py" in workflow.split("      - name: Verify canonical admission,", 1)[1].split("      - name:", 1)[0]


def test_scientific_identity_sources_are_bound_and_trigger_focused_ci() -> None:
    assert ADMISSION_INPUT_PATHS <= REQUIRED_SOURCE_PATHS
    workflow = (ROOT / ".github/workflows/strategy_factory_cohort_001_admission.yml").read_text()
    path_section = workflow.split("    paths:\n", 1)[1].split("  workflow_dispatch:", 1)[0]
    patterns = [line.strip()[2:].strip('"') for line in path_section.splitlines() if line.strip().startswith("- ")]
    for source in REQUIRED_SOURCE_PATHS | ADMISSION_INPUT_PATHS:
        assert any(fnmatch.fnmatchcase(source, pattern) for pattern in patterns), source
    revision_test = "tests/test_strategy_behavior_contract_revision.py"
    assert any(fnmatch.fnmatchcase(revision_test, pattern) for pattern in patterns)
    assert revision_test in workflow.split("      - name: Verify canonical admission,", 1)[1].split("      - name:", 1)[0]


def test_actual_outcome_blind_admission_inputs_are_all_bound() -> None:
    # A fresh interpreter traces names only, using the existing protected-safe
    # qualifier. This catches dependencies omitted from BOTH explicit lists.
    script = """
import json, sys
from pathlib import Path
root = Path.cwd()
sys.path.append(str(root))
opened = set()
def audit(event, args):
    if event == 'open' and isinstance(args[0], str):
        path = Path(args[0]).resolve()
        if path.is_relative_to(root) and '__pycache__' not in path.parts:
            opened.add(path.relative_to(root).as_posix())
sys.addaudithook(audit)
from orchestration.strategy_factory_cohort_001_admission import build_canonical_admission_receipt
receipt = build_canonical_admission_receipt()
assert receipt['outcomes_read'] is False
assert receipt['protected_oos_opened'] is False
for module in list(sys.modules.values()):
    filename = getattr(module, '__file__', None)
    if filename:
        path = Path(filename).resolve()
        if path.is_relative_to(root) and path.is_file():
            opened.add(path.relative_to(root).as_posix())
print(json.dumps(sorted(opened)))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script], cwd=ROOT,
        capture_output=True, text=True, check=True,
    )
    assert set(json.loads(result.stdout)) <= REQUIRED_SOURCE_PATHS | {LOCK_RELATIVE_PATH.as_posix()}


@pytest.mark.parametrize("relative", (
    "orchestration/rejected_fingerprints.py",
    "orchestration/rejected_fingerprints.json",
    "orchestration/rejected_semantic_designs.json",
    "orchestration/strategy_behavior_data_projection.py",
    "orchestration/disc_btc_leadlag_001.json",
    "orchestration/disc_liquidity_meanrev_001.json",
    "orchestration/disc_vol_breakout_001.json",
    "btc_leadlag_selection.py",
))
def test_rejection_and_data_input_drift_fails_closed(tmp_path: Path, relative: str) -> None:
    _copy_lock_fixture(tmp_path)
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((ROOT / relative).read_bytes() + b"\n")
    with pytest.raises(RuntimeError, match="source drift"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def test_identity_revision_semantic_drift_fails_closed(tmp_path: Path) -> None:
    _copy_lock_fixture(tmp_path)
    relative = "orchestration/strategy_behavior_revision.py"
    source = (ROOT / relative).read_text()
    assert "DEFAULT_EXECUTABLE_CONTRACT_REVISION = 1" in source
    (tmp_path / relative).write_text(source.replace(
        "DEFAULT_EXECUTABLE_CONTRACT_REVISION = 1",
        "DEFAULT_EXECUTABLE_CONTRACT_REVISION = 2",
    ))
    with pytest.raises(RuntimeError, match="source drift.*strategy_behavior_revision"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def test_revision_binding_cannot_be_dropped_with_valid_self_digest(tmp_path: Path) -> None:
    lock = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock.read_text())
    payload["bound_source_git_blobs"].pop("orchestration/strategy_behavior_revision.py", None)
    payload["contract_sha256"] = _recompute_contract_digest(payload)
    lock.write_text(json.dumps(payload))
    with pytest.raises(RuntimeError, match="source set mismatch"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def _copy_lock_fixture(tmp_path: Path) -> Path:
    for relative in REQUIRED_SOURCE_PATHS | {LOCK_RELATIVE_PATH.as_posix()}:
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return tmp_path / LOCK_RELATIVE_PATH


def _recompute_contract_digest(payload: dict[str, object]) -> str:
    body = dict(payload)
    body.pop("contract_sha256", None)
    canonical = json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_admission_provenance_lock_verifies_exact_current_inputs() -> None:
    result = verify_admission_provenance_lock()
    assert result["status"] == "VERIFIED_OUTCOME_BLIND_ADMISSION_PROVENANCE"
    assert result["source_count"] == len(REQUIRED_SOURCE_PATHS)
    assert result["outcomes_read"] is False
    assert result["protected_oos_opened"] is False
    assert result["genuine_forward_opened"] is False
    assert result["integration_authority"] == "NONE"
    assert result["broker_connected"] is False
    assert result["trade_authority"] is False


def test_semantically_identical_source_byte_drift_fails_closed(tmp_path: Path) -> None:
    _copy_lock_fixture(tmp_path)
    seed = tmp_path / "orchestration/cohorts/strategy_factory_cohort_001_seed.json"
    seed.write_text(seed.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="source drift"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def test_receipt_byte_drift_fails_closed(tmp_path: Path) -> None:
    _copy_lock_fixture(tmp_path)
    receipt = tmp_path / "orchestration/cohorts/strategy_factory_cohort_001_canonical_admission.json"
    receipt.write_text(receipt.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="source drift"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def test_dropped_source_binding_fails_even_with_valid_new_self_digest(tmp_path: Path) -> None:
    lock = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock.read_text(encoding="utf-8"))
    payload["bound_source_git_blobs"].pop(
        "orchestration/scientific_design_identity.py"
    )
    payload["contract_sha256"] = _recompute_contract_digest(payload)
    lock.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="source set mismatch"):
        verify_admission_provenance_lock(repo_root=tmp_path)


def test_authority_tamper_fails_even_with_valid_new_self_digest(tmp_path: Path) -> None:
    lock = _copy_lock_fixture(tmp_path)
    payload = json.loads(lock.read_text(encoding="utf-8"))
    payload["authority"]["integration_authority"] = "APPROVE"
    payload["contract_sha256"] = _recompute_contract_digest(payload)
    lock.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="cannot grant integration authority"):
        verify_admission_provenance_lock(repo_root=tmp_path)

@pytest.mark.parametrize('defect', ('missing', 'malformed', 'tampered', 'multiplicity_drift'))
def test_public_admission_fails_closed_before_qualification(monkeypatch, tmp_path, defect):
    from orchestration import strategy_factory_cohort_001_admission as admission
    from orchestration import strategy_factory_cohort_001_provenance as provenance
    lock = _copy_lock_fixture(tmp_path)
    if defect == 'missing':
        lock.unlink()
    elif defect == 'malformed':
        lock.write_text('{}')
    elif defect == 'tampered':
        payload = json.loads(lock.read_text())
        payload['authority']['outcomes_read'] = True
        lock.write_text(json.dumps(payload))
    else:
        target = tmp_path / 'orchestration/cohorts/strategy_factory_cohort_001_multiplicity_authority.json'
        target.write_text(target.read_text() + '\n')
    monkeypatch.setattr(provenance, 'REPO_ROOT', tmp_path)
    def forbidden_qualification(_):
        pytest.fail('dataset qualification reached before provenance verification')
    monkeypatch.setattr(admission, '_qualify_common_selection_dataset', forbidden_qualification)
    with pytest.raises(RuntimeError):
        admission.build_canonical_admission_receipt()


def test_public_admission_never_grants_execution_authority():
    from orchestration.strategy_factory_cohort_001_admission import build_canonical_admission_receipt
    receipt = build_canonical_admission_receipt()
    assert all(row['screening_authority'] is False for row in receipt['candidates'])
    assert sum(row['admission_eligible'] for row in receipt['candidates']) == 6


def test_admission_workflow_ignores_ambient_python_and_pytest_inputs(tmp_path):
    import os
    import shlex
    workflow = (ROOT / '.github/workflows/strategy_factory_cohort_001_admission.yml').read_text()
    step = workflow.split('      - name: Verify canonical admission,', 1)[1].split('      - name:', 1)[0]
    command = shlex.split(step.split('run: >-', 1)[1])
    command = command[:next(i for i, value in enumerate(command) if value.startswith('tests/'))]
    command[0] = sys.executable
    command += ['test_positive_control.py']
    marker = tmp_path / 'ambient-executed'
    hook = 'from pathlib import Path\nPath(' + repr(str(marker)) + ').write_text("executed")\n'
    (tmp_path / 'sitecustomize.py').write_text(hook)
    (tmp_path / 'usercustomize.py').write_text(hook)
    (tmp_path / 'conftest.py').write_text(hook + 'raise RuntimeError("ambient conftest")\n')
    (tmp_path / 'ambient_plugin.py').write_text(hook + 'raise RuntimeError("ambient plugin")\n')
    (tmp_path / 'pytest.ini').write_text('[pytest]\naddopts = --invalid-ambient-option\n')
    (tmp_path / 'test_positive_control.py').write_text('def test_positive_control():\n    assert 2 + 2 == 4\n')
    env = dict(os.environ, PYTHONPATH=str(tmp_path), PYTEST_ADDOPTS='--invalid-env-option', PYTEST_PLUGINS='ambient_plugin')
    result = subprocess.run(command, cwd=tmp_path, env=env, text=True, capture_output=True)
    assert not marker.exists(), 'ambient startup hook executed before verification'
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1 passed' in result.stdout


def test_every_admission_workflow_python_process_is_isolated():
    workflow = (ROOT / '.github/workflows/strategy_factory_cohort_001_admission.yml').read_text()
    invocations = re.findall(r'\bpython\s+([^\n]+)', workflow)
    assert invocations
    assert all(command.startswith('-I ') for command in invocations)


@pytest.mark.parametrize('self_consistent_receipt', (False, True))
def test_production_rejects_corrupt_or_unsupported_receipt_even_with_rebound_lock(
    monkeypatch, tmp_path, self_consistent_receipt
):
    from orchestration import strategy_factory_cohort_001_admission as admission
    from orchestration import strategy_factory_cohort_001_provenance as provenance
    lock_path = _copy_lock_fixture(tmp_path)
    relative = 'orchestration/cohorts/strategy_factory_cohort_001_canonical_admission.json'
    target = tmp_path / relative
    receipt = json.loads(target.read_text())
    receipt['stage1_cost_contract']['stress_totals_bps']['3x'] = 1.0
    if self_consistent_receipt:
        body = dict(receipt)
        body.pop('receipt_sha256')
        receipt['receipt_sha256'] = hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    target.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    lock = json.loads(lock_path.read_text())
    lock['bound_source_git_blobs'][relative] = provenance.git_blob_sha1(target)
    lock['bound_admission_receipt_sha256'] = receipt['receipt_sha256']
    lock['contract_sha256'] = _recompute_contract_digest(lock)
    lock_path.write_text(json.dumps(lock))
    monkeypatch.setattr(provenance, 'REPO_ROOT', tmp_path)
    original = admission._load_json
    monkeypatch.setattr(admission, '_load_json', lambda path: receipt if path.name == target.name else original(path))
    if self_consistent_receipt:
        with pytest.raises(RuntimeError, match='regeneration'):
            admission.build_canonical_admission_receipt()
    else:
        with pytest.raises(RuntimeError, match='receipt digest'):
            provenance.verify_admission_provenance_lock()
