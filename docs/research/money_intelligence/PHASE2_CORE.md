# Phase 2 Money Intelligence causal-learning core

Status: first bounded implementation milestone; **Phase 2 is not complete**.

## Purpose

This package turns point-in-time structured evidence into a persistent, evolving
causal-mechanism state. It is a research-memory and hypothesis-routing system,
not a signal engine. It grants no broker, trade, strategy-mutation, OOS-release,
automatic-execution, or promotion authority.

The bounded runtime loop is:

`freeze mechanism -> observe structured fact/control -> immutable append -> update confidence -> preserve contradictions -> decay stale evidence -> emit fresh research hypothesis -> rank research mission`

## Components

- `money_intelligence_learning/contracts.py` freezes stable mechanism IDs,
  falsifiers, causal chains, transmission variables, regime scope, matched-control
  design, search breadth, chronology, source provenance, and evidence identity.
- `money_intelligence_learning/features.py` computes timestamp-safe
  `flow/float`, `flow/market-cap`, `flow/ADV`, `demand/liquidity`, and
  `issuance/float` only when numerator and denominator exist, are comparable,
  and were available by the cutoff. Missing or incompatible denominators stay
  `UNKNOWN`.
- `money_intelligence_learning/evolution.py` applies fixed deterministic evidence
  deltas. Supporting evidence, contradictions, matched-control results, and
  revalidation update the same stable mechanism. Confidence decays toward the
  frozen prior with the declared half-life.
- `money_intelligence_learning/memory.py` provides transactional SQLite memory
  for local/replay tests. Exact replay is idempotent; conflicting rewrites,
  duplicate independence keys, missing mechanisms, corruption, and capacity
  overflow fail closed.
- `money_intelligence_learning/supabase_memory.py` provides the same event model
  on the approved service-role Supabase channel, using compare-and-swap append
  and bounded retry. The migration keeps the table private and append-only.
- `money_intelligence_learning/research_bridge.py` emits fresh Big-Move and
  strategy-component research fingerprints only from `PROMISING` or `SUPPORTED`
  states, attaches exact evidence ancestry, rejects collisions with canonical
  rejected fingerprints, and consumes the hypotheses through the existing
  research-mission priority function.
- `money_intelligence_learning/runtime.py` wires one end-to-end bounded cycle.

## Scientific firewall

- A mechanism must be frozen before an observation and every observation must
  satisfy `observed <= published <= available <= information_cutoff`.
- Free-form narrative is not scored. Only valid structured evidence kinds affect
  confidence; unknown fields are rejected.
- One `independence_key` can contribute at most once. Republishing or relabeling
  the same underlying evidence cannot amplify confidence.
- Matched-control evidence must identify a predeclared control and a consistent
  support/contradiction outcome.
- Evidence strength is persisted and auditable; it is not inferred from prose.
  Upstream source-specific strength calibration remains a future frozen-contract
  task and may not be tuned on outcomes.
- Emitted hypotheses remain research-only and require fresh scientific contracts,
  chronology, multiple-testing treatment, matched controls, OOS protection, and
  normal coordination review before execution.

## Durable storage

Migration `supabase/migrations/20260919173000_money_intelligence_learning_events.sql`
creates the service-role-only event table and atomic append RPC. The migration
must be independently reviewed and applied before enabling deployed persistence.
Until then, absence of the table is a fail-closed deployment state, not permission
to reset or fall back to empty memory.

## What remains before Phase 2 completion

1. Independently integrate the Phase-1/Phase-2 state handoff in PR #452.
2. Independently review and integrate this core, apply the migration, and verify
   exact deployed-SHA persistence/replay against a bounded synthetic mechanism.
3. Add source-specific point-in-time ingestion adapters without rewriting the
   existing append-only research cycles.
4. Freeze and test source-specific strength/calibration rules and repeated-search
   controls on matched historical cases without protected-outcome mining.
5. Make the live research director consume durable ranked missions and verify the
   consumption path after restart/outage.
6. Feed supported results into persistent Big-Move and Strategy Component memory,
   then perform the independent Phase-3 adversarial architecture review.
