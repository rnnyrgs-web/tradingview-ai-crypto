# BUG / REGRESSION LEDGER

Purpose: durable, repository-backed record of confirmed code defects and their permanent regression coverage. Runtime incident fingerprints are useful operational evidence but may disappear across Render redeploys; confirmed defects belong here.

Rules:
- Record only confirmed code defects, not ordinary research-gate failures or weak strategy results.
- Every resolved defect must name the reproducer/regression test and fixing PR/commit.
- Never weaken fail-closed behavior just to make a regression test pass.
- This ledger has no trade, signal, promotion, deployment, or repository-write authority by itself.

## WORKER-DIAG-001 — Failed research subprocess reason discarded

Status: FIXED IN PR (pending merge at time of entry)
Component: `continuous_worker_army.py` / `worker_supervisor.py`
Detected: 2026-09-08
Severity: reliability / diagnosability

### Symptom
Continuous research workers could exit non-zero and the supervisor would record only a generic process failure/exit code. Both subprocess stdout and stderr were sent to `DEVNULL`, so the actual Python traceback/root cause was unavailable after the process ended.

### Reproducer
Run a research subprocess that raises an exception (for example a `ValueError`). Before the fix, worker state records the non-zero exit but preserves no bounded traceback diagnostic or root-cause-specific fingerprint.

### Fix
- stderr is captured only into a per-job temporary file;
- only the bounded tail is read after non-zero exit;
- common credential/token forms are redacted before storage/logging;
- the final traceback exception type is inferred when possible;
- deterministic incident fingerprints include the diagnostic fingerprint;
- sanitized traceback detail is written only to the private runtime incident ledger / private Render logs;
- public worker snapshots receive only error type, classification and diagnostic fingerprint, never the diagnostic excerpt.

### Permanent regression coverage
`tests/test_worker_supervisor.py`
- verifies credential redaction and bounded diagnostics;
- verifies traceback exception type inference;
- verifies diagnostic-sensitive deterministic incident fingerprints;
- verifies private ledger can retain the sanitized excerpt while returned/public incident metadata omits it;
- verifies all supervisor/incident authority fields remain false.

### Safety invariants
No strategy logic, forward-proof threshold, cache TTL, market-data source behavior, concurrency, paper ledger, broker connectivity, or live promotion authority changes as part of this fix.

## ACC002-BLOCK-001 — Expected insufficient-data gate counted as worker crash

Status: FIXED IN PR (pending merge at time of entry)
Component: `cross_asset_runner.py`
Detected: 2026-09-08
Severity: reliability / observability semantics

### Symptom
Fresh post-PR-89 diagnostics proved the recurring 24h/7d exit-code-1 was caused by the fail-closed liquidity-stability requirement after cross-exchange / historical data availability was insufficient. The runner raised `ValueError("insufficient supported liquidity subsets for ACC-002 stability gate")`, so the worker army counted an expected research-not-ready outcome as a software failure and repeatedly entered error backoff.

### Reproducer
Resolve fewer than two predeclared liquidity subsets with the required coverage and run `cross_asset_runner.run()`. Before the fix, the runner raised `ValueError` even though the safety policy was working as intended.

### Fix
The runner now emits a sealed `research_blocked` ACC-002 artifact with reason `insufficient_supported_liquidity_subsets`, zero candidates, zero untouched-OOS openings, failed parameter stability, no promotion eligibility, `live_approved=false`, and `trade_authority=false`. The process can therefore complete normally while preserving the exact fail-closed evidence gate.

### Permanent regression coverage
`tests/test_cross_asset_research_blocked.py`
- reproduces insufficient liquidity coverage;
- verifies the result is a structured research-blocked outcome rather than an exception;
- verifies no OOS is opened;
- verifies no promotion/live/trade authority is created.

### Safety invariants
No liquidity threshold, OOS threshold, survivorship requirement, forward-proof rule, multiple-testing firewall, concurrency limit, paper ledger, broker connectivity, or live promotion authority is weakened by this fix.

## PONS-DIAG-001 — Research-runner failures were invisible to worker stderr capture

Status: FIXED IN PR (pending merge at time of entry)
Component: `research_runner.py`
Detected: 2026-09-08
Severity: reliability / diagnosability

### Symptom
Fresh production evidence showed the PONS research worker could exit with code 1 while the worker supervisor reported `diagnostic=<none>`. `research_runner.py` caught per-job exceptions and printed the structured result only to stdout. The continuous worker intentionally discards stdout and captures stderr on failure, so an all-failed PONS cycle could not expose the bounded root-cause diagnostic needed to distinguish unavailable-data/research-blocked behavior from a real code defect.

### Reproducer
Cause every job in a `research_runner.py` invocation to fail. The runner exits 1, but before this fix no sanitized failure reason is emitted on stderr for the worker supervisor to capture.

### Fix
Each caught research-job exception now emits a bounded, sanitized private stderr diagnostic containing the symbol, timeframe, exception type and sanitized exception message. Existing stdout result behavior is preserved. The worker supervisor still performs its own bounded tail capture and sanitization before private logging, and public worker state still receives no diagnostic excerpt.

### Permanent regression coverage
`tests/test_research_failure_diagnostic.py`
- verifies the failure diagnostic is emitted on stderr only;
- verifies symbol/timeframe and exception type are retained;
- verifies credential-like content is redacted;
- verifies no secret value is emitted.

### Safety invariants
No strategy logic, evidence threshold, OOS/forward-proof rule, market-data source behavior, concurrency, paper ledger, broker connectivity, promotion authority or live-trade authority changes as part of this fix.

## PONS-BLOCK-001 — Expected insufficient history counted as software failure

Status: FIXED IN PR (pending merge at time of entry)
Component: `research_runner.py`
Detected: 2026-09-08
Severity: reliability / observability semantics

### Symptom
Fresh PR #91 production diagnostics proved PONS did not have enough public historical candles for the requested research windows: 15m returned `Need at least 1000 candles for walk-forward`, while 1H and 4H returned `Not enough historical candles`. All three expected evidence insufficiencies were counted as a process failure and triggered worker error backoff.

### Reproducer
Run `research_runner.py` for an asset/timeframe whose available public history is below the existing backtest/walk-forward minimum. Before the fix, an all-insufficient cycle exits 1 even though the correct research decision is simply to abstain.

### Fix
Only the two proven `RuntimeError` insufficient-history messages are classified as `research_blocked` with reason `insufficient_historical_candles`. Blocked items are explicitly research-only, ineligible for promotion, `live_approved=false`, and `trade_authority=false`. Unknown runtime errors and non-RuntimeError exceptions remain software failures and retain private diagnostics. No candle minimum is reduced and no missing history is fabricated.

### Permanent regression coverage
`tests/test_research_insufficient_history_blocked.py`
- verifies both proven insufficient-history messages are blocked;
- verifies blocked output has no promotion/live/trade authority;
- verifies unknown runtime errors are not silently reclassified;
- verifies a different exception type with similar text is not silently reclassified.

### Safety invariants
No historical-data minimum, strategy logic, evidence threshold, OOS/forward-proof rule, market-data source behavior, concurrency, paper ledger, broker connectivity, promotion authority or live-trade authority is weakened by this fix.

## PROTECT-PATH-001 — Divergent protected-path lists across engines and review

Status: FIXED IN PR (pending merge at time of entry)
Component: `agents/autonomous_cloud_runner.py` / `agents/autonomous_orchestrator.py` / `.github/workflows/autonomous_lead.yml`
Detected: 2026-09-13
Severity: scientific/operational integrity (multi-engine coordination prerequisite)

### Symptom
Three independently maintained protected-path lists had drifted out of sync: `agents/autonomous_cloud_runner.py`'s `PROTECTED_PATHS` (the fullest list), `agents/autonomous_orchestrator.py`'s `PROTECTED_PATTERNS` (missing `docs/CHATGPT_SPECIALISTS.md`, `orchestration/*`, `live_promotions.json`, `.env*`), and `.github/workflows/autonomous_lead.yml`'s hand-written bash regex guard (missing the same set). A fourth, previously unnoticed copy existed inline inside `agents/autonomous_orchestrator.py`'s `review_diff()` as a tuple-of-substring check with the same gaps. This was safe as long as only one engine (the OpenAI runner, whose candidate-generation path used the fullest list) ever produced `auto/*` candidate branches, but became a live gap the moment a second engine's candidate branches would flow through the same Lead review workflow, since that workflow's own guard was the weakest of the four.

### Reproducer
Before the fix: construct a diff touching `orchestration/some_file.json` or `live_promotions.json` and pass it to `agents/autonomous_orchestrator.py review_diff()`, or push a branch containing such a change to `.github/workflows/autonomous_lead.yml`'s selection logic. Neither the reviewer function's inline check nor the workflow's grep would refuse it, even though `agents/autonomous_cloud_runner.py`'s candidate-generation-time check would have.

### Fix
`orchestration/protected_paths.json` is now the single canonical list. `orchestration/protected_paths.py` provides `load_protected_paths()`, `is_protected()`, `find_protected_matches()`, and `diff_changed_paths()`. All four locations now load from it: `agents/autonomous_cloud_runner.py`'s `PROTECTED_PATHS`, `agents/autonomous_orchestrator.py`'s `PROTECTED_PATTERNS` and `review_diff()`'s inline check (replaced with `diff_changed_paths()` + `find_protected_matches()`), and `.github/workflows/autonomous_lead.yml`'s guard step (replaced the bash regex with `python -m orchestration.protected_paths --base origin/main --head "origin/$BRANCH"`, operating on the actual `git diff --name-only` changed-file list rather than a hand-maintained regex over raw diff text).

### Permanent regression coverage
`tests/test_protected_paths.py`
- verifies the canonical list loads and is non-empty;
- verifies every path previously protected by any of the three original lists is still protected by the canonical one;
- verifies `find_protected_matches()` and `diff_changed_paths()` correctly identify protected paths from a sample unified diff.

Updated assertions in `tests/test_autonomous_cloud_runner.py` and `tests/test_autonomous_orchestrator.py` continue to pass unchanged against the canonical list.

### Safety invariants
No role's writable-path set was widened by this fix; the canonical list is a superset (stricter) union of the three prior lists. No strategy logic, evidence threshold, OOS/forward-proof rule, paper ledger, broker connectivity, promotion authority, or live-trade authority is affected.

## FLEET-BUDGET-RACE-001 — Shared fleet budget check raced on a stale snapshot and silently zeroed real fetch failures

Status: FIXED IN PR (pending merge at time of entry)
Component: `orchestration/shared_budget.py` / `.github/workflows/autonomous_cloud_specialist.yml` / `autonomous_claude_specialist.yml` / `autonomous_claude_code_specialist.yml`
Detected: 2026-09-13
Severity: scientific/operational integrity (multi-engine coordination correctness)

### Symptom
Two related defects in the first multi-engine fleet budget check:

1. **Race condition.** Each of the three engines' workflows independently fetched a best-effort, point-in-time snapshot of the other two engines' state files at job start, then decided locally whether it had budget with no coordination between engines. Two engines evaluating concurrently (a workflow_dispatch trigger near a scheduled run, or scheduling jitter) could both read a stale "we have room" snapshot and both proceed, together exceeding the shared ceiling that neither saw the other approach.
2. **Fail-open on real fetch failures.** The best-effort bash fetch of a sibling's state file (`fetch_or_skip`/`fetch_or_default ... || true`) treated *any* failure identically to a genuine "this engine has never run" 404: a transient network error, GitHub API rate limit, or 5xx response silently resulted in the local sibling file simply not being written, which `load_sibling_states()` then read as zero spend for that engine -- exactly the case where the fleet check most needs to fail closed instead.

### Reproducer
Before the fix: call `orchestration.shared_budget`'s old flag-based CLI (`--sibling /tmp/sibling_X.json`) twice in quick succession simulating two engines, each seeded with a snapshot that individually looks safe but whose *combined* effect exceeds the ceiling -- both would report `ok: true`. Separately, simulate a sibling fetch returning a non-404 error (network timeout, 500) -- the old bash `|| true` pattern and `load_sibling_states()`'s local-file-existence check could not distinguish this from "file never created," silently contributing zero to the total.

### Fix
Replaced the best-effort local-snapshot check with `reserve_fleet_budget()`, which:
- acquires a short-lived (120s TTL) mutual-exclusion lock on a single shared `fleet_coordination.json`, using the GitHub Contents API's `sha` field as a compare-and-swap primitive -- a concurrent acquire attempt gets a write conflict and must retry against freshly-fetched state, never proceed on what it originally read;
- while holding the lock, fetches fresh own/sibling state live and records a "pending reservation" (with its own 45-minute TTL, self-healing if a run crashes) into the same coordination file before releasing the lock, so a sibling engine's next reservation attempt sees this engine's about-to-happen spend even though its run has not finished and has no completed-run entry yet;
- distinguishes a genuine 404 (`fetch_state_from_github`-equivalent `_gh_get_content` returning `(None, None)`) -- the only case legitimately treated as zero spend -- from any other failure, which raises `FleetCoordinationError` and causes the reservation to fail closed (`ok=False`) rather than silently assuming zero;
- releases the lock (and later clears the pending reservation once the run concludes) via a small, separate CLI (`python -m orchestration.shared_budget reserve` / `clear-reservation`) wired into each of the three workflows in place of the old best-effort sibling prefetch.

`fleet_coordination.json` was added to `orchestration/protected_paths.json` so no engine's generic sandboxed file-write tool can bypass the atomic API and edit it directly.

### Permanent regression coverage
`tests/test_shared_budget.py` (16 new tests, all 14 pre-existing pacing tests unchanged and still passing):
- two sequential reservations correctly accumulate and the second is refused once their combined total would exceed the ceiling (no double-approval);
- a reservation is durably visible to the very next caller;
- a lock-write conflict forces a retry against fresh data rather than a stale decision;
- lock exhaustion (held by a live holder for the whole retry budget) fails closed;
- the lock is released both on success and on a refused reservation;
- `clear_fleet_reservation` removes exactly the matching entry and is idempotent when already gone;
- a genuine 404 for a never-created sibling counts as zero and does not block the reservation;
- a real fetch failure for the lock file, for a sibling's state, or malformed sibling content each fail the reservation closed, never silently as zero -- and the lock is still released afterward so one transient error cannot wedge the fleet for every other engine;
- a conflict on the final reservation-commit write is reported, not silently dropped;
- a missing `GH_TOKEN` fails closed via the CLI.

`tests/test_claude_workflows.py` verifies all three workflows call the new `reserve`/`clear-reservation` subcommands and that the old best-effort local sibling-prefetch pattern is gone.

### Safety invariants
No change to `pacing_snapshot()`/`fleet_budget_gate()`'s pacing math (paced $30/month budget, $2-3 burst days) -- this fix is additive (an optional `pending_reservations_usd` parameter, defaulting to 0.0) and does not alter their existing, separately-tested behavior. No strategy logic, evidence threshold, OOS/forward-proof rule, paper ledger, broker connectivity, promotion authority, or live-trade authority is affected. No engine gained merge, push-to-main, or credential-exposure capability.
