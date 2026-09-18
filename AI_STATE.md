# AI_STATE.md

Last reconciled: 2026-09-18T23:46Z
Last updated: 2026-09-18T23:46Z

This is the authoritative compact handoff for agents working on `rnnyrgs-web/tradingview-ai-crypto`. Read the current default-branch `UNIFIED_PROFITABILITY_LEAD_SPEC.md` first and obey it as the exhaustive operating contract. Also obey the merged `SIGNAL_BACKTEST_CHARTS_SPEC.md`. When this file conflicts with an older chat summary, stale branch note, or stale base coordination row, verify current GitHub/runtime evidence and use the canonical coordination loader state. Do **not** read only the base JSON and treat an overridden historical task row as current.

## PRIMARY OBJECTIVE

Find and validate **one genuinely working strategy** with sustainable positive after-cost expectancy and useful frequency. At most one candidate may consume deep research/backtest/implementation capacity at a time. Broad cheap deterministic screening may select or reject candidates; unrelated broad sweeps, dashboard polish, agent-count growth, and work created merely to keep workers busy are secondary.

Profitability means net expectancy after realistic fees, spread, slippage, funding/carry, adverse selection, missed fills, market impact, drawdown/risk, and uncertainty. Backtests are research evidence, not real profit. Headline accuracy and trade count are not objectives by themselves.

## CURRENT CANONICAL STATE

- Verified GitHub `main` at reconciliation start: **`7a3fabe1abf13afcd6f29ff46b23281dc8df9d93`**, merge commit for PR #398. Re-verify actual head before every write/merge because `main` remains unprotected.
- PR #396 merged immutable ACC-002 evidence-contract helpers. PR #397 merged the fail-closed fixed 24h ACC-002 selection-audit runner/workflow. PR #398 reconciled their handoff state.
- The exact post-merge ACC-002 audit from main `6e95408c88b389bbb100bb8841a97695b785ef9a` has now been retrieved and inspected directly from GitHub Actions workflow run `35405308190`, artifact id `10572248517`.
- The artifact ZIP digest is `sha256:5ad033ac97e057aafea0f4e72faca08c52ee19547f584c050f3ecf1126965efd`; the sealed audit payload hash is `e3df4729d0dee344912f53b27e096ef3ddad9610169e904372397d8f27becb03`.
- PR #400 predeclares the next bounded selection hypothesis in `orchestration/acc003_breakout_candidate.json` with fingerprint `113697e7dd7e22b38e86975bdbaddc8d1167d4b75693d1021b15272a80bf4529`; until #400 is merged, that contract is proposed state, not default-branch functionality or evidence.
- Both Render services were last independently verified live on exact commit `c897f0ee...` after PR #388. Do not claim a newer production deployment without exact deployed-SHA evidence.
- Canonical lifecycle remains **SELECTION** with **no active strategy candidate frozen**.
- Broker/live authority remains **OFF**. Research/paper/shadow only. `live_promotions.json` remains empty.
- Combined variable paid-project ceiling remains approximately **$30/month total**. Do not raise it or add paid services without explicit authorization.

## CURRENT PROFITABILITY EVIDENCE — ACC-002 FIXED SCREEN REJECTED

The sealed audit is reproducible and fail-closed:

- source generated at `2026-09-18T23:25:41.221624+00:00`;
- 1H OKX completed-history data;
- exact normalized dataset SHA-256 `896a127376c80972d07f58ca605a5673f186a2d9ea7ffda8f5266dc67b11890e`;
- exact coverage `2026-05-17T00:00:00Z` through `2026-09-18T22:00:00Z`;
- 83,972 normalized rows; 30 ranked symbols; 28 scored symbols;
- declared round-trip cost 12 bps, stressed at 1x / 1.5x / 2x / 3x;
- every recorded pre-OOS result reproduced from the captured normalized rows;
- untouched OOS remained `LOCKED_UNTOUCHED_OOS`; opened-candidate count = 0;
- `research_only=true`, `trade_authority=false`, `promotion_authority=false`.

All three frozen 24h ACC-002 configurations fail the unchanged two-subset selection/stability rule:

- `(4,16,64)`: Top-15 FAIL; Top-30 FAIL; **0/2** supported subsets pass.
- `(6,24,72)`: Top-15 FAIL; Top-30 FAIL; **0/2** supported subsets pass. Both supported subsets fail the **training** positive-rank-IC and 3x-cost net-spread requirements despite positive validation snapshots. Do not cherry-pick validation.
- `(8,32,96)`: Top-15 FAIL; Top-30 FAIL; **0/2** supported subsets pass.

The sealed selection result is therefore `eligible_candidate_count=0`, `selected_candidate_present=false`, and `eligible_for_promotion_review=false`. This fixed ACC-002 screen is **REJECTED AT SELECTION**. Do not tune/rescue the three fingerprints, relax the two-subset rule, rename the same economic mechanism, or open their untouched OOS.

The dataset is still non-promotable on provenance even if a pre-OOS row had looked attractive: historical point-in-time universe membership has 0 covered and 83,972 uncovered observations, `survivorship_safe=false`, and `promotion_allowed=false`.

The latest recorded mixed paper-account snapshot remains losing overall and is not strategy-specific forward proof. Refresh only from authentic runtime evidence; never use paper aggregate P&L to rescue a rejected research fingerprint.

## SINGLE HIGHEST-VALUE BOTTLENECK

The prior ACC-002 reconciliation bottleneck is closed. The highest-value bottleneck is now **executing one materially distinct, low-cost selection screen with cleaner timestamp-safe evidence without spending untouched OOS on another failed family**.

Ranked next lanes:

1. **ACC-003 fixed-asset compression-breakout screen, 24h first.** PR #400 predeclares one exact BTC/ETH hypothesis before outcome inspection. This is economically distinct from cross-sectional relative-strength, avoids historical survivor-membership reconstruction, adds no paid data service, and is cheap to falsify before OOS. Treat trend/breakout literature as hypothesis support only; recent evidence is mixed and vanilla crypto time-series momentum may have decayed.
2. **ACC-001 prospective microstructure/execution lane.** Potentially valuable but currently blocked until genuinely prospective forecast-time microstructure fields mature through the evidence path; do not reconstruct history.
3. **ACC-004 ensemble weighting.** Premature while there is no independently validated component strategy; do not optimize an ensemble of unproven lanes.

Cross-sectional reversal/residual-momentum ideas may remain research hypotheses, but they inherit a heavier point-in-time universe/survivorship burden and therefore should not outrank the simpler fixed-asset screen right now.

## EXACT NEXT STEP

After PR #400 passes exact-head validation and becomes canonical, implement and execute **exactly** `orchestration/acc003_breakout_candidate.json` without viewing outcomes before the contract is frozen. Do not alter its primary rule or promote a sensitivity variant into the candidate after seeing results.

The frozen screen is BTC-USDT and ETH-USDT, 1H completed OKX bars, 24h primary horizon, one daily non-overlapping decision, 72h breakout after causal low-volatility compression, 12 bps base round-trip cost with 1x/2x/3x stress, a frozen no-compression breakout baseline, chronological 60/40 train/validation with a 24h purge, exact dataset identity/hash binding, minimum per-asset evidence floors, and untouched OOS locked. Request the complete available normalized history up to the frozen 50,000-bar-per-asset bound and require at least 17,520 normalized hourly bars for each asset; if that minimum is unavailable, report `INSUFFICIENT_EVIDENCE` rather than silently shortening the contract. Report exact returned coverage and never synthesize older history. The four predeclared sensitivity checks are falsifiers only and have no selection authority.

If the clean pre-OOS screen fails any frozen gate or lacks the evidence floor, reject/mark insufficient without tuning or rescuing it and keep OOS closed. If it genuinely passes every frozen gate, freeze the exact candidate and exact dataset identity before requesting untouched OOS. Continue genuine prospective DATA-BREADTH-001 cohorts naturally in parallel; never backfill them. Keep the dashboard evidence view fail-closed until scientifically valid chart artifacts exist.

## CANONICAL DATA-MARKET HANDOFF

The coordination loader applies the durable base plus later append-only overrides. Do **not** read only the base JSON and infer that an older READY row is still current.

- `COORD-DATA-005`: **DONE**. DATA-BREADTH-001 selection/falsifier work completed under the frozen contract.
- `COORD-DATA-006`: **DONE**. Prospective point-in-time universe capture integrated and independently verified.
- `COORD-DATA-007`: **BLOCKED** until genuinely prospective point-in-time cohorts mature into sufficient independent non-overlapping 24h/7d outcomes.

Do not select another data candidate while DATA-BREADTH-001 awaits that evidence. Never backfill or reconstruct missing historical membership from current survivors.

## CROSS-ENGINE / WORKER STATUS

- PRs #390–#392 are research-only VectorBT/Nautilus/LEAN reconciliation infrastructure, not an edge.
- Draft PR #394 hardens mismatched/replayed/malformed engine evidence and has green exact-head validation, but infrastructure work must not displace the next falsification-oriented strategy screen.
- Claude signal-accuracy runner has repeatedly returned BLOCKED and is currently paused after a model-execution failure; do not reset merely to create activity.
- Claude Code testing/security runner remains stale at `COORD-TEST-001` after six failed reserved attempts with `TASK_RETRY_LIMIT`; do not reset without a concrete high-EV reason.
- Deterministic/specialist state must remain subordinate to the one-candidate mission. `live_promotions.json` is empty.

## BACKTEST / EVIDENCE CHART CONTRACT

`SIGNAL_BACKTEST_CHARTS_SPEC.md` is canonical. For every signal/strategy chart:

- target 10 years only where defensible; otherwise show exact complete available coverage;
- show after-cost strategy equity vs benchmark, drawdown, visible train/validation/untouched-OOS/genuine-forward boundaries, rolling evidence/sample counts, and regime/year breakdowns;
- preserve immutable strategy/version identity and provenance;
- never fabricate unavailable history or executable bid/ask spreads;
- never rewrite frozen OOS or forward evidence;
- never let an attractive curve bypass promotion gates.

Until a scientifically valid artifact exists, the dashboard must fail closed with **`BACKTEST CHART NOT YET VERIFIED` / `INSUFFICIENT EVIDENCE`** rather than display a misleading performance curve. Issue #381 tracks the UI contract, but chart/UI work remains secondary to valid underlying strategy evidence.

## SAFETY INVARIANTS

- Broker disconnected; no real-order authority.
- Existing $100,000 paper ledger remains authentic/append-only; never reset, reseed, rewrite, or cosmetically improve it.
- Code/state changes on isolated branches only.
- Confirmed defects get regression coverage where practical.
- Require exact-head **Security and Reliability** green before merge; runtime-affecting changes also require exact deployed-SHA verification.
- Missing, stale, malformed, future, ambiguous, provenance-uncertain, or scientifically insufficient evidence fails closed to WAIT / RESEARCH_ONLY.
- Never weaken chronology, purging, non-overlap, untouched OOS/forward boundaries, multiple-testing controls, point-in-time universe safety, cost realism, abstention, or promotion gates to obtain a pass.
- One promising backtest/OOS result grants no production, broker, paper-authority, or promotion authority.

## DURABLE NEGATIVE RESULTS — DO NOT RESCUE

- `ACC-002` fixed 24h cross-sectional relative-strength screen `(4,16,64)`, `(6,24,72)`, `(8,32,96)`: **rejected at selection** on sealed exact-data audit; all three have 0/2 supported liquidity subsets passing and untouched OOS remains locked. Do not retune/relabel/reopen these fingerprints.
- `DATA-BASIS-001`: rejected. Recorded 24h OOS average net about **-8.49 bps** over 134 independent samples; 7d about **-51.21 bps** over 19 samples. Do not tune/relabel/reopen the same fingerprint.
- `DATA-FUNDING-001`: rejected current fingerprint. Its superficially positive 24h headline had **0 incremental expectancy versus the frozen training-only baseline** and unstable halves; 7d lacked the evidence floor. Do not rescue it.
- Historical Binance/Bybit OI routes previously returned access blocks (451/403). Do not repeatedly burn capacity on unchanged blocked routes unless access conditions materially change.
- DATA-BREADTH-001 prospective point-in-time capture is valid only prospectively. Its future cohorts must mature naturally; no historical survivor reconstruction.

## RESEARCH DISCIPLINE

For every new candidate/experiment: state the economic mechanism before outcomes; freeze the immutable fingerprint and training-only decisions; bind the exact dataset/provenance; use chronological purged splits and non-overlapping full-horizon observations; keep horizons separate; compare to a frozen baseline; report incremental after-cost value; stress realistic costs/execution; test parameter/subperiod/liquidity/regime stability; account for search breadth; preserve negative results; and require genuine forward evidence before promotion.

Missed profitable moves and losing trades should become falsifiable hypotheses, not ad-hoc threshold edits. If the cleanest action is to wait for independent forward evidence, wait.
