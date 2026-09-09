"""Read-only runner for continuous learning diagnostics.

Consumes genuine resolved prediction-ledger rows and emits a compact research
report for worker/AI inspection. It has no production or trading authority.
"""

from __future__ import annotations

import json

from db import fetch_shadow_predictions
from research_learning import learning_diagnostics


def main():
    rows = fetch_shadow_predictions(limit=10000)
    report = learning_diagnostics(rows)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
