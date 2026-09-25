from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

import btc_candle_replication as screen

T0 = 1704067200000
MINUTE = 60000


def row(t, open_price=100, quote=100, buy=75):
    return dict(t=t, open=open_price, close=open_price, quote=quote, buy=buy)


def csv_zip(lines, name="BTCUSDT-1m-2024-01.csv"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(name, "\n".join(lines))
    raw = buf.getvalue()
    checksum = f"{hashlib.sha256(raw).hexdigest()}  BTCUSDT-1m-2024-01.zip"
    return raw, checksum


def csv_line(t=T0):
    return f"{t},100,102,98,101,10,{t+59999},1000,20,6,600,0"


def test_parser_binds_checksum_filename_units_and_bounds():
    raw, checksum = csv_zip([csv_line()])
    rows = screen.parse_archive(raw, checksum, "2024-01")
    assert rows[0]["buy"] == 600
    assert rows[0]["t"] == T0
    for invalid in [checksum.replace("2024-01.zip", "2024-02.zip"), "0"*64+checksum[64:]]:
        with pytest.raises(ValueError):
            screen.parse_archive(raw, invalid, "2024-01")


@pytest.mark.parametrize("change", [lambda s:s.replace(",600,", ",1001,"),
    lambda s:s.replace(",100,", ",nan,"), lambda s:s.replace(str(T0),str(T0*1000),1),
    lambda s:s.replace(str(T0+59999),str(T0+60000)),lambda s:s.replace(",20,", ",20.5,"),
    lambda s:s.replace(",102,", ",99,")])
def test_malformed_rows_rejected(change):
    raw, checksum = csv_zip([change(csv_line())])
    with pytest.raises(ValueError):
        screen.parse_archive(raw, checksum, "2024-01")


def test_duplicate_rows_and_archive_member_substitution_rejected():
    for lines,name in [([csv_line(),csv_line()],"BTCUSDT-1m-2024-01.csv"),
                       ([csv_line()],"../BTCUSDT-1m-2024-01.csv")]:
        raw,checksum=csv_zip(lines,name)
        with pytest.raises(ValueError):
            screen.parse_archive(raw,checksum,"2024-01")


def test_features_precede_entry_and_future_mutation_cannot_change_score():
    rows=[row(T0+i*MINUTE) for i in range(60)]
    events,qa=screen.make_events(rows)
    first=events[0]
    assert first["t"] == T0+15*MINUTE
    assert first["score"] == .5
    changed=[dict(r,open=200,close=200,buy=0) if r['t']>=first['t']-MINUTE else r for r in rows]
    mutated,_=screen.make_events(changed)
    assert mutated[0]["score"] == first["score"]
    assert mutated[0]["price_positive"] == first["price_positive"]
    assert all(3 <= e["random_offset"] <= 12 for e in events)
    assert qa["missing_blocks"] == 0


def test_missing_minute_excludes_whole_matched_block_without_compressing_time():
    rows=[row(T0+i*MINUTE) for i in range(60) if i!=20]
    events,qa=screen.make_events(rows)
    assert T0+15*MINUTE not in {e["t"] for e in events}
    assert qa["missing_blocks"] == 1


def event(t, score=0, target=5, placebo=0):
    return dict(t=t,score=score,price_positive=True,target=target,delayed=0,clock=placebo,random=0)


def test_thresholds_fit_predictors_only_and_empty_cells_are_unknown():
    train=[event(T0+i*86400000,score=i) for i in range(100)]
    validation=[event(T0+190*86400000,score=1)]
    report=screen.compare(train,validation)
    assert report["5"]["cutoff"] == 95
    assert report["1"]["validation"]["n"] == 0
    assert report["1"]["validation"]["mean_gross_bps"] is None
    altered=[dict(e,target=-10000) for e in train]
    assert screen.compare(altered,validation)["5"]["cutoff"] == 95


def test_exact_sign_test_and_partial_week_exclusion():
    values=[event(T0+i*7*86400000,target=1) for i in range(26)]
    values.append(event(T0+182*86400000,target=-1000))
    stats=screen.block_sign_test(values,T0,T0+184*86400000)
    assert stats["informative_complete_weeks"] == 26
    assert stats["one_sided_p"] == 2**-26
    assert stats["bonferroni_p"] == 12*2**-26


def test_costs_cash_price_baseline_and_day_tail_are_not_optimistic():
    values=[event(T0,target=30),event(T0+86400000,target=-30)]
    metrics=screen.metrics(values,2)
    assert metrics["costs"]["24"]["mean_net_bps"] == -24
    assert metrics["costs"]["24"]["winner_day_removed_mean_bps"] == -54
    assert metrics["costs"]["24"]["tail_veto"] is True
    assert metrics["cash_per_opportunity_bps"] == 0
    no_signal=screen.metrics([dict(values[0],price_positive=False)],1)
    assert no_signal["costs"]["24"]["price_baseline_per_opportunity_bps"] == 0


def test_protocol_identity_is_fixed():
    assert screen.load_protocol()["fingerprint"] == "EXT-BTC-CANDLE-CLOCK-001-v1"


def test_survivor_requires_every_primary_gate_and_never_uses_best_bucket():
    # Same eligible 15-minute calendar as the contract, with a strong synthetic edge.
    train=[event(t,target=100,placebo=0) for t in range(screen.START+15*MINUTE,screen.SPLIT,15*MINUTE)]
    validation=[event(t,target=100,placebo=0) for t in range(screen.SPLIT,screen.END,15*MINUTE)]
    train=[dict(e,price_positive=False) for e in train]
    validation=[dict(e,price_positive=False) for e in validation]
    buckets=screen.compare(train,validation)
    result=screen.evaluate(buckets,validation)
    assert result["decision"] == "SURVIVOR_REQUIRES_CANONICAL_ADMISSION_AND_FRESH_EVIDENCE"
    buckets["100"]["validation"]["paired_clock_inference"]["bonferroni_p"]=.1
    assert screen.evaluate(buckets,validation)["decision"] == "REJECTED_STAGE1"
    buckets["100"]["validation"]["paired_clock_inference"]["informative_complete_weeks"]=19
    assert screen.evaluate(buckets,validation)["decision"] == "INCONCLUSIVE_DATA_OR_POWER"


def test_no_losses_are_explicit_and_not_fabricated_profit_factor():
    stats=screen.metrics([event(T0,target=100)],1)["costs"]["24"]
    assert stats["profit_factor"] is None
    assert stats["profit_factor_unbounded"] is True


def test_selective_per_opportunity_metrics_count_cash_outside_bucket():
    stats=screen.metrics([event(T0,target=54)],100)["costs"]["24"]
    assert stats["mean_net_bps"] == 30
    assert stats["target_per_opportunity_bps"] == .3
    assert stats["price_baseline_per_opportunity_bps"] == .3
    assert stats["controls_per_opportunity_bps"]["clock"] == -.24
