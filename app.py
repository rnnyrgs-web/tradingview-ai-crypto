from typing import Optional
from fastapi import FastAPI, HTTPException, Header

from config import *
from db import configured
from engine import run_scan
from evaluator import run_evaluation
from backtest import run_backtest, walk_forward
from market_data import build_universe

app=FastAPI(title="Crypto Signal Engine V3")

def verify_secret(secret:Optional[str],x_scan_secret:Optional[str]):
    supplied=x_scan_secret or secret or ""
    if not SCAN_SECRET or supplied!=SCAN_SECRET:
        raise HTTPException(status_code=401,detail="Unauthorized")

@app.get("/")
def root():
    return {
        "ok":True,
        "service":"Crypto Signal Engine V3",
        "version":STRATEGY_VERSION,
        "endpoints":["/health","/scan","/evaluate","/backtest","/walkforward","/universe"]
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

@app.get("/universe")
def universe(secret:Optional[str]=None,x_scan_secret:Optional[str]=Header(default=None)):
    verify_secret(secret,x_scan_secret)
    u=build_universe()
    return {"ok":True,"count":len(u),"top":u[:50]}

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
