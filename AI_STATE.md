# AI DEVELOPMENT STATE
Last updated: 2026-09-06

## PURPOSE
This is the authoritative continuation state for the crypto trading/signal software project.

When the user says "ok1" in a new ChatGPT conversation:
1. Read this file first.
2. Inspect the repository when necessary.
3. Continue from EXACT NEXT STEP.
4. Do not restart completed work.
5. Keep instructions short and one step at a time.
6. Never expose or request API keys, passwords, tokens, or secrets in chat.

## PROJECT
GitHub:
rnnyrgs-web/tradingview-ai-crypto

Render service:
tradingview-ai-crypto

Architecture:
GitHub -> Render -> Python/FastAPI signal engine -> Supabase

## CURRENT VERSION
V3 multi-horizon crypto signal engine.

V3 commit:
1e2e5df

Commit message:
Upgrade to V3 multi-horizon signal engine

V3 repository includes:
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
- tests/
- README_V3.md
- requirements.txt
- GitHub Actions workflow

## V3 GOALS
Broad crypto-market scanning.

Multi-horizon signals:
- intraday
- 24h
- 7d
- longer swing horizons

System should combine:
- quantitative algorithms
- technical features
- market regime
- derivatives data
- news/catalysts
- historical testing
- AI adversarial review
- objective outcome tracking

AI should review evidence, not simply invent trades.

NO TRADE / WAIT is a valid result.

Long-run capital survival and risk-adjusted profitability are more important than forcing trades.

## DATA / MARKET ENGINE
V2/V3 foundation uses OKX market data.

Broad dynamic USDT spot universe.

Features developed include:
- EMA 9
- EMA 20
- EMA 50
- RSI
- ATR
- volume z-score
- slope
- range position
- momentum
- market regime

Derivatives foundation includes:
- funding
- open interest where available

News foundation uses crypto RSS/news sources.

## SUPABASE
Supabase is configured server-side.

Project ref:
dxgksvzibucwuzmppoqy

Main table:
public.trading_signals

RLS is enabled.

Service-role database permissions were previously fixed.

Signals have successfully been written to Supabase.

Schema includes core signal information plus evaluation fields for multiple horizons.

IMPORTANT:
Verify that these columns exist before relying on 12h evaluation:
- price_12h
- return_12h

Never put the Supabase secret/service key in this file.

## AUTOMATION
GitHub Actions workflow exists for automated crypto scanning.

Previous working setup:
- /scan
- /evaluate

Scheduled approximately every 15 minutes.

Authentication uses X-Scan-Secret header.

Do not put SCAN_SECRET in URLs.

Old query-string usage exposed the prior secret in logs, so secret rotation is recommended.

## SECURITY
Repository is public.

Therefore:
- no secrets in source code
- secrets only in secure environment variables
- Supabase service key server-side only
- scan endpoint authenticated
- fail closed where appropriate

Future hardening should include:
- secret rotation
- dependency scanning
- code scanning
- pinned/tested dependencies
- rate limiting
- CI tests
- logging/monitoring
- backups
- least privilege
- staging/prod separation where useful

Never claim the system is completely hacker-proof.

## PREVIOUS WORKING STATE
Before V3 deployment, Render showed successful:

GET /scan -> 200
GET /evaluate -> 200
GET /health -> 200

Therefore the prior deployed engine was operational.

## CURRENT PROBLEM

V3 commit 1e2e5df was pushed successfully to GitHub.

Render automatically attempted to deploy:

"Upgrade to V3 multi-horizon signal engine"

That deployment FAILED.

Render reports:

"Exited with status 1 while running your code."

Traceback visibly reached:

File "/app/app.py", line 4, in <module>

Line 4 of app.py is:

from config import *

config.py top section was visually checked and looked syntactically normal.

requirements.txt currently contains:

fastapi>=0.115,<1
uvicorn[standard]>=0.30,<1
httpx>=0.27,<1
openai>=1.40,<2

The actual final Python exception was not visible in the Render deployment UI.

Do NOT randomly modify dependencies without identifying the failure.

## CURRENT DEBUGGING PATH

We were about to inspect V3 module imports, beginning with:

market_data.py

Goal:
Find whether a V3 module imports a dependency missing from requirements.txt or otherwise causes startup import failure.

Also inspect:
- engine.py
- evaluator.py
- features.py
- news_engine.py
- safety.py
- db.py
- backtest.py

as necessary.

## AFTER V3 IS STABLE

Next major development phase:

SERIOUS HISTORICAL RESEARCH / BACKTESTING.

Requirements include:
- many liquid crypto symbols
- multiple timeframes
- historical data caching
- trend strategies
- breakout strategies
- momentum strategies
- mean reversion
- volatility expansion
- relative strength
- regime-conditioned strategies
- realistic fees
- spread/slippage
- no lookahead
- next-bar execution
- rolling walk-forward testing
- untouched out-of-sample testing
- parameter stability testing
- bootstrap / Monte Carlo robustness
- minimum sample sizes
- portfolio simulation
- drawdown analysis
- expectancy
- profit factor
- regime analysis

Only strategies with convincing out-of-sample evidence should influence live signal weighting.

## IMPORTANT DEVELOPMENT PRINCIPLE
Storing outcomes does NOT mean the system automatically learns.

Actual learning requires validated updating of models/weights based on sufficient out-of-sample evidence.

More data/features are not automatically better.

Every major feature should demonstrate incremental out-of-sample value.

## USER WORKFLOW
User wants:
- extremely short instructions
- one next action at a time
- screenshot-driven development
- minimal scrolling
- no repeating completed steps

Ctrl + Space currently:
takes a reduced-size screenshot and automatically sends it to the active ChatGPT conversation.

Do NOT modify the working Ctrl+Space AutoHotkey screenshot script unless necessary.

## EXACT NEXT STEP

Inspect market_data.py imports/code in GitHub to continue diagnosing why V3 exits during Render startup.

Once the actual startup error is identified:
1. make the smallest correct fix
2. commit to GitHub
3. allow Render auto-deploy
4. verify /health
5. verify /scan
6. verify /evaluate
7. verify Supabase writes
8. then continue V3 development/backtesting.
