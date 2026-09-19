# User implementation brief — 2026-09-19

Preserved from the user attachment. Milestone execution and current limits are in `big_move_event_lab_001.md`.

```text
AUTONOMOUS RESEARCH LAB UPGRADE
Repository: rnnyrgs-web/tradingview-ai-crypto

This is an implementation task, not a planning task.

PRIMARY PURPOSE:
Turn the existing project into a genuinely autonomous 24/7 research/development lab centered on TWO permanent missions:

1. PROFITABLE STRATEGY DISCOVERY
Continuously discover, implement, backtest, falsify, reject, learn from and rigorously validate algorithmic trading strategies until at least one demonstrates genuine sustainable positive after-cost expectancy with useful frequency.

2. 2X+ INTELLIGENCE
Continuously study historical assets that subsequently achieved 2x OR MORE within 90 days, learn measurable pre-move conditions, compare them with matched non-winners, test those precursors scientifically, and identify current liquid assets showing unusually strong evidence of future 2x+ upside.

IMPORTANT:
The target is NEVER “exactly 2x”.

CANONICAL BIG-MOVE TARGET:

2X_PLUS_EVENT_90D:
An eligible liquid asset reaches >= 2.0x its decision-time price
(>= +100%) at any point within the following 90 calendar days.

ALL larger moves count:
- 2x+
- 3x+
- 5x+
- 10x+
- any larger extreme move

For every historical event preserve:
- starting timestamp/price
- maximum forward 30d return
- maximum forward 60d return
- maximum forward 90d return
- maximum 90d price multiple
- reached_2x
- reached_3x
- reached_5x
- reached_10x
- days_to_2x
- days_to_3x
- days_to_5x
- days_to_10x
- maximum drawdown before each threshold where measurable
- liquidity/tradability

Research BOTH:
A. what distinguishes future 2x+ assets from matched non-winners;
B. what distinguishes 3x/5x/10x+ extreme winners from ordinary ~2x winners.

NEVER cap the target at 2x.

==================================================
FIRST — RECOVER REAL CURRENT STATE
==================================================

Before making any changes:

1. Read current main and record exact SHA.
2. Read AI_STATE.md.
3. Read:
   - AGENTS.md
   - orchestration/model_routing_policy.json
   - orchestration/strategy_discovery_queue.json
   - orchestration/rejected_fingerprints.json
   - orchestration/specialist_coordination.json
   - orchestration/specialist_coordination_overrides.json
   - docs/ASTRA_BACKGROUND_WORKER.md
   - docs/LEGACY_SIGNAL_RETIREMENT.md
4. Inspect open PRs, current branches, active worker ownership, scheduled workflows, CI and recent autonomous work.
5. Do not duplicate anything already owned.
6. Treat GitHub + AI_STATE.md as durable shared truth.
7. Preserve the retirement of the old signal/dashboard system.
8. Preserve current Supabase data-hygiene and egress safeguards.
9. Preserve broker disconnected / no real-money trading.

==================================================
A — BUILD A PERMANENT 2X+ EVENT LAB
==================================================

Implement a deterministic historical rare-event research system.

For historical eligible liquid assets, construct point-in-time event records for 2x+ within 90 days.

Where timestamp-safe data exists, study PRE-MOVE conditions such as:

MARKET:
- price/trend
- relative strength
- volume/turnover
- liquidity
- volatility compression/expansion
- cross-sectional ranking
- market beta
- breadth
- spot-led vs leveraged movement

DERIVATIVES:
- open interest
- OI acceleration
- funding
- basis
- liquidations / forced flow
- deleveraging
- leverage normalization

ON-CHAIN/FLOWS where defensible:
- wallet accumulation/distribution
- exchange inflows/outflows
- concentration
- stablecoin flows
- bridge flows
- smart-money behavior

TOKENOMICS/FUNDAMENTALS:
- float/circulating supply
- FDV
- emissions
- unlocks
- TVL
- fees/revenue
- users/addresses/transactions
- ecosystem/developer growth

CATALYST/ATTENTION:
- news
- listings
- protocol launches/upgrades
- catalysts
- narrative acceleration
- attention acceleration

MACRO/REGIME:
- BTC regime
- crypto breadth
- stablecoin liquidity
- rates
- USD/global liquidity
- risk-on/risk-off regime

Never fabricate unavailable historical features.

Label evidence where relevant as:
OBSERVED FACT / INFERENCE / HYPOTHESIS / UNKNOWN.

==================================================
B — MATCHED NON-WINNER CONTROLS
==================================================

For every historical 2x+ event, create multiple controls that looked similar BEFORE the event but did NOT reach 2x within the same forward 90-day horizon.

Match only using point-in-time information:
- market cap/float
- liquidity
- listing age
- sector/narrative
- volatility
- market/BTC regime
- recent returns
- venue/tradability

Never use future survival/outcome information for matching.

Persist deterministic matching rules and dataset hashes.

Core question:

“What measurable pre-move conditions occur disproportionately often before future 2x+ events compared with comparable assets that do not 2x?”

==================================================
C — PRE-2X+ FEATURE DISCOVERY ENGINE
==================================================

Build infrastructure that turns observations into PREDECLARED falsifiable experiments.

For every hypothesis freeze BEFORE outcome inspection:
- mechanism
- feature definitions
- universe
- data sources/provenance
- timeframe
- chronology
- matching
- thresholds
- parameter/search breadth
- multiple-testing treatment
- minimum sample size
- liquidity/tradability requirements
- success criteria
- failure criteria

Evaluate:
- base 2x+ rate
- selected-cohort 2x+ rate
- lift vs base rate
- lift vs matched controls
- precision@top 1%
- precision@top 5%
- precision@top 10%
- recall
- PR-AUC where useful
- calibration when sample size permits
- 30/60/90-day forward return
- magnitude buckets: 2x / 3x / 5x / 10x+
- regime stability
- parameter neighborhood stability
- liquidity/tradability
- uncertainty/confidence intervals

Do NOT optimize raw classification accuracy.

==================================================
D — CURRENT 90-DAY 2X+ CANDIDATE RANKING
==================================================

Build a current-asset candidate engine using ONLY historically supported precursor evidence.

For each candidate ideally expose:

- symbol
- decision timestamp
- eligible-universe rank
- historical base 2x+ rate
- precursor cohort 2x+ rate
- lift vs base
- lift vs matched controls
- historical analogue count
- matched control count
- support for 3x+/5x+/10x+ if enough evidence
- supporting evidence
- contradictory evidence
- liquidity/tradability
- market regime
- catalysts
- major risks
- invalidation
- missing data
- provenance/freshness
- evidence confidence

Never invent a precise probability unless genuine calibration supports it.

Never retroactively call an already-exploded asset an early prediction.

==================================================
E — PROFITABLE STRATEGY FACTORY
==================================================

Strengthen the existing strategy discovery loop.

Maintain a bounded ranked queue of MATERIALLY DISTINCT economic mechanisms.

Possible families include:
- momentum
- residual/beta-neutral momentum
- trend
- forced-flow continuation
- liquidation reversal
- squeeze retention
- funding/OI dislocations
- carry/basis
- volatility breakout
- volatility mean reversion
- post-event drift
- regime-conditioned strategies
- seasonality/session
- cross-market lead/lag

Do not generate endless parameter variants of failed fingerprints.

Canonical lifecycle:

OBSERVE
→ HYPOTHESIS
→ PREDECLARE
→ CHEAP SCREEN
→ FALSIFY
→ REJECT + LEARN + RECORD + PIVOT

OR:

PASS
→ FREEZE EXACT FINGERPRINT
→ DEEP VALIDATION
→ UNTOUCHED OOS
→ ROBUSTNESS/STABILITY
→ REALISTIC COST STRESS
→ MULTIPLE-TESTING PROTECTION
→ CROSS-ENGINE CHECKS when useful
→ GENUINE FORWARD/SHADOW EVIDENCE

Exactly ONE expensive deep strategy candidate at a time.

Failed exact fingerprints become permanent negative memory unless materially new data or a genuinely different mechanism justifies reopening.

==================================================
F — RESEARCH DATA LAKE
==================================================

Move toward:

GitHub:
- code
- contracts
- queues
- fingerprints
- evidence summaries
- handoffs

Supabase:
- compact operational state
- current forward evidence
- current candidate state
- coordination metadata

Parquet/object-storage/local cached artifacts + DuckDB/Polars:
- historical market data
- 2x+ event tables
- matched-control datasets
- feature datasets
- large backtest data

Do not recreate huge repeated Supabase JSON ledgers.

Do not delete scientifically useful historical evidence.

==================================================
G — DATA PROVIDER VALUE TESTING
==================================================

Create infrastructure so future paid datasets must prove incremental predictive value.

For each provider:

BASELINE
vs
BASELINE + NEW DATA FAMILY

Measure incremental chronological/OOS lift.

Possible future providers:
Nansen
CoinGlass
CryptoQuant
Glassnode
Santiment
Token Terminal
Kaiko
etc.

A paid recommendation must state:
- missing-information hypothesis
- exact provider
- approximate cost
- test
- baseline
- expected benefit
- free/cheaper alternative
- KEEP criterion
- CANCEL criterion

Never purchase anything without explicit user approval.

==================================================
H — STALL / QUEUE STARVATION WATCHDOG
==================================================

Implement autonomous detection of:

- no READY work
- empty hypothesis queue
- repeated failed hypothesis
- duplicated work
- stuck PR
- repeatedly failing CI
- stale branch
- worker crash/stall
- unavailable data
- API budget exhaustion
- Work capacity blocker
- data-source blocker
- deep candidate waiting indefinitely

Automatically route around blockers when scientifically safe.

A strategy-data blocker must NOT freeze independent 2x+ work.

A 2x+ blocker must NOT freeze strategy research.

==================================================
I — RESEARCH PRODUCTIVITY SCORECARD
==================================================

Implement weekly machine-readable metrics based on scientific progress:

- materially distinct hypotheses tested
- hypotheses falsified
- negative findings preserved
- search space eliminated
- reliable datasets established
- strategy candidates passing pre-OOS
- OOS openings
- robustness passes
- cost-stress passes
- forward evidence accumulated
- historical 2x+ events studied
- matched controls generated
- precursor hypotheses tested
- lift vs controls
- top-percentile candidate precision
- false discoveries
- dollars/data/API cost per useful experiment
- stalled time
- duplicate work

Do NOT optimize:
- commit count
- agent count
- dashboard activity
- number of backtests

==================================================
J — TRUSTED LEAD INTEGRATOR
==================================================

User explicitly approves building strict Lead-only safe automatic integration.

SPECIALISTS MUST NEVER MERGE THEIR OWN PRs.

Create a Trusted Lead Integrator that may merge a routine reversible research/development PR ONLY when ALL conditions are satisfied:

- PR open
- exact current head SHA
- compatible with current main
- mergeable
- exact-head Security & Reliability PASS
- full applicable tests PASS
- independent security review PASS
- independent Lead review PASS
- Claude adversarial review PASS where required
- no secrets
- no broker/live-trading change
- no trading authority
- no scientific gate weakening
- no OOS contamination
- no paid resource addition
- no budget increase
- no destructive DB operation
- no schema/data deletion
- no auth/permission expansion
- no billing/account changes
- no ambiguous high-risk infrastructure change

Use expected-head SHA guards.

If uncertain:
DO NOT MERGE.

Record blocker and continue other work.

After valid merge:
- reconcile AI_STATE
- reconcile queue
- release ownership
- permit next task to continue automatically

Do NOT enable broad GitHub auto-merge.
Only the central Trusted Lead gets this narrow authority.

==================================================
K — 24/7 MODEL ORCHESTRATION
==================================================

Preserve/use:

Python/GitHub Actions:
deterministic backtests/screens/tests/data processing

GPT-5.6 Luna API:
routine bounded work

GPT-5.6 Terra API:
medium quant/research implementation

GPT-5.6 Sol:
deep scientific reasoning/review/Lead decisions

Work GPT-6 Astra:
substantial implementation/backtesting/debugging
recurring preference = Medium

Codex GPT-6 Astra:
heavy pure coding where appropriate

Claude:
independent scientific falsification

Claude Code:
implementation/testing adversary

GitHub:
durable shared mailbox/state

AI proposes.
Deterministic evidence decides.

==================================================
SAFETY
==================================================

Never:
- fabricate data/results
- use future information
- contaminate untouched OOS
- loosen scientific gates to get positive results
- silently change frozen rules after seeing outcomes
- count overlapping observations as independent
- hide failed hypotheses
- reconnect a broker
- enable real-money trading
- transfer capital
- expose secrets
- increase spend without approval
- revive the retired old signal/dashboard architecture

==================================================
IMPLEMENTATION RULES
==================================================

Use isolated branches.

Before editing:
- inspect existing work
- avoid duplication
- identify one coherent bounded milestone
- define DONE

Prefer implementing the foundational 2x+ Event Lab + matched controls first unless already owned.

Then proceed through dependencies.

For each substantial change:
- add tests
- run targeted tests
- run full applicable tests
- fix in-scope failures
- verify exact-head CI
- create/update PR
- preserve evidence
- update AI_STATE when appropriate

Do not merely create plans.

Do not stop just because an experiment fails.

FAIL
→ EXPLAIN
→ LEARN
→ RECORD
→ PIVOT
→ CONTINUE.

Ask the user only when genuinely necessary for:
- payment
- new subscription
- secret/API key
- authorization/reconnection
- destructive operation
- major budget increase
- account/billing change
- ambiguous high-risk decision

If Work capacity becomes limited:
- commit/push useful work
- checkpoint exact next step to GitHub/AI_STATE
- allow the next background cycle to continue

STOP only when:
1. all safely implementable work in this milestone is completed, OR
2. a genuine user-only blocker exists, OR
3. Work capacity forces a durable checkpoint.

At the end report:
- what was actually implemented
- PRs/commits
- tests and CI
- what autonomous loops are now active
- what remains
- exact next action
- genuine blockers only
```
