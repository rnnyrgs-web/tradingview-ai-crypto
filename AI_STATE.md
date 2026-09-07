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
Expanded Cloud Crypto Research run `34079774231` has now been re-checked and is `completed/success`. All 16 universe shard artifacts (`universe-00` through `universe-15`) plus `swing-a` exist. Artifact contents still require inspection before claiming PONS execution details or new OOS eligibility counts.

## AUTONOMOUS MULTI-AGENT DEVELOPMENT — IMMEDIATE END-TO-END VALIDATION
User requirement: six AI development roles should work continuously without interfering with each other and use GitHub as the shared synchronization layer.

Merged orchestration history:
- PR #1 -> `38b6119f3694a099d6800f9e8ef4df7cd34b00cf`.
- PR #2 -> `8cdaceef7a24a131b8203893dd03702aada57e03`.
- PR #3 -> `2653dd2a1db3afb33bfaec9b7e3f5249350ad610`.
- Lead-owned state PR #4 -> `015b32d7dda03012d2ca6e81e52b77e481da0f3b`.

Repository configuration:
- GitHub Actions secret `OPENAI_API_KEY` configured.
- GitHub Actions variable `OPENAI_AGENT_MODEL=gpt-5.6` configured.
- `AUTONOMOUS_MERGE_ENABLED` remains unset/false.

Core orchestration:
- Lead planning hourly.
- Five parallel specialists: Quant Research, Data/Market, Strategy Registry, Production/Risk, Testing/Security.
- Unique `auto/<role>/<run>` branches.
- Strict role path allowlists and protected paths.
- Full repository pytest before PR creation.
- Independent Security AI and Lead AI reviews before any integration.
- Canonical `AI_STATE.md` is Lead-owned and protected from specialist writes.

Dry-run history:
- Run #1 `34081978561`: import-path + instruction-continuation defects; fail-closed.
- Run #2 `34083255188`: ran old main immediately before PR #2 merge; not a valid retest.
- Run #3 `34083647208`: fixed worker successfully produced real specialist code; four specialists passed full tests and Data/Market explicitly reported `41 passed` + `READY_FOR_PR`; cache artifacts falsely tripped protected-path check, while Strategy Registry exhausted old 12-step cap.
- PR #3 fixed those issues with bytecode suppression/cache cleanup and a still-bounded 20-step specialist budget. Security and Reliability run `34084042179` fully passed.
- Post-state merge Security and Reliability run `34084200860` on main commit `015b32d...` also completed successfully.

To avoid requiring a manual browser click and complete validation in this same development cycle, branch `lead/validate-autonomous-now` temporarily adds a `push` trigger for `main` to `Autonomous Specialist Agents`. This is validation-only. After one complete end-to-end cycle, the push trigger must be removed so the stable cadence returns to manual dispatch + hourly schedule only.

## TARGET QUANT ARCHITECTURE
Continue building evidence in layers: clean multi-exchange data; spot/perpetual microstructure; options where useful; on-chain/tokenomics; timestamped news/macro catalysts; independently validated strategy families; realistic execution costs; rigorous rolling validation and overfit controls; portfolio risk; fail-closed strategy registry; continuous live-vs-backtest monitoring. AI is an adversarial research/review layer, not an oracle.
NO TRADE / WAIT is valid. Capital survival and robust risk-adjusted expectancy outrank signal frequency.

## AUTOMATION
Production market scans: approximately every 15 minutes.
Cloud research/backtesting/algo testing: hourly, 24/7.
Expanded intraday research target: dynamic Top 80 liquid OKX spot markets + forced PONS-USDT-SWAP on 15m and 1H.
Existing major swing research remains on 4H and 1D.
Stable Autonomous Specialist Agents schedule: minute 17 each hour.
Autonomous Lead Integrator schedule: minute 47 each hour.
Autonomous merge remains disabled until the immediate end-to-end validation proves specialist PR creation plus independent Security/Lead review behavior.

## EXACT NEXT STEP
1. Merge the validation-trigger PR only after Security and Reliability CI is green.
2. Observe the resulting `Autonomous Specialist Agents` push-triggered run from the new main.
3. Require all five roles to reach a safe terminal state: valid autonomous PR after full tests/protected-path checks, or explicit `NO_CHANGE`.
4. Verify autonomous specialist PR CI and run the `Autonomous Lead Integrator` review path with `AUTONOMOUS_MERGE_ENABLED` still unset/false; require both Security and Lead AI review approval and confirm no merge occurs.
5. Remove the temporary `push` trigger via a separate Lead branch/PR, leaving only `workflow_dispatch` + hourly schedule.
6. Update canonical `AI_STATE.md` with the complete validated state.
7. Only then consider enabling `AUTONOMOUS_MERGE_ENABLED=true`.
8. Inspect completed Cloud Crypto Research run `34079774231` artifact contents before claiming PONS-specific results or new eligibility counts.
