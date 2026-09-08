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
Fresh post-PR-89 diagnostics proved the recurring ACC-002 24h/7d exit-code-1 was caused by the fail-closed liquidity-stability requirement after cross-exchange / historical data availability was insufficient. The runner raised `ValueError("insufficient supported liquidity subsets for ACC-002 stability gate")`, so the worker army counted an expected research-not-ready outcome as a software failure and repeatedly entered error backoff.

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
