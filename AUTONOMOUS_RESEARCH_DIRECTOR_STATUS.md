# Autonomous Research Director status

Branch: `agent/autonomous-research-director`
PR: #160

Current phase: coordination primitives + tests + operating model added.

Still required before this is considered live 24/7 orchestration:

1. Wire mission generation into the existing adaptive-accuracy / quant-science factory.
2. Persist mission claims/leases in the existing coordinator state store or durable database.
3. Teach the live coordinator to claim the highest-priority eligible mission before starting heavy research work.
4. Release/renew leases on completion, error, timeout, stale-worker recovery, and normal progress.
5. Feed completed/rejected/blocked experiment outcomes back into mission ranking and research memory.
6. Emit the daily Lead report from live coordinator metrics and research state.
7. Add end-to-end tests covering coordinator re-entry, crash recovery, duplicate suppression, and blocked-history yielding.
8. Run exact-head CI and only merge after all required checks pass.

Do not treat PR #160 as production-live until the wiring above is complete and validated.

## Profitability learning implementation (2026-09-19)

User-assigned PROFITABILITY-LEARNING-EVOLUTION-001 adds the economic learning
package, immutable local research-memory adapter, completion hook, experiment
factory feedback and coordinator-side director wrapper. See
`docs/research/profitability_learning/ARCHITECTURE.md` for the implemented data flow,
activation contract and remaining runtime evidence requirements.

This substantially advances item 5 and adds evidence-based mission generation;
it does not claim that the remaining scheduling/lease/deployment work above is
finished. Learning missions remain advisory pending a fresh scientific contract
and independent review. Rich portfolio evidence must be emitted by the newly
selected strategy's actual evaluator; sparse legacy summaries remain explicitly
inconclusive. No OOS release, merge or deployment is implied by this document.
