# AI DEVELOPMENT STATE
Last updated: 2026-09-07

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`.
Read this first in every software-development conversation. Never store secrets here.

## ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase.
Research: OKX public historical APIs -> GitHub Actions cloud runners -> research artifacts/results.
Goal: cloud-first continuous quantitative research; local PC is not the compute/storage bottleneck.

## PRODUCTION STATUS
V3 is LIVE on Render. Docker V3 module-copy failure was fixed by commit `b9c499f3358d22a8d722ebff61d1649879c270f9` using `COPY *.py ./`.
Verified previously: `/scan` 200, `/evaluate` 200, V3 rows reached Supabase, evaluator worked, and 12h evaluation columns exist.

## CONTINUOUS CLOUD BACKTESTING
Deep OKX history pagination: commit `b6ace184c8592366466c8b8fd761765d22cee590`.
Backtest deep-history optimization/max drawdown: `fa776367b8c1a8be827a4a71c85b3ee0fac77aa7`.
Cloud runner: `8ff79cf4820c06fb8ba7682f169178e5b407767c`.
Initial workflow: `0b36932096c24093e30a3c45e38a421d1cf7813a`.
24/7 hourly scheduling: `c498557691d8632893a384d8adc0be33e27d9417`.

`.github/workflows/cloud_research.yml` runs hourly at minute 7, supports manual inputs, defaults to BTC/ETH/SOL/XRP/LINK on 15m/1H with 5000 candles, uses a 30-minute timeout, prevents overlapping runs, and retains artifacts 7 days. Current history safety cap is 50,000 candles per call; it is a cost/rate-limit guardrail, not an architectural limit.

First proof run `34073785214` succeeded and produced artifact `10001378353`. Early results are research-only and insufficient for live weighting.

## SECURITY / RELIABILITY HARDENING
User requires security and reliability to be core architecture because signals may influence real money. Never promise zero bugs/hacks/profit. Fail closed: invalid/uncertain data => no signal / WAIT.

Added automated security/reliability CI:
- commit `99ca875e655cca95efc4a2762e5b82279fb658c8`
- `.github/workflows/security.yml`
- runs on pushes, PRs, and daily
- minimal workflow permission: `contents: read`
- pytest unit tests
- `pip-audit` dependency vulnerability audit
- Bandit static Python security scan
- obvious committed-secret detection
- 15-minute timeout and concurrency cancellation

Hardened `safety.py`:
- commit `0691ec5443b55188eb4d988ae27db3fe768d4b9b`
- rejects NaN/infinite/non-positive OHLC
- rejects invalid/negative/non-finite volume
- rejects invalid/duplicate/non-monotonic timestamps
- rejects future-dated candles
- retains stale-data rejection
- validates all risk-plan prices are finite and positive

Expanded fail-closed tests:
- commit `f7d126c861e8e3518b730926265f87d072cb88f6`
- NaN risk rejection
- duplicate timestamp rejection
- invalid OHLC rejection
- future candle rejection

Security CI run `34074314594` was queued after latest hardening commit at last check; verify its final result before relying on this change as fully validated.

Rules:
- no secrets in source/repo
- secrets only in secret/env stores
- Supabase service key server-side only
- sensitive endpoints authenticated
- least privilege
- exchange research integrations should be public/read-only; no withdrawal permission
- fail closed on data/API integrity problems
- prior query-string SCAN_SECRET exposure still means secret rotation is recommended
- repository is public

## QUANT / ALGO TARGET ARCHITECTURE
To pursue an exceptionally strong crypto quant system, build evidence in layers rather than relying on one AI score:
1. Multi-exchange clean historical/live data with integrity checks and normalized timestamps.
2. Spot + perpetual/futures microstructure: spread, depth, imbalance, trades, funding, OI, basis, liquidations.
3. Options where useful: IV, skew, term structure.
4. On-chain/tokenomics: exchange flows, holder concentration, stablecoin flows, unlocks/emissions/burns/treasury.
5. News/regulatory/macro/catalyst data with event timestamps and surprise/impact scoring.
6. Social/narrative signals, tested for incremental OOS value rather than assumed useful.
7. Multiple independent strategy families: trend, breakout, momentum, mean reversion, volatility expansion, relative strength, regime-conditioned/event strategies.
8. Realistic execution model: next-bar/no-lookahead, fees, spread, slippage, liquidity/capacity, latency assumptions.
9. Rigorous validation: rolling walk-forward, untouched holdout, minimum samples, parameter stability, bootstrap/Monte Carlo, regime/symbol/month breakdowns, multiple-testing/overfit controls.
10. Portfolio/risk engine: correlation, exposure, volatility targeting, drawdown/portfolio heat, kill switches, concentration limits.
11. Strategy registry/ensemble that only weights strategies after convincing OOS evidence and can demote strategies when live performance deteriorates.
12. Continuous monitoring: data freshness, API health, drift, backtest-vs-live slippage, signal/outcome ledger, alerts and audit trail.
13. AI as adversarial research/review layer, not an oracle and not allowed to invent missing evidence.

NO TRADE / WAIT is a valid output. Capital survival and robust risk-adjusted expectancy outrank signal frequency.

## SUPABASE
Project ref `dxgksvzibucwuzmppoqy`. Main table `public.trading_signals`; RLS enabled. Never store service keys here.

## AUTOMATION
Production scan/evaluate workflow runs approximately every 15 minutes using `X-Scan-Secret`. Cloud research runs hourly 24/7.

## EXACT NEXT STEP
1. Verify security CI run `34074314594` finishes successfully; if not, inspect logs and fix before proceeding.
2. Then build V4 cloud research matrix/sharding: many symbols x timeframes x strategy families in parallel, with cost/rate-limit caps and compact longitudinal result persistence.
3. Add research-quality gates so only robust out-of-sample strategies become eligible for the live ensemble.
