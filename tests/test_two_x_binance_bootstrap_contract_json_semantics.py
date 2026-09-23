from __future__ import annotations

from pathlib import Path

import pytest

from two_x_binance_bootstrap_direct_acquisition import CONTRACT_ID, load_contract


CONTRACT_RELATIVE_PATH = Path("money_intelligence/2x_binance_cohort_bootstrap_slice_v1.json")


def _write_contract(tmp_path: Path, text: str) -> None:
    target = tmp_path / CONTRACT_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def _canonical_contract_text() -> str:
    source = Path(__file__).resolve().parents[1] / CONTRACT_RELATIVE_PATH
    return source.read_text(encoding="utf-8")


def test_contract_loader_rejects_duplicate_json_object_keys(tmp_path: Path):
    text = _canonical_contract_text()
    original = f'  "artifact_id": "{CONTRACT_ID}",\n'
    assert text.count(original) == 1
    ambiguous = text.replace(
        original,
        '  "artifact_id": "ATTACKER-CONTROLLED-FIRST-VALUE",\n' + original,
        1,
    )
    _write_contract(tmp_path, ambiguous)

    with pytest.raises(ValueError, match="duplicate JSON object key|contract JSON"):
        load_contract(tmp_path)


def test_contract_loader_rejects_nested_duplicate_json_object_keys(tmp_path: Path):
    text = _canonical_contract_text()
    original = '    "c101h_source_kind_reuse_forbidden": true,\n'
    assert text.count(original) == 1
    ambiguous = text.replace(
        original,
        '    "c101h_source_kind_reuse_forbidden": false,\n' + original,
        1,
    )
    _write_contract(tmp_path, ambiguous)

    with pytest.raises(ValueError, match="duplicate JSON object key|contract JSON"):
        load_contract(tmp_path)


def test_contract_loader_rejects_nonstandard_json_numeric_constants(tmp_path: Path):
    text = _canonical_contract_text()
    assert text.startswith("{\n")
    ambiguous = text.replace("{\n", '{\n  "ambiguous_numeric": NaN,\n', 1)
    _write_contract(tmp_path, ambiguous)

    with pytest.raises(ValueError, match="non-standard JSON numeric constant|contract JSON"):
        load_contract(tmp_path)
