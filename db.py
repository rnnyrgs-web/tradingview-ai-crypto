import httpx
from datetime import datetime, timedelta, timezone

from config import SUPABASE_URL, SUPABASE_SECRET_KEY
from utils import iso, now_utc

http = httpx.Client(timeout=25.0, follow_redirects=True)

def headers(prefer=None):
    h={
        "apikey":SUPABASE_SECRET_KEY,
        "Authorization":f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type":"application/json",
    }
    if prefer:
        h["Prefer"]=prefer
    return h

def configured():
    return bool(SUPABASE_URL and SUPABASE_SECRET_KEY)

def insert_signal(row):
    if not configured():
        return
    r=http.post(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers("return=minimal"),json=row)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase insert failed: {r.status_code} {r.text}")

def fetch_recent(hours=800, limit=1000):
    if not configured():
        return []
    cutoff=iso(now_utc()-timedelta(hours=hours))
    params={"select":"*","created_at":f"gte.{cutoff}","order":"created_at.asc","limit":str(limit)}
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase select failed: {r.status_code} {r.text}")
    return r.json()

def fetch_latest_signal_id():
    if not configured():
        return 0
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params={"select":"id","order":"id.desc","limit":"1"})
    if r.status_code>=300:
        raise RuntimeError(f"Supabase cursor fetch failed: {r.status_code} {r.text}")
    rows=r.json()
    return int(rows[0]["id"]) if rows else 0

def fetch_actionable_after(after_id=0, limit=20):
    if not configured():
        return []
    params={
        "select":"id,created_at,symbol,timeframe,direction,action,entry_price,stop_loss,target_1,target_2,risk_reward,evidence_score,market_regime,status,strategy_version",
        "id":f"gt.{max(0,int(after_id))}","action":"eq.TRADE","order":"id.asc","limit":str(max(1,min(int(limit),100))),
    }
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase signal feed failed: {r.status_code} {r.text}")
    return r.json()

def replace_opportunities(scan_id, horizon, rows):
    if not configured():
        return
    if horizon not in {"24h","7d"}:
        raise ValueError("invalid opportunity horizon")
    if not rows:
        return
    payload=[]
    for row in rows[:20]:
        payload.append({k:v for k,v in row.items() if k in {
            "scan_id","horizon","rank","symbol","direction","action","entry_price","entry_low","entry_high",
            "stop_loss","target_1","target_2","risk_reward","quant_score","evidence_score","market_regime",
            "reasoning","strategy_version","calibration"
        }})
    r=http.post(f"{SUPABASE_URL}/rest/v1/crypto_opportunities",headers=headers("return=minimal"),json=payload)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase opportunity insert failed: {r.status_code} {r.text}")

def insert_prediction_ledger(rows):
    if not configured() or not rows:
        return
    payload=[{k:v for k,v in row.items() if k in {
        "scan_id","symbol","horizon","direction","entry_price","score",
        "market_regime","strategy_identity","action_at_forecast","due_at","calibration"
    }} for row in rows]
    r=http.post(f"{SUPABASE_URL}/rest/v1/prediction_ledger",
        headers=headers("resolution=ignore-duplicates,return=minimal"),json=payload)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase prediction ledger insert failed: {r.status_code} {r.text}")

def fetch_due_predictions(limit=500):
    if not configured():
        return []
    params={"select":"*","resolved_at":"is.null","due_at":f"lte.{iso(now_utc())}",
            "order":"due_at.asc","limit":str(max(1,min(int(limit),1000)))}
    r=http.get(f"{SUPABASE_URL}/rest/v1/prediction_ledger",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase due prediction fetch failed: {r.status_code} {r.text}")
    return r.json()


def _iso_to_epoch_ms(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.astimezone(timezone.utc).timestamp() * 1000)


def _expose_preforecast_market_fields(row):
    """Expose prospective ledger provenance without fabricating historical fields."""
    if not isinstance(row, dict):
        return row
    calibration = row.get("calibration")
    if not isinstance(calibration, dict):
        return row
    context = calibration.get("preforecast_market_context")
    if not isinstance(context, dict):
        return row
    market = context.get("market_consensus")
    if not isinstance(market, dict) or market.get("recorded") is not True:
        return row

    captured_ms = _iso_to_epoch_ms(context.get("captured_at"))
    observations = market.get("accepted_observations") or []
    observed_ms = []
    for observation in observations:
        if not isinstance(observation, dict):
            continue
        try:
            value = int(observation.get("observed_ms") or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            observed_ms.append(value)
    timestamp_safe = bool(captured_ms and observed_ms and max(observed_ms) <= captured_ms)

    row["market_consensus_reliable"] = bool(market.get("reliable_at_forecast") is True and timestamp_safe)
    row["market_consensus_timestamp_safe"] = timestamp_safe
    row["market_consensus_source_count"] = int(market.get("independent_source_count") or 0)
    row["market_consensus_required_source_count"] = int(market.get("required_source_count") or 0)
    row["market_consensus_price_range_bps"] = market.get("price_range_bps")
    row["market_consensus_max_quote_age_seconds"] = market.get("max_quote_age_seconds")
    row["market_consensus_accepted_exchange_names"] = list(market.get("accepted_exchange_names") or [])
    row["preforecast_market_context_captured_at"] = context.get("captured_at")
    return row


def fetch_resolved_predictions(limit=5000):
    if not configured():
        return []
    # Production prediction_ledger has no created_at column. resolved_at/due_at
    # provide the chronology required by calibration and forward-proof logic.
    params={
        "select":"due_at,resolved_at,horizon,score,market_regime,correct,directional_return_pct,strategy_identity,action_at_forecast,calibration",
        "resolved_at":"not.is.null","order":"resolved_at.desc","limit":str(max(1,min(int(limit),10000)))
    }
    r=http.get(f"{SUPABASE_URL}/rest/v1/prediction_ledger",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase resolved prediction fetch failed: {r.status_code} {r.text}")
    return [_expose_preforecast_market_fields(row) for row in r.json()]

def fetch_shadow_predictions(limit=10000):
    """Read immutable resolved forward forecasts for shadow-readiness analysis."""
    if not configured():
        return []
    params={
        "select":"id,due_at,resolved_at,scan_id,symbol,horizon,direction,entry_price,score,market_regime,strategy_identity,action_at_forecast,directional_return_pct,correct,calibration",
        "resolved_at":"not.is.null",
        "order":"resolved_at.asc",
        "limit":str(max(1,min(int(limit),10000))),
    }
    r=http.get(f"{SUPABASE_URL}/rest/v1/prediction_ledger",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase shadow prediction fetch failed: {r.status_code} {r.text}")
    return [_expose_preforecast_market_fields(row) for row in r.json()]

def patch_prediction(prediction_id, fields):
    if not configured() or not fields:
        return
    allowed={"outcome_price","directional_return_pct","correct","resolved_at"}
    payload={k:v for k,v in fields.items() if k in allowed}
    r=http.patch(f"{SUPABASE_URL}/rest/v1/prediction_ledger",headers=headers("return=minimal"),
        params={"id":f"eq.{prediction_id}","resolved_at":"is.null"},json=payload)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase prediction update failed: {r.status_code} {r.text}")

def fetch_ranked_opportunities(horizon="24h", hours=None, limit=20):
    if not configured():
        return []
    if horizon not in {"24h","7d"}:
        raise ValueError("horizon must be 24h or 7d")
    lookback=int(hours if hours is not None else (6 if horizon=="24h" else 12))
    cutoff=iso(now_utc()-timedelta(hours=max(1,lookback)))
    latest_resp=http.get(
        f"{SUPABASE_URL}/rest/v1/crypto_opportunities",headers=headers(),
        params={"select":"scan_id,generated_at","horizon":f"eq.{horizon}","generated_at":f"gte.{cutoff}","order":"generated_at.desc","limit":"1"}
    )
    if latest_resp.status_code>=300:
        raise RuntimeError(f"Supabase latest opportunity fetch failed: {latest_resp.status_code} {latest_resp.text}")
    latest=latest_resp.json()
    if not latest:
        return []
    scan_id=latest[0]["scan_id"]
    r=http.get(
        f"{SUPABASE_URL}/rest/v1/crypto_opportunities",headers=headers(),
        params={"select":"*","scan_id":f"eq.{scan_id}","horizon":f"eq.{horizon}","order":"rank.asc","limit":str(max(1,min(int(limit),20)))}
    )
    if r.status_code>=300:
        raise RuntimeError(f"Supabase opportunities fetch failed: {r.status_code} {r.text}")
    return r.json()

def fetch_signal_by_id(signal_id):
    if not configured():
        return None
    r=http.get(f"{SUPABASE_URL}/rest/v1/crypto_opportunities",headers=headers(),params={"select":"*","id":f"eq.{int(signal_id)}","limit":"1"})
    if r.status_code<300 and r.json():
        row=r.json()[0]
        row["timeframe"]=row.get("horizon")
        return row
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params={"select":"*","id":f"eq.{int(signal_id)}","limit":"1"})
    if r.status_code>=300:
        raise RuntimeError(f"Supabase signal fetch failed: {r.status_code} {r.text}")
    rows=r.json()
    return rows[0] if rows else None

def patch_signal(signal_id, fields):
    if not fields:
        return
    r=http.patch(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers("return=minimal"),params={"id":f"eq.{signal_id}"},json=fields)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase update failed: {r.status_code} {r.text}")
