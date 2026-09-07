# AI DEVELOPMENT STATE
Last updated: 2026-09-07

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this first in every software-development conversation. Never store secrets here.

## ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase.
Research: OKX public historical APIs -> GitHub Actions cloud runners -> research artifacts/results.
Desktop alert path: Render authenticated signal feed -> Windows notifier -> alarm + topmost popup + TradingView chart.
Goal: cloud-first continuous quantitative research; local PC is not the research compute/storage bottleneck.

## PRODUCTION STATUS
V3 is LIVE on Render. Docker V3 module-copy failure was fixed by commit `b9c499f3358d22a8d722ebff61d1649879c270f9` using `COPY *.py ./`.
Latest production code deploy verified LIVE before this state-only update: commit `5998251e0da997f038dd0a54fda1d621d3a8a846`, deploy `dep-daf236v9l3cc73brkh60`.

## CONTINUOUS TOP-20 OPPORTUNITY ENGINE
Implemented and verified.

Core commits:
- `fcda8911dea87f2b47ccef2c9e91bce06dd6c13f` — continuous 24h/7d Top-20 opportunity ranking engine
- `0a003d5e93da9f1419946d33eb852ffd9fe55c22` — persist/read rankings in Supabase
- `8ec7f8366517f5888ba7458d6f92d7901c3d2aea` — generate rankings on every production scan
- `fa9881ea67e75f99f4eeb38e6c9797dd0911f9c9` — log rejected risk-plan candidates instead of silently swallowing them
- `5998251e0da997f038dd0a54fda1d621d3a8a846` — retry production scans during Render deployments

Behavior:
- every production scan constructs separate 24h and 7d rankings
- ranks up to 20 current candidates using deterministic multi-timeframe quant evidence plus liquidity/activity and spread penalties
- direction comes from quant evidence sign
- entry, stop, T1/T2 and entry display zone are generated from the current risk model
- an item is labeled TRADE only if the adversarial AI review explicitly marked that exact symbol+horizon as TRADE and direction agrees; otherwise it remains WAIT
- system does not fabricate 20 trades; WAIT is valid
- evidence score is not a calibrated probability
- fresh rankings are persisted in `public.crypto_opportunities` and dashboard reads latest fresh scan

Supabase table `public.crypto_opportunities` exists with RLS enabled and service-role-only server access. It stores scan_id, horizon, rank, symbol, direction, action, entry/zone, stop, targets, R:R, quant score, evidence score, regime, reasoning and strategy version.

END-TO-END VERIFICATION:
- Security CI run `34076472577` on latest production commit completed SUCCESS.
- Latest Render production deploy for commit `5998251e0da997f038dd0a54fda1d621d3a8a846` finished LIVE.
- Production scan run `34076472531` successfully completed its market-scan step after deployment.
- Supabase verified fresh scan `bd056a38-77dd-4a71-a343-0ad25a06550a` persisted exactly 20 rows for 24h (ranks 1-20) and 20 rows for 7d (ranks 1-20).
- That verification snapshot had 1 AI-approved TRADE in the 24h ranking and 0 AI-approved TRADEs in the 7d ranking; all others correctly remained WAIT.
- The same workflow's evaluator step was still running at the last state check; this does not block the verified Top-20 ranking path.

## DASHBOARD / TRADINGVIEW VISUALS
Private dashboard exists in `dashboard.py` with separate dashboard authentication secret, signed HttpOnly Secure SameSite=Strict session cookie, 24h/7d tabs, BUY/SELL/WAIT, entry area, stop, targets, R:R, evidence, regime, reasoning, risk-level visual and TradingView link.
Entry zone currently displays ±10% of modeled stop distance around strategy entry; this display zone is not yet independently optimized by backtesting.

Windows notifier `tools/windows_signal_notifier.py` polls the authenticated actionable signal feed, prevents historical alert floods, plays a Windows alarm, opens the matching TradingView chart and displays a topmost signal popup. Local activation/autostart on the user's Windows PC is still pending.

IMPORTANT TRADINGVIEW LIMITATION: standard Pine cannot securely pull arbitrary private server signal values. A Pine visual helper exists, but fully automatic placement of current private server entry/stop/target values directly onto TradingView still requires either deterministic signal reproduction in Pine or secure local browser/UI automation.

## CONTINUOUS CLOUD BACKTESTING
Deep OKX history pagination: `b6ace184c8592366466c8b8fd761765d22cee590`.
Backtest deep-history optimization/max drawdown: `fa776367b8c1a8be827a4a71c85b3ee0fac77aa7`.
Cloud runner: `8ff79cf4820c06fb8ba7682f169178e5b407767c`.
24/7 hourly scheduling: `c498557691d8632893a384d8adc0be33e27d9417`.
V4 cloud sharding commit: `8546068a07936494beeab29e942c9210723e3b5a`.
Current history cap is 50,000 candles per call as a cost/rate-limit guardrail, not an architectural limit.
Multiple independent strategy-family implementations are NOT complete yet.

## SECURITY / RELIABILITY
Security is core architecture because signals may influence real money. Never promise zero bugs/hacks/profit. Fail closed: invalid/uncertain data => no signal / WAIT.

Current automated checks:
- pytest
- pip-audit
- Bandit
- committed-secret detector
- read-only GitHub Actions permissions where possible
- timeouts/concurrency controls
- strict candle/risk validation
- defused XML parsing
- authenticated sensitive endpoints
- secrets only in secret/env stores
- exchange research integrations public/read-only; no withdrawal permission

Latest security verification: run `34076472577` SUCCESS on commit `5998251e0da997f038dd0a54fda1d621d3a8a846`.
Prior query-string SCAN_SECRET exposure still means secret rotation is recommended. Repository is public.

## QUANT / ALGO TARGET ARCHITECTURE
To pursue an exceptionally strong crypto quant system, build evidence in layers instead of relying on one AI score:
1. Multi-exchange clean historical/live data with integrity checks and normalized timestamps.
2. Spot + perpetual/futures microstructure: spread, depth, imbalance, trades, funding, OI, basis, liquidations.
3. Options where useful: IV, skew, term structure.
4. On-chain/tokenomics: exchange flows, holder concentration, stablecoin flows, unlocks/emissions/burns/treasury.
5. News/regulatory/macro/catalyst data with event timestamps and surprise/impact scoring.
6. Social/narrative signals only when incremental OOS value is demonstrated.
7. Multiple independent strategy families: trend, breakout, momentum, mean reversion, volatility expansion, relative strength, regime-conditioned/event strategies.
8. Realistic execution: next-bar/no-lookahead, fees, spread, slippage, liquidity/capacity, latency assumptions.
9. Rigorous validation: rolling walk-forward, untouched holdout, minimum samples, parameter stability, bootstrap/Monte Carlo, regime/symbol/month breakdowns, multiple-testing/overfit controls.
10. Portfolio/risk engine: correlations, exposure, volatility targeting, drawdown/portfolio heat, kill switches, concentration limits.
11. Strategy registry/ensemble that only weights strategies after convincing OOS evidence and demotes them when live performance deteriorates.
12. Continuous monitoring: data freshness, API health, drift, backtest-vs-live slippage, signal/outcome ledger, alerts and audit trail.
13. AI as adversarial research/review layer, not an oracle and not allowed to invent missing evidence.

NO TRADE / WAIT is valid. Capital survival and robust risk-adjusted expectancy outrank signal frequency.

## AUTOMATION
Production scan/evaluate workflow runs approximately every 15 minutes using `X-Scan-Secret`. Cloud research runs hourly 24/7 with parallel sharding.
Production scan workflow now retries transient 5xx/network failures during Render deployments.

## EXACT NEXT STEP
1. Implement distinct strategy families (trend, breakout, momentum, mean reversion, volatility expansion, relative strength) in the cloud research matrix.
2. Add strict OOS quality gates/strategy registry so only robust validated strategies can influence live ranking/ensemble weights.
3. Backtest and optimize entry-zone construction instead of using the current display-only ±10% risk-distance zone.
4. Activate/test the Windows notifier and TradingView visual bridge locally without exposing secrets.
