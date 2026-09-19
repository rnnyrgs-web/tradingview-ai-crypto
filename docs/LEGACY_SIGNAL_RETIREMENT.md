# Legacy Signal Retirement and Data Hygiene

Status: ACTIVE CLEANUP

## Why this exists

The project no longer optimizes a high-frequency signal/dashboard product. Its two primary research outcomes are:

1. one genuinely profitable after-cost strategy that survives scientific validation; and
2. scientifically defensible identification of liquid assets with unusually strong evidence for 2x+ upside within 90 days.

The legacy 15-minute scan/dashboard system was still creating roughly 11,520 opportunity rows and 11,520 prediction-ledger forecasts per day before retirement. That activity was not justified by the current research mission.

## Runtime retirement

- The scheduled 15-minute `Crypto 15m Scan` is retired and manual-only/no-op.
- `/scan`, `/evaluate`, `/signals*`, legacy system/signal/paper dashboards, and legacy paper endpoints return HTTP 410.
- The web service no longer starts the paid continuous-AI observer or the legacy paper-trading loop.
- Mission Control and Money Intelligence remain available.
- Historical/backtest/research endpoints remain available.
- A temporary `/research/resolve-pending` endpoint resolves only forecasts that already existed before retirement. It cannot generate new forecasts.
- `.github/workflows/pending_prediction_drain.yml` calls only that drain endpoint and is time-bounded. Remove the workflow as soon as the unresolved legacy ledger reaches zero.

## Supabase policy

Supabase is for compact live coordination and forward evidence, not bulk historical research.

Before cleanup, the two dominant relations were approximately:

- `prediction_ledger`: 112k rows / 245 MB
- `crypto_opportunities`: 115k rows / 230 MB

The `crypto_opportunities` table is redundant legacy presentation state once signal generation is retired and may be truncated after this runtime retirement is deployed.

The `prediction_ledger` is retained temporarily because:
- unresolved immutable forecasts still need to mature;
- recent resolved rows are used by bounded learning/calibration diagnostics;
- historical forecast outcomes may contain scientifically useful negative evidence.

Do not blindly delete it. After pending rows mature, compact scientifically useful columns into a cold research artifact or compact evidence relation, preserve point-in-time provenance, then remove redundant JSON-heavy history.

## Historical data rule

KEEP:
- immutable strategy fingerprints and rejection reasons;
- train/validation/OOS/forward evidence;
- point-in-time universe/provenance;
- historical 2x+ events and matched controls;
- market/on-chain/derivatives/fundamental features used in declared research;
- cost/slippage assumptions and robustness evidence.

RETIRE/COMPACT:
- repeated dashboard snapshots;
- duplicate opportunity rows;
- verbose legacy calibration/presentation payloads that add no incremental research value;
- stale UI-only state.

## Safety

No live broker/trade authority is introduced by this cleanup. Scientific evidence is preserved before destructive compaction. Bulk historical research should use compressed Parquet/object storage + DuckDB/Polars rather than repeated large Supabase JSON reads.


## Prediction-ledger compaction

After the high-volume legacy scan was retired, the remaining large relation is the
scientifically useful prediction ledger. It is compacted rather than discarded.

The compaction migration:
- adds `research_context` for the point-in-time market context and action diagnostics that matter scientifically;
- archives the sparse preforecast universe snapshots separately by `scan_id`;
- leaves unresolved forecasts untouched;
- keeps the newest 2,000 resolved full calibration payloads for recent diagnostics;
- clears older verbose calibration JSON only after the compact context is copied.

Resolved-summary readers no longer request the full calibration blob, reducing egress.
The bounded recent shadow reader can still use full calibration for the newest window.
