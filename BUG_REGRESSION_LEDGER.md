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
