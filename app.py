import hmac
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request

from backtest import run_backtest, walk_forward
from calibration import calibration_summary
from config import *
from dashboard import handle_login, login_page
from db import configured, fetch_resolved_predictions, fetch_shadow_predictions
from evaluator import run_prediction_drain
from market_data import build_universe
from money_intelligence_dashboard import money_dashboard_page
from operational_monitor import health_snapshot, record_error
from production_validation import validate_live_strategy
from research_observability import snapshot as research_observability_snapshot
from selective_precision_observability import resolved_selective_precision_snapshot
from shadow_readiness import assess_shadow_readiness, canary_review_decision
from strategy_mission_dashboard import mission_control_page


LEGACY_SIGNAL_RETIREMENT_REASON = (
    "Legacy signal/dashboard production is retired. The service now prioritizes "
    "strategy discovery and 90-day 2x+ research."
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    # The web process no longer hosts paid AI polling, legacy signal scans, or the
    # old paper-trading loop. Scheduled research/Work/GitHub workers own background
    # execution, keeping this service small and preventing hidden recurring spend.
    yield


app = FastAPI(title="Trading Research Engine", lifespan=lifespan)
log = logging.getLogger(__name__)


def internal_error(component, exc, public_message):
    record_error(component, exc)
    log.exception("%s failed", component)
    raise HTTPException(status_code=500, detail=public_message) from exc


def verify_secret(secret: Optional[str], x_scan_secret: Optional[str]):
    supplied = x_scan_secret or secret or ""
    if not SCAN_SECRET or not hmac.compare_digest(supplied, SCAN_SECRET):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _legacy_retired():
    raise HTTPException(status_code=410, detail=LEGACY_SIGNAL_RETIREMENT_REASON)


@app.get("/")
def root():
    return {
        "ok": True,
        "service": "Trading Research Engine",
        "version": STRATEGY_VERSION,
        "mission_control": "/dashboard",
        "money_intelligence": "/dashboard/money",
        "legacy_signal_pipeline": "RETIRED",
        "endpoints": [
            "/health",
            "/research-observability",
            "/selective-precision",
            "/research/resolve-pending",
            "/calibration",
            "/shadow-readiness",
            "/backtest",
            "/walkforward",
            "/universe",
        ],
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "version": STRATEGY_VERSION,
        "model": OPENAI_MODEL,
        "supabase_configured": configured(),
        "universe_size": UNIVERSE_SIZE,
        "deep_scan_size": DEEP_SCAN_SIZE,
        "horizons": list(HORIZONS.keys()),
        "operations": health_snapshot(),
        "legacy_signal_pipeline": "RETIRED",
        "background_execution": "GITHUB_AND_SCHEDULED_WORK",
    }


@app.get("/research-observability")
def research_observability(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    try:
        return {"ok": True, **research_observability_snapshot()}
    except Exception as e:
        internal_error("research_observability", e, "Research observability unavailable")


@app.post("/research/profitability-learning/acceptance")
def profitability_learning_runtime_acceptance(
    x_scan_secret: Optional[str] = Header(default=None),
):
    """Replay only the repository-sealed rejected pre-OOS acceptance artifact."""
    verify_secret(None, x_scan_secret)
    try:
        from profitability_learning.acceptance import run_rejected_leadlag_acceptance

        return run_rejected_leadlag_acceptance()
    except Exception as e:
        internal_error(
            "profitability_learning_runtime_acceptance",
            e,
            "Profitability Learning runtime acceptance failed",
        )


@app.get("/selective-precision")
def selective_precision_observability(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    try:
        return resolved_selective_precision_snapshot()
    except Exception as e:
        internal_error("selective_precision_observability", e, "Selective precision research unavailable")


@app.get("/research/resolve-pending")
def resolve_pending_predictions(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    """Drain already-created immutable forecasts without generating new signals."""
    verify_secret(secret, x_scan_secret)
    try:
        return run_prediction_drain()
    except Exception as e:
        internal_error("prediction_drain", e, "Pending prediction resolution failed")


@app.get("/dashboard/login")
def dashboard_login_get():
    return login_page()


@app.post("/dashboard/login")
async def dashboard_login_post(request: Request):
    return await handle_login(request)


@app.get("/dashboard")
def dashboard(request: Request):
    try:
        return mission_control_page(request)
    except Exception as e:
        internal_error("dashboard_mission_control", e, "Mission Control unavailable")


@app.get("/dashboard/money")
def dashboard_money(request: Request):
    try:
        return money_dashboard_page(request)
    except Exception as e:
        internal_error("dashboard_money", e, "Money Intelligence dashboard unavailable")


@app.get("/dashboard/system")
def dashboard_system():
    return _legacy_retired()


@app.get("/dashboard/signals")
def dashboard_signals():
    return _legacy_retired()


@app.get("/dashboard/paper")
def dashboard_paper():
    return _legacy_retired()


@app.get("/dashboard/paper/audit")
def dashboard_paper_audit():
    return _legacy_retired()


@app.get("/dashboard/signal/{signal_id}")
def dashboard_signal(signal_id: int):
    del signal_id
    return _legacy_retired()


@app.get("/dashboard/signal/{signal_id}/chart-data")
def dashboard_signal_chart_data(signal_id: int):
    del signal_id
    return _legacy_retired()


@app.get("/signals/cursor")
def signal_cursor(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    return _legacy_retired()


@app.get("/signals")
def signals(
    after_id: int = 0,
    limit: int = 20,
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    del after_id, limit
    verify_secret(secret, x_scan_secret)
    return _legacy_retired()


@app.get("/scan")
def scan(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    return _legacy_retired()


@app.get("/evaluate")
def evaluate(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    return _legacy_retired()


@app.get("/paper")
def paper(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    return _legacy_retired()


@app.get("/paper/run")
def paper_run(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    return _legacy_retired()


@app.get("/universe")
def universe(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    u = build_universe()
    return {"ok": True, "count": len(u), "top": u[:50]}


@app.get("/calibration")
def calibration(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    try:
        return calibration_summary(fetch_resolved_predictions())
    except Exception as e:
        internal_error("calibration", e, "Calibration unavailable")


@app.get("/shadow-readiness")
def shadow_readiness(
    symbol: str = "BTC-USDT",
    horizon: str = "24h",
    strategy_family: str = "",
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    try:
        validation = validate_live_strategy(symbol.upper(), horizon, strategy_family)
        assessment = assess_shadow_readiness(
            fetch_shadow_predictions(),
            target_identity=validation.identity,
            horizon=horizon,
        )
        return {
            "ok": True,
            "symbol": symbol.upper(),
            "horizon": horizon,
            "strategy_family": strategy_family,
            "live_validation": {
                "approved": validation.approved,
                "status": validation.status,
                "reason": validation.reason,
                "identity": validation.identity,
            },
            "shadow": assessment,
            "canary_review": canary_review_decision(validation, assessment),
        }
    except Exception as e:
        internal_error("shadow_readiness", e, "Shadow readiness unavailable")


@app.get("/backtest")
def backtest(
    symbol: str = "BTC-USDT",
    bar: str = "15m",
    bars: int = 2500,
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    try:
        return run_backtest(symbol.upper(), bar, bars)
    except Exception as e:
        internal_error("backtest", e, "Backtest failed")


@app.get("/walkforward")
def walkforward(
    symbol: str = "BTC-USDT",
    bar: str = "15m",
    bars: int = 3000,
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    try:
        return walk_forward(symbol.upper(), bar, bars)
    except Exception as e:
        internal_error("walkforward", e, "Walk-forward validation failed")
