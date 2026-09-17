# One Verified Edge — Integration Validation

## Decision

**BLOCKED**

The implementation audit is bound to Git SHA
`26859128a808453f744fd11ec219652255b7543e`. The branch must remain a draft and
must not be merged or deployed until every blocker below is closed and the full
audit is repeated on the new exact head.

This is not a waiver and is not a partial pass. Real-money trade authority and
broker authority remain disabled.

## Verified in this audit

- Deep-worker identity now binds the strategy fingerprint, experiment ID,
  hypothesis ID, Git SHA, dataset SHA and strategy-contract SHA.
- Deep validation requires the actual immutable dataset snapshot. Its canonical
  content hash must match the certified manifest, its OHLCV invariants and exact
  timestamp range are checked, and the same in-memory rows are passed to the
  canonical backtest, walk-forward, execution robustness and strategy registry.
- `research_validation.evaluate_candidate_stage()` remains the only lifecycle
  authority. Legacy promotion fields remain diagnostics only.
- Director missions and claims preserve the frozen identity and lane permission.
- An OOS survivor automatically invokes independent reproduction when an exact
  identity-bound reproduction input exists. Missing input, missing VectorBT or
  material disagreement remains blocked.
- The real experiment runner calls the optional MLflow adapter with experiment,
  strategy, code, data, metrics, stage and rejection identity.
- One-edge paper decisions and trades derive provenance from the sealed strategy
  contract only after the central gate reaches `FORWARD_PENDING`. Missing,
  caller-forged or mismatched provenance fails closed.
- Mission Control consumes canonical `research_truth` and shows paper economics
  filtered to the exact candidate fingerprint.
- The applied Supabase provenance migration was transactionally smoke-tested:
  duplicate decision insertion remained idempotent; decision mutation/deletion
  was rejected; an `OPEN` to `CLOSED` trade update succeeded; trade provenance
  rewrite and trade deletion were rejected; the test transaction was rolled back.

## Tests and security checks

| Check | Result |
|---|---:|
| Focused runtime/provenance tests | 37 passed |
| Dataset/backtest integration tests | 32 passed |
| Full pytest suite | 916 passed |
| Bandit source scan | passed |
| `pip-audit -r requirements.txt` | no known vulnerabilities |
| Tracked-file secret-pattern scan | passed |
| `git diff --check` | passed |
| Supabase transactional migration smoke test | passed and rolled back |

The first full-suite invocation observed one shared `/tmp` history-cache artifact
from an earlier process (`912 passed, 1 failed`). Re-running in an isolated cache
directory produced the authoritative result above (`916 passed`). This was test
environment contamination, not an application assertion failure.

## Scientific audit

| Risk | Result | Evidence / blocker |
|---|---|---|
| Look-ahead and timestamp leakage | PASS for implemented path | Ordered timestamps, next-bar entry, pre-OOS regime selection and frozen snapshot checks are enforced. |
| Survivorship bias | BLOCKED unless evidence exists | Point-in-time universe certification remains mandatory and fail-closed. No active candidate currently supplies end-to-end evidence. |
| Overlapping forward samples | PASS for implemented gate | Forward proof counts non-overlapping full-horizon observations only. |
| Data snooping / multiple testing | PASS for implemented gate | Declared trial firewall is canonical evidence and cannot be bypassed by legacy promotion flags. |
| Parameter mining | BLOCKED at runtime | The legacy registry emits parameter stability but does not yet emit every candidate-wide canonical robustness field. |
| Unrealistic costs | BLOCKED at runtime | Cost stress exists, but the strategy-registry result does not yet populate canonical `cost_2x_positive` and `cost_3x_acceptable` evidence for the frozen candidate. |
| Regime concentration | PASS for implemented gate | Regimes are selected before holdout and missing regime evidence fails closed. |
| Single-trade dependency | BLOCKED at runtime | `not_single_trade_dominated` is required by the central gate but is not produced by the live registry path. |
| Single-asset dependency | BLOCKED at runtime | `not_single_asset_dominated` requires candidate-wide aggregation; the live runner still evaluates symbol rows independently. |
| Independent implementation | BLOCKED end-to-end | The launcher is wired, but `evaluate_strategy_registry()` does not construct the explicit frozen VectorBT input consumed by the production caller. |
| Execution illusion | PASS for implemented guardrails | Current order-book observations only expand conservative stress and are never backfilled as historical executions. |
| Small samples | PASS for implemented gates | Historical quality gates and non-overlapping forward minimums fail closed. |
| Forward/paper identity chain | BLOCKED end-to-end | Paper persistence validates sealed identity, but no production opportunity producer currently emits `frozen_strategy_contract` plus the authoritative `FORWARD_PENDING` gate result. |

## Exact blockers

1. Build one candidate-wide canonical aggregation step that produces all required
   robustness fields from the frozen multi-asset evidence. Per-symbol legacy rows
   must not be allowed to advance the candidate independently.
2. Generate the independent reproduction specification from the frozen contract
   and exact certified snapshot, run VectorBT automatically, and preserve the
   exact identity in its result.
3. Add a dedicated forward-opportunity producer that accepts only the authoritative
   `FORWARD_PENDING` candidate and emits the sealed contract and gate result into
   the paper-decision path. The generic production opportunity feed must not infer
   or forge this identity.
4. Freeze an actual candidate and run one end-to-end controlled paper cycle so a
   single fingerprint can be traced through hypothesis, experiment, dataset,
   contract, all historical gates, reproduction, forward decision, paper trade
   and P&L.
5. Run Security and Reliability on the exact final head after those changes.

## Database and deployment notes

- Migration `20260917002352 strategy_provenance` is already applied to Supabase.
- The production database reports a separate critical advisory: RLS is disabled on
  `public.cross_asset_research`. It was not changed automatically because enabling
  RLS without correct policies can break access. This must be explicitly reviewed
  before deployment.
- No waivers were granted.
- Deployment decision: **DO NOT MERGE / DO NOT DEPLOY**.
