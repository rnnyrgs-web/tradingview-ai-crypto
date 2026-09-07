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
PR #2, `Fix autonomous dry-run worker and test path`, was merged to `main` at merge commit `8cdaceef7a24a131b8203893dd03702aada57e03`.
Repository configuration:
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
- `agents/autonomous_worker.py` persists specialist instructions across Responses API continuations and requires explicit `CHANGE_STATUS` completion markers.

Dry run #1 — run `34081978561`:
- Lead planner PASS.
- Five specialists started.
- All five failed closed because full pytest lacked repository-root import resolution and specialist instructions were lost across tool continuations.
- No PR reached main.

PR #2 fixed dry-run #1 by adding repository-root pytest import handling, specialist `PYTHONPATH`, persistent instructions and completion markers. Security and Reliability run `34083176744` passed unit tests, dependency audit, Bandit and secret scan.

Scheduled run #2 — run `34083255188`:
- This run started immediately before PR #2 merged and therefore executed old main commit `38b6119f...`.
- Its failures do not test PR #2 and must not be interpreted as a regression in the fix.

Manual dry run #3 — run `34083647208` on fixed main commit `8cdaceef...`:
- Lead planner PASS and generated bounded tasks for all five roles.
- All five roles launched on isolated `auto/<role>/<run>` branches.
- Data/Market, Quant Research, Production/Risk and Testing/Security executed real bounded work and their full repository test gates passed.
- Verified Data/Market result: implemented stricter historical-candle validation; focused tests passed and full suite reported `41 passed`; final marker `CHANGE_STATUS: READY_FOR_PR`.
- Those successful specialist jobs were incorrectly blocked by the protected-path guard because Python/pytest generated untracked `__pycache__/` directories, including `agents/__pycache__/`, which matched the protected `agents/` prefix even though no protected source file was edited.
- Strategy Registry failed separately inside the worker after exhausting the 12-tool-step bound: `RuntimeError: agent exceeded maximum tool steps; failing closed`.
- No specialist PR from run #3 was opened and nothing reached main. Fail-closed containment worked.

Current fix development is isolated on `lead/fix-autonomous-dry-run-3` and is NOT yet merged:
- `.github/workflows/autonomous_agents.yml` sets `PYTHONDONTWRITEBYTECODE=1` for specialist jobs.
- The workflow explicitly removes generated `__pycache__`, `.pytest_cache`, `.pyc` and `.pyo` artifacts after full tests and before protected-path inspection.
- Specialist `AGENT_MAX_STEPS` is raised from 12 to a still-bounded 20 only in the specialist workflow, so more complex bounded tasks such as Strategy Registry can finish without removing the hard cap.
- `agents/autonomous_worker.py` now explicitly instructs specialists to minimize/rationalize tool calls, avoid rereading unchanged files and prioritize bounded completion over optional exploration.
- Protected source-path restrictions, full-test gates, completion-marker enforcement and autonomous-merge disablement are unchanged.

## TARGET QUANT ARCHITECTURE
Continue building evidence in layers: clean multi-exchange data; spot/perpetual microstructure; options where useful; on-chain/tokenomics; timestamped news/macro catalysts; independently validated strategy families; realistic execution costs; rigorous rolling validation and overfit controls; portfolio risk; fail-closed strategy registry; continuous live-vs-backtest monitoring. AI is an adversarial research/review layer, not an oracle.
NO TRADE / WAIT is valid. Capital survival and robust risk-adjusted expectancy outrank signal frequency.

## AUTOMATION
Production market scans: approximately every 15 minutes.
Cloud research/backtesting/algo testing: hourly, 24/7.
Expanded intraday research target: dynamic Top 80 liquid OKX spot markets + forced PONS-USDT-SWAP on 15m and 1H.
Existing major swing research remains on 4H and 1D.
Autonomous development target cadence: Lead planning hourly, up to five specialist jobs in parallel, separate PRs, Security CI, dual AI review, then at most one verified PR integrated per Lead cycle.
Autonomous merge remains disabled until a complete dry-run cycle proves planner execution, specialist completion, branch isolation, full tests, protected-path checks, autonomous PR creation and Lead/Security review behavior.

## EXACT NEXT STEP
1. Open a PR from `lead/fix-autonomous-dry-run-3` to `main`.
2. Require Security and Reliability CI to pass fully: unit tests, dependency audit, Bandit and committed-secret scan.
3. Review the diff specifically to verify generated-cache cleanup cannot hide protected source changes, the 20-step specialist cap remains bounded, no subprocess surface is reintroduced, and autonomous merge remains disabled.
4. Merge only after green CI.
5. Allow the next `Autonomous Specialist Agents` run on the new main (scheduled hourly or manual) and verify all five roles reach one of: valid PR creation with full tests/protected-path checks passing, or explicit safe NO_CHANGE.
6. Inspect any autonomous specialist PRs and exercise the Autonomous Lead Integrator review path with `AUTONOMOUS_MERGE_ENABLED` still unset/false. Verify independent Security + Lead AI reviews before enabling any automatic merge.
7. Only after at least one end-to-end green dry-run cycle should `AUTONOMOUS_MERGE_ENABLED=true` be considered.
8. Separately re-check Cloud Crypto Research run `34079774231`; when complete, inspect Top-80 coverage, actual PONS-USDT-SWAP attempt, insufficient-history fail-closed behavior and newly eligible candidates.
