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
Expanded Cloud Crypto Research run `34079774231` is `completed/success`. All 16 universe shard artifacts (`universe-00` through `universe-15`) plus `swing-a` exist. Artifact contents still require inspection before claiming PONS execution details or new OOS eligibility counts.

## AUTONOMOUS MULTI-AGENT DEVELOPMENT — FINAL ORCHESTRATION VALIDATION
User requirement: six AI development roles should work continuously without interfering with each other and use GitHub as the shared synchronization layer.

Merged orchestration history:
- PR #1 -> `38b6119f3694a099d6800f9e8ef4df7cd34b00cf`.
- PR #2 -> `8cdaceef7a24a131b8203893dd03702aada57e03`.
- PR #3 -> `2653dd2a1db3afb33bfaec9b7e3f5249350ad610`.
- Lead state PR #4 -> `015b32d7dda03012d2ca6e81e52b77e481da0f3b`.
- Validation-trigger PR #5 -> `7724b2502a3f49df92323fe0d9bfb939591fdb39`.
- PR #11 `Remove autonomous PR-create permission dependency` -> `312cd5d8f009dd6d6a3db31d0a0a9e34083d5465`.
- Testing/Security bounded-budget fix -> `f1b154a68c30a9cca2c926795c5bc8dd2d1fd998`.
- PR #14 exact-SHA security dispatch fix -> `ad70344a610c65dae5d59b302b33c69ed12edb58`.

Repository configuration:
- GitHub Actions secret `OPENAI_API_KEY` configured.
- GitHub Actions variable `OPENAI_AGENT_MODEL=gpt-5.6` configured.
- `AUTONOMOUS_MERGE_ENABLED` remains unset/false.

Current branch-based autonomous architecture:
- Lead planner runs each specialist cycle.
- Five specialists run in parallel on isolated `auto/<role>/<run>` branches.
- Specialists can only write their role allowlists; `AI_STATE.md`, `agents/`, `.github/workflows/`, `requirements.txt`, and `Dockerfile` are protected.
- Full repository pytest, generated-cache cleanup, and protected-path checks are mandatory before a candidate branch is published.
- Testing/Security receives a role-specific 32-step budget; all other specialists remain at 20. The orchestrator hard-clamps every configured budget to 1..32.
- Candidate publication explicitly dispatches Security and Reliability on the candidate branch; Lead requires exact matching `headSha` success before review.
- Autonomous Lead Integrator is triggered by completed specialist workflows and has an hourly fallback.
- Lead only considers candidates whose merge-base is exactly current `main`.
- Lead rejects protected or >80 KB diffs, then requires independent Security AI and Lead AI approvals.
- With `AUTONOMOUS_MERGE_ENABLED` false, approved candidates remain unmerged and are recorded as review issues.
- If autonomous merge is later explicitly enabled, Lead may integrate at most one exact-current-main candidate per cycle, reruns pytest, updates canonical `AI_STATE.md`, pushes main, and deletes that candidate branch.

Dry-run history:
- Run #1 `34081978561`: import-path + instruction-continuation defects; failed closed.
- Run #2 `34083255188`: ran old main immediately before PR #2 merge; not a valid retest.
- Run #3 `34083647208`: four specialists produced real bounded changes and passed full tests, but generated Python cache files falsely tripped protected paths; Strategy Registry exhausted the old 12-step cap. PR #3 fixed both issues.
- Run #4 `34084417186`: all five specialists executed bounded work, passed full pytest, cleanup and protected-path enforcement, and pushed isolated branches; GitHub's Actions PR-create policy blocked PR creation. PR #11 removed that dependency.
- Run #5 `34084791870`: four NO_TASK roles completed safely; Testing/Security failed closed at the old 20-step budget. The hard-capped role-specific budget fix is merged.
- Validation cycle `34085259371` published exact candidate `auto/testing-security/34085259371-1` at SHA `62663adcf4100aa8a7774d2f620638483ca2f586`.
- Lead run `34085368879` selected that candidate but failed closed because GITHUB_TOKEN branch pushes did not trigger Security and Reliability. PR #14 fixed this by explicit workflow dispatch.
- Post-PR #14 specialist run `34130259522` started on main `ad70344a...` but the planner received OpenAI API HTTP 429 before producing a plan. The run failed closed and no specialist changes were produced.

Current fix development is isolated on `lead/fix-openai-rate-limit-retry` and is NOT merged:
- OpenAI Responses API calls now retry only bounded transient failures (`408`, `409`, `429`, `500`, `502`, `503`, `504`) and network/timeout errors.
- Retry count is hard-capped at 6 total attempts with bounded backoff 5/10/20/40/60 seconds; server `Retry-After` is honored but capped at 120 seconds.
- Non-retryable HTTP errors still fail immediately; exhausting retries fails closed.
- Tests cover normal backoff, hard cap, Retry-After honoring, malformed Retry-After fallback, and existing safety invariants.
- No write/test/protected-path/exact-SHA/diff-size/dual-review/merge gate is weakened.
- Autonomous merge remains OFF.

A temporary `push` trigger remains on Autonomous Specialist Agents only to enable immediate same-session validation without asking the user for a browser click. It must be removed after the complete branch-based end-to-end cycle is proven green, restoring stable triggers to `workflow_dispatch` + hourly schedule.

## TARGET QUANT ARCHITECTURE
Continue building evidence in layers: clean multi-exchange data; spot/perpetual microstructure; options where useful; on-chain/tokenomics; timestamped news/macro catalysts; independently validated strategy families; realistic execution costs; rigorous rolling validation and overfit controls; portfolio risk; fail-closed strategy registry; continuous live-vs-backtest monitoring. AI is an adversarial research/review layer, not an oracle.
NO TRADE / WAIT is valid. Capital survival and robust risk-adjusted expectancy outrank signal frequency.

## AUTOMATION
Production market scans: approximately every 15 minutes.
Cloud research/backtesting/algo testing: hourly, 24/7.
Expanded intraday research target: dynamic Top 80 liquid OKX spot markets + forced PONS-USDT-SWAP on 15m and 1H.
Existing major swing research remains on 4H and 1D.
Stable Autonomous Specialist Agents target schedule: minute 17 each hour.
Autonomous Lead Integrator target: immediately after each specialist workflow plus minute 47 each hour fallback.
Autonomous merge remains disabled until branch-based end-to-end validation is green.

## EXACT NEXT STEP
1. Open and review a PR from `lead/fix-openai-rate-limit-retry` to `main`.
2. Require Security and Reliability to pass unit tests, dependency audit, Bandit and committed-secret scan.
3. Merge only after green CI; temporary main-push trigger starts a fresh specialist validation cycle.
4. Require the planner to survive transient 429/5xx/network failures within the hard retry cap or fail closed if the API remains unavailable.
5. Require planner + five specialists to finish safely. NO_TASK roles may no-op; TASK roles must pass full pytest, cache cleanup and protected-path enforcement before candidate publication.
6. Verify candidate publication explicitly dispatches Security and Reliability on the exact candidate branch and exact candidate SHA and concludes success.
7. Verify Lead selects that exact-current-main candidate, passes bounded/protected diff checks, receives Security AI + Lead AI approval, records a dry-run review issue, and leaves the candidate unmerged because `AUTONOMOUS_MERGE_ENABLED` is false.
8. Fix any remaining failure and repeat automatically until full cycle is green.
9. After green validation, remove the temporary main-push trigger, update canonical `AI_STATE.md` to READY, run Security CI and merge cleanup.
10. Only then declare the six-agent autonomous collaboration system ready. Do not enable autonomous merging without explicit user decision.
11. Separately inspect completed Cloud Crypto Research run `34079774231` artifacts before claiming PONS-specific results or new OOS eligibility counts.
