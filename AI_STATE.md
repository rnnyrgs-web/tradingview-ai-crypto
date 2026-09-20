# AI_STATE.md

Last reconciled: 2026-09-20T00:56Z
Last updated: 2026-09-20T00:56Z

This is the compact canonical handoff for `rnnyrgs-web/tradingview-ai-crypto`. Verify actual `main` SHA first on every run, then read `UNIFIED_PROFITABILITY_LEAD_SPEC.md`, `AGENTS.md`, `AUTONOMOUS_RESEARCH_DIRECTOR_STATUS.md`, `docs/ASTRA_BACKGROUND_WORKER.md`, strategy/rejected/coordination state including overrides, `orchestration/model_routing_policy.json`, current Money Intelligence / Big-Move artifacts, open PRs, active ownership and exact-head CI. GitHub durable state outranks chat memory.

## MASTER OBJECTIVE

Find and rigorously validate at least one sustainable profitable after-cost algorithmic strategy while independently improving scientifically defensible 90-day large-upside / 2x intelligence. Optimize compounded economic return, drawdown/tail-risk control, OOS robustness, execution realism and information gain. Raw win rate and trade count are diagnostic only. Failure means explain -> learn -> preserve -> evolve -> continue; never manufacture success and never retroactively call an already-moved asset an early prediction.

## OVERNIGHT INTEGRATION PROGRAM

Sequential phases:
1. Profitability Learning + Strategy Evolution Engine — **COMPLETE**.
2. Evolving Money Intelligence + Causal Repricing Engine — **COMPLETE on runtime evidence; canonical state transition pending independent integration of this reconciliation**.
3. Independent adversarial architecture review/fixes — **NEXT**; durable contract issue #462.
4. Permanent autonomous-loop integration — gated on Phase 3.

When this reconciliation is on `main`, the earliest incomplete phase is **PHASE 3**. Do not resume ordinary strategy/2x expansion ahead of the Phase-3 adversarial review unless it is genuinely non-duplicative and does not consume the active deep/audit lane.

## PHASE 1 — VERIFIED COMPLETE

The Profitability Learning + Strategy Evolution Engine passed exact-deployed-SHA production acceptance. Its sealed BTC lead-lag training/validation evidence remains a negative scientific result, not profitability evidence.

Key production evidence:
- canonical accepted Phase-1 SHA: `6d8dce267e35f079c7e91d7538419509bd2d059e`;
- `Profitability Learning Runtime Acceptance` run `35454496075`: **SUCCESS** on that exact deployed SHA;
- target experiment rows persisted and replayed idempotently;
- training and validation classified `LEARN_AND_PIVOT` from truthful after-cost evidence;
- component learning produced evidence-based successor-research input without rescuing the rejected exact fingerprint;
- untouched OOS and genuine-forward evidence remained unopened;
- broker/trade/promotion authority remained false.

Issue #438 is completed. Phase 1 completion does not imply a profitable strategy.

## CURRENT STRATEGY TRUTH

`DISC-BTC-LEADLAG-001-v1` remains **REJECTED_PRE_OOS** on its exact frozen fingerprint. Do not tune, rescue or reopen it.

Frozen 3x-cost result:
- training pooled: 102 trades, mean net **-68.95 bps**, PF **0.420**;
- validation pooled: 24 trades, mean net **-113.69 bps**, PF **0.097**;
- ETH and SOL negative in both train and validation;
- primary negative already at base cost;
- historical untouched OOS opened: **false**;
- genuine-forward evidence opened: **false**.

Useful parts may seed a genuinely **new** frozen hypothesis only with a fresh fingerprint and fresh chronological validation. Durable negative memory includes at least `ACC-002`, `DATA-BASIS-001`, `DATA-FUNDING-001`, `DISC-VOL-BREAKOUT-001-v1`, `DISC-LIQUIDITY-MEANREV-001-v1` and `DISC-BTC-LEADLAG-001-v1`.

Other strategy lanes:
- `active_deep_candidate`: **null**;
- `DISC-SQUEEZE-RETENTION-001-v1`: **BLOCKED_DATA_CONTRACT**; do not substitute venue/proxy data to rescue it;
- `DISC-RESIDUAL-MOMENTUM-001-v1`: **DEPRIORITIZED_EVIDENCE_LIMITED** because historical PIT membership is unverified;
- `DISC-FRIZZ-PLAYBIT-EMA-001-v1`: **BLOCKED_SOURCE_FINGERPRINT**; never approximate or silently substitute existing FFRIZZ logic.

**No validated profitable strategy exists.**

## PHASE 2 — VERIFIED COMPLETE RUNTIME CONTRACT

Durable acceptance contract: issue #451.

### Persistent PIT causal-memory primitive
PR #454 exact head `8da3ff1d212d28cfd9f04521c7ab7b5ec5a4d8e3` was independently integrated. The merged primitive provides:
- immutable point-in-time observations and exact provenance;
- frozen mechanism/direction/horizon/falsifier/matched-control contracts;
- multiple-testing/family protection;
- confidence gain/loss/decay and contradiction memory;
- PIT relative-impact handling such as `flow/float` and `flow/liquidity` only when denominator/timing are defensible;
- exact rejected-fingerprint vetoes;
- deployment-durable service-role Supabase append-only versioning with digest/parent-chain integrity;
- bounded stale-writer replay and fail-closed outage/corruption/replay behavior;
- zero broker/trade/promotion/OOS-opening authority.

### Real autonomous consumption
PR #460 exact head `0ee9e160e4652cfcac4a0890ee27ef9e9639f175` was independently merged as `870ce1cb680d757963b19d9dfc858f25eabf7eb2`. The default autonomous director now consumes structured durable causal memory when generating Big-Move and strategy-component research missions. Supported provenance-bound mechanisms may generate **fresh research-only fingerprints**; unsupported narrative-only claims cannot change eligibility or fingerprint; rejected exact strategies remain ineligible.

### Exact deployed runtime acceptance
PR #461 exact implementation head `ad7b7d4f71175c795670af3c469404410e5f02cc` was independently reviewed and merged as canonical SHA:

`1834c740c9ce85dfeb14f4f0544c7a4957755cbd`

Required exact-main evidence on that SHA:
- Security & Reliability run `35479519648`: **SUCCESS**;
- Phase-1 Profitability Learning Runtime Acceptance regression `35479519652`: **SUCCESS**;
- Money Intelligence Causal Runtime Acceptance run `35479519649`, attempt 2: **SUCCESS**.

The first causal acceptance attempt correctly failed closed because the already-applied production causal-memory migration had intentionally remained at **zero durable rows** after its earlier rollback smoke test. Production inspection reconfirmed the table was exactly empty. The durable store was then explicitly initialized once with the deterministic blank `CausalRepricingMemory` genesis document through the already-approved optimistic append RPC (`expected_sequence=0`, no parent). This created no observation, claim, hypothesis, evidence event, confidence result or strategy result and introduced no empty/local permissive fallback. The acceptance rerun then passed against the exact deployed merged SHA.

The deployed acceptance proves on the real durable/default-director path:
- durable restart/reload;
- structured supportive PIT evidence can cross the frozen scientific gate and create exactly the bounded fresh research lanes;
- narrative-only state does not affect scientific mission eligibility/fingerprint;
- confidence decay removes stale mission eligibility;
- later matched-control contradiction lowers confidence and removes missions;
- optimistic stale-writer replay preserves both durable mutations;
- conflicting replay, backend outage and corrupt document paths fail closed;
- rejected design and PIT-effective fingerprints persist;
- the synthetic acceptance fixture is permanently rejected and ends with zero eligible missions;
- research-only=true and trade/promotion/broker/OOS-opening authority remain false.

`COORD-MI-CAUSAL-001` and `COORD-MI-CAUSAL-002` are therefore DONE in this reconciliation. Issue #451 can be closed only after this state transition is independently integrated on `main`.

## PHASE 3 — ACTIVE NEXT PROGRAM PHASE

Durable contract: issue #462, `Phase 3: independent adversarial architecture review of learning-driven autonomy`.

Exactly one successor should become active after this reconciliation merges:
- task: `COORD-ARCH-ADVERSARIAL-001`;
- owner: `testing-security`;
- status: **READY**;
- isolated branch: `agent/testing-security-phase3`;
- work mode: `AUDIT`.

The Phase-3 worker must independently trace the **actual execution paths**, not review only schemas/tests. Required adversarial scope:
1. Prove durable profitability/component learning and durable causal-repricing memory are truly consumed by default autonomous mission generation, ranking, eligibility, ownership and subsequent experiment execution.
2. Find/prevent post-hoc subgroup/parameter mining, adaptive stopping, repeated-look leakage, family-size/multiple-testing leakage, outcome-selected mission reranking, successor relabeling, ablation mining and cross-lane evidence reuse.
3. Ensure any outcome-selected subgroup/parameter/component becomes a **new frozen hypothesis/fingerprint** with fresh chronology and appropriate multiple-testing treatment rather than being relabeled confirmatory.
4. Prove facts/inferences/narrative prose cannot bypass provenance-bound mechanism/control/falsifier gates or alter promotion/scientific admission.
5. Prove rejected exact fingerprints cannot be rescued by narrative similarity or component learning; useful parts may seed only genuinely new hypotheses.
6. Exercise deploy replacement, stale/concurrent writers, conflicting replay, partial backend outage, corrupt/malformed state, stale data, partially persisted missions and queue/ownership races; all unsafe ambiguity must fail closed.
7. Audit end-to-end chronology so formation evidence, confirmatory evidence, matched controls, untouched OOS and genuine-forward evidence remain separated at every real boundary.
8. Preserve broker/trade/promotion/OOS-opening authority false and the approximately **$30/month** combined variable paid-resource ceiling.

For every blocking finding, reproduce it with an adversarial regression before fixing it. Do not weaken scientific gates to obtain green tests. Require exact-head Security & Reliability and independent integration. Phase 3 is complete only when no unresolved blocking architecture finding remains; then route Phase 4 permanent autonomous-loop integration.

PR #432 is older testing-security discovery-firewall work on a materially stale base. It does **not** claim or satisfy Phase 3; inspect/close/revalidate it separately rather than mixing its old candidate-specific context into `COORD-ARCH-ADVERSARIAL-001`.

## MONEY INTELLIGENCE / BIG-MOVE CURRENT STATE

Latest persisted main-line Money Intelligence append at the Phase-2 transition is the `2026-09-19T2344Z` cycle committed immediately before PR #461. Preserve it as research memory, not a signal.

Important current methodological conclusion: raw USD open-interest growth can materially overstate actual position/leverage growth during a large price move. The exploratory ENA example showed roughly +34.5% raw USD OI versus only about +11% unit-normalized exposure growth; the small ENA/ZEC exploratory sample did not establish useful positive next-day predictive association. Future work should prefer native-unit OI plus price and funding/basis normalization and must freeze hypotheses before evaluating outcomes.

Treasury-wrapper work likewise remains causal research rather than prediction: distinguish financing capacity from realized proceeds, actual asset acquisition/disposition, in-kind transfers, locked assets, liabilities/cash carry and marginal venue flow. Holdings growth alone is not proof of marginal spot demand. No immutable directional forecast currently clears promotion requirements.

**No promotion-grade 90-day 2x candidate exists.**

## OPEN INTEGRATION / INTEGRITY WORK

The state-transition branch/PR for this reconciliation changes only canonical durable state and must receive independent integration; do not self-merge it.

PR #457 is separate Promising Results dashboard work. PR #453 is bounded development-orchestrator work. Neither substitutes for Phase-3 adversarial scientific architecture review.

Older open PRs (#387, #389, #394, #429, #432, #433, #434) materially predate current `main`; old green CI is insufficient. Revalidate against current main/current objectives/current ownership or close superseded work rather than reviving it by inertia.

PR #433's Big-Move event/control lab may later be useful infrastructure but is not evidence of a 2x predictor and must preserve independently auditable historical provenance.

Canonical specialist coordination must be loaded through `orchestration/coordination_overrides.py`; do not read only the base JSON.

## PRESERVED DATA-BREADTH HANDOFF

- `COORD-DATA-005`: **DONE** — breadth evaluator integrated; historical PIT history unavailable.
- `COORD-DATA-006`: **DONE** — prospective PIT capture verified; no fabricated historical backfill.
- `COORD-DATA-007`: **BLOCKED** — wait for genuinely matured independent prospective cohorts.

Do not select another DATA-BREADTH candidate while `COORD-DATA-007` remains blocked on genuine maturation. This does not relax Phase-3 priority or strategy scientific gates.

## SAFETY INVARIANTS

- Broker disconnected; trade/promotion authority **OFF**.
- Never rewrite historical predictions, frozen OOS, genuine-forward evidence or rejected fingerprints.
- Failed exact fingerprints remain rejected; useful components can seed new hypotheses only under new fingerprints and new chronological validation.
- One expensive deep strategy candidate at a time.
- Preserve chronology, PIT safety, realistic costs, robustness, multiple-testing controls, cross-engine checks where applicable, untouched OOS and genuine-forward gates.
- Missing/stale/malformed/future/ambiguous evidence fails closed to WAIT / RESEARCH_ONLY.
- Combined variable paid-project ceiling remains approximately **$30/month** unless the user explicitly changes it.
- Supabase Pro is approved; preserve egress/query/window/throttling safeguards.
- Deterministic Python/GitHub Actions first; API routing uses approved budget-aware model policy. GPT-6 Astra belongs to Work/Codex, never the OpenAI API.

## STATUS

Current truth for this reconciliation: **Phase 1 is complete; Phase 2 has passed persistent, autonomous-consumption and exact-deployed runtime acceptance on canonical SHA `1834c740c9ce85dfeb14f4f0544c7a4957755cbd`; Phase 3 independent adversarial architecture review is the next program phase; no validated profitable strategy exists; `DISC-BTC-LEADLAG-001-v1` remains rejected pre-OOS; no promotion-grade 90-day 2x candidate exists; untouched OOS/forward remain locked; broker/live authority remains off.**

## EXACT NEXT STEP

Independently review and integrate this Phase-2 -> Phase-3 state reconciliation after exact-head Security & Reliability succeeds. Then close issue #451 as completed and execute issue #462 / `COORD-ARCH-ADVERSARIAL-001` on isolated `agent/testing-security-phase3`, beginning from the then-current `main`. Do not duplicate Phase-2 implementation, do not self-certify Phase 3, and do not route Phase 4 until the adversarial execution-path review/fixes pass exact-head CI and independent review.
