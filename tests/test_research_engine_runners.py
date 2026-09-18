import json

import pytest

from research_engines.contract import CrossEngineContract
from research_engines.dataset import canonical_bars, data_fingerprint
from research_engines.lean_adapter import write_lean_contract


def bars():
    return [
        {"ts": 1, "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 5},
        {"ts": 2, "open": 10.5, "high": 12, "low": 10, "close": 11, "volume": 6},
    ]


def test_dataset_fingerprint_is_deterministic_and_chronological():
    assert data_fingerprint(bars()) == data_fingerprint(bars())
    bad = list(reversed(bars()))
    with pytest.raises(ValueError):
        canonical_bars(bad)


def test_lean_contract_contains_no_authority(tmp_path):
    rows = bars()
    contract = CrossEngineContract("strategy", "BTC-USDT", "1H", "trend", data_fingerprint(rows), 10)
    path = write_lean_contract(contract, tmp_path / "contract.json")
    payload = json.loads(open(path, encoding="utf-8").read())
    assert payload["contract_fingerprint"] == contract.fingerprint()
    assert payload["research_only"] is True
    assert payload["trade_authority"] is False
