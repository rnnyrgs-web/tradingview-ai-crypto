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

Repository configuration:
- GitHub Actions secret `OPENAI_API_KEY` configured.
- GitHub Actions variable `OPENAI_AGENT_MODEL=gpt-5.6` configured.
- `AUTONOMOUS_MERGE_ENABLED` remains unset/false.

Current branch-based autonomous architecture:
- Lead planner runs each specialist cycle.
- Five specialists run in parallel on isolated `auto/<role>/<run>` branches.
- Specialists can only write their role allowlists; `AI_STATE.md`, `agents/`, `.github/workflows/`, `requirements.txt`, and `Dockerfile` are protected.
- Full repository pytest, generated-cache cleanup, and protected-path checks are mandatory before a candidate branch is published.
- Security and Reliability CI runs independently on pushed candidate branch SHAs.
- Autonomous Lead Integrator is triggered by completed specialist workflows and has an hourly fallback.
- Lead only considers candidates whose merge-base is exactly current `main`.
- Lead requires successful Security and Reliability on the exact candidate SHA, rejects protected or >80 KB diffs, then requires independent Security AI and Lead AI approvals.
- With `AUTONOMOUS_MERGE_ENABLED` false, approved candidates remain unmerged and are recorded as review issues.
- If autonomous merge is later explicitly enabled, Lead may integrate at most one exact-current-main candidate per cycle, reruns pytest, updates canonical `AI_STATE.md`, pushes main, and deletes that candidate branch.
- GitHub Actions PR-create permission is no longer required for normal autonomous operation.

Dry-run history:
- Run #1 `34081978561`: import-path + instruction-continuation defects; failed closed.
- Run #2 `34083255188`: ran old main immediately before PR #2 merge; not a valid retest.
- Run #3 `34083647208`: four specialists produced real bounded changes and passed full tests, but generated Python cache files falsely tripped protected paths; Strategy Registry exhausted the old 12-step cap. PR #3 fixed both issues.
- Run #4 `34084417186`: all five specialists executed bounded work, passed full pytest, cleanup and protected-path enforcement, and pushed isolated branches; only GitHub's Actions PR-create policy blocked PR creation. PR #11 removed that dependency.
- Run #5 `34084791870` on main `312cd5d8...`: Lead planning PASS. The planner deliberately assigned NO_TASK to Quant Research, Data/Market, Strategy Registry and Production/Risk while assigning one bounded static orchestration-regression task to Testing/Security. The four NO_TASK jobs completed safely. Testing/Security failed closed before tests because it exhausted the specialist 20-tool-step budget while working on that bounded regression task: `RuntimeError: agent exceeded maximum tool steps; failing closed`. No Testing/Security candidate was published and nothing unsafe reached `main`.

Current fix development is isolated on `lead/fix-testing-security-step-budget` and is NOT merged:
- Testing/Security receives a role-specific 32-step budget while all other roles remain at 20.
- `agents/autonomous_orchestrator.py` now hard-clamps every configured tool budget to the inclusive range 1..32, so repository/environment misconfiguration cannot make an autonomous worker unbounded.
- Tests cover default, normal, maximum, excessive, zero and malformed budget values.
- No protected-path gate, test gate, exact-SHA CI gate, review gate, or merge gate is weakened.
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
1. Open a PR from `lead/fix-testing-security-step-budget` to `main` and require Security and Reliability to pass unit tests, dependency audit, Bandit and committed-secret scan.
2. Review that the role-specific 32-step allowance is still absolutely capped at 32 and does not weaken any write, test, protected-path, exact-SHA CI, diff-size, dual-review or merge gate.
3. Merge only after green CI. The temporary main-push trigger will automatically start a fresh specialist validation cycle.
4. Require the planner and all five specialist jobs to finish safely. NO_TASK roles may no-op; any TASK role must pass full pytest, cache cleanup and protected-path checks before publishing a candidate branch.
5. Verify Security and Reliability succeeds on the exact candidate branch SHA and that the workflow_run-triggered Autonomous Lead Integrator selects an exact-current-main candidate, passes bounded/protected diff checks, receives Security AI + Lead AI approval, records a dry-run review issue, and leaves the candidate unmerged because `AUTONOMOUS_MERGE_ENABLED` is false.
6. Fix any remaining failure and repeat automatically until the full cycle is green.
7. After green validation, remove the temporary main-push trigger, update canonical `AI_STATE.md` to READY, run Security CI and merge the cleanup.
8. Only then declare the six-agent autonomous collaboration system ready. Do not enable autonomous merging without an explicit user decision.
9. Separately inspect completed Cloud Crypto Research run `34079774231` artifacts before claiming PONS-specific results or new OOS eligibility counts.
