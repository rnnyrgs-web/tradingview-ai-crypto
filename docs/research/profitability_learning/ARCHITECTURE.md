# Profitability learning and strategy evolution

This package turns completed economic experiments into durable, interpretable
evidence and subsequent research hypotheses. It cannot execute orders, authorize
OOS access, change a frozen strategy or promote anything to production.

## Data flow

`frozen contract + reconciled trade/NAV evidence -> analyze -> development
diagnostics -> immutable memory -> successor hypotheses -> evidence-weighted
research missions -> independent scientific review + fresh frozen contract`

The input schema is `profitability_learning/experiment.schema.json`.
`contracts.py` enforces additional cross-field invariants: strategy fingerprints,
explicit costs, timestamp ordering, feature publication freshness, closed flat
portfolio endpoints, no external flows, finite values and NAV/P&L reconciliation.
Hashes detect mutation; they do not authenticate a historical provider or prove
that a declared freeze/publication timestamp is independently trustworthy.

## Economic measurement

Compounded return comes from portfolio NAV (`last / first - 1`), including idle
capital and concurrent positions. Trade returns are never multiplied as if each
used all capital sequentially. CAGR is emitted only after a full year.
Drawdown/recovery use supplied NAV marks; intrabar losses between marks remain
unknown. Calendar returns include explicitly labelled observed/partial periods.
Unannualized downside RMS uses observed intervals and is labelled accordingly.

Attribution is additive money and contribution relative to initial capital within
each dimension. Dimensions overlap with one another; adding asset plus regime
contributions would double count. The package reports only supplied pre-trade
categorical features and basic trade metadata. Numeric features must be binned by
the upstream frozen contract, never optimized here after outcomes. Missing
capacity, execution audit, cross-engine and walk-forward evidence stay unknown.

Diagnostics flag catastrophic losses, concentration in a trade/asset/regime/period
and cost-sensitive returns. Doubling costs and removing the best trade are
arithmetic sensitivities, not rerun NAV backtests. Win rate is diagnostic only.

## Components, ablation and conditional research

Components carry kind, executable rule identifier, parameters and economic reason.
Fingerprints are stable SHA256 hashes of canonical JSON. A local evaluator takes
isolated copies of the frozen strategy and dataset. Development-only ablation
executes the full strategy, each predeclared omission and declared factorial
pairs. Dataset digest, actual row timestamps, variant rules and cost/chronology
identity are checked. A mutating evaluator is rejected.

Component deltas cover return, drawdown, worst trade, costs and capital use.
They remain development associations, never proof of a component's independent
causal contribution. Interaction effects use the full-minus-A-minus-B-plus-neither
factorial difference. Validation/OOS occurrence is recorded separately; presence
inside a validated strategy does not validate each component's marginal effect.

Conditional mining considers declared categorical singletons and pairs. The full
candidate count plus ablations must fit the frozen search budget, including failed
subgroups. Same-event/overlapping trade intervals are conservatively collapsed.
Mixed-membership blocks do not create independent treated/control observations.
Deterministic block-label randomization and Bonferroni correction produce only
development hypotheses. Exchangeability and regime/time confounding remain
limitations; chronological replication is mandatory. No protected partition can
reach either mining or ablation callbacks.

## Memory and failure learning

SQLite provides explicit transactions, concurrent idempotent insertion, immutable
event identities and integrity-checked restart. Conflicting replay is an error.
Identical replay never increments evidence. Economic replication counts exclude
overlapping time windows. The canonical rejection registry is read-only and is
combined with local rejected hashes; the data-blocked squeeze fingerprint is not
mistakenly classified as strategy-rejected.

Outcomes are LEARN_AND_PIVOT, MECHANISM_DEAD, INFRA_DATA_FAILURE, INCONCLUSIVE, and
SUCCESS_LEARN for adequately sampled successful experiments. MECHANISM_DEAD
requires a frozen falsifier and independent failures, not simply a losing trade.
Legacy summaries lacking a full economic contract remain INCONCLUSIVE with the
missing evidence named. Infrastructure absence never becomes evidence of no edge.

Events retain ancestry, component observations, uncertainty and failure reasons.
Component `last_validated_date` stays null unless marginal validation is actually
implemented; decay is UNKNOWN_REQUIRES_FRESH_REPLICATION. Missing validation is
not hidden behind a recent test timestamp. Capacity is bounded at 10,000 events
and 16 MB/event and blocks at capacity rather than evicting negative memory.
Archives support idempotent transfer with schema/authority/integrity checks.
They must come from a trusted producer; a checksum is not a signature.

## Evolution and ranking

Completion automatically drafts successors when sufficiently supported development
ablations identify a harmful removable component or corrected conditional mining
finds a relationship. Drafts retain executable rule specifications and ancestry,
but are BLOCKED_FRESH_CONTRACT_REQUIRED. Economic/novelty review must determine
whether removing a rule leaves a valid strategy. Lack of evidence produces an
explicit research question, not a fabricated successful component.

`propose_successor` accepts a fully specified fresh contract. It rejects original
or known rejected fingerprints, overlapping used windows, premature freezes,
reused dataset hashes and inadequate embargo. Parameter changes, economic-prose
edits and label changes alone cannot satisfy material novelty. Rule-name changes
still require independent novelty review. Optional timestamped Big-Move, Money
Intelligence, missed-move and causal-repricing references are ancestry only.

Ranking uses economic upside, information gain, mechanism strength, robustness,
uncertainty resolution, novelty, data readiness, compute/monetary/time cost, actual
family outcomes and bounded component evidence. Raw experiment counts and win
rates are not rewards. Replayed evidence cannot amplify votes. Failed mechanisms
lose priority while new mechanisms remain eligible. EXPLORE / EXPLOIT / LEARN
weights emerge from currently ranked missions, not a permanent fixed quota.

## Existing-system integration and activation

- `research_learning_state.append_lesson` adds classified missing-evidence learning
  to the existing persisted lesson JSON; the current durable adapter is unchanged.
- The experiment-factory report includes evidence-weighted learning missions.
- Explicitly matched existing factory/director experiments receive a bounded
  repeat-information penalty from real legacy completions or economic feedback
  from matching families. Eligibility and active claims remain unchanged. Legacy
  missing-evidence completions generate LEARN missions and never count as proof
  of negative economic expectancy.
- The coordinator calls a wrapper around the existing director that adds these
  missions and daily reporting without modifying the files owned by PR #387.
- Rich engine outputs enter through `complete_experiment` or the offline CLI.
  Existing sparse runners do not magically acquire NAV/component evidence.
- New learning missions require scientific design/review and do not enter heavy
  dispatch or existing claims automatically. The one-deep-candidate gate remains
  owned by canonical orchestration.

Initialize an existing approved persistent filesystem location (no new disk or
service is provisioned by this PR):

```sh
python -m profitability_learning --db /approved/persistent/research.sqlite init
python -m profitability_learning --db /approved/persistent/research.sqlite complete experiment.json --ablation ablation.json
python -m profitability_learning --db /approved/persistent/research.sqlite snapshot
python -m profitability_learning --db /approved/persistent/research.sqlite export memory-checkpoint.json
```

Set `PROFITABILITY_LEARNING_DB` to that initialized persistent path to explicitly
use SQLite. When it is unset, a deployment with the already-approved Supabase
service-role channel uses the private `profitability_learning_events` append-only
table and version-checked atomic append RPC. Concurrent writers re-read and
reclassify against the newest evidence before committing, preserving the same
cumulative scientific semantics as the transactional SQLite backend. The table
has RLS enabled, grants no anonymous or
authenticated-user access, and neither the table nor RPC has trading authority.
If neither backend is configured, runtime says WAIT_MEMORY_NOT_CONFIGURED. A
configured missing/corrupt/unreachable store blocks completion; factory/coordinator
feedback reports WAIT_MEMORY_UNAVAILABLE and emits no learned missions or runnable
candidates. It never silently resets to an empty cache. Local/GitHub jobs can
instead export/import versioned archives through an existing approved state
transport. No new paid API or model is needed.

## Status and next action

IMPLEMENTED and synthetic-testable; not merged, deployed, live-backtested, OOS
tested, forward tested, or validated profitable. This milestone introduces no new
market evidence. It neither opens the blocked squeeze data nor reruns rejected
screens. Protected old screens and their artifacts remain unchanged.

Independent Lead: review this exact PR head and CI, then integrate if acceptable.
Next deployment milestone: connect the first newly frozen available-data screen's
real portfolio ledger to the rich completion contract, select an existing durable
state location/transport, and verify deployed-SHA completion -> stored learning ->
ranked mission. Preserve all chronology/cost/OOS/budget gates. Do not revive the
retired dashboard/signal workers merely to exercise this integration.
