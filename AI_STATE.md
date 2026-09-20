# AI_STATE.md

Last reconciled: 2026-09-20T04:22Z
Last updated: 2026-09-20T04:22Z

This is the compact canonical handoff for `rnnyrgs-web/tradingview-ai-crypto`. Verify actual `main` SHA first on every run, then read `UNIFIED_PROFITABILITY_LEAD_SPEC.md`, `AGENTS.md`, `AUTONOMOUS_RESEARCH_DIRECTOR_STATUS.md`, `docs/ASTRA_BACKGROUND_WORKER.md`, strategy/rejected/coordination state including overrides, `orchestration/model_routing_policy.json`, current Money Intelligence / Big-Move artifacts, open PRs, active ownership and exact-head CI. GitHub durable state outranks chat memory.

## MASTER OBJECTIVE

Find and rigorously validate at least one sustainable profitable after-cost algorithmic strategy while independently improving scientifically defensible 90-day large-upside / 2x intelligence. Optimize compounded economic return, drawdown/tail-risk control, OOS robustness, execution realism and information gain. Never manufacture success and never retroactively call an already-moved asset an early prediction.

## OVERNIGHT INTEGRATION PROGRAM

Sequential phases:
1. Profitability Learning + Strategy Evolution Engine.
2. Evolving Money Intelligence + Causal Repricing Engine.
3. Independent adversarial architecture review/fixes.
4. Permanent autonomous-loop integration.

**Phase 1 and Phase 2 acceptance evidence are COMPLETE. Earliest incomplete phase: PHASE 3.**

Issue #451 is the completed Phase-2 acceptance contract. Issue #462 is the durable Phase-3 adversarial-review contract. Do not advance to Phase 4 until the actual merged execution paths pass that independent review and all discovered defects are fixed or durably blocked.

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

## PHASE 2 — VERIFIED COMPLETE ACCEPTANCE

Durable acceptance contract: issue #451, `Phase 2: evolving Money Intelligence + causal repricing memory`.

The Phase-2 core and default autonomous consumption path are integrated:
- PR #454 provided immutable point-in-time evidence/provenance, frozen mechanisms, controls and falsifiers, confidence gain/loss/decay, contradiction memory, defensible relative-impact features, multiple-testing state, durable service-role Supabase versioning and fail-closed restart/replay/outage/corruption behavior.
- PR #460 wired structured support into the default research director and downstream Big-Move / strategy-component mission path.
- PR #461 added exact-deployed runtime acceptance.
- PR #465 closed a critical rescue path in which a causal hypothesis could reuse a canonically rejected strategy ID.
- PR #466 fixed production packaging so the rejected-ID registry is present at runtime.

Exact production acceptance passed on canonical main SHA `c1737bd4b3340a9073bce64f9f9143f8a0bc03f8`:
- Security & Reliability run `35484292738`: **SUCCESS**.
- Money Intelligence Causal Runtime Acceptance run `35484292758`: **SUCCESS**.
- Profitability Learning Runtime Acceptance regression run `35484292890`: **SUCCESS**.
- Acceptance verified default-director structured-support consumption; confidence gain/loss/decay; matched-control contradiction removing missions; narrative-only evidence exclusion; restart/replay/stale-writer/outage/corruption fail-closed behavior; durable rejected-fingerprint memory; and canonical rejected-ID veto.
- The final bounded acceptance fixture emitted zero missions after contradiction/rejection. Untouched OOS and genuine-forward evidence remained unopened; broker/trade/promotion authority remained false.

`COORD-MI-CAUSAL-001` and `COORD-MI-CAUSAL-002` are DONE. Phase 2 completion is an architecture/runtime result, not evidence of profitability or a predictive 2x signal.

## PHASE 3 — ACTIVE NEXT PROGRAM PHASE

Durable acceptance contract: issue #462. Exactly one active milestone is canonical: `COORD-ARCH-ADVERSARIAL-001`, owner `testing-security`, status **READY**, branch `agent/testing-security`.

Independently trace and attempt to falsify the live merged paths, including:
- durable Profitability Learning, Strategy Component Memory and causal memory actually changing ranking, eligibility, queueing and execution;
- compounded after-cost economics, catastrophic-tail and return-concentration treatment rather than win-rate proxies;
- fake attribution/ablation, post-hoc subgroup rescue, parameter tuning, repeated/adaptive looks, incomplete project-wide family size, successor duplication and interaction overfitting;
- causal narrative/correlation entering admission without point-in-time provenance, frozen mechanism, control and falsifier;
- stale beliefs, rejected-ID/fingerprint rescue, chronology leakage and OOS/forward contamination;
- deploy replacement, restart, replay, race, concurrent-writer, partial-persistence, outage and corruption failure modes.

Every defect requires a focused regression and an isolated fix PR. Preserve research-only authority and do not self-certify Phase 3. The stale premature Phase-3 reconciliation in closed PR #463 must not be resurrected.

## MONEY INTELLIGENCE / BIG-MOVE CURRENT STATE

Latest persisted Money Intelligence research cycle cutoff: `2026-09-20T02:43:10Z` (`money_intelligence/research_cycles/2026-09-20T0243Z-cycle.json`). Its status is `MATERIAL_CAUSAL_UPDATE_OWNER_REPORT_ELIGIBLE`; it changed no signal-engine, paper-trade, promotion-gate, broker or real-money state.

Current preserved conclusions from the latest cycle:
- Bank of England QT composition produced a supported regime-specific sovereign-duration learning: removing expected price-insensitive long-duration selling can lower long-end term premia even while the short-rate path remains hawkish. Track net duration supply by maturity rather than treating QT as one scalar liquidity variable; no post-event trade edge is established.
- BTC held near the Sep. 18 breakout while aggregate derivatives leverage and forced-flow intensity fell. That is constructive absorption evidence, but positive funding, weekend liquidity and closed U.S. ETF markets leave the marginal buyer unidentified; the state remains WAIT.
- ENA and AVAX remain high-information movers, but neither has a timestamp-defensible fresh fundamental-flow catalyst sufficient for a BUY thesis. Post-hoc narrative attribution remains rejected.
- The Sep. 19 Saudi/Yanbu episode remains a failed-transmission control: an attempted or intercepted attack is not a verified loss of deliverable barrels. Crude remains fail-closed pending physical impairment and reopened-market confirmation.
- No immutable new directional forecast cleared the evidence bar and no promotion-grade 90-day 2x candidate exists.

These cases may motivate frozen causal hypotheses and tests, but their observed outcomes must not be mined into post-hoc thresholds.

## DEVELOPMENT ORCHESTRATOR V1 — INTEGRATED AND VERIFIED (BOUNDED ACCEPTANCE)

**ORCHESTRATOR V1 = INTEGRATED AND VERIFIED** for its bounded canonical-main schedule/selection/fail-closed path. PR #453 exact head `756353ba2d0a3c6bd149731eb6b8af1c44de5a70` passed Security & Reliability run `35488025693` (1,232 passed, 2 skipped) and fresh independent review with no unresolved Important-or-higher finding. The Lead merged it as `cd2bec2089a62172e9dfaa39592b5b9c11e2aca2`.

The first post-merge main Security run `35488506781` failed one test because its synthetic testing-security READY task duplicated the newly active canonical Phase-3 READY task. PR #470 changed only that test fixture, merged as `f5da85c95f5869583ca5eb23767eb13ddd69de77`. Security & Reliability run `35488718947` then passed on this repaired exact main (1,240 passed, 2 skipped; dependency audit, static security scan and secret check passed).

The first workflow-run-triggered Development Orchestrator V1 run `35488628336` succeeded from merged main `cd2bec2089a62172e9dfaa39592b5b9c11e2aca2`. It loaded the canonical queue, selected existing active `COORD-ARCH-ADVERSARIAL-001`, and returned `READY / MANUAL_ADAPTER_REQUIRED`; it dispatched no duplicate or invented task. After the no-action run, the Lead explicitly bootstrapped the empty version-1 durable state on `automation/specialist-runner-state` at `55415079ea73434d914ac481831e48cabb0a4858` and read it back with empty reviews, dispatches, attempts and runs; the no-action workflow itself did not write state. The workflow is present and enabled on main with manual dispatch, completed Lead/cloud-worker event triggers, and the configured hourly `13 * * * *` schedule. Run `35488628336` proves the completed-workflow event trigger operates; no schedule-triggered run was observed in this acceptance window. Focused exact-head regressions and the green main suite cover worker-outcome reconciliation, WAIT/retry_at release, bounded retries, CAS/restart duplicate suppression, current-main checks, ownership, routing and shared-budget gates. This real acceptance exercised the unsupported-task path; it did **not** exercise a production Luna dispatch because no legitimate Luna task was READY.

V1's only automatic development dispatch route is the existing cost-bounded GitHub Actions cloud specialist for a canonical, ChatGPT-eligible `data-market` task mapped to enabled API `gpt-5.6-luna`. It may import the existing exact-head three-lane review receipt for eligible `auto/*` PRs after Security success. Codex, ChatGPT Work/Astra, API Terra/Sol, Claude, Claude Code, other roles, unsupported review branches, rejected repair and Lead integration require manual handling or V2. V1 has no merge, direct-main, strategy-promotion, broker or live-trading authority. No validated profitable strategy or promotion-grade 90-day 2x candidate follows from this integration.

**Next orchestrator development milestone:** issue #472, `V2-001`, is QUEUED: define the canonical durable multi-agent task/attempt/review/repair/integration contract and deterministic end-to-end acceptance harness before adding broad worker adapters. V2 must eventually coordinate ChatGPT Lead, deterministic GitHub/Python, API Luna/Terra/Sol, ChatGPT Work/Astra, Codex, Claude, Claude Code, independent review and gated Lead integration, then select the next non-duplicative task across the profitable-strategy and defensible 90-day 2x lanes. Keep the current Phase-3 adversarial review under `testing-security` as the sole active overnight-program milestone; do not claim V2 routing or automatic integration until separately verified. Alert the user only for genuine `USER_ACTION_REQUIRED` blockers.

## OPEN INTEGRATION / INTEGRITY WORK

Current active overnight-program work is `COORD-ARCH-ADVERSARIAL-001`; it belongs only to `testing-security` on `agent/testing-security`. Do not let cloud/quant lanes claim this manual independent-review task.

PR #457 is a separate Promising Results dashboard task and does not satisfy Phase-3 adversarial review. PR #453 is a bounded development-orchestrator task and likewise does not substitute for independent architecture evidence. PR #463 is closed, stale and must not be revived.

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

Current truth: **Orchestrator V1 bounded canonical-main acceptance passed; Phase 1 and Phase 2 exact-deployed runtime acceptance passed; Phase 3 is the earliest incomplete overnight-program phase; `COORD-ARCH-ADVERSARIAL-001` is the sole active milestone; no validated profitable strategy exists; `DISC-BTC-LEADLAG-001-v1` remains rejected pre-OOS; no promotion-grade 90-day 2x candidate exists; untouched OOS/forward remain locked; broker/live authority remains off.**

## EXACT NEXT STEP

After independent integration of this reconciliation, execute `COORD-ARCH-ADVERSARIAL-001` from current `main` on the canonical `agent/testing-security` branch under issue #462. Trace the real merged paths end to end, attempt each declared falsification, add focused regressions and isolated fixes for every defect, and require exact-head Security & Reliability plus independent review. Do not self-certify Phase 3, reopen protected OOS/forward evidence, or grant broker/trade/promotion authority.
