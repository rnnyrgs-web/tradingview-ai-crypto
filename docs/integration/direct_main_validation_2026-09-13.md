# Direct-main validation checkpoint — 2026-09-13

This branch intentionally snapshots current `main` at `a7c3811c0a44f0f7a55ed64151fd996ed273234a` so the accumulated direct-main changes can receive pull-request-triggered exact-head Security & Reliability validation.

## Scope

Validation/remediation only. This checkpoint does not alter trading logic, paper history, promotion authority, broker state, scientific gates, or paid-resource ceilings.

## Required gate

- Exact PR head must pass Security & Reliability before this checkpoint can be treated as verified.
- Any failure must be diagnosed and repaired on this isolated branch (or a successor isolated remediation branch), not by weakening tests or scientific/safety gates.
- `live_promotions.json` must remain empty and broker disconnected unless separately authorized by canonical forward-profitability gates.

## Context

The repository's `AI_STATE.md` requires isolated branches and exact-head Security & Reliability green before merge. Current main had advanced through direct commits without a PR workflow run for the latest head. This checkpoint restores an auditable validation path without rewriting repository history or the authentic paper ledger.
