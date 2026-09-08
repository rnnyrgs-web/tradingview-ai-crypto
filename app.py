import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, Request

from config import *
from db import configured, fetch_actionable_after, fetch_latest_signal_id, fetch_resolved_predictions
from engine import run_scan
from evaluator import run_evaluation
from backtest import run_backtest, walk_forward
from market_data import build_universe
from dashboard import login_page, handle_login, dashboard_page, signal_detail_page
from tradingview_overlay import pine_overlay_page
from operational_monitor import health_snapshot, record_error
from calibration import calibration_summary
from continuous_ai_agent import continuous_ai_loop, status_snapshot as continuous_ai_status


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(continuous_ai_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app=FastAPI(title="Crypto Signal Engine V3", lifespan=lifespan)
log = logging.getLogger(__name__)


def internal_error(component, exc, public_message):
    record_error(component, exc)
    log.exception("%s failed", component)
    raise HTTPException(status_code=500, detail=public_message) from exc

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
        "endpoints":["/health","/scan","/evaluate","/calibration","/backtest","/walkforward","/universe","/signals","/signals/cursor"]
    }

@app.get("/health")
def health():
    return {
        "ok":True,"version":STRATEGY_VERSION,"model":OPENAI_MODEL,
        "supabase_configured":configured(),
        "universe_size":UNIVERSE_SIZE,
        "deep_scan_size":DEEP_SCAN_SIZE,
        "horizons":list(HORIZONS.keys()),
        "operations":health_snapshot(),
        "continuous_ai":continuous_ai_status(),
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
        internal_error("dashboard", e, "Dashboard unavailable")

@app.get("/dashboard/signal/{signal_id}")
def dashboard_signal(request:Request,signal_id:int):
    try:
        return signal_detail_page(request,signal_id)
    except Exception as e:
        internal_error("dashboard_signal", e, "Signal visual unavailable")

@app.get("/dashboard/signal/{signal_id}/tradingview-overlay")
def dashboard_signal_tradingview_overlay(request:Request,signal_id:int):
    try:
        return pine_overlay_page(request,signal_id)
    except Exception as e:
        internal_error("dashboard_signal_tradingview_overlay", e, "TradingView overlay unavailable")

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
        internal_error("signal_cursor", e, "Signal cursor unavailable")

@app.get("/signals")
def signals(after_id:int=0,limit:int=20,secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        rows=fetch_actionable_after(after_id,limit)
        return {"ok":True,"count":len(rows),"signals":rows}
    except Exception as e:
        internal_error("signals", e, "Signal feed unavailable")

@app.get("/scan")
def scan(secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        return run_scan()
    except Exception as e:
        internal_error("scan", e, "Production scan failed")

@app.get("/evaluate")
def evaluate(secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        return run_evaluation()
    except Exception as e:
        internal_error("evaluation", e, "Signal evaluation failed")

@app.get("/calibration")
def calibration(secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        return calibration_summary(fetch_resolved_predictions())
    except Exception as e:
        internal_error("calibration", e, "Calibration unavailable")

@app.get("/backtest")
def backtest(symbol:str="BTC-USDT",bar:str="15m",bars:int=2500,
             secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        return run_backtest(symbol.upper(),bar,bars)
    except Exception as e:
        internal_error("backtest", e, "Backtest failed")

@app.get("/walkforward")
def walkforward(symbol:str="BTC-USDT",bar:str="15m",bars:int=3000,
                secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    try:
        return walk_forward(symbol.upper(),bar,bars)
    except Exception as e:
        internal_error("walkforward", e, "Walk-forward validation failed")
