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
Six deterministic strategy families are researched independently: trend, breakout, momentum, mean reversion, volatility expansion, and relative strength vs BTC.
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
None are live-weighted.

## EXPANDED RESEARCH UNIVERSE
User requirement: algo research/backtesting must cover far more than the original ~10 majors and must include PONS.
Implemented commits:
- `4c7f5129835c659a8e69d3d45a7d2a495160999e` — dynamic liquid-universe selection, deterministic sharding and forced special symbols in `research_runner.py`.
- `6ec0b77abf16bfff4e9a191e55555c78cf654c81` — hourly dynamic Top-80 OKX spot universe on 15m + 1H across 16 deterministic shards with max 8 parallel jobs; existing BTC/ETH/SOL/XRP/LINK 4H+1D swing shard retained.
- `9db28766d045ff0acf4b90fbc7c1effc89cd1eab` — tests for deterministic sharding, explicit-symbol override and forced PONS inclusion.
Dynamic research selection uses existing `build_universe()` liquidity/activity/spread filters and takes configured Top 80; runner cap is 100. Explicit `RESEARCH_SYMBOLS` overrides dynamic selection for special jobs.
PONS is forcibly added as `PONS-USDT-SWAP`. Because PONS is very new, insufficient history must fail closed.
Security and Reliability run `34079782584` for commit `9db28766d045ff0acf4b90fbc7c1effc89cd1eab` completed successfully.
Expanded Cloud Crypto Research run `34079774231` was still `in_progress` at the latest verified check. Do not claim success or new OOS eligibility counts until artifacts are inspected.

## AUTONOMOUS MULTI-AGENT DEVELOPMENT — READY FOR END-TO-END DRY-RUN VALIDATION
User requirement: six AI development roles should work continuously without interfering with each other and use GitHub as the shared synchronization layer.

Merged orchestration history:
- PR #1 `Add fail-closed 24/7 autonomous multi-agent orchestration` -> main merge commit `38b6119f3694a099d6800f9e8ef4df7cd34b00cf`.
- PR #2 `Fix autonomous dry-run worker and test path` -> main merge commit `8cdaceef7a24a131b8203893dd03702aada57e03`.
- PR #3 `Fix autonomous dry-run cache guard and step budget` -> main merge commit `2653dd2a1db3afb33bfaec9b7e3f5249350ad610`.

Repository configuration:
- GitHub Actions secret `OPENAI_API_KEY` configured.
- GitHub Actions variable `OPENAI_AGENT_MODEL=gpt-5.6` configured.
- `AUTONOMOUS_MERGE_ENABLED` remains unset/false. Autonomous merging is still intentionally disabled.

Core orchestration:
- Lead planning hourly.
- Five parallel specialists: Quant Research, Data/Market, Strategy Registry, Production/Risk, Testing/Security.
- Unique `auto/<role>/<run>` branches.
- Strict role path allowlists and protected paths.
- Full repository pytest before PR creation.
- Independent Security AI and Lead AI reviews before any integration.
- At most one verified autonomous PR integrated per Lead cycle when autonomous merge is eventually enabled.
- Canonical `AI_STATE.md` remains Lead-owned and protected from specialist writes.

Dry run history:
- Run #1 `34081978561`: Lead planning passed, specialists failed closed due import-path and instruction-continuation issues. No PR reached main.
- Run #2 `34083255188`: scheduled immediately before PR #2 merged, so it used old main and is not a valid test of PR #2.
- Run #3 `34083647208`: executed fixed main `8cdaceef...`; Lead planner passed and all five roles launched on isolated branches. Data/Market, Quant Research, Production/Risk and Testing/Security completed real bounded work and passed the full repository test gate. Data/Market explicitly reported `41 passed` and `CHANGE_STATUS: READY_FOR_PR`.
- Run #3 then exposed two remaining orchestration defects: generated `__pycache__` folders falsely tripped the protected `agents/` path guard; Strategy Registry exhausted the old 12-step tool budget and failed closed.

PR #3 fixes now merged:
- Specialist jobs set `PYTHONDONTWRITEBYTECODE=1`.
- Generated `__pycache__`, `.pytest_cache`, `.pyc` and `.pyo` artifacts are removed before changed-path inspection.
- Specialist-only `AGENT_MAX_STEPS` is now 20: still hard-bounded, but sufficient for more complex bounded tasks.
- Worker instructions explicitly require efficient tool use and minimal file inspection.
- Protected source-path checks remain intact.
- Full-test gates remain intact.
- Completion-marker fail-closed behavior remains intact.
- Autonomous merge remains disabled.

PR #3 Security and Reliability run `34084042179` completed successfully: unit tests PASS, dependency audit PASS, Bandit PASS, committed-secret scan PASS.

## TARGET QUANT ARCHITECTURE
Continue building evidence in layers: clean multi-exchange data; spot/perpetual microstructure; options where useful; on-chain/tokenomics; timestamped news/macro catalysts; independently validated strategy families; realistic execution costs; rigorous rolling validation and overfit controls; portfolio risk; fail-closed strategy registry; continuous live-vs-backtest monitoring. AI is an adversarial research/review layer, not an oracle.
NO TRADE / WAIT is valid. Capital survival and robust risk-adjusted expectancy outrank signal frequency.

## AUTOMATION
Production market scans: approximately every 15 minutes.
Cloud research/backtesting/algo testing: hourly, 24/7.
Expanded intraday research target: dynamic Top 80 liquid OKX spot markets + forced PONS-USDT-SWAP on 15m and 1H.
Existing major swing research remains on 4H and 1D.
Autonomous Specialist Agents schedule: minute 17 each hour.
Autonomous Lead Integrator schedule: minute 47 each hour.
Autonomous merge remains disabled until one complete green end-to-end dry-run cycle proves specialist PR creation plus independent Security/Lead review behavior.

## EXACT NEXT STEP
1. Let the next scheduled `Autonomous Specialist Agents` cycle run from main commit `2653dd2a1db3afb33bfaec9b7e3f5249350ad610` or newer.
2. Verify all five roles reach a safe terminal state: valid autonomous PR creation after full tests and protected-path checks, or explicit `NO_CHANGE`.
3. Inspect autonomous specialist PRs and let `Autonomous Lead Integrator` review the oldest one with `AUTONOMOUS_MERGE_ENABLED` still unset/false.
4. Require both independent Security and Lead AI reviews to approve and verify the PR remains unmerged in dry-run mode.
5. Only after that complete green cycle should `AUTONOMOUS_MERGE_ENABLED=true` be considered.
6. Separately re-check Cloud Crypto Research run `34079774231`; inspect Top-80 coverage, actual PONS-USDT-SWAP attempt, insufficient-history fail-closed behavior and newly eligible candidates.
