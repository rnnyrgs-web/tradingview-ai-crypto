# AI DEVELOPMENT STATE
Last updated: 2026-09-07

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file in full before development. Every development cycle must update this file so a new ChatGPT can continue from the exact repository state.

## PRODUCTION / RESEARCH BASELINE
Production is GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run approximately every 15 minutes and build separate 24h and 7d Top-20 opportunity rankings. WAIT is allowed.
Cloud research uses OKX public historical APIs and GitHub Actions. Research/backtesting runs hourly 24/7. Six strategy families remain trend, breakout, momentum, mean reversion, volatility expansion and relative strength vs BTC. No-lookahead and fail-closed rules remain mandatory.
Chronological validation remains 60% train / 20% validation / 20% untouched holdout. Failed candidates remain `RESEARCH_ONLY`; one OOS pass is never enough for live weighting.

## USER-MANDATED LIVE SIGNAL RULE — ENFORCED
The user requires every BUY/SELL signal to be fully research validated and backtested before production display. No AI review, evidence score, ranking score, or single OOS pass may authorize a live trade by itself.
The fail-closed production rule is:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> LIVE BUY/SELL.
Anything missing any stage must remain `WAIT / RESEARCH_ONLY`.

PR #19 `Fail closed all unvalidated production trade signals` passed Security and Reliability run `34142270947`, including unit tests, dependency vulnerability audit, static security scan and committed-secret rejection. It merged to `main` as `1a0004c31f1f8be570c72cfe0380a99994797316` and Render auto-deploy `dep-dafe5tvavr4c73c187n0` reached `live` successfully.

Live enforcement now includes:
- `production_validation.py` with an explicit exact-fingerprint live-validation registry;
- registry intentionally empty because no strategy has yet completed the full live-promotion process;
- `strategy_identity.py` deterministically binds symbol, production horizon, normalized family, required timeframes, strategy version, modeled trading cost and a SHA-256 of the backtest/feature/strategy implementation into one fingerprint;
- `engine.py` downgrades AI `TRADE` to `WAIT` unless the exact symbol+horizon+strategy-family key is explicitly live validated;
- `opportunity_engine.py` applies the same gate to 24h/7d dashboard opportunities;
- missing/unknown research identity fails closed;
- regression tests verify unpromoted AI TRADE output cannot become production TRADE.
Until a strategy completes the full promotion process, the correct production result is no BUY/SELL signal rather than an unvalidated trade. Existing database rows from scans before commit `1a0004c3...` can remain historically visible until replaced/refreshed; new production decisions are gated.

## ERROR MONITORING / SECURITY HARDENING
Production scans now expose their exact deterministic strategy fingerprint inside research-validation evidence. Changing the backtest, feature or strategy-family implementation changes the fingerprint automatically and invalidates any prior approval.
The 15-minute scan workflow validates the returned JSON rather than trusting HTTP 200 alone. It fails visibly on `ok != true`, empty universe/deep scan, AI failure, opportunity persistence failure, excessive symbol failures, a missing fingerprint, or any unvalidated `TRADE`. Failed response diagnostics are retained for seven days.
`operational_monitor.py` keeps a sanitized in-process record of the last scan and recent component error types. `/health` exposes this summary without exception messages, credentials or upstream response bodies. Protected API endpoints now log full exceptions server-side while returning generic public errors.
Security regression coverage, Bandit static analysis and dependency auditing remain enforced. This hardening passed 45 unit tests locally, Bandit, pip-audit with no known vulnerabilities, workflow YAML parsing and diff checks before publication.

## PREDICTION LEDGER / CONFIDENCE CALIBRATION
Every ranked 24h and 7d forecast is now recorded before its outcome in an append-only Supabase prediction ledger, including timestamp, deadline, direction, entry, score, regime, strategy identity, action and the calibration snapshot available at forecast time. Evaluation resolves each due forecast from the first hourly close at or after its fixed deadline and stores directional return plus correctness, preventing hindsight relabeling.
Calibration is separated by horizon and 10-point score bin, prefers regime-specific evidence once populated, and requires at least 30 comparable resolved forecasts. A 95% Wilson lower confidence bound must be at least 50% before calibration permits an otherwise fully approved live action. Missing, sparse or weak calibration always forces WAIT. Calibration can only restrict a signal; it cannot approve a strategy or bypass research, robustness, registry, risk or dual-signature gates.

## IMMUTABLE EVIDENCE / MULTI-APPROVAL PROMOTION
Research JSON is now wrapped in a canonical SHA-256 envelope. Any later modification to its payload fails integrity verification, and promotion manifests must reference at least three distinct valid SHA-256 research-artifact identities.
`live_promotions.json` is the canonical promotion manifest and is intentionally empty. `production_validation.py` no longer accepts a manually inserted fingerprint set. A live promotion must match the exact current strategy identity, mark every required stage true, and contain valid independent HMAC-SHA256 attestations from both Strategy Registry and Production Risk.
The two signing keys must be distinct secret environment variables with at least 32 characters: `STRATEGY_REGISTRY_SIGNING_KEY` and `PRODUCTION_RISK_SIGNING_KEY`. They are intentionally not configured/populated merely to make signals appear. Missing keys, missing stages, fewer than three research artifacts, modified identity/code, malformed data, or either bad signature all fail closed to `RESEARCH_ONLY`.
`tools/sign_promotion.py` applies exactly one role's attestation at a time. Promotion signing remains forbidden until the underlying evidence genuinely completes every stage. This layer passed 51 unit tests, Bandit and pip-audit with no known vulnerabilities before publication.

## DETERMINISTIC ROBUSTNESS / REPEATED-RUN EVIDENCE
Every strategy-family candidate now receives deterministic OOS robustness evidence before it can enter promotion review:
- 500 seeded bootstrap/Monte Carlo resamples requiring at least 80% positive outcomes, positive fifth-percentile aggregate return and <=25% 95th-percentile drawdown;
- independent ±10% entry-threshold perturbations, each requiring at least six trades and positive average return;
- multi-regime holdout testing across TREND, HIGH_VOL and RANGE, requiring at least two sufficiently represented regimes and positive average return in each;
- the original chronological train/validation/untouched-holdout quality gate must also pass.
Only candidates passing all checks receive `ROBUST_OOS`; they remain research-only.
Cloud research now uploads compact SHA-256-sealed evidence for 30 days. `research_aggregation.py` verifies envelopes, rejects tampering and non-robust results, and requires three distinct sealed runs before outputting `READY_FOR_STRATEGY_REGISTRY_REVIEW`. Aggregation explicitly sets `live_approved=false` and cannot bypass the dual-signature promotion manifest.

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
None are live-weighted. These passes alone do not satisfy the full live-validation requirement.

## 15-AGENT AUTONOMOUS ARCHITECTURE
PR #17 `Expand autonomous development to 15 cost-aware agents` merged as `b20d75f05a81ae8fe1814f515d3d4f99a58abd7d`; state sync PR #18 merged as `fd4863015992c646dec3f855a43f0b0542c8252a`.

The active architecture is 15 total roles: 1 Lead Integrator + 14 specialists:
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

### FIRST VALIDATED 15-AGENT HOURLY CYCLE
Scheduled Autonomous Specialist Agents run `34138477323` on SHA `fd4863015992c646dec3f855a43f0b0542c8252a` completed successfully.
Planner output explicitly contained all 14 specialist roles and assigned `NO_TASK` to all 14, with `Active specialist roles: []`. GitHub created only the planner runner; the specialist matrix job was skipped with zero steps. This validates that NO_TASK roles consume no worker model call or runner setup.
The workflow-run-triggered Autonomous Lead Integrator run `34138519231` completed successfully immediately afterward; fallback Lead run `34140804765` also completed successfully.
Because there was no candidate branch in this zero-worker validation cycle, candidate-SHA Security dispatch/review was not applicable.
This is the first green 15-agent cost-control cycle.

### FIRST FULL 14-SPECIALIST WORK CYCLE
Scheduled run `34151954385` completed successfully with the planner plus all 14 specialist jobs in approximately three minutes. Ten roles published candidate branches from the same main SHA. This exposed an efficiency defect: after one candidate changes main, the remaining same-base candidates become stale and cannot pass the exact-base Lead gate.
The orchestration now requires exactly one `CHANGE` role and thirteen read-only `AUDIT` roles per hourly cycle. All 14 specialists still work, but audit agents have no write tool, do not run fourteen redundant full test suites, and cannot publish branches. The sole change candidate still receives the complete test/security/Lead integration pipeline. This preserves continuous coverage while eliminating predictable stale-candidate waste.

## COST / 24-7 BEHAVIOR
The owner explicitly requested all 15 roles work every hour, 24/7, with cost-aware routing and verified-only autonomous integration.
- A separate always-on `continuous_coordinator.py` watchdog checks production health and this canonical handoff every minute. Normal operation uses zero AI tokens, exposes only sanitized status, has no market-scan/write/promotion/trade authority, and fails unhealthy after repeated observation failures. The 14 specialists remain event/hourly workers so idle model cost is not incurred.
- Continuous coordinator Render service `srv-dafgtead0e5s73cc7ekg` deployed commit `03e91acc6a3242cd99747de2910e161af251b2c0` as `dep-dafgteid0e5s73cc7ffg` and reached `live`. Its first observed `/health` response reported `production_ok=true`, `state_ok=true`, zero consecutive failures, `ai_calls_normal_operation=0`, and `trade_authority=false`.
- Autonomous specialist planner: minute 17 every hour, 24/7.
- Cloud research/backtesting/algo testing: hourly 24/7.
- Production market scans: approximately every 15 minutes.
- Autonomous Lead Integrator: after each specialist workflow plus minute 47 fallback.
- The planner must assign one bounded TASK to all 14 specialist roles each hourly cycle: exactly one mode=`CHANGE` and thirteen mode=`AUDIT`; safe work may finish `NO_CHANGE` rather than manufacture edits.
- Specialist parallelism is 14 so the full roster can work inside the hourly window.
- Deterministic Python remains preferred for calculation/backtesting/filtering; AI is for bounded planning/implementation/review.
- Planner and routine specialists use `gpt-5.6-luna`; testing-security, strategy-registry, portfolio-risk and production-signals use `gpt-5.6-sol`; the Lead Integrator and both independent integration reviews use `gpt-5.6-sol`.
- Official OpenAI model IDs and pricing were verified on 2026-09-07 before routing was implemented. Model pricing can change and should be rechecked before later routing changes.

## SAFETY INVARIANTS
Specialists work on isolated `auto/<role>/<run>` branches. `AI_STATE.md`, `agents/`, `.github/workflows/`, `requirements.txt`, and `Dockerfile` remain protected from specialist writes.
Candidate branches must pass full pytest, generated-cache cleanup and protected-path checks before publication.
Candidate publication explicitly dispatches Security and Reliability. Lead requires exact candidate SHA success, rejects protected or >80 KB diffs, and requires independent Security AI + Lead AI approval.
The owner explicitly enabled verified-only autonomous merging on 2026-09-07. `AUTONOMOUS_MERGE_ENABLED` is now true in the Lead workflow, but a candidate still cannot merge without full repository tests, exact-candidate-SHA Security and Reliability success, bounded/protected-path checks, independent Security AI approval, independent Lead AI approval, a final post-squash pytest pass, and a canonical `AI_STATE.md` update in the same commit.
Insufficient or unreliable evidence always means WAIT / NO TRADE / RESEARCH_ONLY.

## EXACT NEXT STEP
1. Verify the prediction-ledger migration, first production forecast inserts, due-outcome evaluator and protected `/calibration` endpoint on Render; confirm sparse calibration forces WAIT and no historical row is relabeled.
2. Verify the hardened release deploys successfully and the next production scan passes `tools/validate_scan_response.py`, produces no unvalidated `TRADE` / BUY / SELL decision, and exposes a healthy sanitized `/health` operational snapshot.
3. Keep `live_promotions.json` empty and signing keys unused until a strategy has completed repeated backtests, untouched OOS, robustness/stability, strategy-registry review and production-risk review; never sign from a single OOS pass or AI label.
4. Verify the next cloud research run produces SHA-256-sealed envelopes, deterministic robustness output and a sealed repeated-run aggregation artifact; never interpret `READY_FOR_STRATEGY_REGISTRY_REVIEW` as live approval.
5. Inspect research run `34079774231` artifact contents before any PONS-specific result claim or promotion.
6. Verify the first one-CHANGE/thirteen-AUDIT cycle runs all 14 roles, publishes no audit branches, creates at most one current-base candidate, and reduces redundant runner/test cost without weakening exact-SHA Security dispatch.
7. Verify the first automatic integration includes all required gates and updates this file in the same commit; fail closed on any missing check or stale candidate base.
8. Update this file again after every completed development/integration cycle.
