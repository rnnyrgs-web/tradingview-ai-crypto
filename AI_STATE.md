# AI_STATE.md

Last reconciled: 2026-09-18T23:03Z
Last updated: 2026-09-18T23:03Z

This is the authoritative compact handoff for agents working on `rnnyrgs-web/tradingview-ai-crypto`. Read the current default-branch `UNIFIED_PROFITABILITY_LEAD_SPEC.md` first and obey it as the exhaustive operating contract. Also obey the merged `SIGNAL_BACKTEST_CHARTS_SPEC.md`. When this file conflicts with an older chat summary, stale branch note, or stale base coordination row, verify current GitHub/runtime evidence and use the canonical coordination loader state.

## PRIMARY OBJECTIVE

Find and validate **one genuinely working strategy** with sustainable positive after-cost expectancy and useful frequency. At most one candidate may consume deep research/backtest/implementation capacity at a time. Broad cheap deterministic screening may select or reject candidates; unrelated broad sweeps, dashboard polish, agent-count growth, and work created merely to keep workers busy are secondary.

Profitability means net expectancy after realistic fees, spread, slippage, funding/carry, adverse selection, missed fills, market impact, drawdown/risk, and uncertainty. Backtests are research evidence, not real profit. Headline accuracy and trade count are not objectives by themselves.

## CURRENT CANONICAL STATE

- Reconciled GitHub `main`: **`c897f0eed8dd286c2f28c9470599919aa479174d`**, a GitHub-verified merge commit for PR #388.
- PR #388 is merged. It quarantines the unfocused legacy hourly Cloud Crypto Research matrices so they cannot bypass the canonical one-strategy/OOS controls. This is containment/cost/scientific-integrity work, not profitability evidence.
- Both Render services (`crypto-continuous-coordinator` and `tradingview-ai-crypto`) were verified **live on exact commit `c897f0ee...`** after that merge.
- `main` is still not branch-protected. Direct commits therefore remain a governance/integration risk; always verify actual head before acting and require exact-head validation for proposed changes.
- Canonical lifecycle remains **SELECTION** with **no active strategy candidate frozen**.
- Broker/live authority remains **OFF**. Research/paper/shadow only. `live_promotions.json` must remain empty unless every canonical gate and explicit authorization allow otherwise.
- Combined variable paid-project ceiling remains approximately **$30/month total** across approved paid project resources. Do not raise it or add paid services without explicit user authorization.

## CURRENT PROFITABILITY EVIDENCE — NO VALIDATED EDGE YET

The freshest recorded focused ACC-002 selection evidence on 2026-09-18 rejected all three predeclared 24h relative-strength variants **before untouched OOS**:

- `(4,16,64)`: failed stability; 0/2 supported liquidity subsets passed.
- `(6,24,72)`: Top-30 looked positive under the recorded stress screen, but Top-15 failed; only 1/2 subsets passed, so the candidate is **ineligible**.
- `(8,32,96)`: failed stability; 0/2 supported liquidity subsets passed.

Therefore **zero candidate was selected and untouched OOS remains unopened**. Do not cherry-pick the positive Top-30 `(6,24,72)` result, relax the two-subset rule, or open OOS for a failed candidate.

The screen itself is still **exploratory / not promotion-grade scientific evidence** because the exact raw dataset was not durably bound to an immutable dataset hash/archive, the exact source time window was not fully persisted in the bounded summary, and the historical universe was current-survivor based rather than verified point-in-time membership. The evidence-envelope hash is not a substitute for a raw-dataset hash.

Latest recorded mixed paper-account snapshot in issue #112 was losing overall and explicitly **not strategy-specific forward proof**. Treat that snapshot as stale unless refreshed from authentic runtime state; never use it to rescue a candidate.

## SINGLE HIGHEST-VALUE BOTTLENECK

The highest-value blocker to finding the one strategy is now **scientifically reproducible selection evidence**, not more engine scaffolding or more strategy variants.

Before spending another untouched holdout or widening the hypothesis search, ACC-002 must produce an immutable, audit-ready selection artifact that binds the exact data actually scored. At minimum it must persist:

1. exact source venue/instrument/bar identity per symbol;
2. exact first/last timestamp and observation count per scored symbol;
3. exact requested ranked universe and missing symbols, without rank substitution;
4. point-in-time membership provenance/status and an explicit fail-closed survivorship verdict;
5. a canonical SHA-256 over the exact normalized source rows used by the screen (or an immutable archive reference plus hash);
6. train/validation/locked-OOS **timestamp** boundaries, not only array indices;
7. the declared candidate grid/trial count and full pre-OOS selection predicate;
8. every predicate component and failure reason, including validation max-cost positive-net-spread rate;
9. realistic cost assumptions/stress and an explicit statement that the spread proxy is not executable portfolio P&L;
10. `research_only=true`, `trade_authority=false`, untouched OOS locked in SELECTION mode.

If point-in-time membership is unavailable, the artifact must say so and remain non-promotable; never reconstruct historical membership from today's survivors.

## EXACT NEXT STEP

**Do not add another strategy family or tune the failed three ACC-002 variants yet.** Implement/validate the immutable ACC-002 dataset + selection-evidence contract above on an isolated branch, with regression tests proving that provenance/hash/split metadata cannot be silently omitted or mutated and that SELECTION mode cannot open OOS. Then rerun only the already-declared focused screen on the frozen evidence input. If all candidates still fail, reject that screen cleanly and move to the next materially distinct, predeclared economic mechanism rather than parameter-mining the same family.

A 24h lane remains preferable while 7d history/point-in-time evidence is weaker. Genuine prospective point-in-time cohorts from DATA-BREADTH-001 must continue maturing naturally; never backfill them.

## CROSS-ENGINE / INFRASTRUCTURE STATUS

- PRs #390–#392 established research-only VectorBT/Nautilus/LEAN reconciliation infrastructure. This is validation tooling, not an edge.
- Draft PR #394 hardens mismatched/replayed/malformed engine-evidence rejection. Its exact head has passed both Security & Reliability and Research Engines CI, but it remains infrastructure work and must not displace the ACC-002 evidence bottleneck or be called profitability progress.
- Draft PRs #387/#389 remain scientifically/economically blocked unless their scope becomes necessary for the single selected candidate. Do not merge broad backtesting infrastructure merely because tests are green.
- Claude/Claude Code and deterministic workers are subordinate to this same single-candidate mission. Do not reset retry/failure counters merely to manufacture activity.

## BACKTEST / EVIDENCE CHART CONTRACT

`SIGNAL_BACKTEST_CHARTS_SPEC.md` is canonical. For every signal/strategy chart:

- target 10 years only where defensible; otherwise show exact complete available coverage;
- show after-cost strategy equity vs benchmark, drawdown, visible train/validation/untouched-OOS/genuine-forward boundaries, rolling evidence/sample counts, and regime/year breakdowns;
- preserve immutable strategy/version identity and provenance;
- never fabricate unavailable history or executable bid/ask spreads;
- never rewrite frozen OOS or forward evidence;
- never let an attractive curve bypass promotion gates.

Until a scientifically valid artifact exists, the dashboard must fail closed with **`BACKTEST CHART NOT YET VERIFIED` / `INSUFFICIENT EVIDENCE`** rather than display a misleading performance curve. Issue #381 tracks that UI contract, but dashboard work is secondary to producing valid underlying evidence.

## SAFETY / SCIENTIFIC INVARIANTS

- Broker disconnected; no real-order authority.
- Existing $100,000 paper ledger remains authentic/append-only; never reset, reseed, rewrite, or cosmetically improve it.
- Code changes on isolated branches only.
- Confirmed defects get regression coverage where practical.
- Require exact-head **Security and Reliability** green before merge; runtime-affecting changes also require exact deployed-SHA verification.
- Missing, stale, malformed, future, ambiguous, provenance-uncertain, or scientifically insufficient evidence fails closed to WAIT / RESEARCH_ONLY.
- Never weaken chronology, purging, non-overlap, untouched OOS/forward boundaries, multiple-testing controls, point-in-time universe safety, cost realism, abstention, or promotion gates to obtain a pass.
- One promising backtest/OOS result grants no production, broker, paper-authority, or promotion authority.
- If the predefined rigorous evidence/validation criteria are genuinely satisfied, report that successful result clearly with exact supporting evidence and limitations.

## DURABLE NEGATIVE RESULTS — DO NOT RESCUE

- `DATA-BASIS-001`: rejected. Recorded 24h OOS average net about **-8.49 bps** over 134 independent samples; 7d about **-51.21 bps** over 19 samples. Do not tune/relabel/reopen the same fingerprint.
- `DATA-FUNDING-001`: rejected current fingerprint. Its superficially positive 24h headline had **0 incremental expectancy versus the frozen training-only baseline** and unstable halves; 7d lacked the evidence floor. Do not rescue it.
- Historical Binance/Bybit OI routes previously returned access blocks (451/403). Do not repeatedly burn capacity on unchanged blocked routes unless access conditions materially change.
- DATA-BREADTH-001 prospective point-in-time capture is valid only prospectively. Its future cohorts must mature naturally; no historical survivor reconstruction.

## RESEARCH DISCIPLINE

For every new candidate/experiment: state the economic mechanism before outcomes; freeze the immutable fingerprint and training-only decisions; bind the exact dataset/provenance; use chronological purged splits and non-overlapping full-horizon observations; keep horizons separate; compare to a frozen baseline; report incremental after-cost value; stress realistic costs/execution; test parameter/subperiod/liquidity/regime stability; account for search breadth; preserve negative results; and require genuine forward evidence before promotion.

Missed profitable moves and losing trades should become falsifiable hypotheses, not ad-hoc threshold edits. If the cleanest action is to wait for independent forward evidence, wait.
