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
Latest checked Render deploy for commit `e5e14e743f9062d046a4f04831ed41d9acb6311d` finished LIVE at 2026-09-07T02:00:34Z.
Previously verified: `/scan` 200, `/evaluate` 200, V3 rows reached Supabase, evaluator worked, and 12h evaluation columns exist.

## CONTINUOUS CLOUD BACKTESTING
Deep OKX history pagination: `b6ace184c8592366466c8b8fd761765d22cee590`.
Backtest deep-history optimization/max drawdown: `fa776367b8c1a8be827a4a71c85b3ee0fac77aa7`.
Cloud runner: `8ff79cf4820c06fb8ba7682f169178e5b407767c`.
Initial workflow: `0b36932096c24093e30a3c45e38a421d1cf7813a`.
24/7 hourly scheduling: `c498557691d8632893a384d8adc0be33e27d9417`.

### V4-style cloud sharding
Commit `8546068a07936494beeab29e942c9210723e3b5a` (`Shard continuous cloud research in parallel`).
`.github/workflows/cloud_research.yml` now runs an hourly matrix with up to 4 parallel shards:
- majors-a: BTC/ETH/SOL, 15m + 1H
- majors-b: XRP/LINK/BNB, 15m + 1H
- majors-c: DOGE/ADA/TRX, 15m + 1H
- swing-a: BTC/ETH/SOL/XRP/LINK, 4H + 1D
Defaults remain 5000 candles, 30-minute per-job timeout, 7-day artifacts, read-only workflow permissions, and no overlapping top-level research runs.
This is symbol/timeframe sharding. Multiple independent strategy-family implementations are NOT complete yet.

Current history cap is 50,000 candles per call as a cost/rate-limit guardrail, not an architectural limit.
First proof run `34073785214` succeeded; early performance was research-only and insufficient for live weighting.

## SIGNAL VISIBILITY / WINDOWS TRADINGVIEW ALERT BRIDGE
Signals remain stored in Supabase table `public.trading_signals`.

Authenticated actionable feed added:
- `db.py` `fetch_actionable_after()` commit `ac9dd9d1d11eb24882bd7132c902784c38b6ae3c`
- `app.py` GET `/signals` commit `66967e2a52d4c21525e9a96e325066407e847667`
- only `action=TRADE` rows are returned through this feed
- endpoint requires existing scan authentication; never expose the secret in URLs

Safe startup cursor added:
- `db.py` latest-id support commit `87585af689383ff29a15a883728d03de4eb4c7cc`
- `app.py` GET `/signals/cursor` commit `e944c248efc9f0d8a92b391fc4dd7bed6c698312`
This prevents a newly started notifier from alarming on old historical TRADE rows.

Windows notifier:
- file `tools/windows_signal_notifier.py`
- initial commit `1debb68a067e90addd3e2db0f87c4df978c09ff5`
- historical-flood protection `54affb739cd825ebfc0a96932ad3ac01690663df`
- HTTPS server URL validation `296c563fa01edea8bd8ce2f3e6aaf3914be54af4`
Behavior when a NEW actionable signal appears:
1. polls the authenticated `/signals` feed (default 15s)
2. plays a two-tone Windows alarm
3. opens a NEW TradingView tab on the corresponding OKX symbol and mapped timeframe
4. displays a top-most Windows popup with direction, entry, stop, targets, evidence score, and regime

IMPORTANT LIMITATION: the bridge currently opens the correct live TradingView chart and shows the signal details in the Windows popup. It does NOT yet draw external entry/stop/target lines or arrows directly onto the TradingView chart. Standard Pine cannot pull arbitrary private server signal values. Direct chart drawing will require either a deterministic Pine overlay that reproduces eligible signal logic or a secure local UI/browser automation bridge that places TradingView drawings.

The notifier is intended to run on the user's Windows PC and is not copied into the Render Docker image (`Dockerfile` copies root `*.py` only). It requires the existing auth secret from a PRIVATE Windows environment variable. Never ask the user to paste that secret in chat.

## SECURITY / RELIABILITY HARDENING
User requires security and reliability as core architecture because signals may influence real money. Never promise zero bugs/hacks/profit. Fail closed: invalid/uncertain data => no signal / WAIT.

Security CI initially exposed useful defects and was fixed rather than bypassed.
Current workflow `.github/workflows/security.yml`:
- pushes, PRs, daily schedule
- minimal `contents: read`
- PYTHONPATH fixed in commit `6f328b3a6091f2fce7783d9478f8badecbf86204`
- pytest
- pip-audit
- Bandit
- committed-secret pattern scanner
- timeout/concurrency controls

Data/signal safety:
- `safety.py` commit `0691ec5443b55188eb4d988ae27db3fe768d4b9b`
- rejects NaN/infinite/non-positive OHLC, invalid volume, duplicate/non-monotonic/invalid timestamps, future candles, stale short-TF data, invalid risk prices
- expanded tests commit `f7d126c861e8e3518b730926265f87d072cb88f6`

Bandit-driven hardening:
- added `defusedxml>=0.7,<1` in requirements: `c812702596d2b670674598af14fafa83c657a128`
- RSS parsing switched to defusedxml and logs failures: `6eca078da28707985ea55126dc23ebb6f11f2b93`
- derivatives failures are logged instead of silently swallowed: `9f8f0f2022572cafbbc1d61026ddb35b2b9d2c0c`
- notifier restricts server URL to credential-free HTTPS before urlopen: `296c563fa01edea8bd8ce2f3e6aaf3914be54af4`
- committed-secret scanner shell quoting fixed with a Python scanner: `e5e14e743f9062d046a4f04831ed41d9acb6311d`

LATEST SECURITY CI VERIFICATION:
Run `34074805711` completed SUCCESS.
- unit tests: SUCCESS
- dependency vulnerability audit: SUCCESS
- static security scan: SUCCESS
- committed-secret detector: SUCCESS
Therefore the current hardening changes passed the configured automated checks. This does not mean bug-free or hacker-proof.

Security rules:
- no secrets in source/repo/AI_STATE
- secrets only in secret/env stores
- Supabase service key server-side only
- sensitive endpoints authenticated
- least privilege
- exchange research integrations public/read-only; no withdrawal permission
- fail closed on data/API integrity problems
- prior query-string SCAN_SECRET exposure still means secret rotation is recommended
- repository is public

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

## SUPABASE
Project ref `dxgksvzibucwuzmppoqy`. Main table `public.trading_signals`; RLS enabled. Never store service keys here.

## AUTOMATION
Production scan/evaluate workflow runs approximately every 15 minutes using `X-Scan-Secret`. Cloud research runs hourly 24/7 with parallel sharding.

## EXACT NEXT STEP
1. Activate/test the Windows notifier on the user's PC without ever revealing the secret in chat. It needs a private local environment variable and should be configured to start automatically with Windows once verified.
2. Then add direct TradingView visual signal marking using the safest feasible bridge (prefer deterministic overlay when possible; local automation only if necessary).
3. Continue V4 quant research by implementing distinct strategy families and research-quality gates/registry so only robust out-of-sample strategies become eligible for the live ensemble.
