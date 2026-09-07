# AI DEVELOPMENT STATE
Last updated: 2026-09-07

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file in full before development. Every development cycle must update this file so a new ChatGPT can continue from the exact repository state.

## PRODUCTION / RESEARCH BASELINE
Production is GitHub -> Render -> Python/FastAPI V3 -> Supabase. V3 is live; latest production code previously verified live was `5998251e0da997f038dd0a54fda1d621d3a8a846`.
Production scans build separate 24h and 7d Top-20 opportunity rankings and allow WAIT. Live production still does not consume research-family weights.
Cloud research uses OKX public historical APIs and GitHub Actions. Research/backtesting runs hourly 24/7. Six strategy families remain trend, breakout, momentum, mean reversion, volatility expansion and relative strength vs BTC. No-lookahead and fail-closed rules remain mandatory.
Chronological validation remains 60% train / 20% validation / 20% untouched holdout. Failed candidates remain `RESEARCH_ONLY`; one OOS pass is never enough for live weighting.

## RESEARCH UNIVERSE
Dynamic intraday research targets Top-80 liquid OKX spot markets on 15m + 1H across deterministic shards, with PONS forcibly included as `PONS-USDT-SWAP`. Existing major swing research remains on 4H + 1D.
Expanded research run `34079774231` completed successfully and all 16 universe shard artifacts plus `swing-a` exist. Artifact contents still need inspection before making PONS-specific execution or new OOS-eligibility claims.

## FIRST STRICT OOS PASS SET
Research run `34077019168` produced exactly five strict OOS passes:
- ETH-USDT 1H trend
- SOL-USDT 15m mean reversion
- DOGE-USDT 1H volatility expansion
- ADA-USDT 1H breakout
- ADA-USDT 1H volatility expansion
None are live-weighted.

## AUTONOMOUS ORCHESTRATION VALIDATION
Core merged orchestration history includes:
- `38b6119f3694a099d6800f9e8ef4df7cd34b00cf`
- `8cdaceef7a24a131b8203893dd03702aada57e03`
- `2653dd2a1db3afb33bfaec9b7e3f5249350ad610`
- `312cd5d8f009dd6d6a3db31d0a0a9e34083d5465`
- `f1b154a68c30a9cca2c926795c5bc8dd2d1fd998`
- `ad70344a610c65dae5d59b302b33c69ed12edb58`
- `19b6655f1bff02a3d1b228355f7be3d684ebe92c` — bounded OpenAI retry handling.

After API credit was restored, specialist validation run `34130653382` attempt 2 completed successfully: Lead planning passed and all five original specialists completed successfully with full repository tests, cache cleanup and protected-path enforcement.
Autonomous Lead Integrator run `34133251327` then completed successfully. This proves the six-role baseline orchestration is functioning end-to-end in dry-run review mode.
`AUTONOMOUS_MERGE_ENABLED` remains false. Automatic production integration must stay disabled unless explicitly enabled by the user after further validation.

## 15-AGENT EXPANSION — MERGED
User requested expansion to an approximately 15-agent autonomous development team while keeping API/cloud spend tightly controlled.
PR #17 `Expand autonomous development to 15 cost-aware agents` passed Security and Reliability run `34133887403`, including unit tests, dependency audit, static security scan and committed-secret rejection, then merged to `main` as `b20d75f05a81ae8fe1814f515d3d4f99a58abd7d`.

The active architecture is now 15 total roles: 1 Lead Integrator + 14 specialists:
1. quant-trend
2. quant-mean-reversion
3. quant-breakout-volatility
4. quant-cross-asset
5. data-market
6. data-integrity
7. market-microstructure
8. onchain-tokenomics
9. news-macro
10. strategy-registry
11. portfolio-risk
12. production-signals
13. testing-security
14. infra-cost
plus the Lead Integrator.

Merged behavior:
- `agents/roles.json` contains 14 bounded specialist roles.
- `agents/autonomous_orchestrator.py` builds planner role schema dynamically from `roles.json`; no hardcoded five-role planner schema remains.
- Hard API-cost control: `MAX_ACTIVE_TASKS_PER_CYCLE = 4`. Planner output is rejected if more than four specialists are assigned TASK in one hourly cycle.
- Planner is instructed to prefer the smallest useful specialist set and NO_TASK over speculative work.
- `.github/workflows/autonomous_agents.yml` creates its matrix only from active TASK roles, so NO_TASK specialists do not consume worker API calls or runner installation time.
- Specialist parallelism is hard-capped at 4.
- Stable triggers are `workflow_dispatch` + hourly schedule at minute 17; the temporary main-push validation trigger has been removed.
- Testing/Security retains a 32-step ceiling; other active specialists remain at 20; global hard clamp stays 1..32.
- Tests assert exactly 14 specialist roles, protected-path isolation, exact planner role set and rejection above the four-active-specialist cost cap.

## SAFETY INVARIANTS
Specialists work on isolated `auto/<role>/<run>` branches. `AI_STATE.md`, `agents/`, `.github/workflows/`, `requirements.txt`, and `Dockerfile` remain protected from specialist writes.
Candidate branches must pass full pytest, generated-cache cleanup and protected-path checks before publication.
Candidate publication explicitly dispatches Security and Reliability. Lead requires exact candidate SHA success, rejects protected or >80 KB diffs, and requires independent Security AI + Lead AI approval.
With autonomous merge disabled, approved candidates remain unmerged/review-only.
Insufficient or unreliable evidence always means WAIT / NO TRADE / RESEARCH_ONLY.

## COST PRINCIPLES
Use deterministic Python for calculation/backtesting/filtering; use AI only for planning, bounded implementation and independent review.
No-task specialists incur no worker model call. Maximum four active specialist workers per hourly cycle. Parallelism is capped at four. Prefer measurable work over keeping agents busy.
Do not weaken safety, OOS validation or testing to save cost.
A platform-side spend cap should also remain configured by the user; repository controls are an additional layer, not a substitute for the provider billing limit.

## AUTOMATION
Production market scans: approximately every 15 minutes.
Cloud research/backtesting/algo testing: hourly 24/7.
Autonomous specialist planner: minute 17 every hour.
Autonomous Lead Integrator: after each specialist workflow plus minute 47 fallback.

## EXACT NEXT STEP
1. Wait for or manually trigger the first hourly specialist cycle on main commit `b20d75f05a81ae8fe1814f515d3d4f99a58abd7d`.
2. Verify planner sees all 14 specialists and assigns no more than four TASK roles.
3. Verify only TASK roles receive worker jobs; NO_TASK roles must consume no worker API calls or runner setup.
4. If any candidate branch is published, verify explicit Security and Reliability dispatch on the exact candidate SHA and successful conclusion.
5. Verify Autonomous Lead Integrator reviews an exact-current-main candidate, passes bounded/protected diff checks, receives Security AI + Lead AI approval, records dry-run review, and leaves the candidate unmerged because autonomous merge is OFF.
6. Fix any failure and repeat until the 15-agent cycle is green.
7. Update this file again with the first validated 15-agent cycle result.
8. Keep autonomous merging OFF unless the user explicitly chooses to enable it.
9. Separately inspect research run `34079774231` artifact contents before any PONS-specific result claims.
