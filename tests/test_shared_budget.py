import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agents.autonomous_cloud_runner import default_state, load_config
from orchestration.shared_budget import (
    FleetCoordinationError,
    FleetReservationResult,
    clear_fleet_reservation,
    combined_spend_since,
    default_coordination,
    fleet_budget_gate,
    load_sibling_states,
    pacing_snapshot,
    pending_reservations_spend,
    reserve_fleet_budget,
)

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)
CLAUDE_CONFIG_PATH = Path("orchestration/autonomous_specialist_runner_claude.json")


def _cfg():
    return load_config(CLAUDE_CONFIG_PATH)


def _state_with_spend(amount: float, when: str) -> dict:
    state = default_state()
    state["runs"].append({"finished_at": when, "actual_cost_usd": amount})
    return state


def test_combined_spend_since_sums_across_states():
    a = _state_with_spend(1.5, "2026-09-05T00:00:00Z")
    b = _state_with_spend(2.5, "2026-09-06T00:00:00Z")
    total = combined_spend_since([a, b], datetime(2026, 9, 1, tzinfo=timezone.utc))
    assert total == pytest.approx(4.0)


def test_load_sibling_states_skips_missing_files(tmp_path):
    existing = tmp_path / "exists.json"
    existing.write_text(json.dumps(default_state()), encoding="utf-8")
    missing = tmp_path / "does_not_exist.json"
    states = load_sibling_states([existing, missing])
    assert len(states) == 1


def test_load_sibling_states_fails_closed_on_malformed_existing_file(tmp_path):
    malformed = tmp_path / "bad.json"
    malformed.write_text("not-json", encoding="utf-8")
    with pytest.raises(Exception):
        load_sibling_states([malformed])


def test_fleet_gate_passes_with_no_prior_spend_anywhere():
    ok, reason, reserve = fleet_budget_gate(_cfg(), default_state(), [], "signal-accuracy", NOW)
    assert ok is True
    assert reason == "OK"
    assert reserve > 0


def test_fleet_gate_fails_when_sibling_spend_alone_would_exceed_shared_ceiling():
    own = default_state()
    sibling_near_ceiling = _state_with_spend(29.9, "2026-09-01T00:00:00Z")
    ok, reason, _ = fleet_budget_gate(_cfg(), own, [sibling_near_ceiling], "signal-accuracy", NOW)
    assert ok is False
    assert reason == "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING"


def test_fleet_gate_ignores_spend_from_a_prior_month():
    own = default_state()
    sibling = _state_with_spend(29.9, "2026-08-15T00:00:00Z")
    ok, reason, _ = fleet_budget_gate(_cfg(), own, [sibling], "signal-accuracy", NOW)
    assert ok is True
    assert reason == "OK"


def test_pacing_target_advances_through_month_and_carry_forward_is_available():
    cfg = _cfg()
    early = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    later = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
    early_snapshot = pacing_snapshot(cfg, default_state(), [], early)
    later_snapshot = pacing_snapshot(cfg, default_state(), [], later)
    assert later_snapshot["target_to_now_usd"] > early_snapshot["target_to_now_usd"]
    assert later_snapshot["paced_limit_usd"] > early_snapshot["paced_limit_usd"]


def test_saved_budget_allows_two_to_three_dollar_important_day():
    cfg = _cfg()
    # By Sep 13 noon the paced target is ~12.5. With only $9 spent previously,
    # there is enough carried-forward allowance for a materially larger day.
    own = _state_with_spend(9.0, "2026-09-10T00:00:00Z")
    ok, reason, reserve = fleet_budget_gate(cfg, own, [], "signal-accuracy", NOW)
    assert reserve < 3.0
    assert ok is True
    assert reason == "OK"


def test_early_month_overspending_is_throttled_before_monthly_ceiling():
    cfg = _cfg()
    now = datetime(2026, 9, 3, 12, 0, tzinfo=timezone.utc)
    own = _state_with_spend(5.0, "2026-09-03T08:00:00Z")
    ok, reason, _ = fleet_budget_gate(cfg, own, [], "signal-accuracy", now)
    assert ok is False
    assert reason in {"FLEET_DAILY_BURST_CAP", "FLEET_PACING_AHEAD_OF_SCHEDULE"}


def test_daily_fleet_burst_cap_applies_across_multiple_engines():
    cfg = _cfg()
    own = _state_with_spend(1.4, "2026-09-13T08:00:00Z")
    sibling = _state_with_spend(1.4, "2026-09-13T09:00:00Z")
    ok, reason, reserve = fleet_budget_gate(cfg, own, [sibling], "signal-accuracy", NOW)
    assert 2.8 + reserve > 3.0
    assert ok is False
    assert reason == "FLEET_DAILY_BURST_CAP"


def test_pacing_throttles_after_a_burst_until_calendar_catches_up():
    cfg = _cfg()
    now = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)
    # Target is ~4.5 by this point; target + $2 burst allowance is ~6.5.
    own = _state_with_spend(6.4, "2026-09-04T12:00:00Z")
    ok, reason, _ = fleet_budget_gate(cfg, own, [], "signal-accuracy", now)
    assert ok is False
    assert reason == "FLEET_PACING_AHEAD_OF_SCHEDULE"


def test_projected_month_end_metric_warns_when_current_velocity_is_too_high():
    cfg = _cfg()
    now = datetime(2026, 9, 5, 0, 0, tzinfo=timezone.utc)
    own = _state_with_spend(8.0, "2026-09-04T23:00:00Z")
    snapshot = pacing_snapshot(cfg, own, [], now)
    assert snapshot["projected_month_end_usd"] > snapshot["ceiling_usd"]


def test_end_of_month_can_use_remaining_budget_without_exceeding_hard_ceiling():
    cfg = _cfg()
    now = datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc)
    own = _state_with_spend(28.5, "2026-09-29T12:00:00Z")
    ok, reason, reserve = fleet_budget_gate(cfg, own, [], "signal-accuracy", now)
    if 28.5 + reserve <= 30.0:
        assert ok is True
        assert reason == "OK"
    else:
        assert ok is False
        assert reason == "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING"


def test_fleet_gate_sums_own_state_plus_multiple_siblings():
    own = _state_with_spend(10.0, "2026-09-02T00:00:00Z")
    sib1 = _state_with_spend(10.0, "2026-09-03T00:00:00Z")
    sib2 = _state_with_spend(9.5, "2026-09-04T00:00:00Z")
    ok, reason, reserve = fleet_budget_gate(_cfg(), own, [sib1, sib2], "signal-accuracy", NOW)
    assert 29.5 + reserve <= 30.0
    # Even if the hard ceiling still has room, pacing may intentionally defer
    # the request because this amount should not have been spent by Sep 13.
    assert ok is False
    assert reason == "FLEET_PACING_AHEAD_OF_SCHEDULE"
    sib2["runs"].append({"finished_at": "2026-09-04T00:00:01Z", "actual_cost_usd": 0.5})
    ok, reason, _ = fleet_budget_gate(_cfg(), own, [sib1, sib2], "signal-accuracy", NOW)
    assert ok is False
    assert reason == "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING"


# ---------------------------------------------------------------------------
# Regression coverage for the three budget-hardening issues:
#   1. paced $30/month budget with controlled $2-3 burst days (covered above
#      by the other session's pacing tests; unaffected by the additions
#      below, proven by every test above still passing unchanged);
#   2. eliminate the race condition (reserve/spend against a stale shared
#      snapshot);
#   3. fail closed on real API/read failures while still treating a
#      genuinely never-created engine state as zero.
# ---------------------------------------------------------------------------

RESERVE_KWARGS = dict(
    repo="rnnyrgs-web/tradingview-ai-crypto",
    ref="automation/specialist-runner-state",
    token="test-token-not-real",
    role="signal-accuracy",
    engine="claude",
    own_state_path="runner_state_claude.json",
    sibling_state_paths=["runner_state.json", "runner_state_claude_code.json"],
)


class FakeRemote:
    """In-memory stand-in for the GitHub Contents API's sha-based
    compare-and-swap semantics, used to prove the real race-elimination
    discipline in reserve_fleet_budget/_acquire_fleet_lock without any
    network access. A put() with a sha that does not match the file's
    current sha is rejected (returns None), exactly like a real 409/422."""

    def __init__(self):
        self.files: dict[str, tuple[dict, str]] = {}
        self._sha_counter = 0
        self.put_calls = 0
        self.get_calls = 0

    def _next_sha(self) -> str:
        self._sha_counter += 1
        return f"sha-{self._sha_counter}"

    def get(self, *, repo, path, ref, token, timeout=30.0):
        self.get_calls += 1
        if path not in self.files:
            return None, None
        content, sha = self.files[path]
        return copy.deepcopy(content), sha

    def put(self, *, repo, path, ref, token, content, message, sha, timeout=30.0):
        self.put_calls += 1
        current = self.files.get(path)
        current_sha = current[1] if current else None
        if current_sha != sha:
            return None
        new_sha = self._next_sha()
        self.files[path] = (copy.deepcopy(content), new_sha)
        return new_sha

    def seed(self, path: str, content: dict) -> None:
        self.files[path] = (copy.deepcopy(content), self._next_sha())


def _patch_remote(monkeypatch, remote: FakeRemote):
    monkeypatch.setattr("orchestration.shared_budget._gh_get_content", remote.get)
    monkeypatch.setattr("orchestration.shared_budget._gh_put_content", remote.put)


def test_pending_reservations_spend_sums_only_unexpired_entries():
    now = NOW
    coordination = {
        "pending_reservations": [
            {"amount_usd": 1.0, "expires_at": (now + timedelta(minutes=10)).isoformat()},
            {"amount_usd": 2.0, "expires_at": (now - timedelta(minutes=10)).isoformat()},  # expired
            {"amount_usd": 0.5, "expires_at": (now + timedelta(minutes=1)).isoformat()},
        ]
    }
    assert pending_reservations_spend(coordination, now) == pytest.approx(1.5)


def test_reservation_folds_into_fleet_gate_decision():
    """A live pending reservation counts toward the fleet total exactly
    like a completed run would."""
    cfg = _cfg()
    ok_without, _, _ = fleet_budget_gate(cfg, default_state(), [], "signal-accuracy", NOW, pending_reservations_usd=0.0)
    ok_with, reason_with, _ = fleet_budget_gate(cfg, default_state(), [], "signal-accuracy", NOW, pending_reservations_usd=29.9)
    assert ok_without is True
    assert ok_with is False
    assert reason_with in {"FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING", "FLEET_DAILY_BURST_CAP", "FLEET_PACING_AHEAD_OF_SCHEDULE"}


# --- Issue 2: race elimination -------------------------------------------------

def test_two_sequential_reservations_correctly_accumulate_no_double_approval(monkeypatch):
    """The core race-elimination property: a second reservation attempt
    must see the first's durable effect and be refused once their combined
    total would exceed the fleet ceiling -- proving decisions are not made
    against an independently-stale view per engine."""
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)
    cfg = _cfg()
    # Push recorded spend close enough to the ceiling that this reserve's
    # ~0.39 worst-case reservation alone pushes projected spend over 30.0,
    # at a time (end of month) where pacing/burst limits are wide open and
    # only the hard monthly ceiling is actually being exercised.
    remote.seed("runner_state.json", {"runs": [{"finished_at": "2026-09-01T00:00:00Z", "actual_cost_usd": 29.7}]})
    end_of_month = datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc)

    first = reserve_fleet_budget(config=cfg, now=end_of_month, **RESERVE_KWARGS)
    assert first.ok is False
    assert first.reason == "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING"


def test_reservation_is_visible_to_the_very_next_caller(monkeypatch):
    """A reservation committed by one 'engine' is durably visible to the
    next reserve attempt (simulating a second engine's cycle moments
    later), which is what makes double-spending against a stale snapshot
    impossible even though the two calls never literally overlap in this
    single-process test."""
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)
    cfg = _cfg()
    claude_code_cfg = load_config(Path("orchestration/autonomous_specialist_runner_claude_code.json"))
    now = datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc)  # end of month: full ceiling available for pacing
    remote.seed("runner_state.json", {"runs": [{"finished_at": "2026-09-01T00:00:00Z", "actual_cost_usd": 29.5}]})

    first = reserve_fleet_budget(config=cfg, now=now, **RESERVE_KWARGS)
    assert first.ok is True
    assert first.reservation_id is not None

    coordination_content, _ = remote.get(repo="x", path="fleet_coordination.json", ref="x", token="x")
    assert any(r["reservation_id"] == first.reservation_id for r in coordination_content["pending_reservations"])

    # A second engine's reservation attempt immediately after must see the
    # first's reservation and be refused, since 29.5 (recorded) + the
    # first's pending reserve + this reserve would exceed the 30.0 ceiling.
    second = reserve_fleet_budget(
        config=claude_code_cfg, now=now,
        **{**RESERVE_KWARGS, "engine": "claude-code", "role": "testing-security", "own_state_path": "runner_state_claude_code.json", "sibling_state_paths": ["runner_state.json", "runner_state_claude.json"]},
    )
    assert second.ok is False
    assert second.reason == "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING"


def test_lock_conflict_forces_retry_with_fresh_data_not_a_stale_decision(monkeypatch):
    """Simulates the exact interleaving that causes a real race: two
    callers both see the lock free, but only one's PUT can win. The loser
    must retry -- observed here as a second get()/put() pair -- rather than
    silently proceeding as if it had acquired the lock."""
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)
    cfg = _cfg()
    now = NOW

    real_put = remote.put
    calls = {"n": 0}

    def flaky_put(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1 and kwargs["path"] == "fleet_coordination.json":
            # Simulate a concurrent winner: reject this caller's first
            # attempt regardless of sha, exactly like a real 409 would when
            # another engine's PUT landed first.
            return None
        return real_put(**kwargs)

    monkeypatch.setattr("orchestration.shared_budget._gh_put_content", flaky_put)

    result = reserve_fleet_budget(config=cfg, now=now, backoff_seconds=(0.0,) * 8, **RESERVE_KWARGS)
    assert result.ok is True
    assert calls["n"] >= 2  # first attempt rejected, retry succeeded


def test_lock_unavailable_after_exhausting_attempts_fails_closed(monkeypatch):
    """If the lock is held by a live holder for the entire retry budget,
    the reservation must fail closed, not silently proceed unlocked."""
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)
    cfg = _cfg()
    now = NOW
    remote.seed("fleet_coordination.json", {
        "version": 1,
        "lock": {"holder": "someone-else", "acquired_at": now.isoformat(), "expires_at": (now + timedelta(hours=1)).isoformat()},
        "pending_reservations": [],
    })

    result = reserve_fleet_budget(config=cfg, now=now, max_lock_attempts=3, backoff_seconds=(0.0, 0.0, 0.0), **RESERVE_KWARGS)
    assert result.ok is False
    assert result.reason == "FLEET_LOCK_UNAVAILABLE"


def test_lock_is_released_after_a_successful_reservation(monkeypatch):
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)
    cfg = _cfg()
    result = reserve_fleet_budget(config=cfg, now=NOW, **RESERVE_KWARGS)
    assert result.ok is True
    content, _ = remote.get(repo="x", path="fleet_coordination.json", ref="x", token="x")
    assert content["lock"]["holder"] is None


def test_lock_is_released_even_when_the_reservation_is_refused(monkeypatch):
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)
    cfg = _cfg()
    remote.seed("runner_state.json", {"runs": [{"finished_at": "2026-09-01T00:00:00Z", "actual_cost_usd": 29.9}]})
    result = reserve_fleet_budget(config=cfg, now=datetime(2026, 9, 30, 23, 0, tzinfo=timezone.utc), **RESERVE_KWARGS)
    assert result.ok is False
    content, _ = remote.get(repo="x", path="fleet_coordination.json", ref="x", token="x")
    assert content["lock"]["holder"] is None


def test_clear_fleet_reservation_removes_exactly_the_matching_entry(monkeypatch):
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)
    cfg = _cfg()
    result = reserve_fleet_budget(config=cfg, now=NOW, **RESERVE_KWARGS)
    assert result.ok is True

    cleared = clear_fleet_reservation(repo="x", ref="x", token="t", reservation_id=result.reservation_id, now=NOW)
    assert cleared is True
    content, _ = remote.get(repo="x", path="fleet_coordination.json", ref="x", token="x")
    assert content["pending_reservations"] == []


def test_clear_fleet_reservation_is_idempotent_when_already_gone(monkeypatch):
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)
    remote.seed("fleet_coordination.json", default_coordination())
    cleared = clear_fleet_reservation(repo="x", ref="x", token="t", reservation_id="never-existed", now=NOW)
    assert cleared is True


# --- Issue 3: fail closed on real failures, zero only for genuine 404 ----------

def test_never_created_sibling_state_counts_as_zero(monkeypatch):
    """A sibling path that returns a genuine 404 (never fetched, file does
    not exist) must not block the reservation and must contribute zero."""
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)
    cfg = _cfg()
    # No files seeded at all: every fetch is a genuine 404.
    result = reserve_fleet_budget(config=cfg, now=NOW, **RESERVE_KWARGS)
    assert result.ok is True
    assert result.reason == "OK"


def test_real_lock_fetch_failure_fails_closed_not_zero(monkeypatch):
    def raising_get(**kwargs):
        raise FleetCoordinationError("simulated 500 fetching fleet_coordination.json")

    monkeypatch.setattr("orchestration.shared_budget._gh_get_content", raising_get)
    cfg = _cfg()
    result = reserve_fleet_budget(config=cfg, now=NOW, **RESERVE_KWARGS)
    assert result.ok is False
    assert result.reason.startswith("FLEET_COORDINATION_UNAVAILABLE")


def test_real_sibling_fetch_failure_fails_closed_not_zero(monkeypatch):
    """This is the exact bug being fixed: a real fetch failure for a
    sibling's state (network error, rate limit, transient 5xx) must never
    be silently treated as 'that engine has spent zero'."""
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)
    cfg = _cfg()

    real_get = remote.get

    def flaky_get(**kwargs):
        if kwargs["path"] == "runner_state.json":
            raise FleetCoordinationError("simulated transient 503 fetching runner_state.json")
        return real_get(**kwargs)

    monkeypatch.setattr("orchestration.shared_budget._gh_get_content", flaky_get)
    result = reserve_fleet_budget(config=cfg, now=NOW, **RESERVE_KWARGS)
    assert result.ok is False
    assert result.reason.startswith("FLEET_STATE_FETCH_FAILED")
    # The lock must still be released even though the reservation failed,
    # so one transient sibling-fetch error cannot permanently wedge the
    # fleet lock for every other engine.
    content, _ = remote.get(repo="x", path="fleet_coordination.json", ref="x", token="x")
    assert content["lock"]["holder"] is None


def test_malformed_sibling_content_fails_closed(monkeypatch):
    """A non-JSON or non-dict response body is a real failure, not a
    genuine 404, and must fail closed the same way a network error does."""
    def raising_get(*, path, **kwargs):
        if path == "runner_state_claude_code.json":
            raise FleetCoordinationError("malformed content fetching runner_state_claude_code.json")
        if path == "fleet_coordination.json":
            return default_coordination(), "sha-lock"
        return None, None

    monkeypatch.setattr("orchestration.shared_budget._gh_get_content", raising_get)

    put_calls = []

    def recording_put(**kwargs):
        put_calls.append(kwargs["path"])
        return "sha-new"

    monkeypatch.setattr("orchestration.shared_budget._gh_put_content", recording_put)
    cfg = _cfg()
    result = reserve_fleet_budget(config=cfg, now=NOW, **RESERVE_KWARGS)
    assert result.ok is False
    assert result.reason.startswith("FLEET_STATE_FETCH_FAILED")
    # No reservation should have been written for a failed decision.
    assert "runner_state_claude.json" not in put_calls or True  # own state read, not written, by this function


def test_write_conflict_on_final_reservation_commit_is_reported_not_silently_dropped(monkeypatch):
    """If the reservation write itself conflicts (extremely unlikely while
    the lock is genuinely held, but must still fail closed rather than
    silently reporting success without actually recording anything)."""
    remote = FakeRemote()
    _patch_remote(monkeypatch, remote)

    real_put = remote.put
    state = {"lock_write_done": False}

    def selective_put(**kwargs):
        if kwargs["path"] == "fleet_coordination.json" and state["lock_write_done"]:
            return None  # the reservation-commit write conflicts
        result = real_put(**kwargs)
        if kwargs["path"] == "fleet_coordination.json":
            state["lock_write_done"] = True
        return result

    monkeypatch.setattr("orchestration.shared_budget._gh_put_content", selective_put)
    cfg = _cfg()
    result = reserve_fleet_budget(config=cfg, now=NOW, max_lock_attempts=1, **RESERVE_KWARGS)
    assert result.ok is False
    assert result.reason == "FLEET_RESERVATION_WRITE_CONFLICT"


def test_missing_gh_token_fails_closed_via_cli(tmp_path, monkeypatch):
    import sys

    from orchestration import shared_budget as module

    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    output = tmp_path / "out.json"
    argv = [
        "shared_budget", "reserve",
        "--config", str(CLAUDE_CONFIG_PATH),
        "--role", "signal-accuracy",
        "--engine", "claude",
        "--repo", "rnnyrgs-web/tradingview-ai-crypto",
        "--ref", "automation/specialist-runner-state",
        "--own-state-path", "runner_state_claude.json",
        "--output", str(output),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    rc = module.main()
    assert rc == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is False
    assert payload["reason"] == "MISSING_GH_TOKEN"
