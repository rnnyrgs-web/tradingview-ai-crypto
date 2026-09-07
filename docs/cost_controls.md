# Cloud cost controls and waste measurement

This document records the controls that should be used to measure cloud/API waste without trading away fail-closed behavior. It distinguishes repository-observed facts from values that still need to be collected; it does not claim savings that have not been measured.

## Scheduled workload inventory

| Workload | Current cadence / behavior | Cost signal to record | Waste indicator |
| --- | --- | --- | --- |
| Autonomous specialist cycle | Planner runs at minute 17 of every hour; the roster contains 14 specialists. A specialist may safely finish `NO_CHANGE`. | Workflow run count, queued minutes, runner minutes, model calls, input/output tokens, and result (`CHANGE`/`NO_CHANGE`) per role and cycle. | A skipped or `NO_TASK` role still starting a runner, or repeated `NO_CHANGE` work with no bounded task. The validated zero-worker cycle demonstrated that `NO_TASK` can skip the specialist matrix. |
| Lead integration | Triggered after the specialist workflow, with a minute-47 fallback. | Lead runs by trigger reason, candidate count, checkout/setup minutes, review calls, and duplicate-run count. | Fallback and event-triggered lead runs processing the same completed cycle, or reviews with no candidate SHA. Do not remove either trigger without preserving recovery coverage. |
| Cloud research/backtesting | Runs hourly, 24/7, against the documented research universes and timeframes. | Run duration, symbols/timeframes, API requests by endpoint, retries, response bytes, cache hit rate, and artifact count/size. | Re-fetching identical candles, retries caused by avoidable rate-limit pressure, or research runs with an empty/unchanged input window. No-lookahead and validation stages must remain intact. |
| Production scan | Runs approximately every 15 minutes and performs separate 24h and 7d rankings. | Scan duration, symbols attempted/succeeded/failed, upstream requests, response bytes, persistence calls, and returned decision class. | Duplicate symbol/timeframe requests within a scan or failed partial work hidden behind HTTP success. A scan must continue to fail visibly on validation errors. |
| Logging and diagnostics | Scan failure diagnostics are retained for seven days; `/health` exposes a sanitized operational snapshot. | Diagnostic record count/bytes, retention deletes, log ingestion bytes, and health endpoint latency. | Repeated identical diagnostics, unbounded retention, exception bodies or upstream payloads in public output. Sanitization and useful failure evidence are safety requirements, not optional savings. |

## Minimum measurement contract

Record one row per workflow run and scan, using UTC timestamps and a run identifier. At minimum, capture:

- `run_id`, workflow/job, trigger reason, status, and terminal result;
- runner duration and billed minutes when the platform exposes them;
- model name, request count, and token counts when an AI call is made;
- upstream request count, retries, status classes, and bytes for research/scan traffic;
- diagnostic bytes created, retained, and deleted; and
- whether a candidate, artifact, or persisted opportunity was actually produced.

Derive these review metrics without estimating missing data:

- **Cost per useful run** = recorded platform/API spend divided by runs that produced a candidate, artifact, or persisted scan result. Report `unknown` when spend or useful-result counts are unavailable.
- **No-output rate** = `NO_CHANGE` plus failed/no-artifact runs divided by all completed runs, split by role and workload.
- **Duplicate-work rate** = requests or jobs identified as duplicates divided by total requests or jobs.
- **Diagnostic retention waste** = bytes deleted at retention time that were not required by an active incident or audit.

A missing counter is an observability gap, not permission to infer savings. Review hourly workloads daily for the first week after instrumentation and then weekly; retain raw counters long enough to reconcile provider invoices.

## Safe control actions

1. Prefer deterministic filtering, caching, batching, and bounded retries before reducing validation coverage or safety checks.
2. Route a role to `NO_CHANGE` when inspection finds no safe bounded change; do not manufacture edits to increase output.
3. Deduplicate identical research/scan inputs only when the cache key includes symbol, timeframe, source, and requested time range. Never reuse data across incompatible windows.
4. Bound diagnostic retention and redact secrets, exception bodies, and upstream response bodies while preserving sanitized error types and run identifiers.
5. Investigate high no-output or duplicate-work rates with run-level evidence before changing cadence, parallelism, model routing, or retry limits.

These controls must not weaken chronological train/validation/untouched-OOS separation, fail-closed production validation, scan response validation, or security/reliability gates. Model prices and provider billing should be rechecked before using token or runner measurements to justify a routing change.
