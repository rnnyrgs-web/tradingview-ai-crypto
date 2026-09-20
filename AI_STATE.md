# AI_STATE.md

Last reconciled: 2026-09-19T21:58Z
Last updated: 2026-09-19T21:58Z

This is the compact canonical handoff for `rnnyrgs-web/tradingview-ai-crypto`. Verify actual `main` SHA first on every run, then read `UNIFIED_PROFITABILITY_LEAD_SPEC.md`, `AGENTS.md`, `AUTONOMOUS_RESEARCH_DIRECTOR_STATUS.md`, `docs/ASTRA_BACKGROUND_WORKER.md`, strategy/rejected/coordination state including overrides, `orchestration/model_routing_policy.json`, current Money Intelligence / Big-Move artifacts, open PRs, active ownership and exact-head CI. GitHub durable state outranks chat memory.

## MASTER OBJECTIVE

Find and rigorously validate at least one sustainable profitable after-cost algorithmic strategy while independently improving scientifically defensible 90-day large-upside / 2x intelligence. Optimize compounded economic return, drawdown/tail-risk control, OOS robustness, execution realism and information gain. Never manufacture success and never retroactively call an already-moved asset an early prediction.

## OVERNIGHT INTEGRATION PROGRAM

Sequential phases:
1. Profitability Learning + Strategy Evolution Engine.
2. Evolving Money Intelligence + Causal Repricing Engine.
3. Independent adversarial architecture review/fixes.
4. Permanent autonomous-loop integration.

**Phase 1 acceptance evidence is COMPLETE. Earliest incomplete phase: PHASE 2.**

Issue #451 is the durable Phase-2 acceptance contract. Do not advance to Phase 3 until Phase 2 has genuine persistent/runtime evidence, not merely schemas or tests.

## PHASE 1 — VERIFIED COMPLETE ACCEPTANCE

The Profitability Learning + Strategy Evolution Engine passed genuine exact-deployed-SHA production acceptance on canonical production SHA:

`6d8dce267e35f079c7e91d7538419509bd2d059e`

Evidence:
- PR #450 exact implementation head `859f439fb54df7954010fce576dc71972da2f144` passed exact-head Security & Reliability run `35454379268` with 1,115 tests passed / 2 skipped plus dependency audit, Bandit and secret scan before independent integration.
- PR #450 merged to `main` as `6d8dce267e35f079c7e91d7538419509bd2d059e`.
- `Profitability Learning Runtime Acceptance` run `35454496075` completed **SUCCESS** on exact head SHA `6d8dce267e35f079c7e91d7538419509bd2d059e`.
- The workflow required exact deployed SHA equality, the sealed rejected fingerprint `DISC-BTC-LEADLAG-001-v1`, `PRE_OOS_FAIL`, both training and validation `LEARN_AND_PIVOT`, both persistence statuses `PERSISTED`, target-scoped replay idempotency, exactly two target experiment rows, exact rejected-fingerprint consumption, eligibility-changing queue feedback, zero heavy dispatch of the rejected fingerprint, at least one component observation, and at least one `LEARN` mission whose `source_experiment_id` equals the exact sealed training experiment.
- The same successful workflow required untouched OOS and genuine-forward evidence to remain unopened and broker/trade/promotion authority to remain false.
- Independent production persistence observation at 2026-09-19T16:18:26Z–16:18:27Z found exactly two new `experiment` events, both `LEARN_AND_PIVOT`, with distinct input digests.

Production acceptance identifiers:
- rejected strategy fingerprint: `e34357280eb06acc965b81aa8a4655d71c29010cd39f476e18d974e54d244e4e`;
- dataset SHA-256: `047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f`;
- experiment IDs: `0bc7d582a0730149242d700d848f5fb23c16c2fdea35944579587c1c813f2b97`, `806f6bd58d69a3ad1d81c7191f06cf564be2dfbfc8697f889eff3038426ac696`;
- distinct input digests: `da20482d5ebd04d642225d887cc21d239854b050e9d9a32db3491098ad24507d`, `0d97017ed073c98bed72eaa36c4ff672afcf655163bfd46cdd02b900c8fa5332`.

Source status remained `REJECTED`; development-learning permission was true only where allowed and false for the locked component. Phase 1 completion grants **no** profitability, OOS, broker, trading or promotion authority. Issue #438 is closed as completed.

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

No validated profitable strategy exists yet.

## PHASE 2 — ACTIVE NEXT PROGRAM PHASE

Durable acceptance contract: issue #451, `Phase 2: evolving Money Intelligence + causal repricing memory`.

The first bounded Phase-2 primitive is **integrated**:
- PR #454 exact head `8da3ff1d212d28cfd9f04521c7ab7b5ec5a4d8e3` passed exact-head Security & Reliability and was independently merged as `dbc5e80c5c664863df645689dcd6df418db8194f`.
- The merged core provides immutable point-in-time observations/provenance, frozen causal mechanism/direction/horizon/falsifier/matched-control contracts, multiple-testing protection, confidence gain/loss/decay, contradiction memory, PIT `flow/float` and `flow/liquidity`, exact rejected-fingerprint vetoes, deployment-durable service-role Supabase append-only versioning with digest/parent-chain integrity, bounded stale-writer replay, and fail-closed outage/corruption behavior.
- This primitive is research-only and has zero broker/trade/promotion/OOS-opening authority.

The Phase-2 routing handoff is also **integrated**:
- PR #458 exact reviewed head `f2e7a8779fede7f058a7fc89e6f591ffc5b9354b` passed exact-head Security & Reliability, was independently merged as canonical `main` SHA `ae23d01686bc71422143e2335c78a8c527f7b72c`, and post-merge Security & Reliability run `35471848162` completed **SUCCESS** on that exact SHA.
- `COORD-MI-CAUSAL-001` is DONE.
- Exactly one active Phase-2 successor is canonical: `COORD-MI-CAUSAL-002`, owner `quant-research`, status **READY**, issue #451.
- At the reconciliation checkpoint, `agent/quant-research` still points to the already-integrated #454 primitive head and no open PR claims `COORD-MI-CAUSAL-002`; do not duplicate it if a worker claims it after this checkpoint.

Required Phase-2 end state remains a persistent point-in-time Money Intelligence / causal-repricing / reflexivity memory that:
- records immutable/versioned evidence with observation/publication/availability cutoffs and source provenance;
- maintains stable mechanism IDs and can **gain confidence, lose confidence, record contradictions and decay when stale**;
- separates observed fact, inference, hypothesis and supported mechanism in machine-readable state;
- freezes causal chain, expected direction/timing, falsifier, transmission variables and matched-control design before outcome evaluation;
- accounts for chronology and repeated testing/search breadth;
- uses relative-impact variables such as `flow/float`, `flow/free_float`, `flow/liquidity`, `flow/ADV`, leverage/positioning concentration and source-of-funds distinctions only when data genuinely supports the denominator and timing;
- keeps missing/non-comparable denominators UNKNOWN rather than inventing them;
- can emit provenance-bound **new** Big-Move precursor hypotheses and **new** strategy-component hypotheses with fresh fingerprints;
- cannot rescue Phase-1 rejected exact strategy fingerprints;
- cannot grant broker/trade/promotion authority from narrative or LLM prose;
- survives restart/replay and fails closed on corrupt/missing/outage state;
- is genuinely consumed by autonomous research routing before Phase 2 is called complete.

**Active bounded milestone — `COORD-MI-CAUSAL-002`:** wire the approved durable causal memory into the actual autonomous Money Intelligence -> Big-Move / strategy-component mission-generation path. Structured provenance-bound mechanism evidence must affect mission eligibility/ranking by default; unsupported narrative-only claims must not. Prove one bounded mechanism can gain confidence, lose confidence from contradiction/matched controls, decay when stale, persist through restart/deploy replacement, and change downstream mission eligibility/ranking with exact provenance. Prove replay idempotency and fail-closed backend outage/corruption/stale-writer behavior. Keep rejected exact fingerprints ineligible. Exact-head Security & Reliability is required before integration and exact-deployed-SHA runtime acceptance is required afterward. Only then may Phase 2 be marked DONE and Phase 3 routed.

Do not rewrite existing append-only research cycles or duplicate the routine research-cycle writer while wiring the runtime path.

## MONEY INTELLIGENCE / BIG-MOVE CURRENT STATE

Latest persisted Money Intelligence research cycle cutoff: `2026-09-19T21:31:42Z` (`money_intelligence/research_cycles/2026-09-19T2131Z-cycle.json`). Its status is `RESEARCH_IN_PROGRESS_NO_OWNER_REPORT`; it changed no signal-engine, paper-trade, promotion-gate, broker or real-money state.

Current preserved conclusions from the latest cycle:
- SOL-treasury equities formed a high-beta matched cluster around the Sep. 18 SOL move; the event is better treated as a wrapper-factor / heterogeneous premium-leverage case than as a DFDV-specific news reaction. Predictive return value remains untested.
- Treasury-wrapper causality must distinguish realized financing proceeds, actual asset acquisition/disposition, in-kind transfers, locked assets, seniority/cash carry, unused financing capacity, and liability-adjusted treasury value. Token-per-common-share accretion alone is not proof of common-equity economic accretion.
- Upexi provides a direct in-kind SOL control: treasury holdings can rise without contemporaneous public-market buying, so holdings growth cannot be assumed to equal marginal spot demand.
- Cross-wrapper primary-source evidence supports a causal bridge of financing/cash need -> realized proceeds or assets -> allocation decision -> actual acquisition/disposition mode -> venue/counterparty -> marginal flow. Registered capacity, legal permission and treasury size are state variables, not realized flow themselves.
- Weekend Middle-East attack claims still did not establish a verified incremental deliverable-barrel loss; crude remains fail-closed pending physical damage/supply evidence and reopened-market confirmation.
- No immutable new directional forecast cleared the evidence bar and no promotion-grade 90-day 2x candidate exists.

These cases may motivate frozen causal hypotheses and tests, but their observed outcomes must not be mined into post-hoc thresholds.

## OPEN INTEGRATION / INTEGRITY WORK

Current active Phase-2 core work is `COORD-MI-CAUSAL-002`; prioritize it over unrelated dashboard or legacy cleanup work unless another worker has already claimed it.

PR #457 is a separate Promising Results dashboard task and does not satisfy Phase-2 causal-runtime acceptance. PR #453 is a bounded development-orchestrator task and likewise does not substitute for scientific/runtime Phase-2 evidence.

Older open PRs (#387, #389, #394, #429, #432, #433, #434) predate the current main materially. Their old green CI is not sufficient for integration. Revalidate against current `main`, current scientific objectives and current active ownership before considering any merge; close superseded work rather than reviving it by inertia.

PR #433's Big-Move event/control lab may become relevant to Phase 2/Big-Move work, but it must first be rebased/revalidated against current main and its historical-source provenance must remain independently auditable. It is infrastructure, not evidence of a 2x predictor.

Canonical specialist coordination must be loaded through `orchestration/coordination_overrides.py`; do **not** read only the base JSON.

## PRESERVED DATA-BREADTH HANDOFF

- `COORD-DATA-005`: **DONE** — breadth evaluator integrated; historical point-in-time history unavailable.
- `COORD-DATA-006`: **DONE** — prospective point-in-time capture verified; no fabricated historical backfill.
- `COORD-DATA-007`: **BLOCKED** — wait for enough genuinely matured independent prospective cohorts.

Do not select another DATA-BREADTH candidate while `COORD-DATA-007` remains blocked on genuine prospective maturation. This wait does not block independent Phase-2 implementation or fresh strategy discovery under current gates.

## SAFETY INVARIANTS

- Broker disconnected; trade/promotion authority **OFF**.
- Do not rewrite historical predictions, frozen OOS, genuine-forward evidence or rejected fingerprints.
- One expensive deep strategy candidate at a time.
- Preserve chronology, point-in-time safety, realistic costs, robustness, multiple-testing controls, cross-engine checks where applicable, untouched OOS and genuine-forward gates.
- Missing/stale/malformed/future/ambiguous evidence fails closed to WAIT / RESEARCH_ONLY.
- Combined variable paid-project ceiling remains approximately **$30/month** unless the user explicitly changes it.
- Supabase Pro is approved; preserve egress/query/window/throttling safeguards from PRs #413/#414.
- Deterministic Python/GitHub Actions first; API routing uses approved budget-aware model policy. GPT-6 Astra belongs to Work/Codex, never the OpenAI API.

## STATUS

Current truth: **Phase 1 exact-deployed profitability-learning runtime acceptance passed; Phase 2 is the earliest incomplete overnight-program phase; its durable causal-memory primitive and `COORD-MI-CAUSAL-002` routing are integrated; runtime consumption/deployed acceptance is still missing; no validated profitable strategy exists; `DISC-BTC-LEADLAG-001-v1` remains rejected pre-OOS; no promotion-grade 90-day 2x candidate exists; untouched OOS/forward remain locked; broker/live authority remains off.**

## EXACT NEXT STEP

Execute `COORD-MI-CAUSAL-002` from current `main` on an isolated `quant-research` branch unless a current owner/PR already claims it. Wire the approved durable causal-memory store into the actual autonomous Money Intelligence -> Big-Move / strategy-component mission path; prove provenance-bound mission/ranking changes, restart/replay/deploy replacement and outage/corruption/stale-writer fail-closed behavior; pass exact-head Security & Reliability; integrate only after independent review; then run exact-deployed-SHA runtime acceptance. Do not call Phase 2 complete or route Phase 3 before that evidence exists.
