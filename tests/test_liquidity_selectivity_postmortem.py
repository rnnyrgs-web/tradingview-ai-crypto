from __future__ import annotations

import copy
import gzip
import json
from pathlib import Path

import pytest

import liquidity_selectivity_postmortem as audit
from research_artifact import seal_research_payload


HOUR = 3_600_000


def trade(score, hour, gross=50.0, instrument="BTC"):
    return dict(instrument=instrument, signal_ts=hour * HOUR,
                entry_ts=(hour + 1) * HOUR, exit_ts=(hour + 7) * HOUR,
                shock_return=score / 100, trailing_sigma=.01, gross_bps=gross)


def inputs():
    return [trade(i, 10 * i) for i in range(1, 101)], [
        trade(2, 2000), trade(96, 2010), trade(99, 2020), trade(101, 2030)]


def test_cutoffs_use_training_predictors_only_and_keep_all_buckets():
    train, validation = inputs()
    report = audit.summarize(train, validation)
    assert list(report) == ["1", "5", "10", "20", "50", "100"]
    assert report["5"]["training_score_cutoff"] == pytest.approx(96)
    assert report["5"]["validation"]["trade_labels"] == 3
    assert report["5"]["validation"]["coverage_fraction"] == .75
    changed = [dict(t, gross_bps=-999) for t in train]
    reordered = list(reversed(validation)) + [trade(1000, 2100)]
    second = audit.summarize(changed, reordered)
    assert [v["training_score_cutoff"] for v in second.values()] == [v["training_score_cutoff"] for v in report.values()]
    assert report["100"]["validation"]["trade_labels"] == 4


def test_ties_are_included_and_overlap_is_not_independent_sample_size():
    train = [trade(10, 10), trade(10, 10, instrument="ETH"), trade(1, 20)]
    validation = [trade(10, 100), trade(10, 103), trade(10, 109)]
    report = audit.summarize(train, validation)["1"]
    assert report["train"]["trade_labels"] == 2
    assert report["train"]["distinct_signal_hours"] == 1
    assert report["train"]["holding_interval_clusters"] == 1
    assert report["validation"]["holding_interval_clusters"] == 2
    assert report["train"]["coverage_fraction"] == pytest.approx(2 / 3)


def test_empty_bucket_is_unknown_not_zero_and_costs_are_frozen():
    report = audit.summarize([trade(10, 10)], [trade(1, 100)])["1"]
    assert report["validation"]["trade_labels"] == 0
    assert report["validation"]["costs_bps"]["20"]["mean_net_bps"] is None
    assert report["train"]["costs_bps"]["60"]["mean_net_bps"] == -10
    assert list(report["train"]["costs_bps"]) == ["20", "30", "40", "60"]
    assert audit.summarize([trade(10, 10)], [])["1"]["validation"]["coverage_fraction"] is None
    with pytest.raises(ValueError, match="training"):
        audit.summarize([], [])


@pytest.mark.parametrize("field,value", [("trailing_sigma", 0), ("gross_bps", float("nan")),
    ("shock_return", float("inf")), ("trailing_sigma", True), ("signal_ts", 1.5),
    ("entry_ts", 0), ("exit_ts", 0)])
def test_invalid_or_noncausal_rows_fail_closed(field, value):
    row = trade(10, 10)
    row[field] = value
    with pytest.raises(ValueError):
        audit.summarize([row], [])


def test_duplicate_identity_and_overlapping_splits_rejected():
    row = trade(10, 10)
    with pytest.raises(ValueError, match="duplicate"):
        audit.summarize([row, row], [])
    with pytest.raises(ValueError, match="chronolog"):
        audit.summarize([row], [trade(10, 15)])


def test_real_artifact_replay_reads_only_the_sealed_evidence(monkeypatch):
    original = Path.read_bytes
    seen = []
    def guarded(path):
        seen.append(path.name)
        assert path.name == "evidence.json.gz", "market dataset must never be opened"
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", guarded)
    report = audit.build_report()
    assert seen == ["evidence.json.gz"]
    assert report["buckets"]["100"]["train"]["trade_labels"] == 425
    assert report["buckets"]["100"]["validation"]["trade_labels"] == 123
    assert report["buckets"]["100"]["validation"]["costs_bps"]["20"]["mean_net_bps"] == pytest.approx(-5.48, abs=.01)
    assert report["strategy_status"] == "REJECTED_UNCHANGED"
    assert report["promotion_authority"] is False
    assert report["untouched_oos_opened"] is False


def test_resigned_or_tampered_evidence_cannot_replace_original(tmp_path):
    source = json.loads(gzip.decompress(audit.EVIDENCE_PATH.read_bytes()))
    changed = copy.deepcopy(source)
    changed["payload"]["selection"]["fingerprint_id"] = "replacement"
    for envelope in [changed, seal_research_payload(changed["payload"])]:
        path = tmp_path / "evidence.json.gz"
        path.write_bytes(gzip.compress(json.dumps(envelope).encode()))
        with pytest.raises(ValueError, match="original.*evidence"):
            audit.build_report(path)


def test_committed_report_is_reproducible():
    path = Path(__file__).resolve().parents[1] / "docs/research/evidence/liquidity_selectivity_20260924.json"
    assert json.loads(path.read_text(encoding="utf-8")) == audit.build_report()
