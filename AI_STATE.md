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

Repository configuration:
- GitHub Actions secret `OPENAI_API_KEY` configured.
- GitHub Actions variable `OPENAI_AGENT_MODEL=gpt-5.6` configured.
- `AUTONOMOUS_MERGE_ENABLED` remains unset/false.

Dry-run history:
- Run #1 `34081978561`: import-path + instruction-continuation defects; failed closed.
- Run #2 `34083255188`: ran old main immediately before PR #2 merge; not a valid retest.
- Run #3 `34083647208`: four specialists produced real bounded changes and passed full tests, but generated Python cache files falsely tripped protected paths; Strategy Registry exhausted the old 12-step cap. PR #3 fixed both issues.
- Run #4 `34084417186` on main `7724b250...`: Lead planning PASS; all five specialists executed their assigned bounded tasks; all five passed full repository pytest; all five passed cache cleanup and protected-path enforcement; all five successfully committed and pushed isolated candidate branches.
- Run #4 then exposed a repository-policy limitation outside the agent code: GitHub returned `GitHub Actions is not permitted to create or approve pull requests (createPullRequest)`. The branch push succeeded first, so candidate work was preserved. Quant Research, for example, added a six-family no-lookahead regression and reported focused `6 passed`, full suite `31 passed`, `CHANGE_STATUS: READY_FOR_PR`.
- For validation only, PRs #6-#10 were opened through the connected GitHub integration from the five preserved run #4 branches. Quant PR #6 Security and Reliability run `34084566963` is verified `completed/success`; the remaining PR checks must not be assumed until inspected.

The system must not depend on a repository setting that prevents `GITHUB_TOKEN` from opening PRs. Current fix development is isolated on `lead/remove-pr-permission-dependency`:
- Specialists publish verified `auto/<role>/<run>` candidate branches after their full-test and protected-path gates; PR creation is no longer required.
- Security and Reliability already runs automatically on every pushed candidate branch and therefore validates the exact candidate SHA independently.
- Autonomous Lead Integrator is changed to run automatically after every completed `Autonomous Specialist Agents` workflow via `workflow_run`, with the hourly schedule retained as fallback.
- Lead selects only an autonomous candidate whose merge-base is the exact current `main`, preventing stale branches from entering a new integration state.
- Lead waits for a successful Security and Reliability run on the exact candidate SHA, bounds/rejects protected diffs, and performs independent Security AI + Lead AI reviews.
- While `AUTONOMOUS_MERGE_ENABLED` is false, an approved candidate remains unmerged and the Lead records the exact SHA and both reviews in a GitHub review issue. This lets dry-run review progress without PR-create permission.
- If autonomous merge is later explicitly enabled, Lead re-verifies the exact candidate SHA, dual-reviews again, squash-integrates one candidate based on current main, runs pytest, updates canonical `AI_STATE.md`, pushes main, and deletes that integrated candidate branch.
- `agents/lead_state.py` is generalized from PR wording to verified-candidate wording; validation and malformed-output fail-closed checks remain unchanged.
- Specialist source protections, full pytest, 80 KB diff bound, dual AI review, exact-SHA Security CI requirement, one-candidate-at-a-time integration, and autonomous-merge default OFF are preserved.

A temporary `push` trigger remains on Autonomous Specialist Agents only to enable immediate same-session validation without asking the user for a browser click. It must be removed after the branch-based end-to-end cycle is proven green, restoring stable triggers to `workflow_dispatch` + hourly schedule.

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
1. Open a PR from `lead/remove-pr-permission-dependency` to `main` and require Security and Reliability to pass unit tests, dependency audit, Bandit and committed-secret scan.
2. Review the workflow diff specifically for exact-current-main candidate selection, exact-SHA Security CI matching, protected-path/diff bounds, independent dual AI review, and one-candidate-at-a-time fail-closed integration.
3. Merge only after green CI. The temporary main-push trigger should immediately start a fresh specialist cycle based on the new main.
4. Verify all five specialist jobs finish successfully and either publish a valid current-base candidate branch or explicitly make no change.
5. Verify Security and Reliability succeeds on candidate branch SHAs and that the `workflow_run`-triggered Autonomous Lead Integrator independently reviews candidates, records approved dry-run review issues, and does not merge while `AUTONOMOUS_MERGE_ENABLED` is false.
6. Fix any remaining failure and repeat automatically until the entire cycle is green.
7. After green validation, remove the temporary main-push trigger from Autonomous Specialist Agents, update canonical `AI_STATE.md`, run Security CI, and merge that final cleanup.
8. Only then declare the six-agent autonomous collaboration system ready. Do not enable autonomous merging without an explicit user decision.
9. Separately inspect completed Cloud Crypto Research run `34079774231` artifacts before claiming PONS-specific results or new OOS eligibility counts.
