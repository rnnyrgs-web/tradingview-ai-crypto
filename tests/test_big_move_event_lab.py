"""Hand-derived synthetic integrity fixtures; never market/alpha evidence."""
import copy
import importlib
import importlib.util
from datetime import datetime, timedelta, timezone

import pytest


T0 = datetime(2020, 1, 1, tzinfo=timezone.utc)


def ts(days=0):
    return (T0 + timedelta(days=days)).isoformat().replace("+00:00", "Z")


def contract():
    return {
        "schema_version": 1, "target": "2X_PLUS_EVENT_90D",
        "partition": "DEVELOPMENT", "partition_start": ts(), "partition_end": ts(365),
        "bar_seconds": 86400, "max_feature_age_seconds": 86400,
        "min_liquidity_usd": 1000000, "min_listing_age_days": 30,
        "neighbor_pool_size": 3, "min_controls": 2,
        "calipers": {"market_cap_usd": 100000000, "float_supply": 100000000,
                     "liquidity_usd": 10000000, "listing_age_days": 365,
                     "volatility_30d": 0.1, "return_30d": 0.5},
        "universe_source": "synthetic-pit-fixture", "price_source": "synthetic-ohlc-fixture",
    }


def snapshot(asset="A", day=0, **changes):
    values = {"price": 100, "liquidity_usd": 2000000, "market_cap_usd": 100000000,
              "float_supply": 1000000, "listing_age_days": 100,
              "volatility_30d": 0.05, "return_30d": 0.1, "sector": "test",
              "regime": "neutral", "tradable": True, "member": True}
    values.update(changes)
    return {"asset_id": asset, "venue": "fixture", "decision_time": ts(day),
            "features": {k: {"value": v, "observed_at": ts(day),
                             "available_at": ts(day), "source": "synthetic-pit-fixture"}
                         for k, v in values.items()}}


def bars(asset="A", day=0, highs=None, count=90):
    highs = highs or {}
    return [{"asset_id": asset, "venue": "fixture", "start": ts(day+i-1),
             "end": ts(day+i), "available_at": ts(day+i),
             "open": 100, "high": highs.get(i, 100), "low": 80, "close": 100,
             "source": "synthetic-ohlc-fixture"} for i in range(1, count+1)]


@pytest.fixture
def lab():
    assert importlib.util.find_spec("big_move_lab") is not None, "event lab missing"
    return importlib.import_module("big_move_lab")


def run(lab, snapshots=None, prices=None, cfg=None, as_of=None):
    cfg = cfg or contract()
    return lab.build_dataset(cfg, snapshots or [snapshot()],
                             bars() if prices is None else prices,
                             as_of=as_of or ts(100), expected_contract_hash=lab.digest(cfg))


def test_uncapped_maxima_and_thresholds_include_day_90(lab):
    out = run(lab, prices=bars(highs={2: 200, 20: 300, 40: 500, 90: 1250}))
    row = out["labels"][0]
    assert row["status"] == "COMPLETE"
    assert row["max_forward_30d_return"] == 2
    assert row["max_forward_60d_return"] == 4
    assert row["max_forward_90d_return"] == 11.5
    assert row["maximum_90d_price_multiple"] == 12.5
    for n, day in [(2, 2), (3, 20), (5, 40), (10, 90)]:
        assert row[f"reached_{n}x"] is True
        assert row[f"days_to_{n}x"] == day
        assert row[f"days_to_{n}x_lower_bound"] == day-1
        assert row[f"max_drawdown_before_{n}x"] is None
    assert row["forward_90d_return"] == 0
    assert out["summary"]["event_count"] == 1
    assert out["summary"]["trade_authority"] is False


def test_high_before_decision_and_after_horizon_cannot_be_events(lab):
    prices = bars(day=-1, count=92)
    prices[0]["high"] = 10000
    prices[-1]["high"] = 10000
    cfg = contract()
    cfg["partition_start"] = ts(-30)
    row = run(lab, prices=prices, cfg=cfg)["labels"][0]
    assert row["reached_2x"] is False
    assert row["maximum_90d_price_multiple"] == 1


@pytest.mark.parametrize("mode", ["gap", "immature", "late_publication", "no_history"])
def test_incomplete_history_never_becomes_nonwinner(lab, mode):
    prices = bars(highs={2: 300})
    as_of = ts(100)
    if mode == "gap":
        del prices[40]
    elif mode == "immature":
        as_of = ts(45)
    elif mode == "late_publication":
        prices[40]["available_at"] = ts(101)
    else:
        prices = []
    row = run(lab, prices=prices, as_of=as_of)["labels"][0]
    assert row["status"] == "CENSORED"
    assert row["reached_2x"] is None
    assert row["maximum_90d_price_multiple"] is None
    assert row["observed_reached_2x"] is (mode != "no_history")


def test_close_sampled_drawdown_excludes_unknown_crossing_bar_order(lab):
    prices = bars(highs={4: 200})
    prices[0].update(high=120, close=120)
    prices[1].update(close=90)
    prices[2].update(close=100)
    prices[3].update(low=1)
    row = run(lab, prices=prices)["labels"][0]
    assert row["max_close_drawdown_before_2x"] == 0.25
    assert row["max_drawdown_before_2x"] is None


@pytest.mark.parametrize("field", list(snapshot()["features"]))
def test_every_snapshot_field_requires_predecision_availability(lab, field):
    snap = snapshot()
    snap["features"][field]["available_at"] = ts(1)
    with pytest.raises(ValueError, match="point-in-time"):
        run(lab, snapshots=[snap])


@pytest.mark.parametrize("mutation", ["duplicate", "nan", "boolean_price", "bad_ohlc", "naive_time", "offgrid", "early_available", "wrong_source"])
def test_malformed_bars_fail_closed(lab, mutation):
    prices = bars()
    if mutation == "duplicate": prices.append(copy.deepcopy(prices[0]))
    elif mutation == "nan": prices[0]["high"] = float("nan")
    elif mutation == "boolean_price": prices[0]["close"] = True
    elif mutation == "bad_ohlc": prices[0]["low"] = 101
    elif mutation == "naive_time": prices[0]["end"] = "2020-01-02T00:00:00"
    elif mutation == "offgrid": prices[0]["start"] = "2019-12-31T23:59:00Z"
    elif mutation == "early_available": prices[0]["available_at"] = ts()
    elif mutation == "wrong_source": prices[0]["source"] = "unregistered"
    with pytest.raises(ValueError): run(lab, prices=prices)


def test_contract_hash_and_partition_protect_outcomes(lab):
    cfg = contract()
    original_hash = lab.digest(cfg)
    cfg["min_liquidity_usd"] = 1
    with pytest.raises(ValueError, match="hash"):
        lab.build_dataset(cfg, [snapshot()], bars(), as_of=ts(100), expected_contract_hash=original_hash)
    cfg["partition"] = "UNTOUCHED_OOS"
    with pytest.raises(ValueError, match="DEVELOPMENT"):
        run(lab, cfg=cfg)


def test_point_in_time_exclusions_and_overlap_are_auditable(lab):
    snaps = [snapshot(), snapshot(day=1), snapshot(day=90), snapshot("ILLIQ", liquidity_usd=10),
             snapshot("NEW", listing_age_days=2), snapshot("GONE", tradable=False),
             snapshot("NONMEMBER", member=False)]
    out = run(lab, snapshots=snaps, prices=bars(count=180), as_of=ts(180))
    audit = {r["snapshot_id"]: r for r in out["snapshots"]}
    assert len(out["labels"]) == 2
    assert sorted(r["exclusion_reason"] for r in audit.values() if not r["eligible"]) == [
        "INSUFFICIENT_LIQUIDITY", "LISTING_TOO_YOUNG", "NOT_MEMBER", "NOT_TRADABLE", "OVERLAPPING_WINDOW"]


def test_order_does_not_change_dataset_or_pool_hashes(lab):
    snaps = [snapshot(a) for a in "ABCD"]
    prices = sum([bars(a, highs={2: 200} if a == "A" else {}) for a in "ABCD"], [])
    first = run(lab, snapshots=snaps, prices=prices)
    second = run(lab, snapshots=list(reversed(snaps)), prices=list(reversed(prices)))
    assert first == second
    pairs = first["controls"]
    assert [r["control_asset_id"] for r in pairs] == ["B", "C", "D"]
    assert first["summary"]["complete_cohort_base_rate"] == 0.25


def test_pools_are_outcome_blind_and_never_refilled(lab):
    snaps = [snapshot(a, return_30d=0.1+i*0.01) for i,a in enumerate("ABCDE")]
    prices = sum([bars(a, highs={2: 200} if a in "ABC" else {}) for a in "ABCDE"], [])
    first = run(lab, snapshots=snaps, prices=prices)
    other_prices = sum([bars(a) for a in "ABCDE"], [])
    second = run(lab, snapshots=snaps, prices=other_prices)
    assert first["matching_pools"] == second["matching_pools"]
    assert first["hashes"]["matching_pools"] == second["hashes"]["matching_pools"]
    case = next(x for x in first["cases"] if x["asset_id"] == "A")
    assert case["control_count"] == 1  # D; E must not replace future winners B/C
    assert case["status"] == "INSUFFICIENT_CONTROLS"
    assert first["summary"]["complete_cohort_base_rate"] == 0.6


def test_missing_future_or_wrong_stratum_never_used_as_controls(lab):
    snaps = [snapshot("A"), snapshot("B"), snapshot("C", sector="different"), snapshot("D", regime="bear")]
    out = run(lab, snapshots=snaps, prices=bars("A", highs={2: 200})+bars("C")+bars("D"))
    assert out["controls"] == []
    assert out["cases"][0]["unknown_neighbor_count"] == 1
    assert out["summary"]["censored_count"] == 1
    assert out["summary"]["full_cohort_base_rate"] is None


def test_missing_stale_future_observed_or_undeclared_features_fail(lab):
    for change in ("missing", "stale", "future_observed", "extra"):
        snap = snapshot()
        if change == "missing": del snap["features"]["float_supply"]
        elif change == "stale": snap["features"]["sector"]["observed_at"] = ts(-3)
        elif change == "future_observed": snap["features"]["sector"]["observed_at"] = ts(1)
        else: snap["features"]["future_return"] = snap["features"]["return_30d"]
        with pytest.raises(ValueError): run(lab, snapshots=[snap])


def test_decision_price_cannot_be_a_stale_preexplosion_price(lab):
    snap = snapshot()
    snap["features"]["price"]["observed_at"] = ts(-1)
    with pytest.raises(ValueError, match="decision-time price"):
        run(lab, snapshots=[snap])


def test_bars_outside_declared_development_partition_are_rejected(lab):
    with pytest.raises(ValueError, match="DEVELOPMENT"):
        run(lab, prices=bars(day=364, count=2))


def test_empty_snapshot_input_is_not_a_completed_research_dataset(lab):
    cfg = contract()
    with pytest.raises(ValueError, match="snapshot"):
        lab.build_dataset(cfg, [], [], as_of=ts(100), expected_contract_hash=lab.digest(cfg))


def test_hourly_bars_preserve_fractional_threshold_arrival(lab):
    cfg = contract()
    cfg["bar_seconds"] = 3600
    prices = []
    for h in range(2160):
        start = T0 + timedelta(hours=h)
        end = start + timedelta(hours=1)
        prices.append({"asset_id": "A", "venue": "fixture", "start": start.isoformat(),
                       "end": end.isoformat(), "available_at": end.isoformat(),
                       "open": 100, "low": 100, "close": 100,
                       "high": 200 if h == 11 else 100, "source": "synthetic-ohlc-fixture"})
    row = run(lab, prices=prices, cfg=cfg)["labels"][0]
    assert row["days_to_2x"] == 0.5
    assert row["days_to_2x_lower_bound"] == pytest.approx(11/24)


def test_calipers_reuse_and_cross_venue_overlap(lab):
    snaps = [snapshot(a) for a in "ABCDE"] + [snapshot("F", market_cap_usd=1000000000)]
    other_venue = snapshot("A")
    other_venue["venue"] = "z-other"
    out = run(lab, snapshots=snaps+[other_venue],
              prices=sum([bars(a, highs={2: 200} if a in "AB" else {}) for a in "ABCDEF"], []))
    assert not any(p["neighbor_asset_id"] == "F" for p in out["matching_pools"])
    assert out["summary"]["excluded_count"] == 1
    assert out["summary"]["control_pair_count"] == 4
    assert out["summary"]["unique_control_count"] == 2
    assert all(r["control_reuse_count"] == 2 for r in out["controls"])


def test_artifact_roundtrip_is_immutable_and_detects_tampering(lab, tmp_path):
    assert importlib.util.find_spec("big_move_lab.artifacts") is not None, "artifact writer missing"
    artifacts = importlib.import_module("big_move_lab.artifacts")
    data = run(lab, prices=bars(highs={10: 200}))
    target = tmp_path / "dataset"
    manifest = artifacts.write_bundle(target, contract(), data)
    assert manifest["dataset_hash"] == data["dataset_hash"]
    loaded = artifacts.verify_bundle(target, expected_dataset_hash=data["dataset_hash"])
    assert loaded["labels"] == data["labels"]
    with pytest.raises(FileExistsError): artifacts.write_bundle(target, contract(), data)
    with pytest.raises(ValueError): artifacts.verify_bundle(target, expected_dataset_hash="0"*64)
    (target / "labels.jsonl.gz").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        artifacts.verify_bundle(target, expected_dataset_hash=data["dataset_hash"])


def test_cli_builds_local_artifact_and_refuses_changed_contract(lab, tmp_path):
    import json
    import os
    import subprocess
    import sys
    cfg = contract()
    cpath, ipath = tmp_path / "contract.json", tmp_path / "input.json"
    cpath.write_text(json.dumps(cfg))
    ipath.write_text(json.dumps({"snapshots": [snapshot()], "bars": bars(highs={90: 300})}))
    cmd = [sys.executable, "-m", "big_move_lab", "--contract", str(cpath),
           "--input", str(ipath), "--expected-contract-sha256", lab.digest(cfg),
           "--as-of", ts(100), "--output", str(tmp_path / "output")]
    result = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["event_count"] == 1
    cfg["min_liquidity_usd"] = 10
    cpath.write_text(json.dumps(cfg))
    result = subprocess.run(cmd[:-1]+[str(tmp_path / "other")], capture_output=True, text=True)
    assert result.returncode != 0
    assert not (tmp_path / "other").exists()


def test_parquet_export_matches_canonical_tables(lab, tmp_path):
    pytest.importorskip("pyarrow")
    from big_move_lab.artifacts import verify_bundle, write_bundle
    data = run(lab)
    write_bundle(tmp_path / "parquet", contract(), data, parquet=True)
    loaded = verify_bundle(tmp_path / "parquet", expected_dataset_hash=data["dataset_hash"])
    assert loaded == data


@pytest.mark.parametrize("key,value", [("bar_seconds", True), ("neighbor_pool_size", 1),
                                       ("min_controls", 1), ("max_feature_age_seconds", -1),
                                       ("min_liquidity_usd", float("inf"))])
def test_unsafe_contract_values_are_rejected(lab, key, value):
    cfg = contract()
    cfg[key] = value
    with pytest.raises(ValueError): run(lab, cfg=cfg)


def test_manifest_cannot_relabel_verified_dataset(lab, tmp_path):
    import json
    from big_move_lab.artifacts import verify_bundle, write_bundle
    data = run(lab)
    write_bundle(tmp_path / "bundle", contract(), data)
    path = tmp_path / "bundle" / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["target"] = "PRECISE_90_DAY_PROBABILITY"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="identity"):
        verify_bundle(tmp_path / "bundle", expected_dataset_hash=data["dataset_hash"])


@pytest.mark.parametrize("high,hit", [(0.3, True), (0.29999999999999993, False)])
def test_exact_decimal_thresholds_and_immediately_below(lab, high, hit):
    prices = bars()
    for bar in prices:
        bar.update(open=0.1, high=0.1, low=0.08, close=0.1)
    prices[1]["high"] = high
    row = run(lab, snapshots=[snapshot(price=0.1)], prices=prices)["labels"][0]
    assert row["reached_3x"] is hit
    assert row["days_to_3x"] == (2 if hit else None)
    if hit:
        assert row["maximum_90d_price_multiple"] == 3
        assert row["max_forward_90d_return"] == 2


def test_manifest_cannot_hide_tampered_parquet(lab, tmp_path):
    import json
    pytest.importorskip("pyarrow")
    import pyarrow as pa
    import pyarrow.parquet as pq
    from big_move_lab.artifacts import verify_bundle, write_bundle
    data = run(lab)
    path = tmp_path / "bundle"
    write_bundle(path, contract(), data, parquet=True)
    labels = pq.read_table(path / "labels.parquet").to_pylist()
    labels[0]["reached_2x"] = True
    pq.write_table(pa.Table.from_pylist(labels), path / "labels.parquet")
    manifest = json.loads((path / "manifest.json").read_text())
    manifest["parquet"] = False
    manifest["files"] = {k: v for k, v in manifest["files"].items() if not k.endswith(".parquet")}
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="unexpected"):
        verify_bundle(path, expected_dataset_hash=data["dataset_hash"])
