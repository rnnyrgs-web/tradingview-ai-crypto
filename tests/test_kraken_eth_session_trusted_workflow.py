from __future__ import annotations

from pathlib import Path


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/pit-trusted-remote-acquisition.yml"
)


def _workflow() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def test_workflow_exposes_only_the_two_frozen_kraken_session_sources() -> None:
    text = _workflow()
    assert "KRAKEN_ETH_SESSION_2026Q1_ARCHIVE" in text
    assert "KRAKEN_ETH_SESSION_2026Q2_ARCHIVE" in text
    assert "KRAKEN_ETH_SESSION_ARBITRARY" not in text
    assert "kraken_eth_session_direct_acquisition.py" in text


def test_kraken_route_needs_no_user_supplied_url_or_pair_override() -> None:
    text = _workflow()
    route = text.split(
        'elif [[ "$SOURCE_KIND" == "KRAKEN_ETH_SESSION_2026Q1_ARCHIVE"', 1
    )[1].split("else", 1)[0]
    assert '--source-kind "$SOURCE_KIND"' in route
    assert "--object-path" not in route
    assert "--target-url" not in route
    assert "ETHUSD" not in route


def test_trusted_workflow_remains_canonical_main_only_and_attested() -> None:
    text = _workflow()
    assert 'test "$GITHUB_REF" = "refs/heads/main"' in text
    assert 'test "$GITHUB_EVENT_NAME" = "workflow_dispatch"' in text
    assert (
        "rnnyrgs-web/tradingview-ai-crypto/.github/workflows/"
        "pit-trusted-remote-acquisition.yml@refs/heads/main"
    ) in text
    assert "subject-path: trusted-acquisition-output/trusted-acquisition.tar" in text
    assert "id-token: write" in text
    assert "attestations: write" in text
