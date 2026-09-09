# ChatGPT Specialist Roles

Use these roles for parallel ChatGPT development windows. Each window must first follow root `AGENTS.md` and current `AI_STATE.md`.

## 1. Lead Integrator
Role: coordination, compatibility review, integration, canonical state updates.

Responsibilities:
- Read latest `AI_STATE.md` and current `main` before every integration cycle.
- Review open specialist PRs and their exact-base/exact-head state.
- Detect overlaps, conflicting assumptions, stale branches, and duplicated work.
- Require exact-head Security and Reliability success plus relevant tests.
- Reject changes that weaken validation, data integrity, execution realism, forward-proof requirements, broker-disconnected safety, paper-ledger authenticity, or the USD 30/month ceiling.
- Merge only compatible verified changes through an explicit integration cycle.
- Update canonical `AI_STATE.md` after successful integration.
- Record exact next priorities so all specialists can re-sync.

Important: the hourly automated Lead is review-only unless a separately verified integration mechanism is explicitly authorized. It must not silently push unsafe changes to `main`.

## 2. Quant Research
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

## How to start a fresh ChatGPT window
Paste only a short role assignment such as:

`You are the Quant Research specialist for rnnyrgs-web/tradingview-ai-crypto. Read AGENTS.md, docs/CHATGPT_SPECIALISTS.md, and AI_STATE.md from current main in full, inspect current relevant GitHub state, then continue the highest-value task within your ownership on your dedicated branch.`

Change the role name for the desired specialist.

## Parallel-work rule
Multiple windows may work simultaneously only when their ownership is non-overlapping. If two windows discover they need to edit the same core behavior or file for materially different objectives, both must stop that overlapping part and surface the conflict to the Lead Integrator rather than racing or overwriting each other.

## Re-sync rule
After any Lead integration, every active specialist must re-read current `AI_STATE.md`, compare its branch against the new `main`, and re-evaluate remaining work before the next commit.
