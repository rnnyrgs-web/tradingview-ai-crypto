import pytest

from big_move_coinmetrics_git_snapshot import (
    bind_metric_from_snapshot,
    git_blob_sha,
    validate_snapshot_attestation,
)


def _csv(rows):
    header = "time,CapMrktCurUSD,SplyCur\n"
    body = "\n".join(f"{d},{cap},{supply}" for d, cap, supply in rows)
    return (header + body + "\n").encode()


def _attestation(raw, *, commit_at="2023-12-31T13:27:49Z", path="csv/btc.csv"):
    commit = "028cc389e272a99ebf408f31cd92087a2e300653"
    return {
        "schema": "coinmetrics_upstream_git_snapshot_proof.v1",
        "repository": "coinmetrics/data",
        "commit_sha": commit,
        "tree_sha": "6d147e6e0ea65003a569c91922e335c4ecc3483a",
        "author_login": "coinmetricsbot",
        "commit_at": commit_at,
        "csv_path": path,
        "csv_blob_sha": git_blob_sha(raw),
        "upstream_commit_api_url": f"https://api.github.com/repos/coinmetrics/data/commits/{commit}",
        "upstream_contents_api_url": f"https://api.github.com/repos/coinmetrics/data/contents/{path}?ref={commit}",
        "capture_verdict": "UPSTREAM_RESOLUTION_VERIFIED",
    }


def test_binds_latest_nonblank_predecision_market_cap_and_supply():
    raw = _csv(
        [
            ("2023-12-29", "822504553591.41", "19584092.9"),
            ("2023-12-30", "826574939575.07", "19584999.2"),
            ("2023-12-31", "", ""),
        ]
    )
    attestation = _attestation(raw)
    cap = bind_metric_from_snapshot(
        raw, attestation, metric="CapMrktCurUSD", decision_at="2024-01-01T00:00:00Z"
    )
    supply = bind_metric_from_snapshot(
        raw, attestation, metric="SplyCur", decision_at="2024-01-01T00:00:00Z"
    )
    assert cap["row_date"] == "2023-12-30"
    assert cap["staleness_days"] == 2
    assert cap["value"] == "826574939575.07"
    assert supply["value"] == "19584999.2"
    assert cap["fork_contents_used_as_evidence"] is False
    assert cap["outcome_access"] == "SEALED"
    assert cap["prediction_authority"] is False
    assert cap["trade_authority"] is False


def test_current_day_row_is_never_eligible_even_when_populated():
    raw = _csv(
        [
            ("2023-12-30", "100", "10"),
            ("2023-12-31", "200", "20"),
            ("2024-01-01", "999999", "999999"),
        ]
    )
    attestation = _attestation(raw)
    result = bind_metric_from_snapshot(
        raw, attestation, metric="CapMrktCurUSD", decision_at="2024-01-01T00:00:00Z"
    )
    assert result["row_date"] == "2023-12-31"
    assert result["value"] == "200"


def test_stale_nonblank_metric_fails_closed_instead_of_backfilling():
    raw = _csv(
        [
            ("2023-12-20", "100", "10"),
            ("2023-12-31", "", ""),
        ]
    )
    attestation = _attestation(raw)
    with pytest.raises(ValueError, match="too stale"):
        bind_metric_from_snapshot(
            raw, attestation, metric="SplyCur", decision_at="2024-01-01T00:00:00Z"
        )


def test_retained_csv_must_match_exact_git_blob():
    raw = _csv([("2023-12-30", "100", "10")])
    attestation = _attestation(raw)
    tampered = _csv([("2023-12-30", "101", "10")])
    with pytest.raises(ValueError, match="does not match upstream Git blob SHA"):
        bind_metric_from_snapshot(
            tampered, attestation, metric="CapMrktCurUSD", decision_at="2024-01-01T00:00:00Z"
        )


def test_fork_or_unverified_capture_can_never_pass_attestation():
    raw = _csv([("2023-12-30", "100", "10")])
    attestation = _attestation(raw)
    attestation["repository"] = "croque-m/coinmetrics-data"
    with pytest.raises(ValueError, match="original upstream repository"):
        validate_snapshot_attestation(attestation, decision_at="2024-01-01T00:00:00Z")

    attestation = _attestation(raw)
    attestation["capture_verdict"] = "SELF_ASSERTED"
    with pytest.raises(ValueError, match="trusted capture"):
        validate_snapshot_attestation(attestation, decision_at="2024-01-01T00:00:00Z")


def test_post_cutoff_commit_and_wrong_url_fail_closed():
    raw = _csv([("2023-12-30", "100", "10")])
    attestation = _attestation(raw, commit_at="2024-01-01T00:00:00Z")
    with pytest.raises(ValueError, match="must predate decision cutoff"):
        validate_snapshot_attestation(attestation, decision_at="2024-01-01T00:00:00Z")

    attestation = _attestation(raw)
    attestation["upstream_contents_api_url"] = "https://api.github.com/repos/coinmetrics/data/contents/csv/eth.csv"
    with pytest.raises(ValueError, match="contents URL"):
        validate_snapshot_attestation(attestation, decision_at="2024-01-01T00:00:00Z")


def test_only_predeclared_metrics_and_positive_values_are_accepted():
    raw = _csv([("2023-12-30", "100", "10")])
    attestation = _attestation(raw)
    with pytest.raises(ValueError, match="not predeclared"):
        bind_metric_from_snapshot(
            raw, attestation, metric="PriceUSD", decision_at="2024-01-01T00:00:00Z"
        )

    bad = _csv([("2023-12-30", "100", "0")])
    attestation = _attestation(bad)
    with pytest.raises(ValueError, match="finite and > 0"):
        bind_metric_from_snapshot(
            bad, attestation, metric="SplyCur", decision_at="2024-01-01T00:00:00Z"
        )
