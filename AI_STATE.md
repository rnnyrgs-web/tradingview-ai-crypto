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

## AUTONOMOUS MULTI-AGENT DEVELOPMENT — ACTIVE DRY-RUN PHASE
User requirement: six AI development roles should work continuously without interfering with each other and use GitHub as the shared synchronization layer.
PR #1, `Add fail-closed 24/7 autonomous multi-agent orchestration`, was merged to `main` at merge commit `38b6119f3694a099d6800f9e8ef4df7cd34b00cf`.
Repository configuration after merge:
- GitHub Actions secret `OPENAI_API_KEY` configured.
- GitHub Actions variable `OPENAI_AGENT_MODEL=gpt-5.6` configured.
- `AUTONOMOUS_MERGE_ENABLED` remains unset/false during dry-run validation.

Merged orchestration components:
- `agents/roles.json` defines five specialist missions, branch prefixes and strict file allowlists.
- `agents/autonomous_orchestrator.py` implements Lead planning, bounded specialist tools and independent Lead/Security diff review.
- Protected specialist-write paths include `AI_STATE.md`, `agents/`, `.github/workflows/`, `requirements.txt` and `Dockerfile`.
- `.github/workflows/autonomous_agents.yml` schedules hourly Lead planning and up to five parallel specialist jobs on unique `auto/<role>/<run>` branches.
- `.github/workflows/autonomous_lead.yml` performs hourly oldest-PR review, requires checks, rejects protected/oversized diffs, and runs independent security + lead AI reviews.
- `agents/lead_state.py` prepares canonical `AI_STATE.md` replacement after verified autonomous integration.

First manual autonomous dry run:
- Workflow run `34081978561`.
- Lead planning job: PASS.
- Lead produced bounded tasks for all five specialists.
- All five specialist jobs started on isolated branches.
- All five failed closed at the mandatory full-repository test gate; no autonomous PR was opened and nothing reached `main`.

Verified dry-run #1 root causes:
1. `pytest -q` collection failed with six import errors (`agents`, `dashboard`, `features`, `research_runner`, `safety`, `strategy_families`) because the autonomous specialist workflow lacked the repository-root `PYTHONPATH` used by the existing Security and Reliability workflow.
2. After the specialist read `AI_STATE.md`, it answered `What task would you like me to perform?` instead of continuing. The worker used `previous_response_id` after a tool call without re-supplying the specialist instructions, so the continuation lost the assigned-task instructions.

Fix development is isolated on branch `lead/fix-autonomous-dry-run-1` and is NOT yet merged:
- `conftest.py` ensures the repository root is available during pytest collection.
- `agents/autonomous_worker.py` executes specialist tasks with the assigned task repeated explicitly, re-supplies instructions on every Responses API continuation call, and fails closed unless the final response contains `CHANGE_STATUS: READY_FOR_PR` or `CHANGE_STATUS: NO_CHANGE`.
- `.github/workflows/autonomous_agents.yml` sets `PYTHONPATH: ${{ github.workspace }}` for specialist jobs and calls `agents/autonomous_worker.py`.
- `tests/test_autonomous_orchestrator.py` adds fail-closed completion-marker tests.

## TARGET QUANT ARCHITECTURE
Continue building evidence in layers: clean multi-exchange data; spot/perpetual microstructure; options where useful; on-chain/tokenomics; timestamped news/macro catalysts; independently validated strategy families; realistic execution costs; rigorous rolling validation and overfit controls; portfolio risk; fail-closed strategy registry; continuous live-vs-backtest monitoring. AI is an adversarial research/review layer, not an oracle.
NO TRADE / WAIT is valid. Capital survival and robust risk-adjusted expectancy outrank signal frequency.

## AUTOMATION
Production market scans: approximately every 15 minutes.
Cloud research/backtesting/algo testing: hourly, 24/7.
Expanded intraday research target: dynamic Top 80 liquid OKX spot markets + forced PONS-USDT-SWAP on 15m and 1H.
Existing major swing research remains on 4H and 1D.
Autonomous development target cadence: Lead planning hourly, up to five specialist jobs in parallel, separate PRs, Security CI, dual AI review, then at most one verified PR integrated per Lead cycle.
Autonomous merge remains disabled until successful dry-run validation proves planner execution, specialist task completion, branch isolation, full tests, PR creation, protected-path enforcement and dual-review behavior.

## EXACT NEXT STEP
1. Open a PR from `lead/fix-autonomous-dry-run-1` to `main` and require Security and Reliability CI to pass fully: unit tests, dependency audit, Bandit and secret scan.
2. Review that PR for import-path safety, no weakening of protected-path controls, no subprocess reintroduction, and correct persistence of specialist instructions across Responses API tool-call continuations.
3. Merge only after CI passes.
4. Manually dispatch autonomous dry run #2 with `AUTONOMOUS_MERGE_ENABLED` still unset/false. Verify Lead plan, five isolated specialist branches, actual bounded changes or explicit NO_CHANGE, full tests, protected-path checks, and PR creation.
5. Separately re-check Cloud Crypto Research run `34079774231`; when complete, inspect Top-80 shard coverage, actual PONS-USDT-SWAP attempt, insufficient-history fail-closed behavior and newly eligible candidates.
6. Only after successful dry-run cycles consider `AUTONOMOUS_MERGE_ENABLED=true`. Security CI + independent Security/Lead AI review + protected-path gates remain mandatory.
7. Continue deeper histories, rolling walk-forward validation, nearby-parameter stability, bootstrap/Monte Carlo checks and longitudinal registry history before any research-family live weighting.
