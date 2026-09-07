import os

STRATEGY_VERSION = "v3.0"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
SCAN_SECRET = os.getenv("SCAN_SECRET", "")
DASHBOARD_SECRET = os.getenv("DASHBOARD_SECRET", "")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

OKX_BASE = "https://www.okx.com"
BINANCE_SPOT_BASE = "https://api.binance.com"
BINANCE_FUTURES_BASE = "https://fapi.binance.com"

PRICE_CONSENSUS_MIN_SOURCES = int(os.getenv("PRICE_CONSENSUS_MIN_SOURCES", "2"))
PRICE_CONSENSUS_MAX_DEVIATION_BPS = float(os.getenv("PRICE_CONSENSUS_MAX_DEVIATION_BPS", "50"))
MARKET_DATA_MAX_AGE_SECONDS = int(os.getenv("MARKET_DATA_MAX_AGE_SECONDS", "120"))
ORDER_BOOK_DEPTH = int(os.getenv("ORDER_BOOK_DEPTH", "50"))
ORDER_BOOK_MIN_LEVELS = int(os.getenv("ORDER_BOOK_MIN_LEVELS", "10"))
ORDER_BOOK_MAX_SPREAD_BPS = float(os.getenv("ORDER_BOOK_MAX_SPREAD_BPS", "50"))

UNIVERSE_SIZE = int(os.getenv("UNIVERSE_SIZE", "180"))
DEEP_SCAN_SIZE = int(os.getenv("DEEP_SCAN_SIZE", "40"))
AI_CANDIDATES = int(os.getenv("AI_CANDIDATES", "12"))
MAX_SAVED_SIGNALS = int(os.getenv("MAX_SAVED_SIGNALS", "4"))

MIN_QUOTE_VOLUME = float(os.getenv("MIN_QUOTE_VOLUME", "1000000"))
MAX_SPREAD_BPS = float(os.getenv("MAX_SPREAD_BPS", "40"))
MIN_EVIDENCE_SCORE = float(os.getenv("MIN_EVIDENCE_SCORE", "74"))
MIN_RR = float(os.getenv("MIN_RR", "1.8"))

BACKTEST_COST_BPS = float(os.getenv("BACKTEST_COST_BPS", "12"))
STALE_CANDLE_MINUTES = int(os.getenv("STALE_CANDLE_MINUTES", "30"))

STABLE_BASES = {
    "USDC","USDT","DAI","FDUSD","TUSD","USDE","PYUSD",
    "EUR","EURT","USD","USDK","BUSD"
}

HORIZONS = {
    "intraday": {"bars": ["15m", "1H"], "hold_hours": 4},
    "24h": {"bars": ["1H", "4H"], "hold_hours": 24},
    "7d": {"bars": ["4H", "1D"], "hold_hours": 24*7},
    "30d": {"bars": ["1D"], "hold_hours": 24*30},
}
