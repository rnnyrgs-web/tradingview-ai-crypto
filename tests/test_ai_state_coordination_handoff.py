from pathlib import Path


def test_authoritative_ai_state_tracks_effective_data_market_handoff():
    text = Path("AI_STATE.md").read_text(encoding="utf-8")

    # Regression for the PR #322 state-drift incident: the durable base
    # coordination JSON still contains the historical COORD-DATA-005 READY row,
    # while the canonical loader applies the later append-only override that
    # marks DATA-BREADTH selection/capture complete and DATA-007 blocked.
    assert "`COORD-DATA-005`: **DONE**" in text
    assert "`COORD-DATA-006`: **DONE**" in text
    assert "`COORD-DATA-007`: **BLOCKED**" in text
    assert "Do not select another data candidate" in text
    assert "do **not** read only the base json" in text.lower()

    stale_claims = (
        "COORD-DATA-005 as the next READY data-market task",
        "COORD-DATA-005 is the next READY data-market task",
    )
    assert not any(claim in text for claim in stale_claims)
