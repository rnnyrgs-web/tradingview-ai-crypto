"""Frozen BTC candle-clock replication: acquire once, then screen offline.

python btc_candle_replication.py acquire --cache PATH
python btc_candle_replication.py screen --cache PATH --output PATH
No canonical admission, protected-data, profitability or trading authority.
"""
from __future__ import annotations

import argparse
import calendar
import csv
import gzip
import hashlib
import io
import json
import math
import statistics
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTRACT = ROOT / "research_data/btc_candle_2024"
IDENTITIES = {
    "protocol": "e5ed40c277e213c9d604a573a6b18b6f949c812c9e4b98727dca57fdbe6a8911",
    "inference_amendment": "2e9bb89ccf4d370fa2717f64f71aeab6b8c30a0a90926ab82c521f0696fe873c",
    "tail_amendment": "7cc5bb27c8f3cb4d669d350b8013087fc99d0a226503f8add1d694290facd616",
}
MINUTE, DAY = 60000, 86400000
START = 1704067200000
SPLIT = 1719792000000
END = 1735689600000
FINGERPRINT = "EXT-BTC-CANDLE-CLOCK-001-v1"
COSTS = (24, 48, 72)
BUCKETS = (1, 5, 10, 20, 50, 100)
MAX_ZIP = 16 * 1024 * 1024


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def load_protocol():
    contracts = {}
    for name, expected in IDENTITIES.items():
        value = json.loads((CONTRACT / f"{name}.json").read_text(encoding="utf-8"))
        if digest(value) != expected:
            raise ValueError("frozen protocol/amendment identity changed")
        contracts[name] = value
    return contracts["protocol"]


def parse_archive(raw, checksum, month):
    if month not in [f"2024-{m:02}" for m in range(1, 13)]:
        raise ValueError("month outside frozen development window")
    filename = f"BTCUSDT-1m-{month}.zip"
    if checksum.strip().split() != [hashlib.sha256(raw).hexdigest(), filename]:
        raise ValueError("provider checksum or filename mismatch")
    if len(raw) > MAX_ZIP:
        raise ValueError("archive exceeds bound")
    first = int(datetime.fromisoformat(month + "-01T00:00:00+00:00").timestamp()*1000)
    last = first + calendar.monthrange(2024, int(month[-2:]))[1] * DAY
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) != 1 or members[0].filename != filename[:-4] + ".csv" or members[0].file_size > 32*1024*1024:
            raise ValueError("unexpected archive member or size")
        text = archive.read(members[0]).decode("utf-8")
    rows, prior = [], first - MINUTE
    for fields in csv.reader(io.StringIO(text)):
        if len(fields) != 12:
            raise ValueError("expected exactly12 provider kline fields")
        t, close_time, count = int(fields[0]), int(fields[6]), int(fields[8])
        op, high, low, close, volume, quote, buy_base, buy = (float(fields[i]) for i in (1,2,3,4,5,7,9,10))
        if not all(math.isfinite(v) for v in (op,high,low,close,volume,quote,buy_base,buy)):
            raise ValueError("nonfinite provider value")
        if not first <= t < last or t % MINUTE or t <= prior or close_time != t+MINUTE-1:
            raise ValueError("invalid timestamp, units, ordering or duplicate")
        if not 0 < low <= min(op,close) <= max(op,close) <= high or count < 0:
            raise ValueError("invalid OHLC or trade count")
        if not 0 <= buy <= quote or not 0 <= buy_base <= volume:
            raise ValueError("invalid volume or taker units")
        rows.append(dict(t=t, open=op, close=close, quote=quote, buy=buy))
        prior = t
    if not rows:
        raise ValueError("empty archive")
    return rows


def _fetch(url, maximum):
    # URL is constructed exclusively from frozen month names and this exact host.
    if not url.startswith("https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/"):
        raise ValueError("unexpected source")
    with urllib.request.urlopen(url, timeout=45) as response:  # nosec B310 - exact HTTPS origin above
        if response.geturl() != url:
            raise ValueError("source redirect not accepted")
        raw = response.read(maximum + 1)
        if len(raw) > maximum:
            raise ValueError("source exceeds byte bound")
        metadata = {key: response.headers.get(key) for key in ("Date", "Last-Modified", "ETag", "Content-Length")}
    return raw, metadata


def acquire(cache):
    protocol = load_protocol()
    cache.mkdir(parents=True, exist_ok=True)
    manifest_path = cache / "manifest.json"
    if manifest_path.exists():
        raise ValueError("immutable acquisition already exists; use offline screen")
    manifest = {"fingerprint": FINGERPRINT, "contracts": IDENTITIES, "objects": [],
                "provenance_grade": "PUBLIC_HTTPS_PROVIDER_ARCHIVES_NOT_CANONICAL_PIT_VINTAGE_ATTESTATION"}
    for month in protocol["data"]["months"]:
        filename = f"BTCUSDT-1m-{month}.zip"
        url = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m/" + filename
        raw, headers = _fetch(url, MAX_ZIP)
        check, check_headers = _fetch(url + ".CHECKSUM", 1024)
        parsed = parse_archive(raw, check.decode("ascii"), month)
        (cache / filename).write_bytes(raw)
        (cache / (filename + ".CHECKSUM")).write_bytes(check)
        manifest["objects"].append({"month": month, "filename": filename, "url": url,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "sha256": hashlib.sha256(raw).hexdigest(),
            "checksum_sha256": hashlib.sha256(check).hexdigest(), "bytes": len(raw), "rows": len(parsed),
            "headers": headers, "checksum_headers": check_headers})
        print(json.dumps({"acquired": month, "bytes":len(raw), "rows":len(parsed)}), flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2)+"\n", encoding="utf-8")
    return manifest


def load_cache(cache):
    protocol = load_protocol()
    manifest = json.loads((cache / "manifest.json").read_text(encoding="utf-8"))
    if manifest["fingerprint"] != FINGERPRINT or manifest["contracts"] != IDENTITIES:
        raise ValueError("acquisition contract mismatch")
    if [o["month"] for o in manifest["objects"]] != protocol["data"]["months"]:
        raise ValueError("acquisition months mismatch")
    rows = []
    for obj in manifest["objects"]:
        name = f"BTCUSDT-1m-{obj['month']}.zip"
        if obj["filename"] != name:
            raise ValueError("cache path mismatch")
        raw, check = (cache/name).read_bytes(), (cache/(name+".CHECKSUM")).read_bytes()
        if hashlib.sha256(raw).hexdigest() != obj["sha256"] or hashlib.sha256(check).hexdigest() != obj["checksum_sha256"]:
            raise ValueError("cached source identity changed")
        parsed = parse_archive(raw,check.decode("ascii"),obj["month"])
        if len(parsed) != obj["rows"] or len(raw) != obj["bytes"]:
            raise ValueError("cached source count changed")
        rows.extend(parsed)
    return rows, manifest


def make_events(rows):
    lookup = {r["t"]: r for r in rows}
    if len(lookup) != len(rows):
        raise ValueError("duplicate row")
    # Pure function accepts shorter synthetic windows; CLI requires every frozen month.
    start, end = min(lookup), max(lookup) + MINUTE
    first = ((start + 6*MINUTE + 15*MINUTE-1)//(15*MINUTE))*(15*MINUTE)
    events, missing, invalid = [], [], []
    for t in range(first, end-14*MINUTE, 15*MINUTE):
        if any(t+i*MINUTE not in lookup for i in range(-6,15)):
            missing.append(t)
            continue
        past = [lookup[t+i*MINUTE] for i in range(-6,-1)]
        volume = sum(r["quote"] for r in past)
        if volume <= 0:
            invalid.append(t)
            continue
        score = 2*sum(r["buy"] for r in past)/volume - 1
        offset = 3+int(hashlib.sha256(f"{FINGERPRINT}|{t}".encode()).hexdigest()[:8],16)%10
        def ret(offset):
            return (lookup[t+(offset+1)*MINUTE]["open"]/lookup[t+offset*MINUTE]["open"]-1)*10000
        events.append(dict(t=t,score=score,price_positive=past[-1]["close"]>past[0]["open"],
                           target=ret(0), delayed=ret(1), clock=ret(5), random=ret(offset),random_offset=offset))
    return events, {"missing_blocks":len(missing), "missing_block_times":missing,
                    "zero_volume_blocks":len(invalid), "zero_volume_block_times":invalid,
                    "expected_blocks":len(range(first,end-14*MINUTE,15*MINUTE)), "eligible_blocks":len(events)}


def block_sign_test(events, start, end):
    complete_weeks = (end-start)//(7*DAY)
    sums = defaultdict(float)
    for event in events:
        index = (event["t"]-start)//(7*DAY)
        if 0 <= index < complete_weeks:
            sums[index] += event["target"]-event["clock"]
    values = [v for v in sums.values() if v != 0]
    n, wins = len(values), sum(v>0 for v in values)
    p = sum(math.comb(n,k) for k in range(wins,n+1))/2**n if n else None
    return {"informative_complete_weeks":n,"positive_weeks":wins,"one_sided_p":p,
            "bonferroni_p":min(1.,12*p) if p is not None else None}


def metrics(events, opportunities):
    n = len(events)
    result = {"n":n,"coverage":n/opportunities if opportunities else None,
              "mean_gross_bps":statistics.mean(e["target"] for e in events) if n else None,
              "cash_per_opportunity_bps":0,"costs":{}}
    for cost in COSTS:
        net = [e["target"]-cost for e in events]
        by_day, counts = defaultdict(float), defaultdict(int)
        for e,v in zip(events,net):
            day = e["t"]//DAY
            by_day[day] += v
            counts[day] += 1
        positive = sum(v for v in by_day.values() if v>0)
        worst = min(by_day.values(),default=0)
        best_day = max(by_day,key=by_day.get) if by_day else None
        remaining = n-counts[best_day] if best_day is not None else 0
        wins, losses = sum(v for v in net if v>0), -sum(v for v in net if v<0)
        result["costs"][str(cost)] = {
            "mean_net_bps":statistics.mean(net) if n else None,
            "profit_factor":wins/losses if losses else None,
            "profit_factor_unbounded":bool(wins>0 and losses==0),
            "win_fraction":sum(v>0 for v in net)/n if n else None,
            "day_count":len(by_day), "worst_day_net_sum_bps":worst if n else None,
            "winner_day_removed_mean_bps":(sum(net)-by_day[best_day])/remaining if remaining else None,
            "tail_veto":positive<=0 or max(0,-worst)>.5*positive,
            "target_per_opportunity_bps":sum(net)/opportunities if opportunities else None,
            "price_baseline_per_opportunity_bps":sum(e["target"]-cost for e in events if e["price_positive"])/opportunities if opportunities else None,
            "controls_per_opportunity_bps":{name:sum(e[name]-cost for e in events)/opportunities if opportunities else None for name in ("delayed","clock","random")},
            "controls_mean_net_bps":{name:statistics.mean(e[name]-cost for e in events) if n else None for name in ("delayed","clock","random")},
        }
    return result


def compare(train, validation):
    if not train:
        raise ValueError("empty training sample")
    scores = sorted((e["score"] for e in train), reverse=True)
    result = {}
    for percent in BUCKETS:
        cutoff = scores[math.ceil(len(scores)*percent/100)-1] if percent<100 else None
        cell = {"cutoff":cutoff}
        for name, rows, start, end in (("train",train,START,SPLIT),("validation",validation,SPLIT,END)):
            subset = [e for e in rows if cutoff is None or e["score"]>=cutoff]
            cell[name] = metrics(subset,len(rows))
            cell[name]["paired_clock_inference"] = block_sign_test(subset,start,end)
        result[str(percent)] = cell
    return result


def evaluate(buckets, validation):
    primary = buckets["100"]
    insufficiency, failures = [], []
    for name, lo, hi in (("train",START,SPLIT),("validation",SPLIT,END)):
        stats = primary[name]
        expected = (hi-lo)//(15*MINUTE)-(1 if name=="train" else 0)
        if stats["n"]/expected < .99 or stats["n"]<200 or stats["paired_clock_inference"]["informative_complete_weeks"]<20:
            insufficiency.append(name+":coverage_or_power")
        econ = stats["costs"]["24"]
        if (econ["mean_net_bps"] or 0)<=0: failures.append(name+":nonpositive_after_cost")
        if not econ["profit_factor_unbounded"] and (econ["profit_factor"] is None or econ["profit_factor"]<=1): failures.append(name+":profit_factor")
        if econ["tail_veto"] or (econ["winner_day_removed_mean_bps"] or 0)<=0: failures.append(name+":day_tail_or_winner_dependence")
        if any((econ["mean_net_bps"] or 0)<=v for k,v in econ["controls_mean_net_bps"].items() if k in ("clock","random") and v is not None):
            failures.append(name+":timing_placebo_not_beaten")
        if (econ["mean_net_bps"] or 0)<=(econ["price_baseline_per_opportunity_bps"] or 0): failures.append(name+":price_baseline_not_beaten")
        if stats["paired_clock_inference"]["bonferroni_p"] is None or stats["paired_clock_inference"]["bonferroni_p"]>.05:
            failures.append(name+":weak_adjusted_block_sign_evidence")
    if (primary["validation"]["costs"]["72"]["mean_net_bps"] or 0)<=0:
        failures.append("validation:nonpositive_stress")
    quarter_split = 1727740800000  # 2024-10-01T00:00Z
    quarters = {"Q3":metrics([e for e in validation if e["t"]<quarter_split],len(validation)),
                "Q4":metrics([e for e in validation if e["t"]>=quarter_split],len(validation))}
    for name, value in quarters.items():
        if (value["costs"]["24"]["mean_net_bps"] or 0)<=0: failures.append(name+":nonpositive_after_cost")
    decision = "INCONCLUSIVE_DATA_OR_POWER" if insufficiency else "REJECTED_STAGE1" if failures else "SURVIVOR_REQUIRES_CANONICAL_ADMISSION_AND_FRESH_EVIDENCE"
    return {"decision":decision,"inconclusive_reasons":insufficiency,"failed_gates":failures,"validation_quarters":quarters}


def screen(cache, output):
    rows, manifest = load_cache(cache)
    events, qa = make_events(rows)
    train, validation = [e for e in events if e["t"]<SPLIT], [e for e in events if e["t"]>=SPLIT]
    buckets = compare(train,validation)
    verdict = evaluate(buckets,validation)
    report = {"fingerprint":FINGERPRINT,"contracts":IDENTITIES,"manifest_sha256":digest(manifest),
        **verdict,"data_qa":qa,"rows":len(rows),"buckets":buckets,
        "authority":{"canonical_admission":False,"profitability":False,"causal":False,"protected_oos":False,"forward":False,"broker":False,"trading":False},
        "limitations":["Historical provider revisions/publication vintage are not independently certified; no canonical acquisition attestation.",
          "Trade-open proxies omit execution detail; fee/spread/slippage values are assumptions. No rebate, maker fill or funding model.",
          "Nested diagnostic buckets cannot rescue primary. No project-wide confirmatory budget is created.",
          "Weekly sign test assumes independent block signs; non-overlapping minutes do not establish independent observations.",
          "Calendar predictability cannot identify algorithmic intent, initiating cause, whales, news or macro liquidity."]}
    output.mkdir(parents=True,exist_ok=True)
    payload = json.dumps(events,separators=(",",":"),allow_nan=False).encode()
    packed = gzip.compress(payload,mtime=0)
    report["events_sha256"] = hashlib.sha256(payload).hexdigest()
    (output/"events.json.gz").write_bytes(packed)
    (output/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    (output/"result.json").write_text(json.dumps(report,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps({"decision":verdict["decision"],"rows":len(rows),"events":len(events),"failed_gates":verdict["failed_gates"],"inconclusive":verdict["inconclusive_reasons"]}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("acquire","screen"))
    parser.add_argument("--cache",type=Path,required=True)
    parser.add_argument("--output",type=Path)
    args = parser.parse_args()
    if args.command == "acquire":
        acquire(args.cache)
    else:
        if args.output is None:
            parser.error("screen requires --output")
        screen(args.cache,args.output)
