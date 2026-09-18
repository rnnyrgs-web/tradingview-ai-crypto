# AI_STATE.md

Last reconciled: 2026-09-18
Last updated: 2026-09-18

Authoritative bounded handoff for `rnnyrgs-web/tradingview-ai-crypto`. Read current main, this file, AGENTS.md and canonical coordination (base + overrides) before work. GitHub/code/check results override older conversation claims. This handoff is proposed on PR #394; it is not yet integrated into main.

## CURRENT OBJECTIVE

Discover -> backtest -> falsify -> validate -> forward-test one strategy with useful trade frequency and credible positive expectancy after realistic costs. At most one candidate may consume deep research. No profitable strategy has been established by this milestone.

For this bounded Work run, finish/verify the cross-engine research foundation associated with PR #392. The user explicitly assigned implementation and this AI_STATE.md handoff. Signaling, dashboard/UI/P&L display, alerts, Strategy Discovery Supervisor, Frizz research and other roadmap work are deprioritized and were not started. Preserve enough capacity for tested durable checkpoints.

## CURRENT MAIN / WHAT WAS VERIFIED BEFORE CHANGES

- Current main verified: `21875225951481cc866dab6d0f99c430152ea452`, merge of PR #392. The old AI_STATE.md still named September 16 main `881f1ed...`; that was stale.
- PR #392 is MERGED (2026-09-18T22:44:12Z), not an open work branch. Its final exact head is `7a3a0878a0e5d1ac104c43cb0249d1dee815dd2e`; the user's earlier `65bd8c4...` head is superseded.
- Verified on that final #392 head: Security and Reliability run `35402594855` SUCCESS; Research Engines run `35402594901` SUCCESS. Both adapter-contract and source-built three-engine-proof jobs completed successfully, including execution/reconciliation and artifact upload. Adapter log: 19 passed, no skips.
- Source-built LEAN proof artifact `10571088611`, `three-engine-frozen-path-35402594901`, digest `sha256:54ed130a971a0338228c12019685788d3c5b6c3335da3d9c12e871bdf986efef`, expires 2026-10-18. This proves the fixed fixture only.
- Actual code executes real VectorBT and NautilusTrader paths and a real source-built LEAN SPY fixture. Native engine is absent from cross-engine reconciliation. No adapter output is substituted for another.
- Read AGENTS.md, docs/CHATGPT_SPECIALISTS.md, docs/MULTI_ENGINE_PROTOCOL.md, coordination base/overrides, and loaded testing-security queue with PYTHONPATH=. COORD-TEST-001 remains a separate existing task; this direct user-assigned milestone did not take over its ownership. Open #387/#388/#389 were inspected for overlap; their files were not edited.
- Initial local baseline without optional research packages: 18 passed, 1 skipped. These counts are separate from GitHub's real-engine proof.

## IMPLEMENTED IN PR #394

1. Python adapters recompute the fingerprint of actual canonical OHLCV before executing. Changed prices, volume or chronology cannot inherit a different dataset's declared identity.
2. Contract validation rejects missing identities, nonfinite costs/sizing/capital and noninteger decision lags. Dataset validation rejects nonfinite/negative values and lossy timestamps.
3. LEAN evidence must echo a fresh UUID generated for the current subprocess invocation. The adapter passes a copied per-process environment containing that ID, contract fingerprint, evidence path, capital and quantity. The C# fixture emits the ID. A successful process cannot reuse a previous file. Fixed executable/whitelisted argv and shell=False remain intact.
4. Reconciliation rejects malformed trade/metric schemas, wrong engine attribution, missing or unsafe authority fields, nonfinite/oversized numbers, bad chronology, trade-count inconsistencies, fewer than two distinct engines and nonfinite tolerances. It supports an expected contract fingerprint; the three-engine CI caller supplies it. Invalid evidence returns WAIT_RESEARCH_ONLY without authority.
5. VectorBT open positions cannot masquerade as closed round trips. Both Python engines are exercised for long/short paths, nonzero fees, quantity and initial capital.

Changed components: research_engines/{contract,dataset,evidence,protocol,vectorbt_adapter,nautilus_adapter,lean_adapter,ci_three_engine}.py; research_engines/lean_fixture/FrozenPathResearchAlgorithm.cs; tests/test_research_engines.py; tests/test_research_engine_runners.py; this file and its historical archive. Production dependencies, workflows, strategy workers, paper ledger and broker state were not changed.

## BRANCH / COMMITS / PR STATUS / EXACT HEAD

- Role: direct user-assigned implementation + handoff; task label CROSS-ENGINE-MILESTONE-1.
- Branch: `agent/cross-engine-milestone1-audit`, based on current main above.
- Successor PR: https://github.com/rnnyrgs-web/tradingview-ai-crypto/pull/394 — DRAFT / PR_OPEN at handoff creation. No merge or deployment by this run.
- Published implementation checkpoints:
  - `c4394b5a021151a7de10a4431fa1b49562a46831`: dataset/contract rejection and LEAN replay protection.
  - `eaae925bb4d8f93b09506646237468693bd7d99e`: schema/authority/chronology reconciliation and open-position rejection.
  - `90645af1a231aaf6cb82ff36e7de55064b703f08`: real cost/direction/size tests, LEAN failure paths and oversized-number rejection.
- Exact implementation head tested locally: `90645af1a231aaf6cb82ff36e7de55064b703f08`. A later documentation-only commit adds this handoff. Read PR #394's current head SHA / `git rev-parse HEAD` before continuing; a file cannot embed its own eventual commit SHA.
- Local git push had no HTTPS credential; commits were durably published using the authorized GitHub connector Git-object/ref operations with force=false. Local checkout was then aligned with identical published trees. No user credential is required for continuation through that connector.

## TESTS RUN / EXACT RESULTS / REVIEW

- Latest focused command: `python -m pytest -q tests/test_research_engines.py tests/test_research_engine_runners.py --tb=short` -> **78 passed, 0 skipped, 10 upstream NumPy/pandas/Nautilus deprecation warnings**, 7.67 seconds locally, Python 3.12, VectorBT 0.28.5, NautilusTrader 1.231.0.
- Real Python engines independently match four cases, using entry bar 1 and exit bar 3: long/zero cost P&L 2.0; long/10bps/quantity3 P&L 5.694; short/10bps/quantity3 P&L -6.306; short/zero cost P&L -2.0. Capital is 100000 or 20000 as frozen per case. Synthetic engineering fixtures, not profitability evidence.
- Tests reproduce dataset mismatch, malformed contract/data, old LEAN results, copied engine attribution, missing engines, malformed/unsafe evidence, inconsistent chronology/counts, wrong expected identity, disagreement, infinite tolerance and open-position defects. LEAN unavailable/nonzero exit/timeout/missing result/nonobject result/not-executed paths cannot return success.
- Initial new guards: 18 intended failures before the first fix (plus optional-engine skips). Second batch: 23 failures before reconciliation hardening. Real VectorBT open-position regression failed before its fix. Independent reviewer reproduced oversized-integer OverflowError; regression failed before its fix and now passes.
- `PYTHONPATH=. python orchestration/specialist_coordination.py --validate` -> specialist coordination: valid. `git diff --check` -> success.
- Handoff/coordination tests: `python -m pytest -q tests/test_ai_state_coordination_handoff.py tests/test_specialist_coordination.py --tb=short` -> 12 passed in 0.38 seconds.
- Independent read-only code review found no blocking regressions in the two primary checkpoints; the one reported nonblocking oversized-number path was fixed and tested. Review does not replace CI.

## CI / SECURITY STATUS

- Original merged #392 exact head: both required workflows verified SUCCESS as recorded above.
- Successor `eaae925...`: Security and Reliability run `35403820043` and Research Engines run `35403820046` both verified SUCCESS, including the real LEAN fixture with the new invocation ID.
- Newest implementation `90645af...`: Security and Reliability run `35403913542` verified SUCCESS; Research Engines run `35403913567` is still in progress at handoff creation. The subsequent handoff commit has not yet completed CI. Inspect completed runs for PR #394's CURRENT exact head; never carry an earlier green status forward. Final run IDs/status are also recorded in the PR body after observation.
- No local LEAN run: this workspace has neither lean CLI nor dotnet/Launcher. `python -m research_engines.runner` correctly reports WAIT_RESEARCH_ONLY with VectorBT/Nautilus available and LEAN unavailable. Source-built CI is the real LEAN validation environment; no purchase/QuantConnect credentials are needed for that path.

## WHAT IS GENUINELY WORKING / STILL NOT VERIFIED

IMPLEMENTED and LOCALLY TESTED: the bounded rejection fixes and Python engine parity described above.
CI VERIFIED: only exact commits/workflows explicitly marked SUCCESS above or in fresh GitHub evidence.
DEPLOYED: no successor deployment or production service verification claimed.
FORWARD VALIDATED: no strategy forward evidence added; no profitable strategy claim.

The full requested milestone is **PARTIAL**, not complete:

- Native/existing backtest engine has no adapter/independent comparison under this contract yet.
- LEAN is a fixed 2013-10-07 SPY hourly long/zero-cost fixture, with hard-coded decision/execution indices. It does not generically consume arbitrary strategies, assets, short paths, costs or split declarations. Echoing contract/run IDs alone is not verification that arbitrary LEAN code executed that strategy.
- Contract still lacks explicit parameters, decision-path hash, experiment ID/version, train/test/OOS partition metadata and separate fee/slippage/execution models. Dataset hash includes chronology, but adapters do not yet bind an arbitrary strategy implementation to its declared fingerprint. Identical output is corroboration only.
- Reconciliation validates explicit attribution/schema; it is not cryptographic attestation of an engine or complete provenance verification. Global freshness/version policy across persisted engine results remains unfinished; LEAN replay rejection is invocation-specific.
- Metrics use shared closed-trade accounting. max_drawdown_pct excludes intra-trade mark-to-market drawdown; avg_trade_pct is mean P&L as percent of starting capital, not return on each trade's notional. Do not use these metrics for strategy promotion.
- Nautilus uses a synthetic VALIDATION currency pair; actual venue/instrument constraints, realistic slippage, partial/missed fills and funding/carry are not proven by the fixture. Engine versions/upstream LEAN revision are not fully pinned in current research requirements/workflow.
- No integration with strategy discovery, canonical promotion gates or forward paper validation was added. Cross-engine agreement has zero live/paper/broker/promotion authority.

## EXACT NEXT STEP

First re-read current main and PR #394, check for overlap/current head, and obtain exact-head Security and Reliability plus Research Engines success (including the real LEAN three-engine-proof artifact). If any current check fails, fix that bounded failure on the isolated branch; do not merge merely because the original #392 was green. Keep this PR's coherent hardening available for Lead review/integration.

After verified Lead integration, continue this SAME milestone: bind strategy parameters and decision-path identity plus explicit experiment/chronological split/cost metadata, wire the native engine under that contract without copying another engine's output, then generalize LEAN execution with independently checked data/path evidence and nonzero-cost/short/multi-trade fixtures. Unsupported cases remain blocked. No Supervisor/Frizz/dashboard milestone until this foundation is complete. This run stopped new implementation after a coherent verified subset to preserve checkpoint and CI capacity.

## SAFETY INVARIANTS

- Broker disconnected; no real-order, paper-ledger, promotion or production authority from research results. live_promotions.json remains unchanged/empty unless all canonical independent gates authorize otherwise.
- Keep the authentic append-only $100,000 paper-account baseline and history. Never reset/reseed/rewrite results.
- Shared approved paid-project ceiling remains approximately $30/month total. No paid service or ceiling increase authorized here. Paid-AI throttling must not stop free/local deterministic evidence accumulation.
- Isolated branches only; no direct-main writes or self-merge. Require exact-head Security and Reliability before Lead integration and deployment health checks for any runtime-affecting merge.
- Preserve chronological/purged untouched OOS, sufficient independent samples, walk-forward, parameter/regime/cost stress, multiple-testing controls, point-in-time universe safety and genuine prospective forward validation. Missing/stale/contradictory evidence fails closed.

## CANONICAL COORDINATION / FROZEN SCIENTIFIC STATE

Load orchestration/specialist_coordination.json with orchestration/specialist_coordination_overrides.json. Do **not** read only the base JSON.

- `COORD-DATA-005`: **DONE** — DATA-BREADTH-001 selected/frozen.
- `COORD-DATA-006`: **DONE** — prospective point-in-time universe capture integrated and previously verified live.
- `COORD-DATA-007`: **BLOCKED** — requires genuinely prospective non-overlapping matured outcomes. Do not select another data candidate or reconstruct membership from current survivors to bypass this gate. No new maturation count was verified in this run.
- DATA-BREADTH-001 stays frozen: minimum eight independent observations per primary horizon, separate 24h/7d, frozen baseline/feature/sign, incremental after-cost value, 1x/2x/3x costs and OOS-half/liquidity/regime stability. No outcome-driven rescue.
- DATA-BASIS-001 rejected: 24h 134 samples, -8.490253160921695bps; 7d 19 samples, -51.210226000078bps.
- DATA-FUNDING-001 rejected: 24h 38 samples, +43.56917973482839bps headline but zero incremental value and unstable halves; 7d only 6 versus required 8 samples. Do not resurrect either fingerprint.
- ACC-001 remains blocked pending timestamp-defensible forecast-time execution evidence; ACC-005 stays subject to the breadth freeze. No historical reconstruction is authorized.
- See docs/research/AI_STATE_2026-09-16_ARCHIVE.md for the full historical scientific/deployment record. Its old main SHA, open-PR claim and next-action suggestions are historical, not current instructions.
