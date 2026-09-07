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
- `6ec0b77abf16bfff4e9a191e55555c78cf654c81` — hourly workflow expanded to dynamic Top-80 liquid OKX spot markets on 15m + 1H, split across 16 deterministic shards with max 8 parallel jobs; existing BTC/ETH/SOL/XRP/LINK 4H+1D swing shard retained.
- `9db28766d045ff0acf4b90fbc7c1effc89cd1eab` — tests added for deterministic sharding, explicit-symbol override and forced PONS inclusion.

Dynamic research selection uses existing `build_universe()` liquidity/activity/spread filters and takes the configured Top 80. The runner caps configurable dynamic universe size at 100. Explicit `RESEARCH_SYMBOLS` still overrides dynamic selection for special jobs.
PONS is forcibly added as `PONS-USDT-SWAP`. PONS is extremely new, so insufficient historical samples are expected initially and must fail closed.

Security and Reliability run `34079782584` for commit `9db28766d045ff0acf4b90fbc7c1effc89cd1eab` completed successfully.
Expanded Cloud Crypto Research run `34079774231` was still `in_progress` at the latest verified check. Do not claim it succeeded or claim new OOS eligibility counts until it completes and artifacts are inspected.

## AUTONOMOUS MULTI-AGENT DEVELOPMENT — PROPOSED V1
User requirement: six AI development roles should work continuously without interfering with each other and use GitHub as the shared synchronization layer.

Development is isolated on branch `agent/autonomous-orchestration-v1`; PR #1 is open and NOT merged to main or active.
Implemented on that branch:
- `agents/roles.json` defines five specialist missions, branch prefixes and strict file allowlists.
- `agents/autonomous_orchestrator.py` implements a Lead planner plus bounded specialist tool loop using the OpenAI Responses API. Specialists can list/read files, write only allowlisted files and run pytest. Tool steps are capped and failures are fail-closed.
- Protected specialist-write paths include `AI_STATE.md`, `agents/`, `.github/workflows/`, `requirements.txt` and `Dockerfile`, preventing agents from rewriting orchestration safeguards or canonical state.
- `.github/workflows/autonomous_agents.yml` schedules hourly Lead planning and up to five parallel specialist jobs. Each cycle uses a unique `auto/<role>/<run>` branch, runs full pytest, checks protected paths, then opens an unmerged PR only when there are changes.
- `.github/workflows/autonomous_lead.yml` schedules hourly review of the oldest autonomous PR, requires existing PR checks to pass, rejects oversized/protected-path diffs, and runs independent security + lead AI diff reviews.
- Autonomous merge is additionally gated by repository variable `AUTONOMOUS_MERGE_ENABLED=true`; without it, reviewed PRs remain open.
- `agents/lead_state.py` prepares a complete canonical `AI_STATE.md` update after a verified autonomous integration; it fails closed if the generated state is malformed or omits `## EXACT NEXT STEP`.
- `tests/test_autonomous_orchestrator.py` covers role allowlists, protected paths, traversal rejection and JSON parsing.

PR #1 Security and Reliability run `34081196120` initially produced:
- unit tests: PASS, 23 passed
- dependency audit: PASS, no known vulnerabilities
- Bandit static scan: FAIL on 9 low-severity/high-confidence subprocess findings in the new orchestration files
- secret scan: skipped because Bandit stopped the job

The subprocess surface was then removed instead of suppressed:
- commit `3cc699332dc0cfdce25ca7494c83a73e7a2a4cf7` removes subprocess/git-shell execution from `agents/autonomous_orchestrator.py`; pytest now runs through `pytest.main()` and planning uses AI_STATE + GitHub context rather than local git subprocesses.
- commit `6b6fb726cdb6f05cfa27c4b93ed135fd4ec8b8ca` removes subprocess from `agents/lead_state.py`; workflow-level `git diff --check` remains the validation gate.
A fresh Security and Reliability run after these fixes must pass fully before PR #1 may be merged.

Required activation inputs after merge:
- GitHub Actions secret `OPENAI_API_KEY`.
- GitHub Actions variable `OPENAI_AGENT_MODEL` set to a supported OpenAI API model.
- Keep `AUTONOMOUS_MERGE_ENABLED` unset/false for initial dry-run operation. Enable only after autonomous planning, branch isolation, CI and dual-review behavior are observed working correctly.

## TARGET QUANT ARCHITECTURE
Continue building evidence in layers: clean multi-exchange data; spot/perpetual microstructure; options where useful; on-chain/tokenomics; timestamped news/macro catalysts; independently validated strategy families; realistic execution costs; rigorous rolling validation and overfit controls; portfolio risk; fail-closed strategy registry; continuous live-vs-backtest monitoring. AI is an adversarial research/review layer, not an oracle.

NO TRADE / WAIT is valid. Capital survival and robust risk-adjusted expectancy outrank signal frequency.

## AUTOMATION
Production market scans: approximately every 15 minutes.
Cloud research/backtesting/algo testing: hourly, 24/7.
Expanded intraday research target: dynamic Top 80 liquid OKX spot markets + forced PONS-USDT-SWAP on 15m and 1H.
Existing major swing research remains on 4H and 1D.
Proposed autonomous development cadence after activation: Lead planning hourly, up to five specialist jobs in parallel, separate PRs, Security CI, dual AI review, then at most one verified PR integrated per Lead cycle.

## EXACT NEXT STEP
1. Verify the fresh Security and Reliability CI on PR #1 after subprocess removal; require unit tests, dependency audit, Bandit and secret scan all to pass before merge.
2. Keep autonomous merge disabled initially. After PR #1 is safely merged, configure `OPENAI_API_KEY` and `OPENAI_AGENT_MODEL`, manually dispatch one dry-run cycle, and inspect generated plan/branches/PRs for correct isolation and fail-closed behavior.
3. Separately re-check expanded Cloud Crypto Research run `34079774231`; once completed, inspect artifacts for Top-80 shard coverage, actual PONS-USDT-SWAP attempt, safe insufficient-history behavior and all newly eligible candidates.
4. Only after successful dry-run agent cycles should `AUTONOMOUS_MERGE_ENABLED=true` be considered. Even then, Security CI + independent security/lead AI reviews + protected-path gates remain mandatory.
5. Continue robustness work: deeper histories, rolling walk-forward windows, nearby-parameter stability, bootstrap/Monte Carlo confidence checks and longitudinal registry history before any research-family live weighting.
