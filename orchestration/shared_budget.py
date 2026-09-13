from __future__ import annotations

import base64
import binascii
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

import calendar

from agents.autonomous_cloud_runner import day_start, iso, load_json, month_start, parse_iso, spend_since


def combined_spend_since(states: list[dict[str, Any]], start: datetime) -> float:
    """Sum recorded (completed-run) spend across every engine's runner state since ``start``."""
    return sum(spend_since(state, start) for state in states)


def load_sibling_states(paths: list[Path]) -> list[dict[str, Any]]:
    """Load whichever sibling engine state files currently exist, from local files.

    A missing sibling file (an engine that has never run, or is not yet
    enabled) contributes zero spend. An existing malformed file fails closed
    through load_json/load_state validation rather than being silently
    ignored. Kept for local/offline diagnostics; the live workflow path uses
    ``reserve_fleet_budget`` below instead, which fetches fresh state over
    the network and distinguishes a genuine 404 from a real fetch failure --
    something a local-file existence check cannot do (see
    BUG_REGRESSION_LEDGER.md FLEET-BUDGET-RACE-001).
    """
    states = []
    for path in paths:
        if path.exists():
            states.append(load_json(path))
    return states


def _next_month_start(now: datetime) -> datetime:
    current = month_start(now)
    if current.month == 12:
        return current.replace(year=current.year + 1, month=1)
    return current.replace(month=current.month + 1)


def pacing_snapshot(
    config: dict[str, Any],
    own_state: dict[str, Any],
    sibling_states: list[dict[str, Any]],
    now: datetime,
    reserve: float = 0.0,
    pending_reservations_usd: float = 0.0,
) -> dict[str, float]:
    """Return fleet-wide monthly pacing metrics.

    The project has one shared paid-AI allowance. The pacing target advances
    continuously through the calendar month, unused allowance carries forward,
    and a small bounded burst allowance can temporarily run ahead of pace. Any
    overshoot is then repaid by throttling later work until the calendar catches
    up. This prevents spending most of the month's budget in the first few days.

    ``pending_reservations_usd`` folds in every other engine's currently live
    (not yet recorded, not yet expired) reservation from the shared fleet
    coordination ledger -- see ``reserve_fleet_budget`` -- so an in-flight run
    that has not yet written its completed-run entry still counts toward both
    the daily and monthly totals. It defaults to 0.0 so this function's
    existing pacing-only callers/tests are unaffected.
    """
    all_states = [own_state, *sibling_states]
    start = month_start(now)
    end = _next_month_start(now)
    month_seconds = max(1.0, (end - start).total_seconds())
    elapsed_seconds = min(month_seconds, max(0.0, (now - start).total_seconds()))
    elapsed_fraction = elapsed_seconds / month_seconds

    ceiling = float(config["budget"]["project_monthly_ceiling_usd"])
    monthly = combined_spend_since(all_states, start) + pending_reservations_usd
    daily = combined_spend_since(all_states, day_start(now)) + pending_reservations_usd
    projected = monthly + reserve
    target_to_now = ceiling * elapsed_fraction
    burst_allowance = float(config["budget"].get("fleet_pacing_burst_allowance_usd", 2.0))
    paced_limit = min(ceiling, target_to_now + burst_allowance)
    daily_burst_cap = float(config["budget"].get("fleet_daily_burst_cap_usd", 3.0))

    # Forecast is intentionally conservative early in the month. It is an
    # observability metric, not the sole gate, because a one-off important burst
    # should be allowed and then repaid by subsequent throttling.
    min_fraction = 1.0 / float(calendar.monthrange(start.year, start.month)[1])
    forecast_fraction = max(elapsed_fraction, min_fraction)
    projected_month_end = projected / forecast_fraction if forecast_fraction > 0 else ceiling

    return {
        "monthly_spend_usd": monthly,
        "daily_spend_usd": daily,
        "reserved_cost_usd": reserve,
        "pending_reservations_usd": pending_reservations_usd,
        "projected_after_run_usd": projected,
        "target_to_now_usd": target_to_now,
        "paced_limit_usd": paced_limit,
        "daily_burst_cap_usd": daily_burst_cap,
        "projected_month_end_usd": projected_month_end,
        "elapsed_fraction": elapsed_fraction,
        "ceiling_usd": ceiling,
    }


def fleet_budget_gate(
    config: dict[str, Any],
    own_state: dict[str, Any],
    sibling_states: list[dict[str, Any]],
    role: str,
    now: datetime,
    pending_reservations_usd: float = 0.0,
) -> tuple[bool, str, float]:
    """Fleet-wide pacing and hard-ceiling gate for every paid AI engine.

    This is additive to each engine's local safety limits. The shared gate
    enforces one combined project budget, a maximum daily burst, and a rolling
    calendar-month pace. Unused budget carries forward naturally. A bounded
    burst can run ahead of pace for important work, after which routine paid
    work is automatically deferred until the target catches up.

    Pure decision function: it does not fetch state itself and does not
    know anything about locking. ``reserve_fleet_budget`` below is the
    race-free, fail-closed caller that fetches fresh state under a shared
    lock and then calls this function to decide.
    """
    from agents.autonomous_cloud_runner import reserved_cost_usd  # deferred import

    raw_reserve = reserved_cost_usd(config, role)
    reserve = raw_reserve * float(config["budget"].get("provider_retry_safety_multiplier", 1.0))
    snapshot = pacing_snapshot(config, own_state, sibling_states, now, reserve, pending_reservations_usd)

    if snapshot["projected_after_run_usd"] > snapshot["ceiling_usd"]:
        return False, "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING", reserve

    if snapshot["daily_spend_usd"] + reserve > snapshot["daily_burst_cap_usd"]:
        return False, "FLEET_DAILY_BURST_CAP", reserve

    if snapshot["projected_after_run_usd"] > snapshot["paced_limit_usd"]:
        return False, "FLEET_PACING_AHEAD_OF_SCHEDULE", reserve

    return True, "OK", reserve


# ---------------------------------------------------------------------------
# Race-free, fail-closed fleet coordination.
#
# The functions above decide *whether* a reservation should be granted, given
# a snapshot of state. They say nothing about *how that snapshot is obtained*
# safely when three independent GitHub Actions workflows (OpenAI, Claude,
# Claude Code) can be evaluating the same shared budget concurrently. Reading
# each engine's state file independently and deciding locally -- the
# previous design -- is a classic check-then-act race: two engines can both
# read a stale "we have room" snapshot and both commit spend, together
# exceeding the ceiling neither saw. See BUG_REGRESSION_LEDGER.md
# FLEET-BUDGET-RACE-001.
#
# The fix uses the GitHub Contents API's ``sha`` field as a compare-and-swap
# primitive (the same primitive already used to persist each engine's own
# run-history state) against a single shared coordination file,
# ``fleet_coordination.json``, holding a short-lived mutual-exclusion lock
# plus a list of currently-live "pending reservations" -- spend that has been
# approved but not yet reflected in any engine's completed-run history
# because the run is still executing. The lock is held only for the few HTTP
# round trips needed to fetch fresh state and record a pending reservation,
# never for an entire (up to 35-minute) run, so it cannot starve sibling
# engines' own scheduled cycles.
# ---------------------------------------------------------------------------

FLEET_COORDINATION_PATH = "fleet_coordination.json"
LOCK_TTL_SECONDS = 120
PENDING_RESERVATION_TTL_SECONDS = 2700  # 45 min: > every workflow's 35-min timeout, plus buffer
DEFAULT_LOCK_BACKOFF_SECONDS = (2.0, 4.0, 8.0, 15.0, 20.0, 25.0, 30.0, 30.0)
DEFAULT_MAX_LOCK_ATTEMPTS = 8


class FleetCoordinationError(RuntimeError):
    """A real failure fetching or writing shared fleet coordination state.

    Raised on anything other than a genuine "file does not exist yet" 404:
    network errors, timeouts, non-200/404/409/422 statuses, or malformed
    content. Callers must fail closed on this -- never treat it as
    equivalent to "no one else has spent anything."
    """


def default_coordination() -> dict[str, Any]:
    return {"version": 1, "lock": {"holder": None, "acquired_at": None, "expires_at": None}, "pending_reservations": []}


def _gh_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}


def _gh_get_content(*, repo: str, path: str, ref: str, token: str, timeout: float = 30.0) -> tuple[dict[str, Any] | None, str | None]:
    """GET a JSON file via the GitHub Contents API.

    Returns ``(content, sha)``. Both are ``None`` only on a genuine 404 --
    the sole condition under which a caller may legitimately treat the file
    as "never created" / zero spend. Any other failure (network error,
    timeout, non-200/404 status, malformed base64/JSON) raises
    ``FleetCoordinationError`` so callers fail closed instead of silently
    proceeding on an unverifiable view of fleet state.
    """
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=_gh_headers(token), params={"ref": ref})
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise FleetCoordinationError(f"network failure fetching {path}: {exc}") from exc
    if response.status_code == 404:
        return None, None
    if response.status_code != 200:
        raise FleetCoordinationError(f"unexpected status {response.status_code} fetching {path}: {response.text[:200]}")
    try:
        payload = response.json()
        raw = base64.b64decode(payload["content"])
        return json.loads(raw.decode("utf-8")), str(payload["sha"])
    except (KeyError, ValueError, UnicodeDecodeError, binascii.Error) as exc:
        raise FleetCoordinationError(f"malformed content fetching {path}: {exc}") from exc


def _gh_put_content(*, repo: str, path: str, ref: str, token: str, content: dict[str, Any], message: str, sha: str | None, timeout: float = 30.0) -> str | None:
    """Conditional PUT via the GitHub Contents API.

    Returns the new blob sha on success (200/201). Returns ``None`` on a
    sha conflict (409, or 422 for a stale/missing sha) -- the expected,
    non-exceptional signal that another writer won the race and this caller
    must re-fetch fresh state and retry, never proceed with its stale
    decision. Raises ``FleetCoordinationError`` on any other failure.
    """
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    body: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(json.dumps(content, sort_keys=True).encode("utf-8")).decode("ascii"),
        "branch": ref,
    }
    if sha is not None:
        body["sha"] = sha
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.put(url, headers=_gh_headers(token), json=body)
    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise FleetCoordinationError(f"network failure writing {path}: {exc}") from exc
    if response.status_code in (200, 201):
        try:
            return str(response.json()["content"]["sha"])
        except (KeyError, ValueError) as exc:
            raise FleetCoordinationError(f"malformed success response writing {path}: {exc}") from exc
    if response.status_code in (409, 422):
        return None
    raise FleetCoordinationError(f"unexpected status {response.status_code} writing {path}: {response.text[:200]}")


def _lock_is_live(coordination: dict[str, Any], now: datetime) -> bool:
    lock = coordination.get("lock") or {}
    if not lock.get("holder"):
        return False
    expires_at = parse_iso(lock.get("expires_at"))
    return bool(expires_at and now < expires_at)


def _prune_pending_reservations(coordination: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    kept = []
    for entry in coordination.get("pending_reservations", []) or []:
        expires_at = parse_iso(entry.get("expires_at"))
        if expires_at and now < expires_at:
            kept.append(entry)
    return kept


def pending_reservations_spend(coordination: dict[str, Any], now: datetime) -> float:
    """Sum every currently-live (unexpired) pending reservation's amount."""
    return sum(float(e.get("amount_usd", 0) or 0) for e in _prune_pending_reservations(coordination, now))


def _acquire_fleet_lock(
    *, repo: str, ref: str, token: str, holder: str, now: datetime,
    max_attempts: int = DEFAULT_MAX_LOCK_ATTEMPTS, backoff_seconds: tuple[float, ...] = DEFAULT_LOCK_BACKOFF_SECONDS,
    sleep_fn=time.sleep,
) -> tuple[dict[str, Any], str] | None:
    """Acquire the fleet coordination lock via compare-and-swap.

    Returns ``(coordination, sha)`` for the just-written lock state on
    success, or ``None`` if the lock could not be acquired within
    ``max_attempts`` (a live lock held by someone else the whole time, or
    repeated write conflicts). Callers must fail closed on ``None`` -- it
    means fleet spend could not be safely verified, not that no one else is
    spending.
    """
    for attempt in range(max_attempts):
        fetched, sha = _gh_get_content(repo=repo, path=FLEET_COORDINATION_PATH, ref=ref, token=token)
        current = fetched if isinstance(fetched, dict) else default_coordination()
        if _lock_is_live(current, now):
            sleep_fn(backoff_seconds[min(attempt, len(backoff_seconds) - 1)])
            continue
        candidate = {
            **current,
            "lock": {"holder": holder, "acquired_at": iso(now), "expires_at": iso(now + timedelta(seconds=LOCK_TTL_SECONDS))},
            "pending_reservations": _prune_pending_reservations(current, now),
        }
        new_sha = _gh_put_content(repo=repo, path=FLEET_COORDINATION_PATH, ref=ref, token=token, content=candidate, message=f"acquire fleet budget lock for {holder}", sha=sha)
        if new_sha is not None:
            return candidate, new_sha
        sleep_fn(backoff_seconds[min(attempt, len(backoff_seconds) - 1)])
    return None


def release_fleet_lock(*, repo: str, ref: str, token: str, holder: str, now: datetime) -> None:
    """Best-effort lock release.

    If this fails or conflicts, the lock's TTL guarantees it becomes
    available again regardless, so failures here are swallowed rather than
    raised -- a failed release must never crash the calling workflow step
    that already got its reservation decision.
    """
    try:
        fetched, sha = _gh_get_content(repo=repo, path=FLEET_COORDINATION_PATH, ref=ref, token=token)
    except FleetCoordinationError:
        return
    current = fetched if isinstance(fetched, dict) else default_coordination()
    if (current.get("lock") or {}).get("holder") != holder:
        return  # already released, or the TTL expired and someone else holds it now
    updated = {**current, "lock": {"holder": None, "acquired_at": None, "expires_at": None}}
    try:
        _gh_put_content(repo=repo, path=FLEET_COORDINATION_PATH, ref=ref, token=token, content=updated, message=f"release fleet budget lock for {holder}", sha=sha)
    except FleetCoordinationError:
        return


@dataclass(frozen=True)
class FleetReservationResult:
    ok: bool
    reason: str
    reserved_cost_usd: float = 0.0
    reservation_id: str | None = None


def reserve_fleet_budget(
    *, repo: str, ref: str, token: str, config: dict[str, Any], role: str, engine: str,
    own_state_path: str, sibling_state_paths: list[str], now: datetime,
    max_lock_attempts: int = DEFAULT_MAX_LOCK_ATTEMPTS, backoff_seconds: tuple[float, ...] = DEFAULT_LOCK_BACKOFF_SECONDS,
    sleep_fn=time.sleep,
) -> FleetReservationResult:
    """Race-free, fail-closed fleet budget reservation.

    Acquires the shared fleet lock before reading any state, so two engines
    can never both decide against the same stale snapshot: the loser of a
    concurrent lock-acquire attempt gets a write conflict (see
    ``_acquire_fleet_lock``) and must retry against freshly-fetched state,
    never proceed on what it originally read. Holds the lock only long
    enough to fetch fresh own/sibling state and record a pending
    reservation, then releases it -- never for the whole run.

    Sibling and own state are fetched live via the GitHub Contents API. A
    genuine 404 (an engine that has never run) counts as zero spend. Any
    other fetch failure raises internally and is converted here into a
    clean ``ok=False`` result -- fleet spend could not be verified, so this
    reservation fails closed rather than silently assuming zero.
    """
    holder = f"{engine}:{role}:{uuid.uuid4()}"
    try:
        acquired = _acquire_fleet_lock(repo=repo, ref=ref, token=token, holder=holder, now=now, max_attempts=max_lock_attempts, backoff_seconds=backoff_seconds, sleep_fn=sleep_fn)
    except FleetCoordinationError as exc:
        return FleetReservationResult(False, f"FLEET_COORDINATION_UNAVAILABLE:{exc}")
    if acquired is None:
        return FleetReservationResult(False, "FLEET_LOCK_UNAVAILABLE")
    coordination, _lock_sha = acquired

    try:
        try:
            own_content, _ = _gh_get_content(repo=repo, path=own_state_path, ref=ref, token=token)
            own_state = own_content if isinstance(own_content, dict) else {"runs": []}
            sibling_states: list[dict[str, Any]] = []
            for path in sibling_state_paths:
                content, _ = _gh_get_content(repo=repo, path=path, ref=ref, token=token)
                if content is not None:
                    sibling_states.append(content)
        except FleetCoordinationError as exc:
            return FleetReservationResult(False, f"FLEET_STATE_FETCH_FAILED:{exc}")

        from agents.autonomous_cloud_runner import reserved_cost_usd

        raw_reserve = reserved_cost_usd(config, role)
        reserve = raw_reserve * float(config["budget"].get("provider_retry_safety_multiplier", 1.0))
        pending_usd = pending_reservations_spend(coordination, now)
        ok, reason, _ = fleet_budget_gate(config, own_state, sibling_states, role, now, pending_reservations_usd=pending_usd)
        if not ok:
            return FleetReservationResult(False, reason, reserve)

        reservation_id = str(uuid.uuid4())
        updated = dict(coordination)
        updated["pending_reservations"] = [
            *coordination.get("pending_reservations", []),
            {
                "reservation_id": reservation_id,
                "engine": engine,
                "role": role,
                "amount_usd": round(reserve, 8),
                "reserved_at": iso(now),
                "expires_at": iso(now + timedelta(seconds=PENDING_RESERVATION_TTL_SECONDS)),
            },
        ]
        try:
            # We still hold the lock (no other writer may touch
            # fleet_coordination.json while a live lock is held), so this
            # write uses the sha from our own lock acquisition and is
            # expected to succeed without conflict.
            written = _gh_put_content(repo=repo, path=FLEET_COORDINATION_PATH, ref=ref, token=token, content=updated, message=f"reserve ${reserve:.4f} for {holder}", sha=_lock_sha)
        except FleetCoordinationError as exc:
            return FleetReservationResult(False, f"FLEET_RESERVATION_WRITE_FAILED:{exc}")
        if written is None:
            return FleetReservationResult(False, "FLEET_RESERVATION_WRITE_CONFLICT")
        return FleetReservationResult(True, "OK", reserve, reservation_id)
    finally:
        release_fleet_lock(repo=repo, ref=ref, token=token, holder=holder, now=now)


def clear_fleet_reservation(
    *, repo: str, ref: str, token: str, reservation_id: str, now: datetime,
    max_attempts: int = DEFAULT_MAX_LOCK_ATTEMPTS, backoff_seconds: tuple[float, ...] = DEFAULT_LOCK_BACKOFF_SECONDS,
    sleep_fn=time.sleep,
) -> bool:
    """Remove one pending reservation once its run has actually completed.

    Idempotent: a reservation that is already gone (cleared previously, or
    expired and pruned) counts as success. Uses the same lock-protected CAS
    discipline as reservation itself, so clearing cannot race with another
    engine's concurrent reserve/clear. Best-effort by design (mirrors
    ``release_fleet_lock``): if this cannot complete, the reservation's own
    TTL still expires it eventually, so a failure here degrades to
    "temporarily conservative," never to a safety gap.
    """
    holder = f"clear:{reservation_id}:{uuid.uuid4()}"
    for attempt in range(max_attempts):
        try:
            fetched, sha = _gh_get_content(repo=repo, path=FLEET_COORDINATION_PATH, ref=ref, token=token)
        except FleetCoordinationError:
            return False
        current = fetched if isinstance(fetched, dict) else default_coordination()
        if _lock_is_live(current, now):
            sleep_fn(backoff_seconds[min(attempt, len(backoff_seconds) - 1)])
            continue
        remaining = [r for r in _prune_pending_reservations(current, now) if r.get("reservation_id") != reservation_id]
        candidate = {**current, "lock": {"holder": holder, "acquired_at": iso(now), "expires_at": iso(now + timedelta(seconds=LOCK_TTL_SECONDS))}, "pending_reservations": remaining}
        try:
            new_sha = _gh_put_content(repo=repo, path=FLEET_COORDINATION_PATH, ref=ref, token=token, content=candidate, message=f"clear reservation {reservation_id}", sha=sha)
        except FleetCoordinationError:
            return False
        if new_sha is None:
            sleep_fn(backoff_seconds[min(attempt, len(backoff_seconds) - 1)])
            continue
        release_fleet_lock(repo=repo, ref=ref, token=token, holder=holder, now=now)
        return True
    return False


def main() -> int:
    """CLI used by every engine's workflow around its execute step.

    ``reserve`` performs the race-free, fail-closed fleet reservation right
    before executing and prints ``{"ok", "reason", "reserved_cost_usd",
    "reservation_id"}``; the workflow proceeds only when ``ok`` is true.
    ``clear-reservation`` removes the reservation once the run has
    concluded (success, no-change, or failure alike), so normal completion
    does not wait for the 45-minute pending-reservation TTL to free the
    budget for sibling engines.
    """
    import argparse
    import os

    from agents.autonomous_cloud_runner import load_config, utc_now

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    reserve = sub.add_parser("reserve")
    reserve.add_argument("--config", required=True)
    reserve.add_argument("--role", required=True)
    reserve.add_argument("--engine", required=True, choices=("openai", "claude", "claude-code"))
    reserve.add_argument("--repo", required=True)
    reserve.add_argument("--ref", required=True)
    reserve.add_argument("--own-state-path", required=True)
    reserve.add_argument("--sibling-state-path", action="append", default=[], dest="sibling_state_paths")
    reserve.add_argument("--output", required=True)

    clear = sub.add_parser("clear-reservation")
    clear.add_argument("--repo", required=True)
    clear.add_argument("--ref", required=True)
    clear.add_argument("--reservation-id", required=True)

    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""

    if args.command == "reserve":
        if not token:
            result = FleetReservationResult(False, "MISSING_GH_TOKEN")
        else:
            config = load_config(Path(args.config))
            result = reserve_fleet_budget(
                repo=args.repo, ref=args.ref, token=token, config=config, role=args.role, engine=args.engine,
                own_state_path=args.own_state_path, sibling_state_paths=args.sibling_state_paths, now=utc_now(),
            )
        Path(args.output).write_text(
            json.dumps({"ok": result.ok, "reason": result.reason, "reserved_cost_usd": round(result.reserved_cost_usd, 8), "reservation_id": result.reservation_id}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"ok": result.ok, "reason": result.reason, "reservation_id": result.reservation_id}, separators=(",", ":")))
        return 0 if result.ok else 1

    if args.command == "clear-reservation":
        if not token:
            print(json.dumps({"cleared": False, "reason": "MISSING_GH_TOKEN"}))
            return 1
        cleared = clear_fleet_reservation(repo=args.repo, ref=args.ref, token=token, reservation_id=args.reservation_id, now=utc_now())
        print(json.dumps({"cleared": cleared}))
        return 0 if cleared else 1

    raise RuntimeError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
