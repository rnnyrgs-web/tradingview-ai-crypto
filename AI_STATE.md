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

## EXPANDED RESEARCH UNIVERSE
User requirement: algo research/backtesting must cover far more than the original ~10 majors and must include PONS.

Implemented commits:
- `4c7f5129835c659a8e69d3d45a7d2a495160999e` — `research_runner.py` supports dynamic liquid-universe selection, deterministic sharding and forced special symbols.
- `6ec0b77abf16bfffde506ce70d488d2` — placeholder invalid historical note; do not rely on this value.
- `6ec0b77abf16bfff4e9a191e55555c78cf654c81` — hourly workflow expanded to dynamic Top-80 liquid OKX spot markets on 15m + 1H, split across 16 deterministic shards with max 8 parallel jobs; existing BTC/ETH/SOL/XRP/LINK 4H+1D swing shard retained.
- `9db28766d045ff0acf4b90fbc7c1effc89cd1eab` — tests added for deterministic sharding, explicit-symbol override and forced PONS inclusion.

Dynamic research selection uses existing `build_universe()` liquidity/activity/spread filters and takes the configured Top 80. The runner caps configurable dynamic universe size at 100. Explicit `RESEARCH_SYMBOLS` still overrides dynamic selection for special jobs.
PONS is forcibly added as `PONS-USDT-SWAP`. PONS is extremely new, so insufficient historical samples are expected initially and must fail closed.

Security and Reliability run `34079782584` for commit `9db28766d045ff0acf4b90fbc7c1effc89cd1eab` completed successfully.
Expanded Cloud Crypto Research run `34079774231` was still `in_progress` at the latest verified check. Do not claim it succeeded or claim new OOS eligibility counts until it completes and artifacts are inspected.

## AUTONOMOUS MULTI-AGENT DEVELOPMENT — ACTIVE DRY-RUN PHASE
User requirement: six AI development roles should work continuously without interfering with each other and use GitHub as the shared synchronization layer.

PR #1, `Add fail-closed 24/7 autonomous multi-agent orchestration`, was merged to `main` at merge commit `38b6119f3694a099d6800f9e8ef4df7cd34b00cf`.
Repository configuration completed manually after merge:
- GitHub Actions secret `OPENAI_API_KEY` is configured.
- GitHub Actions variable `OPENAI_AGENT_MODEL` is configured as `gpt-5.6`.
- `AUTONOMOUS_MERGE_ENABLED` remains unset/false; autonomous merging is intentionally disabled during dry-run validation.

Merged orchestration components:
- `agents/roles.json` defines five specialist missions, branch prefixes and strict file allowlists.
- `agents/autonomous_orchestrator.py` implements Lead planning, bounded specialist tools and independent Lead/Security diff review.
- Protected specialist-write paths include `AI_STATE.md`, `agents/`, `.github/workflows/`, `requirements.txt` and `Dockerfile`.
- `.github/workflows/autonomous_agents.yml` schedules hourly Lead planning and up to five parallel specialist jobs, each on a unique `auto/<role>/<run>` branch.
- `.github/workflows/autonomous_lead.yml` schedules hourly review/integration checks, requires passing PR checks, rejects protected/oversized diffs, and runs independent security + lead AI review.
- `agents/lead_state.py` prepares canonical `AI_STATE.md` replacement after verified autonomous integration.

First manual autonomous dry run:
- Workflow: `Autonomous Specialist Agents`
- Run ID: `34081978561`
- Lead planning job: PASS.
- The Lead successfully produced five bounded specialist tasks for quant-research, data-market, strategy-registry, production-risk and testing-security.
- All five specialist jobs started on isolated branches and reached the mandatory full-repository test gate.
- All five jobs failed closed before any PR was opened.

Verified root causes from run `34081978561`:
1. Full `pytest -q` collection failed with six import errors such as `ModuleNotFoundError: dashboard`, `features`, `research_runner`, `safety`, `strategy_families`, and `agents`, because the autonomous specialist workflow did not set the repository root on `PYTHONPATH`, unlike the existing Security and Reliability workflow.
2. The specialist model read `AI_STATE.md`, then responded `What task would you like me to perform?` instead of continuing the assigned task. The worker used `previous_response_id` after tool calls without re-supplying the specialist instructions; Responses API instructions are not assumed to persist across continuation calls.

Fix development is isolated on branch `lead/fix-autonomous-dry-run-1` and is NOT yet merged:
- `conftest.py` adds the repository root to Python import resolution for pytest.
- `agents/autonomous_worker.py` executes specialist tasks with the assigned task repeated explicitly, re-supplies instructions on every Responses API continuation call, and fails closed unless the final response contains `CHANGE_STATUS: READY_FOR_PR` or `CHANGE_STATUS: NO_CHANGE`.
- `.github/workflows/autonomous_agents.yml` now sets `PYTHONPATH: ${{ github.workspace }}` for specialist jobs and calls `agents/autonomous_worker.py` for specialist execution.
- `tests/test_autonomous_orchestrator.py` adds fail-closed completion-marker tests for the worker.

No autonomous specialist change from dry run #1 reached a PR or `main`. Fail-closed isolation therefore worked as intended.

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
2. Review the fix PR diff specifically for import-path safety, no weakening of protected-path controls, no subprocess reintroduction, and correct persistence of specialist instructions across Responses API tool-call continuations.
3. Merge the fix only after CI passes.
4. Manually dispatch autonomous dry run #2 with `AUTONOMOUS_MERGE_ENABLED` still unset/false. Verify the Lead plan, five isolated specialist branches, actual bounded file changes or explicit NO_CHANGE, full repository tests, protected-path checks, and autonomous PR creation.
5. Separately re-check expanded Cloud Crypto Research run `34079774231`; once completed, inspect artifacts for Top-80 shard coverage, actual PONS-USDT-SWAP attempt, safe insufficient-history behavior and newly eligible candidates.
6. Only after successful dry-run cycles should `AUTONOMOUS_MERGE_ENABLED=true` be considered. Security CI + independent security/lead AI review + protected-path gates remain mandatory even then.
7. Continue robustness work: deeper histories, rolling walk-forward windows, nearby-parameter stability, bootstrap/Monte Carlo confidence checks and longitudinal registry history before any research-family live weighting.
