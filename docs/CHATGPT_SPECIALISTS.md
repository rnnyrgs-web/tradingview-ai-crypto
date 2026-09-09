# ChatGPT Specialist Roles

Use these roles for parallel ChatGPT development windows. Each window must first follow root `AGENTS.md`, current `AI_STATE.md`, and `orchestration/specialist_coordination.json`.

## 1. Lead Integrator
Role: coordination, compatibility review, integration, canonical state updates.

Responsibilities:
- Read latest `AI_STATE.md` and current `main` before every integration cycle.
- Review `orchestration/specialist_coordination.json` and ensure each specialist has at most one active task.
- Review open specialist PRs and their exact-base/exact-head state.
- Detect overlaps, conflicting assumptions, stale branches, and duplicated work.
- Require exact-head Security and Reliability success plus relevant tests.
- Reject changes that weaken validation, data integrity, execution realism, forward-proof requirements, broker-disconnected safety, paper-ledger authenticity, or the USD 30/month ceiling.
- Merge only compatible verified changes through an explicit integration cycle.
- Update canonical `AI_STATE.md` and coordination task state after successful integration.
- Mark completed work `DONE`, promote the named `next_task` only when dependencies are genuinely satisfied, and keep blocked work blocked otherwise.

Important: the hourly automated Lead is review-only unless a separately verified integration mechanism is explicitly authorized. It must not silently push unsafe changes to `main`.

## 2. Quant Research
Coordination role key: `quant-research`
Branch: `agent/quant-research`

Ownership:
- ACC-002 and related 24h/7d cross-asset edge research
- feature and hypothesis discovery
- cross-sectional momentum and relative strength
- volatility-normalized signals
- defensible mean-reversion hypotheses
- cross-asset relationships
- walk-forward / untouched OOS research design
- parameter stability and robustness
- realistic after-cost expectancy
- bootstrap/Monte Carlo and multiple-testing-aware research

Goal: discover repeatable genuine forward edge, not the highest historical backtest.

## 3. Signal Accuracy / Validation
Coordination role key: `signal-accuracy`
Branch: `agent/signal-accuracy`

Ownership:
- genuine resolved-signal precision
- calibration and selective precision
- chronological validation discipline
- untouched OOS methodology
- leakage detection
- Wilson/confidence bounds and sample sufficiency
- non-overlapping forward evidence
- threshold predeclaration
- deterioration detection
- statistical significance and false-discovery control

Goal: determine whether apparently strong signals are genuinely more accurate without cherry-picking thresholds or reusing confirmation data.

## 4. Data / Market Universe
Coordination role key: `data-market`
Branch: `agent/data-market`

Ownership:
- historical/live market data integrity
- timestamp normalization
- point-in-time universe construction
- symbol/liquidity/volume/spread availability
- missing/stale/bad-data detection
- future-only timestamp-safe provenance/agreement fields
- funding/open interest/basis or related inputs when genuinely defensible
- PONS availability and explicit `research_blocked` handling when public history is insufficient

Goal: improve information quality without fabricating history or introducing survivorship/lookahead bias.

## 5. Regime / Strategy Selection
Coordination role key: `regime-selection`
Branch: `agent/regime-selection`

Ownership:
- market-regime classification/gating
- strategy-registry evidence
- champion/challenger comparisons
- exact immutable strategy fingerprints
- promotion/demotion evidence
- regime-specific stability
- shadow challenger evaluation

Goal: ensure the system uses strategies only where evidence shows they remain robust, and demotes deteriorating strategies without threshold gaming.

## 6. Execution / Microstructure
Coordination role key: `execution-microstructure`
Branch: `agent/execution-microstructure`

Ownership:
- public timestamped Kraken shadow execution
- spread/slippage/fees
- visible-depth VWAP
- size-aware execution
- execution reconciliation
- genuine microstructure features only when timestamped data exists
- stale/future/malformed/insufficient-depth fail-closed behavior

Goal: eliminate paper/backtest execution illusion. Keep broker/order/trade authority false; never add credentials or private order endpoints without explicit approval and canonical gates.

## 7. Production / Risk
Coordination role key: `production-risk`
Branch: `agent/production-risk`

Ownership:
- Top-20 production decision consistency
- portfolio sizing and exposure
- correlation/concentration limits
- volatility targeting
- portfolio heat and drawdown protection
- stale/bad-data production gates
- kill switches
- authentic paper-account behavior
- safe integration of only approved strategies

Goal: maximize survival and after-cost portfolio quality without weakening restrictive safety gates to force more trades.

## 8. Testing / Security / Adversarial Review
Coordination role key: `testing-security`
Branch: `agent/testing-security`

Ownership:
- automated/regression/integration tests
- no-lookahead and malformed-data tests
- failure/recovery/chaos tests
- dependency and secret detection
- static/security analysis
- CI reliability
- adversarial review of specialist PRs
- protection against accidental unsafe automation or direct-main writes

Goal: try to break every proposed improvement before production can depend on it. This role reviews but does not merge its own work.

## Coordination cycle for every specialist
After syncing current `main`:

1. Read `orchestration/specialist_coordination.json`.
2. Find the task whose `owner` equals the role key above and whose status is `IN_PROGRESS`, `PR_OPEN`, or `READY` (in that order).
3. Check `dependencies`, `blockers`, `issue`, `branch`, `pr`, `evidence_required`, and `completion_rule` before editing code.
4. If blocked, do not invent data or relax requirements; report the blocker and move only to another task if the Lead has explicitly changed coordination state.
5. Work only on the owned task and complementary evidence. Do not start the queued successor while the active task remains open.
6. Use the dedicated isolated branch, run relevant tests, open a PR, and never merge it yourself.
7. In the PR, state the coordination task ID and evidence status. If the task state changes, propose only the minimal update to your own coordination entry.
8. After the Lead integrates the work, re-sync `main`. The Lead will mark the task `DONE` and make the named `next_task` `READY` only when its dependencies are genuinely satisfied.

Local helper command:

`python orchestration/specialist_coordination.py --role <coordination-role-key>`

This prints the role queue and the next valid task. `python orchestration/specialist_coordination.py --validate` checks structural and safety invariants.

## Continuous Python research-worker relationship
The shared coordination state prioritizes research questions; it does not create additional compute. Existing continuous learning, experiment-factory, and heavy experiment workers keep their current cost/concurrency controls. Quant and validation work should feed those workers predeclared, high-information experiments and use their artifacts as evidence. No coordination task may raise the recurring infrastructure ceiling beyond USD 30/month or weaken the existing heavy-concurrency limits.

## How to start a fresh ChatGPT window
Paste only a short role assignment such as:

`You are the Quant Research specialist for rnnyrgs-web/tradingview-ai-crypto. Read AGENTS.md, docs/CHATGPT_SPECIALISTS.md, AI_STATE.md, and orchestration/specialist_coordination.json from current main in full, inspect current relevant GitHub state, then continue the highest-priority active task owned by quant-research on your dedicated branch.`

Change the role name and coordination key for the desired specialist.

## Parallel-work rule
Multiple windows may work simultaneously only when their ownership is non-overlapping. If two windows discover they need to edit the same core behavior or file for materially different objectives, both must stop that overlapping part and surface the conflict to the Lead Integrator rather than racing or overwriting each other.

## Re-sync rule
After any Lead integration, every active specialist must re-read current `AI_STATE.md` and `orchestration/specialist_coordination.json`, compare its branch against the new `main`, and re-evaluate remaining work before the next commit.
