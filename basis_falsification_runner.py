"""Retired compatibility runtime for the reserved profitability-falsification lane.

DATA-BASIS-001 and DATA-FUNDING-001 are both permanently rejected under their
frozen fingerprints.  The historical filename remains only because the bounded
worker-army wiring still references it.  Re-running either rejected experiment
would waste scarce research compute and encourage accidental hypothesis rescue.

This runtime therefore performs no market-data requests and no evaluation.  It
writes only a compact fail-closed retirement summary so existing observability
continues to work until this compatibility worker is removed during a broader
worker-layout refactor.

It has no signal, paper, promotion, broker, or live-trade authority.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

SUMMARY_ENV = "BASIS_FALSIFICATION_SUMMARY_PATH"


def run() -> dict:
    return {
        "research_only": True,
        "task_id": "COORD-DATA-004",
        "candidate_id": "DATA-FUNDING-001",
        "legacy_runtime_filename": "basis_falsification_runner.py",
        "evidence_conclusion": "retired_rejected_fingerprint",
        "retired": True,
        "retirement_reason": "candidate_rejected_no_material_condition_change",
        "market_data_requests": 0,
        "evaluation_performed": False,
        "production_authority": False,
        "signal_authority": False,
        "paper_authority": False,
        "promotion_authority": False,
        "broker_authority": False,
    }


def main() -> int:
    summary_path = os.getenv(SUMMARY_ENV)
    if not summary_path:
        raise RuntimeError(f"{SUMMARY_ENV} is required")
    payload = run()
    path = Path(summary_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
