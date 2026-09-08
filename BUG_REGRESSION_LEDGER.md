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
