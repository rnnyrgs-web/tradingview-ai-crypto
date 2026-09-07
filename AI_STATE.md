# AI DEVELOPMENT STATE
Last updated: 2026-09-07

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file in full before any development work. Every development change must update this file in the same development cycle so a brand-new ChatGPT can continue from the exact current state.

## ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase.
Research: OKX public historical APIs -> GitHub Actions cloud runners -> research artifacts/results.
Desktop alerts: authenticated Render signal feed -> Windows notifier -> alarm + topmost popup + TradingView chart.
Goal: cloud-first continuous quantitative research; the local PC is not the research compute/storage bottleneck.

## PRODUCTION STATUS
V3 is LIVE on Render.
Latest production code previously verified LIVE: `5998251e0da997f038dd0a54fda1d621d3a8a846`.
Continuous production scans build separate 24h and 7d Top-20 opportunity rankings, persist them to Supabase, and allow WAIT rather than fabricating trades. Live production does NOT yet consume research-family weights.

## DASHBOARD / ALERTS
Private dashboard exists with 24h/7d tabs, BUY/SELL/WAIT, entry area, stop, targets, R:R, evidence, regime, reasoning, risk visualization and TradingView link.
Windows notifier exists in `tools/windows_signal_notifier.py`; local activation/autostart is still pending.
Current displayed entry zone is ±10% of modeled stop distance and has not yet been independently optimized by backtesting.

## CLOUD RESEARCH CORE
Deep OKX history pagination and cloud backtesting are implemented. Research runs hourly 24/7 on GitHub Actions.
Six deterministic strategy families are researched independently:
1. trend
2. breakout
3. momentum
4. mean reversion
5. volatility expansion
6. relative strength vs BTC

Execution is no-lookahead: signals use data through candle i, entry is next-bar open, ATR stop/1.9R target, configured round-trip cost, conservative stop-first same-candle ambiguity, and non-overlapping holds.
Chronological split remains 60% train / 20% validation / 20% untouched holdout.
Failed candidates remain `RESEARCH_ONLY`; passed candidates become `ELIGIBLE_OOS`. Passing once is NOT sufficient for live weighting.

## FIRST COMPLETED STRATEGY-FAMILY OOS RUN
Cloud research run `34077019168` completed successfully on all four original shards.
Exactly 5 candidates passed the strict OOS gate:
- ETH-USDT 1H — trend
- SOL-USDT 15m — mean reversion
- DOGE-USDT 1H — volatility expansion
- ADA-USDT 1H — breakout
- ADA-USDT 1H — volatility expansion
No candidates from the original majors-b or swing-a shards passed. None of these are live-weighted yet.

## EXPANDED RESEARCH UNIVERSE — NEW DEVELOPMENT
User requirement: algo research/backtesting must cover far more than the original ~10 majors and must include PONS.

Implemented commits:
- `4c7f5129835c659a8e69d3d45a7d2a495160999e` — `research_runner.py` now supports dynamic liquid-universe selection, deterministic sharding and forced special symbols.
- `6ec0b77abf16bfff4e9a191e55555c78cf654c81` — hourly workflow expanded to dynamic Top-80 liquid OKX spot markets on 15m + 1H, split across 16 deterministic shards with max 8 parallel jobs. Existing BTC/ETH/SOL/XRP/LINK 4H+1D swing shard is retained.
- `9db28766d045ff0acf4b90fbc7c1effc89cd1eab` — tests added for deterministic sharding, explicit-symbol override and forced PONS inclusion.

Dynamic research selection uses existing `build_universe()` liquidity/activity/spread filters and takes the configured Top 80. The runner caps configurable dynamic universe size at 100. Explicit `RESEARCH_SYMBOLS` still overrides dynamic selection for special jobs.

PONS is forcibly added as `PONS-USDT-SWAP`. OKX announced PONS/USDT perpetual futures on 2026-09-05; PONS is extremely new, so insufficient historical samples are expected initially. Insufficient history must never create eligibility; it must remain research-only or fail that symbol safely.

Expanded cloud research run `34079774231` was triggered from the workflow expansion and was pending at the last check.
Latest security/test run `34079782584` for commit `9db28766d045ff0acf4b90fbc7c1effc89cd1eab` was pending at the last check.
Do not claim the expanded run succeeded or claim new OOS eligibility counts until these runs complete and artifacts are inspected.

## TARGET QUANT ARCHITECTURE
Continue building evidence in layers: clean multi-exchange data; spot/perpetual microstructure; options where useful; on-chain/tokenomics; timestamped news/macro catalysts; independently validated strategy families; realistic execution costs; rigorous rolling validation and overfit controls; portfolio risk; fail-closed strategy registry; continuous live-vs-backtest monitoring. AI is an adversarial research/review layer, not an oracle.

NO TRADE / WAIT is valid. Capital survival and robust risk-adjusted expectancy outrank signal frequency.

## AUTOMATION
Production market scans: approximately every 15 minutes.
Cloud research/backtesting/algo testing: hourly, 24/7.
Expanded intraday research target: dynamic Top 80 liquid OKX spot markets + forced PONS-USDT-SWAP on 15m and 1H.
Existing major swing research remains on 4H and 1D.

## EXACT NEXT STEP
1. Inspect completion of Security run `34079782584` and expanded Cloud Crypto Research run `34079774231`.
2. Inspect expanded research artifacts and verify dynamic shard coverage, broad Top-80 coverage, actual PONS-USDT-SWAP attempt, and fail-closed behavior for insufficient-history symbols.
3. Record all eligible strategy-family/symbol/timeframe candidates here. Do NOT live-weight anything merely because it passed one run.
4. Then strengthen robustness: deeper histories, rolling walk-forward windows, nearby-parameter stability, bootstrap/Monte Carlo confidence checks, and longitudinal registry history.
5. Only after repeated robust OOS evidence, connect approved strategy weights into the live Top-20 ensemble with a hard fail-closed registry gate.
6. Later optimize entry-zone construction and activate/test the Windows notifier/TradingView bridge locally.
