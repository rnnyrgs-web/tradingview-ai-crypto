# AI_STATE.md

Last reconciled: 2026-09-19T11:24Z
Last updated: 2026-09-19T11:24Z

This is the compact canonical handoff for `rnnyrgs-web/tradingview-ai-crypto`. Verify actual `main` SHA first on every run, then read `UNIFIED_PROFITABILITY_LEAD_SPEC.md`, `AGENTS.md`, `AUTONOMOUS_RESEARCH_DIRECTOR_STATUS.md`, `docs/ASTRA_BACKGROUND_WORKER.md`, strategy/rejected/coordination state including overrides, `orchestration/model_routing_policy.json`, current Money Intelligence / Big-Move artifacts, open PRs, active ownership, and exact-head CI. GitHub durable state outranks chat memory.

## MASTER OBJECTIVE

Find and rigorously validate at least one sustainable profitable after-cost algorithmic strategy, while independently improving scientifically defensible 90-day large-upside / 2x intelligence. Optimize compounded economic return, drawdown/tail-risk control, OOS robustness, execution realism and information gain. Never manufacture success, and never call an already-moved asset an early prediction.

## OVERNIGHT INTEGRATION PROGRAM

Sequential phases:
1. Profitability Learning + Strategy Evolution Engine.
2. Evolving Money Intelligence + Causal Repricing Engine.
3. Independent adversarial architecture review/fixes.
4. Permanent autonomous-loop integration.

**Earliest incomplete phase: PHASE 1. Phase 2 must not start yet.**

Phase 1 architecture is materially advanced, but acceptance still requires genuine runtime proof on the actual autonomous/deployed path: experiment -> reconciled after-cost trades/NAV -> profitability/risk analysis -> component/interaction learning -> failure/success classification -> durable memory -> evidence-based mission/admission re-ranking, with restart/replay/outage fail-closed behavior. Issue #438 is the durable acceptance contract.

## CURRENT CANONICAL STRATEGY RESULT

PR #442 is merged to canonical `main` as `9368dfe0d3f22573b5331b1086547c3884330b1b` after exact-head Security & Reliability success on PR head `722c2615f8b87368e84b7e576fe5cc853bb9c2cd` (run `35436865197`).

`DISC-BTC-LEADLAG-001-v1` is **REJECTED_PRE_OOS** on its exact frozen fingerprint. Do not tune or reopen it.

Frozen 3x-cost result:
- training pooled: 102 trades, mean net **-68.95 bps**, PF **0.420**;
- validation pooled: 24 trades, mean net **-113.69 bps**, PF **0.097**;
- ETH and SOL were both negative in train and validation;
- the primary was already negative at base cost;
- both fixed 35/65 bps falsifiers were negative;
- historical untouched OOS opened: **false**;
- genuine-forward evidence opened: **false**.

The predeclared underreaction component improved training compounded return by 6.03 percentage points versus its valid ablation, but the full strategy still lost 16.30% after costs. Treat that as **development-only component evidence**, not a rescue of v1. Useful parts may seed a NEW hypothesis only under a fresh fingerprint and fresh chronological validation.

PR #442 also fixed and regression-tested the evaluator -> `profitability_learning.complete_experiment` -> durable memory -> exact rejected-fingerprint admission-veto path. That is necessary Phase-1 wiring, but **MERGED/TESTED is not yet the same as live autonomous runtime acceptance**.

Durable negative memory now includes at least:
- `ACC-002`;
- `DATA-BASIS-001`;
- `DATA-FUNDING-001`;
- `DISC-VOL-BREAKOUT-001-v1`;
- `DISC-LIQUIDITY-MEANREV-001-v1`;
- `DISC-BTC-LEADLAG-001-v1`.

## OTHER STRATEGY LANES

- `active_deep_candidate`: **null**.
- `DISC-SQUEEZE-RETENTION-001-v1`: **BLOCKED_DATA_CONTRACT**, not strategy-rejected. DATA-004 found no scientifically defensible zero-new-cost timestamp-safe historical forced-flow source under the exact frozen Binance contract. Strategy outcomes/OOS were never opened.
- `DISC-RESIDUAL-MOMENTUM-001-v1`: **DEPRIORITIZED_EVIDENCE_LIMITED** because historical point-in-time membership is not verified.
- `DISC-FRIZZ-PLAYBIT-EMA-001-v1`: **BLOCKED_SOURCE_FINGERPRINT**. Never approximate or silently substitute existing FFRIZZ logic.
- No candidate may enter expensive deep validation unless it first passes a newly frozen, predeclared cheap screen under current scientific gates.

## PHASE 1 EXACT NEXT ACCEPTANCE ACTION

Continue issue #438 without duplicating already merged work. On an isolated branch, verify the merged `9368dfe...` evaluator/learning path through the **actual autonomous runtime/state channel**, not only unit/integration tests:

1. use only the already-opened train/validation evidence for the rejected BTC lead-lag experiment; do not open historical untouched OOS or genuine-forward data;
2. execute completion into the approved durable profitability-learning state channel;
3. prove the resulting failure/component memory is consumed by the real autonomous admission/mission-generation path, including exact-fingerprint veto and bounded component influence;
4. prove restart/re-entry/idempotency, duplicate/replay suppression, and configured-memory missing/corrupt/outage fail-closed behavior;
5. if the real runtime lacks a necessary dispatch/transport hook, implement the smallest bounded fix on an isolated branch with regression coverage;
6. require exact-head Security & Reliability before merge and actual deployed/runtime SHA verification before declaring Phase 1 complete.

Only after that proof may Phase 1 be marked complete and Phase 2 begin automatically.

## MONEY INTELLIGENCE / BIG-MOVE STATE

Independent Money Intelligence may continue when it cannot contaminate protected strategy evidence. The latest merged research cycle at cutoff `2026-09-19T10:49Z` deepened trust-to-ETF wrapper transmission using ZCSH/ZEC plus GBTC/ETHE controls. Key learning: ETF/wrapper **AUM, net creation flow, and marginal spot demand are different variables**; direction depends on cash vs in-kind sourcing, legacy-holder supply, free float/liquidity and leverage.

Current decision support remains **WAIT / AVOID CHASING** for ZEC after its extreme move, and **WAIT** for BTC pending stronger spot-led confirmation. There is still **no promotion-grade 90-day 2x candidate and no immutable forecast clearing the evidence bar**.

Do not infer "ETF conversion = bullish". Treat wrapper transmission as a mechanism whose sign must be measured with point-in-time creations/redemptions, sourcing mechanics and matched controls.

## OPEN INTEGRATION / INTEGRITY WORK

Older open PRs must be revalidated against current main before any integration; do not merge merely because an old exact-head CI run was green. Avoid duplicate work where a current PR/branch/run already owns the task.

PR #432 (strategy-discovery firewall), PR #433 (development-only Big-Move event lab), PR #441 (superseded older AI_STATE reconciliation), and other stale PRs are **not canonical merely because they are open**. Review them against current main and current scientific objectives before deciding whether to supersede, rebase, integrate, or close.

## PRESERVED DATA-BREADTH HANDOFF

- `COORD-DATA-005`: **DONE** — breadth evaluator integrated; historical point-in-time history unavailable.
- `COORD-DATA-006`: **DONE** — prospective point-in-time capture verified; no fabricated historical backfill.
- `COORD-DATA-007`: **BLOCKED** — wait for enough genuinely matured independent prospective cohorts.

Do not select another DATA-BREADTH candidate while `COORD-DATA-007` remains blocked on genuine prospective maturation. This legacy breadth maturation wait does not block strategy discovery.

Canonical specialist coordination must be loaded through `orchestration/coordination_overrides.py`, which applies the historical override ledger and the Lead reconciliation layer. Do **not** read only the base JSON.

## SAFETY INVARIANTS

- Broker disconnected; trade/promotion authority **OFF**.
- Do not rewrite historical predictions, frozen OOS, genuine-forward evidence, or rejected fingerprints.
- Use isolated branches for changes and require exact-head Security & Reliability before merge.
- Runtime-affecting work also requires actual deployed/runtime-SHA verification.
- Missing/stale/malformed/future/ambiguous evidence fails closed to WAIT / RESEARCH_ONLY.

## COST / MODEL ROUTING

- Broker disconnected; trade/promotion authority **OFF**.
- Combined variable paid-project ceiling remains approximately **$30/month** unless the user explicitly changes it.
- Supabase Pro is approved; preserve egress/query/window/throttling safeguards from PRs #413/#414.
- Deterministic Python/GitHub Actions first when possible.
- API routing: GPT-5.6 Luna/Terra/Sol only within approved budget.
- GPT-6 Astra belongs to Work/Codex, never the OpenAI API.
- One expensive deep strategy candidate at a time.
- Preserve chronology, point-in-time safety, realistic costs, robustness, multiple-testing controls, cross-engine checks where applicable, untouched OOS and genuine-forward gates.
- Missing/stale/malformed/future/ambiguous evidence fails closed to WAIT / RESEARCH_ONLY.

## STATUS

Current truth: **no validated profitable strategy; `DISC-BTC-LEADLAG-001-v1` rejected pre-OOS; no promotion-grade 90-day 2x candidate; Phase 1 not yet live-runtime accepted; Phase 2 gated; untouched OOS/forward for the rejected lead-lag fingerprint remain unopened; broker/live authority off.**

## EXACT NEXT STEP

Complete the Phase-1 acceptance action above through issue #438. Do not freeze a successor strategy or begin Phase 2 until the merged runtime path is proven on the actual durable/deployed channel, or a precise blocker is recorded.
