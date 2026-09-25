import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "orchestration/external_replication/ext_eth_tuesday_drift_001_source_chronology.json"
EXPECTED = "573bf9136e87f92054bf3488d4b585c7eb3345d996668a6af2182ca1b1f4d7fc"


def test_source_chronology_receipt_is_self_bound_and_pre_outcome() -> None:
    value = json.loads(PATH.read_text(encoding="utf-8"))
    observed = value.pop("artifact_sha256")
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    assert observed == EXPECTED
    assert hashlib.sha256(raw).hexdigest() == EXPECTED
    assert value["formed_pre_outcome"] is True
    assert value["outcomes_read_to_form_attestation"] is False
    evidence = value["source_evidence"]["independent_platform"]
    assert evidence["platform"] == "ResearchGate"
    assert evidence["upload_date"] == "2024-08-12"
    assert evidence["content_observed_on_record"]["ethereum_tuesday_coefficient"] == 0.790
    assert evidence["content_observed_on_record"]["ethereum_tuesday_p_value"] == 0.002
    assert value["chronology_assessment"]["byte_level_immutability_proven"] is False
    assert value["scientific_interpretation"]["profitability_claim_allowed_from_stage1"] is False
    assert all(v is False for v in value["authority_locks"].values())
