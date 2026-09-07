# AI DEVELOPMENT STATE
Last updated: 2026-09-07

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`.

When the user says `ok1` in a new chat:
1. Read this file first.
2. Verify relevant repository/deploy/database state as needed.
3. Continue from EXACT NEXT STEP.
4. Do not restart completed work.
5. Keep instructions short and one step at a time.
6. Never expose/request API keys, passwords, tokens, or secret values.

## ARCHITECTURE
GitHub -> Render -> Python/FastAPI V3 signal engine -> Supabase.

Research/backtesting path now also includes:
OKX public historical APIs -> GitHub Actions cloud runner -> backtest artifact/results.

Goal: heavy research runs in cloud, not on the user's local PC. Local CPU/disk are not the limiting factor. Limits are instead exchange history depth, API rate limits, cloud-runner limits/cost, and data quality.

## CURRENT VERSION
V3 multi-horizon crypto signal engine.

Core V3 commit: `1e2e5df`.

V3 modules include:
- app.py
- backtest.py
- config.py
- db.py
- engine.py
- evaluator.py
- features.py
- market_data.py
- news_engine.py
- safety.py
- utils.py
- research_runner.py
- tests/
- README_V3.md
- GitHub Actions workflows

## PRODUCTION STATUS
V3 is LIVE on Render.

Docker startup bug was fixed by commit:
`b9c499f3358d22a8d722ebff61d1649879c270f9`
`Fix Docker image to include V3 modules`

Root cause was Dockerfile copying only `app.py`; V3 sibling modules such as `config.py` were missing from the image.

Fix:
`COPY *.py ./`

Verified after fix:
- Render deploy status LIVE
- `/scan` -> 200
- `/evaluate` -> 200
- GitHub Actions scan/evaluate rerun -> success
- Supabase received V3.0 signals
- evaluator updated records successfully
- `price_12h` exists
- `return_12h` exists

## CLOUD BACKTESTING — COMPLETED FOUNDATION
User explicitly wants online/cloud backtesting instead of relying on local CPU strength.

Implemented:

### Deep online history
Commit:
`b6ace184c8592366466c8b8fd761765d22cee590`
`Enable deep paginated cloud history fetches`

`market_data.get_history()` now:
- fetches historical candles directly from OKX public API
- paginates on demand
- supports up to 50,000 requested candles per call by current safety guardrail
- does not require local historical storage
- uses rate-limit-friendly pacing

The 50,000 cap is a safety guardrail, not an architectural limit. Raise only when justified.

### Backtest performance improvements
Commit:
`fa776367b8c1a8be827a4a71c85b3ee0fac77aa7`
`Optimize cloud backtests for deeper history`

Improvements:
- rolling ~140-candle feature context avoids O(n^2) slicing over very deep histories
- max drawdown metric added
- realistic round-trip cost remains included
- conservative same-candle stop-first ambiguity remains
- walk-forward train/validation/holdout remains

### Cloud runner
Commit:
`8ff79cf4820c06fb8ba7682f169178e5b407767c`
`Add cloud research backtest runner`

Added `research_runner.py`.
It accepts environment-configured:
- symbols
- timeframes
- bars
- threshold

It runs standard backtest + walk-forward tests and writes JSON results.

### GitHub Actions cloud research workflow
Commit:
`0b36932096c24093e30a3c45e38a421d1cf7813a`
`Add GitHub Actions cloud backtesting workflow`

Added `.github/workflows/cloud_research.yml`.

It:
- runs on GitHub-hosted cloud compute
- downloads market history online from OKX
- does not use the user's local CPU
- supports manual workflow inputs
- uploads `cloud-backtest-results` artifact
- keeps result artifact 30 days
- has a 30-minute safety timeout

First automatic cloud research run:
- Workflow run ID: `34073785214`
- status: SUCCESS
- artifact ID: `10001378353`
- tested BTC, ETH, SOL
- tested 15m and 1H
- requested 3000 candles per test
- all 6 research jobs completed

Important first-run findings:
- BTC 15m: negative
- BTC 1H: positive in basic test and positive holdout
- ETH 15m: negative
- ETH 1H: basic test slightly negative; holdout positive but sample is small
- SOL 15m: negative
- SOL 1H: positive basic test and positive holdout

These are NOT yet sufficient evidence for live weighting. Sample sizes and time coverage are still too small; this first run mainly proves the cloud research pipeline works.

Latest Render deploy after cloud-backtest changes is LIVE.

## DATA / SIGNAL PRINCIPLES
System combines:
- quantitative algorithms
- technical features
- market regime
- derivatives data
- news/catalysts
- historical testing
- AI adversarial review
- objective outcome tracking

AI reviews evidence; it should not invent trades.
NO TRADE / WAIT is valid.
Long-run capital survival and risk-adjusted profitability are more important than forced activity.

## SUPABASE
Project ref: `dxgksvzibucwuzmppoqy`
Main table: `public.trading_signals`
RLS enabled.
Service-role permissions previously fixed.
Never put Supabase secret/service key in this file.

## AUTOMATION
Existing GitHub Actions scan workflow calls:
- `/scan`
- `/evaluate`
approximately every 15 minutes.

Authentication uses `X-Scan-Secret` header.
Never put SCAN_SECRET in URLs.
Prior query-string secret exposure means rotation is still recommended.

## SECURITY
Repository is public.

Rules:
- no secrets in source code
- secrets only in secure environment variables / secret stores
- Supabase service key server-side only
- authenticated sensitive endpoints
- least privilege
- fail closed where appropriate

Future hardening:
- rotate exposed old scan secret
- dependency scanning
- code scanning
- pin/test dependencies
- rate limiting
- better monitoring/alerts
- backups
- staging/prod separation where useful

Never claim hacker-proof security.

## SERIOUS BACKTESTING ROADMAP
Next phase is not merely running more of the same test. Build a robust research engine that can search and reject strategies across larger datasets.

Required next capabilities:
- many liquid crypto symbols
- multiple timeframes
- deeper historical coverage
- cloud-parallel job matrix/sharding
- trend strategies
- breakout strategies
- momentum strategies
- mean reversion
- volatility expansion
- relative strength
- regime-conditioned strategies
- realistic fees/spread/slippage
- no lookahead
- next-bar execution
- rolling walk-forward testing
- untouched out-of-sample testing
- parameter stability testing
- bootstrap / Monte Carlo robustness
- minimum sample thresholds
- portfolio simulation
- expectancy/profit factor/drawdown
- per-regime/per-symbol/per-month analysis
- reject overfit strategies

Only strategies with convincing out-of-sample evidence should influence live signal weighting.

Storing outcomes is NOT automatic learning. Actual learning requires validated model/weight updates based on sufficient out-of-sample evidence.

## EXACT NEXT STEP
Build V4 cloud research matrix/sharding so GitHub Actions can test many symbols, strategy families, timeframes, and historical depths in parallel without depending on local hardware. Persist compact research summaries/results for longitudinal comparison, while keeping raw candle storage optional/on-demand to control cost.
