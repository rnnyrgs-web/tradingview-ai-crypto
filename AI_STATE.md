# AI_STATE.md

Last reconciled: 2026-09-19T14:21Z
Last updated: 2026-09-19T14:21Z

This is the compact canonical handoff for `rnnyrgs-web/tradingview-ai-crypto`. Verify actual `main` SHA first on every run, then read `UNIFIED_PROFITABILITY_LEAD_SPEC.md`, `AGENTS.md`, `AUTONOMOUS_RESEARCH_DIRECTOR_STATUS.md`, `docs/ASTRA_BACKGROUND_WORKER.md`, strategy/rejected/coordination state including overrides, `orchestration/model_routing_policy.json`, current Money Intelligence / Big-Move artifacts, open PRs, active ownership and exact-head CI. GitHub durable state outranks chat memory.

## MASTER OBJECTIVE

Find and rigorously validate at least one sustainable profitable after-cost algorithmic strategy while independently improving scientifically defensible 90-day large-upside / 2x intelligence. Optimize compounded economic return, drawdown/tail-risk control, OOS robustness, execution realism and information gain. Never manufacture success and never retroactively call an already-moved asset an early prediction.

## OVERNIGHT INTEGRATION PROGRAM

Sequential phases:
1. Profitability Learning + Strategy Evolution Engine.
2. Evolving Money Intelligence + Causal Repricing Engine.
3. Independent adversarial architecture review/fixes.
4. Permanent autonomous-loop integration.

**Earliest incomplete phase: PHASE 1. Phase 2 must not start yet.**

## PHASE 1 INTEGRATION STATE

PR #446 (`Add exact deployed Profitability Learning runtime acceptance`) was independently reviewed and merged. Exact reviewed head: `b18c20f464ada4b03834a7cd0a3d9e4f621abb8c`; exact-head Security & Reliability run `35446478010` passed with 1,112 tests passed / 2 skipped plus dependency audit, Bandit and secret scan. The two prior acceptance defects were fixed before integration: replay idempotency is target-row scoped and unrelated concurrent appends are allowed; mission acceptance requires an exact-provenance `LEARN` mission from the sealed training experiment.

Integration merge on `main`: `f3ab73e5714be23d82295a0f79ea606cf5d13528`. Post-merge Security & Reliability `verify` run `35448367392` passed on that exact SHA.

Merged runtime-acceptance path now:
- exposes a POST-only, `X-Scan-Secret`-protected acceptance endpoint with no caller-selected research payload;
- binds to the sealed rejected `DISC-BTC-LEADLAG-001-v1` artifact, frozen contract SHA, frozen dataset SHA and `PRE_OOS_FAIL` state;
- replays only already-inspected train/validation evidence through the real durable `persist_selection` path;
- requires durable memory availability, target-scoped idempotency, `LEARN_AND_PIVOT`, component evidence, an exact-training-provenance learning mission, canonical rejected-fingerprint memory and zero heavy-dispatch admission for the rejected exact fingerprint;
- requires a valid deployed `RENDER_GIT_COMMIT` and preserves untouched OOS / genuine-forward locks plus broker/trade/promotion-off boundaries.

**Phase 1 is still NOT complete.** Merged code and CI are necessary but insufficient; issue #438 remains the durable acceptance contract.

## PHASE 1 EXACT NEXT ACCEPTANCE ACTION

Do not duplicate PR #446. The next action is deployed-runtime proof against the exact currently deployed `main` SHA:

1. wait until the deployed service reports the exact current `main` SHA through `RENDER_GIT_COMMIT`;
2. dispatch `.github/workflows/profitability-learning-runtime-acceptance.yml` (`Profitability Learning Runtime Acceptance`) on `main`;
3. require the workflow attestation to prove the deployed SHA equals the workflow `GITHUB_SHA`;
4. independently inspect the two exact target durable experiment rows and confirm one-row multiplicity, stable input/full-row digests and exact replay idempotency;
5. confirm both completions classify `LEARN_AND_PIVOT`, component evidence exists, at least one `LEARN` mission has `source_experiment_id` equal to the exact sealed training experiment, the exact rejected fingerprint remains rejected and heavy admission selects zero copies of it;
6. preserve restart/re-entry/replay/contention and configured-memory missing/corrupt/outage fail-closed behavior;
7. do not open historical untouched OOS or genuine-forward evidence and do not enable broker/trade/promotion authority.

Only a passing exact-deployed-SHA acceptance plus independent durable-row inspection may complete Phase 1 and unlock Phase 2.

## CURRENT CANONICAL STRATEGY RESULT

`DISC-BTC-LEADLAG-001-v1` remains **REJECTED_PRE_OOS** on its exact frozen fingerprint. Do not tune, rescue or reopen it.

Frozen 3x-cost result:
- training pooled: 102 trades, mean net **-68.95 bps**, PF **0.420**;
- validation pooled: 24 trades, mean net **-113.69 bps**, PF **0.097**;
- ETH and SOL negative in both train and validation;
- primary negative already at base cost;
- fixed 35/65 bps falsifiers negative;
- historical untouched OOS opened: **false**;
- genuine-forward evidence opened: **false**.

The predeclared underreaction component improved development-only training performance versus its valid ablation, but the full strategy still lost materially after costs. Useful parts may seed a **new** hypothesis only under a fresh fingerprint and fresh chronological validation; they cannot rescue v1.

Durable negative memory includes at least `ACC-002`, `DATA-BASIS-001`, `DATA-FUNDING-001`, `DISC-VOL-BREAKOUT-001-v1`, `DISC-LIQUIDITY-MEANREV-001-v1` and `DISC-BTC-LEADLAG-001-v1`.

## OTHER STRATEGY LANES

- `active_deep_candidate`: **null**.
- `DISC-SQUEEZE-RETENTION-001-v1`: **BLOCKED_DATA_CONTRACT**, not strategy-rejected; do not substitute venues/proxies to rescue it.
- `DISC-RESIDUAL-MOMENTUM-001-v1`: **DEPRIORITIZED_EVIDENCE_LIMITED** because historical point-in-time membership is unverified.
- `DISC-FRIZZ-PLAYBIT-EMA-001-v1`: **BLOCKED_SOURCE_FINGERPRINT**; never approximate or silently substitute existing FFRIZZ logic.
- No candidate enters expensive deep validation without a newly frozen predeclared cheap screen under current scientific gates.

## MONEY INTELLIGENCE / BIG-MOVE STATE

Independent Money Intelligence may continue only when it cannot contaminate protected strategy evidence. Latest persisted research cycle cutoff is `2026-09-19T13:37:53Z`.

Current evidence does **not** justify a promotion-grade 90-day 2x forecast:
- BTC: Sep. 18 regulated spot-vehicle demand is corroborated, but the five-session flow is approximately flat; state remains WAIT / tactical-momentum research.
- ETH: Sep. 18 inflow improved, but the completed-looking weekly regulated flow remains negative; WAIT.
- SOL: strongest recent regulated-flow intensity relative to market cap among BTC/ETH/SOL in the preserved snapshot, but evidence is one-week and issuer-concentrated; HOLD / WAIT FOR VALIDATION, not a frozen BUY or 2x call.
- ZEC/privacy complex: extreme move remains a causal-research case; avoid chasing and do not rewrite it as an early prediction.

No immutable new forecast currently clears the evidence bar.

## OPEN INTEGRATION / INTEGRITY WORK

Older PRs must be revalidated against current main before any integration. Do not merge merely because an old CI run was green. PR #441 is this AI_STATE reconciliation branch; older state in its prior commits was superseded when the branch was reset onto `f3ab73e...`. Other stale PRs such as #432/#433 remain non-canonical until independently re-reviewed against current objectives and current main.

Canonical specialist coordination must be loaded through `orchestration/coordination_overrides.py`; do not rely on base JSON alone.

## PRESERVED DATA-BREADTH HANDOFF

- `COORD-DATA-005`: **DONE** — breadth evaluator integrated; historical point-in-time history unavailable.
- `COORD-DATA-006`: **DONE** — prospective point-in-time capture verified; no fabricated historical backfill.
- `COORD-DATA-007`: **BLOCKED** — wait for enough genuinely matured independent prospective cohorts.

Do not select another DATA-BREADTH candidate while `COORD-DATA-007` remains blocked on genuine prospective maturation. This legacy maturation wait does not block independent strategy discovery or Phase-1 runtime acceptance.

## SAFETY INVARIANTS

- Broker disconnected; trade/promotion authority **OFF**.
- Do not rewrite historical predictions, frozen OOS, genuine-forward evidence or rejected fingerprints.
- One expensive deep strategy candidate at a time.
- Preserve chronology, point-in-time safety, realistic costs, robustness, multiple-testing controls, cross-engine checks where applicable, untouched OOS and genuine-forward gates.
- Missing/stale/malformed/future/ambiguous evidence fails closed to WAIT / RESEARCH_ONLY.
- Combined variable paid-project ceiling remains approximately **$30/month** unless the user explicitly changes it.
- Supabase Pro is approved; preserve egress/query/window/throttling safeguards from PRs #413/#414.
- Deterministic Python/GitHub Actions first; API routing uses GPT-5.6 Luna/Terra/Sol within budget. GPT-6 Astra belongs to Work/Codex, never the OpenAI API.

## STATUS

Current truth: **no validated profitable strategy; `DISC-BTC-LEADLAG-001-v1` rejected pre-OOS; no promotion-grade 90-day 2x candidate; Phase 1 code integration is materially advanced and PR #446 is merged, but exact deployed-runtime acceptance is not yet proven; Phase 2 remains gated; untouched OOS/forward remain locked; broker/live authority remains off.**

## EXACT NEXT STEP

Complete the exact deployed-SHA Phase-1 acceptance through issue #438. Do not begin Phase 2 or freeze a successor strategy merely to keep activity high. If deployed acceptance is temporarily waiting, continue only independent non-contaminating research work and preserve the exact next runtime action durably.
