"""Fail-closed cross-engine trade/equity reconciliation."""
from __future__ import annotations

REQUIRED_METRICS=("trades","avg_trade_pct","max_drawdown_pct","return_pct","win_rate","ending_equity")

def _near(a,b,tol): return abs(float(a)-float(b)) <= tol

def reconcile(engine_results, required=("vectorbt","nautilus","lean"), price_tolerance=1e-8, pnl_tolerance=1e-6, metric_tolerance=1e-6):
    missing=[n for n in required if n not in engine_results]; invalid=[]; ids=set()
    for n in required:
        r=engine_results.get(n)
        if not isinstance(r,dict) or r.get("ok") is not True: invalid.append(n); continue
        cid=str(r.get("contract_fingerprint") or "")
        if not cid or any(k not in (r.get("metrics") or {}) for k in REQUIRED_METRICS) or not isinstance(r.get("trades"),list): invalid.append(n); continue
        ids.add(cid)
    mismatches=[]
    if not missing and not invalid and len(ids)==1:
        base=engine_results[required[0]]
        for n in required[1:]:
            other=engine_results[n]
            if len(base["trades"])!=len(other["trades"]): mismatches.append(f"{n}:trade_count"); continue
            for i,(a,b) in enumerate(zip(base["trades"],other["trades"])):
                for k in ("direction","entry_ts","exit_ts"):
                    if a[k]!=b[k]: mismatches.append(f"{n}:trade[{i}].{k}")
                for k in ("entry_price","exit_price","size","fees","pnl"):
                    tol=pnl_tolerance if k in ("fees","pnl") else price_tolerance
                    if not _near(a[k],b[k],tol): mismatches.append(f"{n}:trade[{i}].{k}")
            for k in REQUIRED_METRICS:
                if not _near(base["metrics"][k],other["metrics"][k],metric_tolerance): mismatches.append(f"{n}:metric.{k}")
    ok=not missing and not invalid and len(ids)==1 and not mismatches
    return {"ok":ok,"research_only":True,"trade_authority":False,"promotion_authority":False,
      "missing_engines":missing,"invalid_engines":invalid,"same_contract":len(ids)==1 and bool(ids),
      "mismatches":mismatches,"status":"COMPARABLE_RESEARCH_EVIDENCE" if ok else "WAIT_RESEARCH_ONLY",
      "note":"Agreement is corroboration only; untouched-OOS and genuine forward gates still apply."}
