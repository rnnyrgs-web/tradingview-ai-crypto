import hmac
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Request

from config import *
from db import configured, fetch_actionable_after, fetch_latest_signal_id
from engine import run_scan
from evaluator import run_evaluation
from backtest import run_backtest, walk_forward
from market_data import build_universe
from dashboard import login_page, handle_login, dashboard_page, signal_detail_page

app=FastAPI(title="Crypto Signal Engine V3")

def verify_secret(secret:Optional[str],x_scan_secret:Optional[str]):
    supplied=x_scan_secret or secret or ""
    if not SCAN_SECRET or not hmac.compare_digest(supplied,SCAN_SECRET):
        raise HTTPException(status_code=401,detail="Unauthorized")

@app.get("/")
def root():
    return {
        "ok":True,
        "service":"Crypto Signal Engine V3",
        "version":STRATEGY_VERSION,
        "dashboard":"/dashboard",
        "endpoints":["/health","/scan","/evaluate","/backtest","/walkforward","/universe","/signals","/signals/cursor"]
    }

@app.get("/health")
def health():
    return {
        "ok":True,"version":STRATEGY_VERSION,"model":OPENAI_MODEL,
        "supabase_configured":configured(),
        "universe_size":UNIVERSE_SIZE,
        "deep_scan_size":DEEP_SCAN_SIZE,
        "horizons":list(HORIZONS.keys())
    }

@app.get("/dashboard/login")
def dashboard_login_get():
    return login_page()

@app.post("/dashboard/login")
async def dashboard_login_post(request:Request):
    return await handle_login(request)

@app.get("/dashboard")
def dashboard(request:Request,horizon:str="24h"):
    try:
        return dashboard_page(request,horizon)
    except Exception as e:
        raise HTTPException(status_code=500,detail="Dashboard unavailable") from e

@app.get("/dashboard/signal/{signal_id}")
def dashboard_signal(request:Request,signal_id:int):
    try:
        return signal_detail_page(request,signal_id)
    except Exception as e:
        raise HTTPException(status_code=500,detail="Signal visual unavailable") from e

@app.get("/universe")
def universe(secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    u=build_universe()
    return {"ok":True,"count":len(u),"top":u[:50]}

@app.get("/signals/cursor")
def signal_cursor(secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        return {"ok":True,"latest_id":fetch_latest_signal_id()}
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))

@app.get("/signals")
def signals(after_id:int=0,limit:int=20,secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        rows=fetch_actionable_after(after_id,limit)
        return {"ok":True,"count":len(rows),"signals":rows}
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))

@app.get("/scan")
def scan(secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        return run_scan()
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))

@app.get("/evaluate")
def evaluate(secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        return run_evaluation()
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))

@app.get("/backtest")
def backtest(symbol:str="BTC-USDT",bar:str="15m",bars:int=2500,
             secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        return run_backtest(symbol.upper(),bar,bars)
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))

@app.get("/walkforward")
def walkforward(symbol:str="BTC-USDT",bar:str="15m",bars:int=3000,
                secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        return walk_forward(symbol.upper(),bar,bars)
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e))
