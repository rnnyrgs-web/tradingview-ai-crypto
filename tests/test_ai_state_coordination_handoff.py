from pathlib import Path
import json

from continuous_coordinator import parse_state_last_updated



def test_authoritative_ai_state_tracks_effective_data_market_handoff():
    text = Path("AI_STATE.md").read_text(encoding="utf-8")

    # Durable state must preserve the historical DATA-BREADTH maturation gate
    # while allowing a separate strategy-discovery data task to advance.
    assert "## SAFETY INVARIANTS" in text
    assert "## EXACT NEXT STEP" in text
    assert "`COORD-DATA-005`: **DONE**" in text
    assert "`COORD-DATA-006`: **DONE**" in text
    assert "`COORD-DATA-007`: **BLOCKED**" in text
    assert "Do not select another DATA-BREADTH candidate" in text
    assert "do **not** read only the base json" in text.lower()

    stale_claims = (
        "COORD-DATA-005 as the next READY data-market task",
        "COORD-DATA-005 is the next READY data-market task",
    )
    assert not any(claim in text for claim in stale_claims)


def test_data_market_backlog_respects_data_breadth_maturation_gate():
    """Prevent DATA-BREADTH backlog work from bypassing its prospective-maturation gate."""
    text = Path("AI_STATE.md").read_text(encoding="utf-8")
    backlog = json.loads(Path("orchestration/priority_backlog.json").read_text(encoding="utf-8"))
    acc005 = next(item for item in backlog["items"] if item["id"] == "ACC-005")

    assert "`COORD-DATA-007`: **BLOCKED**" in text
    assert "Do not select another DATA-BREADTH candidate" in text
    assert acc005["owner"] == "data-market"
    assert acc005["status"] == "BLOCKED"
    assert "DATA-BREADTH-001" in acc005["block_reason"]

def test_authoritative_ai_state_preserves_coordinator_freshness_contract():
    """Regression for PR #325: coordinator must parse the real state header."""
    text = Path("AI_STATE.md").read_text(encoding="utf-8")
    first_ten_lines = text.splitlines()[:10]

    # The deployed coordinator intentionally scans only a bounded header window.
    # Renaming/removing this marker previously made a healthy research service
    # fail closed with canonical_state_check_failed/coordinator_repeated_failures.
    assert any(line.startswith("Last updated:") for line in first_ten_lines)
    parsed = parse_state_last_updated(text)
    assert parsed is not None
    assert parsed.strip()

    # Keep the human reconciliation marker too; it is useful context, but it is
    # not a substitute for the machine-readable coordinator freshness contract.
    assert any(line.startswith("Last reconciled:") for line in first_ten_lines)
