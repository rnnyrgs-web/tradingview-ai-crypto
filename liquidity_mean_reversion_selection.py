"""Research-only cheap screen for frozen DISC-LIQUIDITY-MEANREV-001-v1.

Scores train/validation only. Untouched OOS stays locked. No trade/promotion authority.
"""
from __future__ import annotations
import argparse, gzip, json, statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from volatility_breakout_selection import (
    LOCKED_OOS, _dataset_manifest, _max_stress, _regime, _selection_decision,
    _sha256_hex, _split_bounds, _stress_metrics, _validate_rows as _validate_ohlcv,
)

ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "orchestration" / "disc_liquidity_meanrev_001.json"
FROZEN_CONTRACT_SHA256 = "19252de4464fc997632b0500fded857bc58d5bdad49d6f72e3660eba75a28b57"
CACHE_PATH = ROOT / "orchestration/evidence/liquidity_meanrev_001_cache"
FROZEN_DATASET_SHA256 = "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f"
FROZEN_ENVELOPE_SHA256 = "8630b22e7c2a8e0ef0e44fad2ea0fcd30395c9e2b2ef99bc08c98afb6e968f4e"

def _load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    c = json.loads(path.read_text(encoding="utf-8"))
    return _validate_contract(c)

def _validate_contract(c):
    payload = dict(c); payload.pop("contract_sha256", None); payload.pop("contract_fingerprint_definition", None)
    if _sha256_hex(payload) != c.get("contract_sha256") or c.get("contract_sha256") != FROZEN_CONTRACT_SHA256:
        raise RuntimeError("selection contract fingerprint mismatch")
    if c.get("fingerprint_id") != "DISC-LIQUIDITY-MEANREV-001-v1":
        raise RuntimeError("unexpected fingerprint")
    if c.get("chronology", {}).get("untouched_oos") != "LOCKED":
        raise RuntimeError("untouched OOS must remain locked")
    if c.get("source", {}).get("asset_substitution_allowed") is not False:
        raise RuntimeError("asset substitution forbidden")
    if c.get("search_breadth", {}).get("parameter_optimization_allowed") is not False:
        raise RuntimeError("parameter optimization forbidden")
    return c

def _validate_rows(rows):
    clean = _validate_ohlcv(rows)
    for row in clean:
        if row["ts"] % 3_600_000:
            raise ValueError("history must use UTC hourly bar-open timestamps")
    if any(b["ts"] - a["ts"] != 3_600_000 for a, b in zip(clean, clean[1:])):
        raise ValueError("missing hourly bars; interpolation and row-count time compression forbidden")
    return clean

def _signal(rows, i, contract, *, sigma_multiple=None, liquidity_filters=True):
    r = contract["primary_rule"]; w = int(r["volatility_window_bars"])
    if i < w + 1: return 0, None
    prior = [float(rows[j]["close"]) / float(rows[j-1]["close"]) - 1 for j in range(i-w, i)]
    sigma = statistics.stdev(prior)
    ret = float(rows[i]["close"]) / float(rows[i-1]["close"]) - 1
    m = float(r["sigma_multiple"] if sigma_multiple is None else sigma_multiple)
    threshold = max(float(r["absolute_return_floor"]), m * sigma)
    prior_qv = [float(rows[j]["quote_volume"]) for j in range(i-w, i)]
    prior_rng = [(float(rows[j]["high"])-float(rows[j]["low"])) / float(rows[j-1]["close"]) for j in range(i-w, i)]
    qv_med, rng_med = statistics.median(prior_qv), statistics.median(prior_rng)
    qv_ratio = None if qv_med <= 0 else float(rows[i]["quote_volume"]) / qv_med
    signal_rng = (float(rows[i]["high"])-float(rows[i]["low"])) / float(rows[i-1]["close"])
    rng_ratio = None if rng_med <= 0 else signal_rng / rng_med
    f = {"return":ret,"sigma":sigma,"threshold":threshold,"quote_volume_ratio":qv_ratio,"range_ratio":rng_ratio}
    if abs(ret) <= threshold: return 0, f
    if liquidity_filters and (qv_ratio is None or rng_ratio is None or qv_ratio < float(r["quote_volume_ratio_min"]) or rng_ratio < float(r["range_ratio_min"])): return 0, f
    return (-1 if ret > 0 else 1), f

def _trades(rows, start, end, contract, *, sigma_multiple=None, liquidity_filters=True):
    i = max(start, int(contract["chronology"]["minimum_warmup_bars"])); hold = int(contract["primary_rule"]["holding_period_bars"]); out = []
    while i < end:
        direction, f = _signal(rows, i, contract, sigma_multiple=sigma_multiple, liquidity_filters=liquidity_filters)
        if not direction: i += 1; continue
        entry_i, exit_i = i + 1, i + 1 + hold
        if exit_i >= end: break
        entry, exit_price = float(rows[entry_i]["open"]), float(rows[exit_i]["open"])
        out.append({"signal_index":i,"signal_ts":int(rows[i]["ts"]),"entry_index":entry_i,"entry_ts":int(rows[entry_i]["ts"]),"exit_index":exit_i,"exit_ts":int(rows[exit_i]["ts"]),"direction":"LONG" if direction>0 else "SHORT","regime":_regime(rows,i),"gross_bps":direction*(exit_price/entry-1)*10000,"shock_return":f["return"],"trailing_sigma":f["sigma"],"quote_volume_ratio":f["quote_volume_ratio"],"range_ratio":f["range_ratio"]})
        i = exit_i + 1
    return out

def _segment(rows, start, end, contract, **kwargs):
    t = _trades(rows,start,end,contract,**kwargs); mid = start + (end-start)//2
    first=[x for x in t if x["signal_index"]<mid]; second=[x for x in t if x["signal_index"]>=mid]
    return {"start_ts":int(rows[start]["ts"]),"end_ts":int(rows[end-1]["ts"]),"trades":t,"cost_stress":_stress_metrics(t,contract),"first_half_cost_stress":_stress_metrics(first,contract),"second_half_cost_stress":_stress_metrics(second,contract),"regime_cost_stress":{r:_stress_metrics([x for x in t if x["regime"]==r],contract) for r in ("BULL","BEAR")}}

def _evaluate(rows, contract, **kwargs):
    clean=_validate_rows(rows); b=_split_bounds(len(clean),contract)
    return {"row_count":len(clean),"bounds":b,"train":_segment(clean,b["train_start"],b["train_end"],contract,**kwargs),"validation":_segment(clean,b["validation_start"],b["validation_end"],contract,**kwargs),"untouched_oos":{**LOCKED_OOS,"start_ts":int(clean[b["oos_start"]]["ts"]),"end_ts":int(clean[-1]["ts"]),"rows":b["oos_end"]-b["oos_start"]}}

def _pooled(evidence, segment, contract):
    t=[]
    for inst,e in evidence.items():
        for row in e[segment]["trades"]:
            x=dict(row); x["instrument"]=inst; t.append(x)
    t.sort(key=lambda x:(x["signal_ts"],x["instrument"])); starts=[e[segment]["start_ts"] for e in evidence.values()]; ends=[e[segment]["end_ts"] for e in evidence.values()]; mid=min(starts)+(max(ends)-min(starts))//2
    first=[x for x in t if x["signal_ts"]<mid]; second=[x for x in t if x["signal_ts"]>=mid]
    return {"cost_stress":_stress_metrics(t,contract),"first_half_cost_stress":_stress_metrics(first,contract),"second_half_cost_stress":_stress_metrics(second,contract),"regime_cost_stress":{r:_stress_metrics([x for x in t if x["regime"]==r],contract) for r in ("BULL","BEAR")}}

def _instrument_pass(p,b,c):
    reasons=[]; tr=_max_stress(p["train"]["cost_stress"],c); va=_max_stress(p["validation"]["cost_stress"],c); base=_max_stress(b["validation"]["cost_stress"],c)
    if tr["trades"]<15: reasons.append("TRAIN_SAMPLE_FLOOR")
    if va["trades"]<5: reasons.append("VALIDATION_SAMPLE_FLOOR")
    if tr["mean_net_bps"] is None or tr["mean_net_bps"]<=0: reasons.append("TRAIN_EXPECTANCY")
    if va["mean_net_bps"] is None or va["mean_net_bps"]<=0: reasons.append("VALIDATION_EXPECTANCY")
    if va["profit_factor"] is None or va["profit_factor"]<=1: reasons.append("VALIDATION_PROFIT_FACTOR")
    if va["mean_net_bps"] is None or base["mean_net_bps"] is None or va["mean_net_bps"]<base["mean_net_bps"]: reasons.append("NO_INCREMENTAL_VALIDATION_VALUE")
    return not reasons,reasons

def _pooled_pass(p,b,c):
    reasons=[]; tr=_max_stress(p["train"]["cost_stress"],c); va=_max_stress(p["validation"]["cost_stress"],c); base=_max_stress(b["validation"]["cost_stress"],c); first=_max_stress(p["validation"]["first_half_cost_stress"],c); second=_max_stress(p["validation"]["second_half_cost_stress"],c)
    if tr["trades"]<45: reasons.append("POOLED_TRAIN_SAMPLE_FLOOR")
    if va["trades"]<15: reasons.append("POOLED_VALIDATION_SAMPLE_FLOOR")
    if tr["mean_net_bps"] is None or tr["mean_net_bps"]<=0: reasons.append("POOLED_TRAIN_EXPECTANCY")
    if va["mean_net_bps"] is None or va["mean_net_bps"]<=0: reasons.append("POOLED_VALIDATION_EXPECTANCY")
    if va["profit_factor"] is None or va["profit_factor"]<=1: reasons.append("POOLED_VALIDATION_PROFIT_FACTOR")
    if first["mean_net_bps"] is None or first["mean_net_bps"]<=-20: reasons.append("VALIDATION_FIRST_HALF_INSTABILITY")
    if second["mean_net_bps"] is None or second["mean_net_bps"]<=-20: reasons.append("VALIDATION_SECOND_HALF_INSTABILITY")
    if va["mean_net_bps"] is None or base["mean_net_bps"] is None or va["mean_net_bps"]<base["mean_net_bps"]: reasons.append("POOLED_NO_INCREMENTAL_VALIDATION_VALUE")
    for regime in ("BULL","BEAR"):
        m=_max_stress(p["validation"]["regime_cost_stress"][regime],c)
        if m["trades"]>=6 and (m["mean_net_bps"] is None or m["mean_net_bps"]<=-60): reasons.append(f"{regime}_REGIME_CATASTROPHIC")
    return not reasons,reasons

def _sensitivity_pass(p,c):
    reasons=[]; tr=_max_stress(p["train"]["cost_stress"],c); va=_max_stress(p["validation"]["cost_stress"],c)
    if tr["trades"]<30: reasons.append("TRAIN_SAMPLE_FLOOR")
    if va["trades"]<10: reasons.append("VALIDATION_SAMPLE_FLOOR")
    if tr["mean_net_bps"] is None or tr["mean_net_bps"]<=0: reasons.append("TRAIN_EXPECTANCY")
    if va["mean_net_bps"] is None or va["mean_net_bps"]<=0: reasons.append("VALIDATION_EXPECTANCY")
    return not reasons,reasons

def evaluate_selection_from_histories(histories, *, contract=None):
    c=_load_contract() if contract is None else _validate_contract(contract); fixed=list(c["source"]["fixed_instruments"]); minimum=int(c["source"]["minimum_history_bars_per_asset"]); clean={}; errors={}
    for inst in fixed:
        if inst not in histories: errors[inst]="MISSING_FIXED_INSTRUMENT"; continue
        try: rows=_validate_rows(histories[inst])
        except ValueError as exc: errors[inst]=str(exc); continue
        if len(rows)<minimum: errors[inst]=f"INSUFFICIENT_HISTORY:{len(rows)}<{minimum}"; continue
        clean[inst]=rows
    data_ok=len(clean)==len(fixed) and not errors; primary={}; baseline={}; sens={x["id"]:{} for x in c["falsifier_sensitivities"]}
    if data_ok:
        for inst in fixed:
            primary[inst]=_evaluate(clean[inst],c,liquidity_filters=True); baseline[inst]=_evaluate(clean[inst],c,liquidity_filters=False)
            for s in c["falsifier_sensitivities"]: sens[s["id"]][inst]=_evaluate(clean[inst],c,sigma_multiple=float(s["sigma_multiple"]),liquidity_filters=True)
    passes={}; count=0; pooled_primary={"train":{},"validation":{}}; pooled_baseline={"train":{},"validation":{}}; pooled_ok=False; pooled_reasons=[]; sp={}; sr={}; sens_pooled={}
    if data_ok:
        for inst in fixed:
            ok,reasons=_instrument_pass(primary[inst],baseline[inst],c); passes[inst]={"passes":ok,"failure_reasons":reasons}; count+=int(ok)
        pooled_primary={seg:_pooled(primary,seg,c) for seg in ("train","validation")}; pooled_baseline={seg:_pooled(baseline,seg,c) for seg in ("train","validation")}; pooled_ok,pooled_reasons=_pooled_pass(pooled_primary,pooled_baseline,c)
        for sid,ev in sens.items():
            p={seg:_pooled(ev,seg,c) for seg in ("train","validation")}; sens_pooled[sid]=p; sp[sid],sr[sid]=_sensitivity_pass(p,c)
    decision=_selection_decision(data_integrity_ok=data_ok,passing_instruments=count,pooled_primary_pass=pooled_ok,sensitivity_passes=sp,contract=c)
    return {"hypothesis_id":c["hypothesis_id"],"fingerprint_id":c["fingerprint_id"],"contract_sha256":c["contract_sha256"],"research_only":True,"trade_authority":False,"promotion_authority":False,"screen_stage":"SELECTION_ONLY","data_integrity_ok":data_ok,"data_errors":errors,"passing_instruments":count,"instrument_passes":passes,"primary":primary,"baseline":baseline,"pooled_primary":pooled_primary,"pooled_baseline":pooled_baseline,"pooled_primary_pass":pooled_ok,"pooled_primary_failure_reasons":pooled_reasons,"sensitivity_pooled":sens_pooled,"sensitivity_passes":sp,"sensitivity_failure_reasons":sr,"untouched_oos":dict(LOCKED_OOS),"untouched_oos_opened":False,"genuine_forward_opened":False,**decision}

def _load_frozen_cache(cache_path=CACHE_PATH):
    from research_artifact import verify_research_envelope
    c = _load_contract()
    with gzip.open(cache_path / "evidence.json.gz", "rt", encoding="utf-8") as f:
        evidence = json.load(f)
    with gzip.open(cache_path / "dataset.json.gz", "rt", encoding="utf-8") as f:
        dataset = json.load(f)
    if not verify_research_envelope(evidence) or evidence["integrity"]["payload_sha256"] != FROZEN_ENVELOPE_SHA256:
        raise RuntimeError("original evidence integrity mismatch")
    if _sha256_hex(dataset) != FROZEN_DATASET_SHA256:
        raise RuntimeError("frozen dataset identity mismatch; no fresh-history substitution")
    payload = evidence["payload"]
    if payload["contract_sha256"] != c["contract_sha256"]:
        raise RuntimeError("evidence contract mismatch")
    manifest, _ = _dataset_manifest(dataset["histories"], c)
    if manifest != payload["dataset_manifest"]:
        raise RuntimeError("dataset provenance mismatch")
    # Check timestamp metadata only; never derive outcomes from the locked tail.
    observed_ms = int(datetime.fromisoformat(payload["generated_at"]).timestamp() * 1000)
    for rows in dataset["histories"].values():
        _validate_rows(rows)
        if rows[-1]["ts"] + 3_600_000 > observed_ms:
            raise RuntimeError("incomplete bar at artifact observation time")
    return evidence, dataset

def run():
    """Offline exact replay of the first screen, never a new selection trial.

    Cache includes the original opaque OOS tail for provenance only. All trade
    generation and metrics remain confined to the original purged train/val.
    Missing/corrupt cache fails closed; there is no network fallback.
    """
    evidence, dataset = _load_frozen_cache()
    selection = evaluate_selection_from_histories(dataset["histories"])
    if selection != evidence["payload"]["selection"]:
        raise RuntimeError("frozen selection replay differs from original evidence")
    return evidence, dataset

def main():
    p=argparse.ArgumentParser(); p.add_argument("--output",default="liquidity_mean_reversion_selection.json"); p.add_argument("--dataset-output",default="liquidity_mean_reversion_selection_dataset.json.gz"); a=p.parse_args(); evidence,dataset=run(); Path(a.output).write_text(json.dumps(evidence,indent=2,sort_keys=True),encoding="utf-8")
    with gzip.open(a.dataset_output,"wt",encoding="utf-8") as h: json.dump(dataset,h,sort_keys=True,separators=(",",":"))
    s=evidence["payload"]["selection"]; print(json.dumps({"fingerprint_id":s["fingerprint_id"],"screen_status":s["screen_status"],"economic_pre_oos_pass":s["economic_pre_oos_pass"],"passing_instruments":s["passing_instruments"],"untouched_oos_opened":s["untouched_oos_opened"],"dataset_sha256":evidence["payload"]["dataset_manifest"]["normalized_rows_sha256"]},sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
