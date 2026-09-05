# Crypto Signal Engine V3

V3 adds:
- broad liquid-crypto universe scanning
- four separate horizons: intraday, 24h, 7d, 30d
- multi-timeframe quantitative scoring
- funding/open-interest context
- public crypto-news context
- AI adversarial review
- strict fail-closed market/risk invariants
- signal logging and evaluation
- research backtest endpoint
- chronological walk-forward endpoint
- GitHub regression/security checks

## Existing Render environment variables
Keep:
- OPENAI_API_KEY
- OPENAI_MODEL
- SCAN_SECRET
- SUPABASE_URL
- SUPABASE_SECRET_KEY

Optional:
- UNIVERSE_SIZE=180
- DEEP_SCAN_SIZE=40
- AI_CANDIDATES=12
- MAX_SAVED_SIGNALS=4
- MIN_EVIDENCE_SCORE=74
- BACKTEST_COST_BPS=12

## Endpoints
- /health
- /scan
- /evaluate
- /universe
- /backtest?symbol=BTC-USDT&bar=15m
- /walkforward?symbol=BTC-USDT&bar=15m

All endpoints except /health and / require X-Scan-Secret.

## Important
This is still research software, not guaranteed profitable software.
The walk-forward and live-forward results should determine whether a signal family is trusted.
