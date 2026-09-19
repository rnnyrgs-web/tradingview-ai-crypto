"""Sparse, read-only owner view of canonical research evidence for issue #456.

Presentation eligibility is deliberately stricter than queue membership. The
threshold below is fixed in code; this module never writes research state.
"""

from __future__ import annotations

import html
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import UUID


ROOT = Path(__file__).resolve().parent
STRATEGY_LIMIT = 3
TWO_X_LIMIT = 5
RESEARCH_LIMIT = 5
STRATEGY_MAX_AGE = timedelta(hours=72)
CYCLE_MAX_AGE = timedelta(hours=48)
MARKET_MAX_AGE = timedelta(hours=24)
UNAVAILABLE = "DATA NOT YET AVAILABLE"
STRATEGY_DISPLAY_RULE = (
    "Predeclared screen pass; positive after-cost train and validation expectancy "
    "and profit factor above 1; at least 30 train and 20 validation trades; "
    "positive validation halves and stressed-cost result; explicit data-integrity, "
    "robustness, and multiple-testing passes; no failure reasons or rejection."
)


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(_str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except ValueError:
        return None


def _fresh(value: Any, now: datetime, maximum: timedelta) -> bool:
    moment = _time(value)
    return moment is not None and -timedelta(minutes=5) <= now - moment <= maximum


def _read(path: Path) -> dict | None:
    try:
        if path.stat().st_size > 8_000_000:
            return None
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else None
    except (OSError, ValueError, UnicodeError):
        return None


def _safe_ref(root: Path, reference: Any, prefix: str) -> Path | None:
    ref = _str(reference).replace("\\", "/")
    if not ref.startswith(prefix) or ".." in Path(ref).parts:
        return None
    path = (root / ref).resolve()
    return path if path.is_relative_to((root / prefix).resolve()) else None


def _coordination(root: Path) -> dict | None:
    state = _read(root / "orchestration/specialist_coordination.json")
    if state is None or not isinstance(state.get("tasks"), list):
        return None
    try:
        from orchestration.coordination_overrides import apply_coordination_overrides

        if root == ROOT:
            return apply_coordination_overrides(state)
        for name in ("specialist_coordination_overrides.json", "lead_coordination_overrides.json"):
            state = apply_coordination_overrides(state, root / "orchestration" / name)
        return state
    except (OSError, ValueError, RuntimeError, TypeError):
        return None


def _rejected(root: Path) -> set[str] | None:
    data = _read(root / "orchestration/rejected_fingerprints.json")
    if data is None or not isinstance(data.get("entries"), list):
        return None
    return {_str(row.get("fingerprint_id")) for row in data["entries"] if isinstance(row, dict)}


def _blocked_by_coordination(fingerprint: str, coordination: dict) -> bool:
    for task in _list(coordination.get("tasks")):
        if not isinstance(task, dict) or task.get("fingerprint_id") != fingerprint:
            continue
        decision = _str(_dict(task.get("completion_evidence")).get("decision")).upper()
        if any(word in decision for word in ("REJECTED", "FAIL", "BLOCKED")):
            return True
        if _str(task.get("status")).upper() == "BLOCKED":
            return True
    return False


def _positive_metric(value: Any, min_trades: int) -> bool:
    metric = _dict(value)
    trades = _number(metric.get("trades"))
    expectancy = _number(metric.get("mean_net_bps"))
    profit_factor = _number(metric.get("profit_factor"))
    return (trades is not None and trades >= min_trades and expectancy is not None
            and expectancy > 0 and profit_factor is not None and profit_factor > 1)


def _eligible_strategy(candidate: dict, evidence: dict, rejected: set[str],
                       coordination: dict, now: datetime) -> bool:
    fingerprint = _str(candidate.get("fingerprint_id"))
    stage = _str(candidate.get("stage")).upper()
    selection = _dict(evidence.get("selection"))
    dataset = _dict(evidence.get("dataset"))
    coverage_start = _time(dataset.get("coverage_start_utc"))
    coverage_end = _time(dataset.get("coverage_end_utc"))
    generated = _time(evidence.get("generated_at"))
    contract_hash = _str(evidence.get("contract_sha256"))
    dataset_hash = _str(dataset.get("normalized_rows_sha256") or dataset.get("dataset_sha256"))
    if (not fingerprint or fingerprint in rejected or _blocked_by_coordination(fingerprint, coordination)
            or evidence.get("fingerprint_id") != fingerprint
            or not re.fullmatch(r"[0-9a-f]{64}", contract_hash)
            or not re.fullmatch(r"[0-9a-f]{64}", dataset_hash)
            or stage not in {"CHEAP_SCREEN_PASS", "VALIDATION_CANDIDATE", "OOS_CANDIDATE", "FORWARD_CANDIDATE"}
            or any(term in _str(evidence.get("status")).upper() for term in ("REJECT", "FAIL", "WAIT", "BLOCK"))
            or not _fresh(evidence.get("generated_at"), now, STRATEGY_MAX_AGE)
            or not _str(dataset.get("source")) or coverage_start is None or coverage_end is None
            or coverage_start >= coverage_end or coverage_end > now or generated is None or generated < coverage_end
            or selection.get("screen_status") != "PRE_OOS_PASS"
            or selection.get("economic_pre_oos_pass") is not True
            or selection.get("eligible_for_deep_freeze") is not True
            or selection.get("data_integrity_ok") is not True
            or selection.get("robustness_pass") is not True
            or selection.get("multiple_testing_pass") is not True
            or not isinstance(selection.get("pooled_failure_reasons"), list)
            or selection["pooled_failure_reasons"]):
        return False
    if not (_positive_metric(selection.get("pooled_train"), 30)
            and _positive_metric(selection.get("pooled_validation"), 20)):
        return False
    halves = _list(selection.get("validation_halves_mean_net_bps"))
    stress = _number(selection.get("stressed_validation_mean_net_bps"))
    cost = _number(selection.get("max_stress_round_trip_cost_bps"))
    return (len(halves) == 2 and all(_number(x) is not None and _number(x) > 0 for x in halves)
            and stress is not None and stress > 0 and cost is not None and cost > 0)


def _strategy_card(candidate: dict, evidence: dict) -> dict:
    selection = evidence["selection"]
    dataset = evidence["dataset"]
    validation = selection["pooled_validation"]
    return {
        "kind": "strategy", "title": _str(candidate.get("name")) or candidate["fingerprint_id"],
        "fingerprint": candidate["fingerprint_id"], "mechanism": _str(candidate.get("economic_mechanism")),
        "markets": _list(candidate.get("target_markets")), "timeframes": _list(candidate.get("target_timeframes")),
        "phase": _str(candidate.get("stage")), "train": selection["pooled_train"],
        "validation": validation, "stressed_bps": selection["stressed_validation_mean_net_bps"],
        "cost_bps": selection["max_stress_round_trip_cost_bps"],
        "oos": "OPENED" if selection.get("untouched_oos_opened") is True else "LOCKED",
        "forward": "OPENED" if selection.get("genuine_forward_opened") is True else "NOT YET VALIDATED",
        "data_period": f"{dataset['coverage_start_utc']} to {dataset['coverage_end_utc']}",
        "provenance": dataset["source"], "updated": evidence["generated_at"],
        "blocker": _str(candidate.get("blocker")) or "Untouched OOS and genuine forward proof remain required.",
        "next_test": _str(selection.get("exact_next_action")) or "Run frozen chronological deep validation without reusing this screen as confirmation.",
        "visuals": _dict(evidence.get("visuals")),
        "mechanism_steps": _list(evidence.get("mechanism_steps")),
        "source_ref": candidate["evidence_ref"],
    }


def _strict_strategies(root: Path, now: datetime) -> list[dict]:
    queue = _read(root / "orchestration/strategy_discovery_queue.json")
    rejected = _rejected(root)
    coordination = _coordination(root)
    if queue is None or rejected is None or coordination is None or not isinstance(queue.get("candidates"), list):
        return []
    result = []
    for candidate in queue["candidates"]:
        if not isinstance(candidate, dict):
            continue
        path = _safe_ref(root, candidate.get("evidence_ref"), "orchestration/evidence/")
        evidence = _read(path) if path else None
        if evidence and _eligible_strategy(candidate, evidence, rejected, coordination, now):
            result.append(_strategy_card(candidate, evidence))
    return result[:STRATEGY_LIMIT]


def _https_source(row: Any, cutoff: datetime) -> bool:
    source = _dict(row)
    url = _str(source.get("url"))
    if not url or any(char.isspace() or ord(char) < 32 or char == "\\" for char in url):
        return False
    try:
        parsed = urlsplit(url)
        valid_host = (parsed.hostname is not None and "." in parsed.hostname
                      and all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", part)
                              for part in parsed.hostname.split(".")))
        if parsed.scheme != "https" or not valid_host or parsed.username or parsed.password or parsed.port == 0:
            return False
    except ValueError:
        return False
    published = _time(source.get("published_at"))
    available = _time(source.get("available_at"))
    captured = _time(source.get("captured_at"))
    return (bool(_str(source.get("source_id")) and _str(source.get("publisher")))
            and published is not None and available is not None and captured is not None
            and published <= available <= captured <= cutoff)


def _timely_evidence(manifest: dict, cutoff: datetime, source_ids: set[str]) -> bool:
    rows = _dict(manifest.get("evidence_rows"))
    for name in ("pit_provenance_verified", "matched_controls_pass",
                 "base_rate_documented", "spot_leverage_decomposed"):
        item = _dict(rows.get(name))
        timestamp = _time(item.get("recorded_at"))
        referenced = _list(item.get("source_ids"))
        if (timestamp is None or timestamp > cutoff or not _str(item.get("summary"))
                or not referenced or any(not isinstance(source, str) or source not in source_ids
                                      for source in referenced)):
            return False
    return True


def _immutable_2x_card(candidate: dict, row: Any, now: datetime) -> dict | None:
    """Use only canonical ledger data for a forward 2x scientific claim."""
    row = _dict(row)
    manifest = _dict(_dict(row.get("calibration")).get("big_move_2x"))
    evidence = _dict(manifest.get("evidence"))
    created = _time(row.get("created_at"))  # Must be database-created, not candidate-supplied.
    cutoff = _time(manifest.get("information_cutoff"))
    observed = _time(manifest.get("reference_observed_at"))
    captured = _time(manifest.get("evidence_captured_at"))
    price = _number(row.get("entry_price"))
    manifest_price = _number(manifest.get("reference_price"))
    candidate_price = _number(candidate.get("reference_price"))
    sources = _list(manifest.get("sources"))
    source_ids = [_str(_dict(source).get("source_id")) for source in sources]
    flags = ("pit_provenance_verified", "matched_controls_pass", "base_rate_documented",
             "spot_leverage_decomposed")
    try:
        valid_scan = str(UUID(_str(row.get("scan_id")))) == row.get("scan_id")
    except ValueError:
        valid_scan = False
    if (isinstance(row.get("id"), bool) or not isinstance(row.get("id"), int) or row["id"] <= 0
            or candidate.get("forecast_id") != row["id"]
            or not valid_scan or candidate.get("scan_id") != row["scan_id"]
            or not _str(row.get("symbol")) or candidate.get("asset") != row["symbol"]
            or row.get("horizon") != "90d" or candidate.get("horizon_days") != 90
            or row.get("direction") != "LONG"
            or row.get("resolved_at") is not None
            or manifest.get("target_multiplier") != 2
            or manifest.get("target_definition") != "at_least_2x_frozen_reference_within_90_days"
            or _number(manifest.get("target_price")) != (price * 2 if price is not None else None)
            or price is None or price <= 0 or manifest_price != price or candidate_price != price
            or created is None or cutoff is None or observed is None or captured is None
            or not _fresh(row.get("created_at"), now, MARKET_MAX_AGE)
            or not observed <= captured <= cutoff <= created <= cutoff + timedelta(minutes=5)
            or cutoff - observed > timedelta(minutes=15)
            or _time(candidate.get("frozen_at")) != created
            or _time(candidate.get("information_cutoff")) != cutoff
            or _time(candidate.get("observed_at")) != observed
            or _time(row.get("due_at")) != created + timedelta(days=90)
            or candidate.get("retrospective") is True
            or _str(candidate.get("status")).upper() not in {"PROMISING_RESEARCH", "STRONG_WATCH"}
            or not all(evidence.get(flag) is True for flag in flags)
            or not all(_dict(candidate.get("evidence")).get(flag) is True for flag in flags)
            or not _str(manifest.get("causal_mechanism"))
            or not _list(manifest.get("evidence_for")) or not _list(manifest.get("evidence_against"))
            or not _str(manifest.get("invalidation")) or not _str(manifest.get("next_test"))
            or not sources or len(source_ids) != len(set(source_ids))
            or any(not _https_source(source, cutoff) for source in sources)
            or not _timely_evidence(manifest, cutoff, set(source_ids))
            or candidate.get("sources") != sources
            or manifest.get("reference_price_source_id") not in source_ids):
        return None
    price_source = next(source for source in sources
                        if source["source_id"] == manifest["reference_price_source_id"])
    if (_number(price_source.get("reference_price")) != price
            or _time(price_source.get("observed_at")) != observed
            or _time(price_source.get("published_at")) < observed
            or _time(price_source.get("available_at")) > cutoff):
        return None
    # All scientific text and visuals on a strict card come from the immutable row.
    card = {key: manifest[key] for key in (
        "causal_mechanism", "evidence_for", "evidence_against", "invalidation", "next_test")}
    card.update({"kind": "2x", "title": row["symbol"], "asset": row["symbol"],
                 "forecast_id": row["id"], "reference_price": price,
                 "observed_at": manifest["reference_observed_at"], "frozen_at": row["created_at"],
                 "horizon_days": 90, "two_x_price": price * 2, "sources": sources,
                 "visuals": _dict(manifest.get("visuals"))})
    return card


def _strict_2x(root: Path, now: datetime) -> list[dict]:
    lab = _read(root / "money_intelligence/big_move_lab.json")
    if lab is None or not isinstance(lab.get("forward_candidates", []), list):
        return []
    result = []
    for candidate in lab.get("forward_candidates", [])[:20]:
        if len(result) >= TWO_X_LIMIT:
            break
        if not isinstance(candidate, dict) or candidate.get("retrospective") is True:
            continue
        identity = candidate.get("forecast_id")
        if isinstance(identity, bool) or not isinstance(identity, int) or identity <= 0:
            continue
        try:
            from db import fetch_prediction_by_id
            row = fetch_prediction_by_id(identity)
        except (OSError, RuntimeError, ValueError, TypeError):
            continue
        card = _immutable_2x_card(candidate, row, now)
        if card:
            result.append(card)
    return result[:TWO_X_LIMIT]


CASE_RULES = (
    ("ENA/StablecoinX", ("ena", "stablecoinx"), ("ena", "stablecoinx"), True),
    ("ZEC/ZCSH", ("zec", "zcsh"), ("zec", "zcsh"), True),
    ("BTC tactical momentum", ("btc", "crypto continuation"), ("btc", "etf"), False),
)


def _closest(root: Path, now: datetime) -> list[dict]:
    directory = root / "money_intelligence/research_cycles"
    try:
        paths = sorted(directory.glob("*-cycle.json"), reverse=True)
    except OSError:
        return []
    # A malformed newest cycle blocks fallback to older, possibly contradicted truth.
    if not paths:
        return []
    cycle = _read(paths[0])
    if cycle is None or not _fresh(cycle.get("information_cutoff"), now, CYCLE_MAX_AGE):
        return []
    observations = _list(cycle.get("fresh_validated_observations"))
    next_tests = [_str(x) for x in _list(cycle.get("next_research")) if _str(x)]
    sources = [x for x in _list(cycle.get("source_log")) if isinstance(x, dict)]
    result = []
    for title, topic_tokens, test_tokens, retrospective in CASE_RULES:
        observation = next((row for row in observations if isinstance(row, dict)
                            and any(token in _str(row.get("topic")).lower() for token in topic_tokens)), None)
        if not observation or not _list(observation.get("observed_facts")):
            continue
        inference = (_str(observation.get("inference")) or _str(observation.get("transmission_mechanism"))
                     or _str(observation.get("point_in_time_chain")))
        if not inference or not _str(observation.get("decision_support")):
            continue
        next_test = next((item for item in next_tests if any(token in item.lower() for token in test_tokens)), "")
        if not next_test:
            continue
        relevant_sources = [source for source in sources if any(token in
                            (_str(source.get("topic")) + " " + _str(source.get("url"))).lower()
                            for token in topic_tokens) and _str(source.get("url")).startswith("https://")]
        if not relevant_sources:
            continue
        against = _list(observation.get("alternative_explanations")) + _list(observation.get("negative_controls"))
        if _str(observation.get("negative_control")):
            against.append(observation["negative_control"])
        quality = _str(observation.get("data_quality_note"))
        if quality:
            against.append(quality)
        unknowns = _list(observation.get("unknowns"))
        if not (against or unknowns):
            continue
        result.append({
            "kind": "research", "title": title, "topic": observation["topic"],
            "retrospective": retrospective, "why": _str(observation.get("transmission_mechanism")) or inference,
            "facts": observation["observed_facts"], "inference": inference,
            "causal_chain": _str(observation.get("point_in_time_chain")) or _str(observation.get("transmission_mechanism")),
            "for": _list(observation.get("matched_controls")) or observation["observed_facts"][:2],
            "against": against, "unknowns": unknowns,
            "next_test": next_test, "decision": observation["decision_support"],
            "promote_if": "A predeclared, timestamp-safe matched-control test shows independent after-cost value and clears the applicable canonical validation gates.",
            "drop_if": "The mechanism is falsified, contradictory evidence dominates, or the supporting cycle becomes stale.",
            "sources": relevant_sources[:4], "updated": cycle["information_cutoff"],
            "source_ref": str(paths[0].relative_to(root)).replace("\\", "/"),
        })
    return result[:RESEARCH_LIMIT]


def build_results_snapshot(root: Path = ROOT, *, now: datetime | None = None) -> dict:
    root = Path(root).resolve()
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return {
        "as_of": now.isoformat(), "strategies": _strict_strategies(root, now),
        "candidates_2x": _strict_2x(root, now), "closest_research": _closest(root, now),
        "strategy_rule": STRATEGY_DISPLAY_RULE,
    }


def _esc(value: Any) -> str:
    return html.escape(str(value if value not in (None, "") else "—"), quote=True)


def _field(label: str, value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = "; ".join(str(item) for item in value) or UNAVAILABLE
    return f"<div class='field'><dt>{_esc(label)}</dt><dd>{_esc(value)}</dd></div>"


def _svg_line(values: Any, label: str) -> str:
    if not isinstance(values, list) or len(values) < 2 or len(values) > 1000:
        return f"<div class='unavailable'>{UNAVAILABLE}</div>"
    numeric = [_number(x) for x in values]
    if any(x is None for x in numeric):
        return f"<div class='unavailable'>{UNAVAILABLE}</div>"
    lo, hi = min(numeric), max(numeric)
    span = hi - lo or 1
    points = " ".join(f"{20+i*300/(len(numeric)-1):.1f},{125-(x-lo)*95/span:.1f}" for i, x in enumerate(numeric))
    return (f"<svg viewBox='0 0 340 145' role='img' aria-label='{_esc(label)}'>"
            f"<path d='M20 125H325' stroke='#52677e' fill='none'/>"
            f"<polyline points='{points}' fill='none' stroke='#68cfa7' stroke-width='3'/></svg>")


def _distribution(values: Any) -> str:
    if not isinstance(values, list) or len(values) < 20 or len(values) > 10000:
        return f"<div class='unavailable'>{UNAVAILABLE}</div>"
    numeric = [_number(x) for x in values]
    if any(x is None for x in numeric):
        return f"<div class='unavailable'>{UNAVAILABLE}</div>"
    lo, hi = min(numeric), max(numeric)
    if lo == hi:
        return f"<div class='unavailable'>{UNAVAILABLE}</div>"
    counts = [0] * 10
    for value in numeric:
        counts[min(9, int((value - lo) / (hi - lo) * 10))] += 1
    maximum = max(counts)
    bars = "".join(f"<rect x='{22 + i*30}' y='{125 - count/max(maximum,1)*95:.1f}' width='22' "
                   f"height='{count/max(maximum,1)*95:.1f}' fill='#68cfa7'/>" for i, count in enumerate(counts))
    return (f"<svg viewBox='0 0 340 145' role='img' aria-label='Trade-return distribution'>"
            f"<path d='M20 125H325' stroke='#52677e' fill='none'/>{bars}</svg>"
            f"<div class='sub'>Range: {_esc(round(lo, 3))} to {_esc(round(hi, 3))} · "
            f"{sum(x > 0 for x in numeric)} winners · {sum(x < 0 for x in numeric)} losers · "
            f"{len(numeric)} trades</div>")


def _cost_chart(rows: Any) -> str:
    if not isinstance(rows, list) or len(rows) < 2 or len(rows) > 10:
        return f"<div class='unavailable'>{UNAVAILABLE}</div>"
    points = []
    for row in rows:
        row = _dict(row)
        cost, net = _number(row.get("round_trip_bps")), _number(row.get("mean_net_bps"))
        if cost is None or cost < 0 or net is None:
            return f"<div class='unavailable'>{UNAVAILABLE}</div>"
        points.append((cost, net))
    if len({x for x, _ in points}) != len(points):
        return f"<div class='unavailable'>{UNAVAILABLE}</div>"
    points.sort()
    caption = " · ".join(f"{cost:g} bps cost → {net:+g} bps net" for cost, net in points)
    return _svg_line([net for _, net in points], "After-cost sensitivity") + f"<div class='sub'>{_esc(caption)}</div>"


def _equity_chart(value: Any) -> str:
    segments = _dict(value)
    if not segments:
        return f"<div class='unavailable'>{UNAVAILABLE}</div>"
    items = []
    for key, title in (("train", "Train"), ("validation", "Validation"),
                       ("untouched_oos", "Untouched OOS"), ("forward", "Forward")):
        if key in segments:
            chart = _svg_line(segments[key], title + " after-cost equity")
            if UNAVAILABLE in chart:
                return f"<div class='unavailable'>{UNAVAILABLE}</div>"
            items.append(f"<div><b>{title}</b>{chart}</div>")
    return "".join(items) if items else f"<div class='unavailable'>{UNAVAILABLE}</div>"


def _breakdown(rows: Any) -> str:
    if not isinstance(rows, list) or not rows:
        return f"<div class='unavailable'>{UNAVAILABLE}</div>"
    output = []
    for row in rows[:12]:
        row = _dict(row)
        count = _number(row.get("independent_trades"))
        net = _number(row.get("mean_net_bps"))
        if count is None or count < 20 or net is None or not _str(row.get("label")):
            return f"<div class='unavailable'>{UNAVAILABLE}</div>"
        output.append(_field(row["label"], f"{count:g} independent trades · {net:+g} bps net"))
    return "<dl class='breakdown'>" + "".join(output) + "</dl>"


def _visual_panel(title: str, content: str) -> str:
    return f"<div class='visual'><h4>{_esc(title)}</h4>{content}</div>"


def _strategy_visuals(card: dict) -> str:
    visuals = card["visuals"]
    steps = [str(x) for x in card["mechanism_steps"] if _str(x)]
    diagram = "<div class='flow'>" + "<span>→</span>".join(f"<b>{_esc(x)}</b>" for x in steps) + "</div>" if len(steps) >= 3 else f"<div class='unavailable'>{UNAVAILABLE}</div>"
    panels = [_visual_panel("Mechanism diagram", diagram)]
    trade = _dict(visuals.get("annotated_trade"))
    trade_text = (f"<p>{_esc(trade.get('selection_rule'))}</p>"
                  + _svg_line(trade.get("prices"), "Representative price setup")
                  + "".join(_field(x, trade.get(x)) for x in
                  ("signal_time", "entry", "stop", "exit", "decision_time_information"))) if (
                      _str(trade.get("selection_rule")) and _str(trade.get("signal_time"))
                      and _str(trade.get("decision_time_information")) and _number(trade.get("entry")) is not None
                      and _number(trade.get("stop")) is not None and _number(trade.get("exit")) is not None
                      and len(_list(trade.get("prices"))) >= 2) else f"<div class='unavailable'>{UNAVAILABLE}</div>"
    panels.append(_visual_panel("Representative annotated setup", trade_text))
    panels.append(_visual_panel("After-cost equity curve", _equity_chart(visuals.get("after_cost_equity"))))
    panels.append(_visual_panel("Drawdown curve", _svg_line(visuals.get("drawdown"), "Drawdown curve")))
    panels.append(_visual_panel("Return distribution", _distribution(visuals.get("trade_returns_bps"))))
    panels.append(_visual_panel("Cost sensitivity", _cost_chart(visuals.get("cost_sensitivity"))))
    panels.append(_visual_panel("Parameter and robustness", _svg_line(visuals.get("parameter_robustness"), "Parameter robustness")))
    panels.append(_visual_panel("Asset and regime breakdown", _breakdown(visuals.get("asset_regime_breakdown"))))
    funnel = ["SCREEN: PASS", "VALIDATION: PRE-OOS SCREEN ONLY", f"UNTOUCHED OOS: {card['oos']}",
              f"FORWARD: {card['forward']}", "PROMOTION ELIGIBLE: NO"]
    panels.append(_visual_panel("Validation funnel", "<div class='flow'>" + "<span>→</span>".join(f"<b>{_esc(x)}</b>" for x in funnel) + "</div>"))
    return "<div class='visual-grid'>" + "".join(panels) + "</div>"


def _report(card: dict) -> str:
    if card["kind"] == "strategy":
        rows = [
            ("FACTS", f"Validation: {card['validation']['trades']} trades; {card['validation']['mean_net_bps']} bps after cost; PF {card['validation']['profit_factor']}."),
            ("INFERENCE", "The frozen development screen cleared the presentation bar; independent confirmation is still required."),
            ("HYPOTHESIS", card["mechanism"]), ("CAUSAL CHAIN", card["mechanism"]),
            ("EVIDENCE FOR", f"Positive train, validation halves and stressed cost ({card['stressed_bps']} bps)."),
            ("EVIDENCE AGAINST", card["blocker"]), ("FALSIFIERS", "Failure on untouched OOS, forward proof, cost stress, or robustness."),
            ("UNKNOWNS", "Independent OOS and forward outcomes; representative chart inputs if unavailable."),
            ("NEXT TEST", card["next_test"]), ("SOURCES / PROVENANCE", card["source_ref"] + " · " + card["provenance"]),
        ]
    elif card["kind"] == "2x":
        rows = [("FACTS", card.get("evidence_for")), ("INFERENCE", card.get("thesis")),
                ("HYPOTHESIS", card.get("causal_mechanism")), ("CAUSAL CHAIN", card.get("causal_mechanism")),
                ("EVIDENCE FOR", card.get("evidence_for")), ("EVIDENCE AGAINST", card.get("evidence_against")),
                ("FALSIFIERS", card.get("invalidation")), ("UNKNOWNS", card.get("missing_evidence")),
                ("NEXT TEST", card.get("next_test")), ("SOURCES / PROVENANCE", [x.get("url") for x in _list(card.get("sources")) if isinstance(x, dict)])]
    else:
        rows = [("FACTS", card["facts"]), ("INFERENCE", card["inference"]), ("HYPOTHESIS", card["topic"]),
                ("CAUSAL CHAIN", card["causal_chain"]), ("EVIDENCE FOR", card["for"]),
                ("EVIDENCE AGAINST", card["against"]), ("FALSIFIERS", card["drop_if"]),
                ("UNKNOWNS", card["unknowns"]), ("NEXT TEST", card["next_test"]),
                ("SOURCES / PROVENANCE", card["source_ref"] + " · " + "; ".join(_str(x.get("url")) for x in card["sources"]))]
    return "<dl class='report'>" + "".join(_field(key, value or UNAVAILABLE) for key, value in rows) + "</dl>" + _source_links(card)


def _source_links(card: dict) -> str:
    links = []
    reference = _str(card.get("source_ref"))
    if reference and not reference.startswith("/") and ".." not in Path(reference).parts:
        url = "https://github.com/rnnyrgs-web/tradingview-ai-crypto/blob/main/" + quote(reference)
        links.append(f"<a href='{_esc(url)}' rel='noopener noreferrer'>Canonical artifact</a>")
    for source in _list(card.get("sources"))[:6]:
        url = _str(_dict(source).get("url"))
        if url.startswith("https://"):
            links.append(f"<a href='{_esc(url)}' rel='noopener noreferrer'>{_esc(_dict(source).get('publisher') or 'Source')}</a>")
    return "<div class='source-links'>" + " · ".join(links) + "</div>" if links else ""


def _strategy_html(card: dict) -> str:
    fields = [
        ("Fingerprint", card["fingerprint"]), ("Markets / timeframe", card["markets"] + card["timeframes"]),
        ("Phase", card["phase"]), ("After-cost expectancy", f"{card['validation']['mean_net_bps']} bps / validation trade"),
        ("Profit factor", card["validation"]["profit_factor"]), ("Train / validation trades", f"{card['train']['trades']} / {card['validation']['trades']}"),
        ("Win rate", card["validation"].get("win_rate", UNAVAILABLE)), ("Drawdown", card["validation"].get("max_drawdown", UNAVAILABLE)),
        ("Fees / slippage stress", f"{card['cost_bps']} bps round trip"), ("Stressed result", f"{card['stressed_bps']} bps / validation trade"),
        ("Train", "SCREEN PASS"), ("Validation", "DEVELOPMENT SCREEN PASS"), ("Untouched OOS", card["oos"]),
        ("Forward", card["forward"]), ("Robustness", "EXPLICIT PASS"), ("Search breadth", "EXPLICIT PASS"),
        ("Data period", card["data_period"]), ("Provenance", card["provenance"]),
        ("Blocker", card["blocker"]), ("Next test", card["next_test"]), ("Last updated", card["updated"]),
    ]
    return (f"<article class='card'><div class='tag'>RESEARCH ONLY / NOT LIVE</div><h3>{_esc(card['title'])}</h3>"
            f"<p>{_esc(card['mechanism'])}</p><div class='quick'>"
            f"<strong>{_esc(card['validation']['mean_net_bps'])} bps</strong><span>after cost · validation screen</span>"
            f"<strong>PF {_esc(card['validation']['profit_factor'])}</strong><span>{_esc(card['validation']['trades'])} trades</span></div>"
            f"<details><summary>Evidence, visuals and research report</summary><dl class='facts'>"
            + "".join(_field(k, v) for k, v in fields) + "</dl>" + _strategy_visuals(card)
            + "<h4>Research report</h4>" + _report(card) + "</details></article>")


def _two_x_html(card: dict) -> str:
    rows = [("Reference price", card.get("reference_price")), ("Reference timestamp", card.get("observed_at")),
            ("2x reference", card["two_x_price"]), ("Horizon", f"{card['horizon_days']} days"),
            ("Market cap", card.get("market_cap")), ("Free float", card.get("free_float")),
            ("Liquidity / ADV", card.get("liquidity_adv")), ("Relative strength", card.get("relative_strength")),
            ("Move to date", card.get("move_to_date")), ("Spot vs leverage", card.get("spot_leverage")),
            ("OI", card.get("open_interest")), ("Funding", card.get("funding")), ("Basis", card.get("basis")),
            ("Liquidations", card.get("liquidations")), ("Flows", card.get("flows")),
            ("Tokenomics / unlocks", card.get("tokenomics")), ("Catalyst timeline", card.get("catalysts")),
            ("Matched controls / base rate", card.get("matched_controls")),
            ("Alternative explanation", card.get("alternative_explanation")), ("Invalidation", card.get("invalidation")),
            ("Missing evidence", card.get("missing_evidence")), ("Next test", card.get("next_test"))]
    data = _dict(card.get("visuals"))
    price = _dict(data.get("price_volume_timeline"))
    price_panel = (_svg_line(price.get("prices"), "Price and catalyst timeline")
                   + _svg_line(price.get("volumes"), "Volume timeline")
                   + _field("Catalysts", price.get("catalysts"))) if (
                       len(_list(price.get("prices"))) >= 2 and len(_list(price.get("volumes"))) >= 2
                       and _list(price.get("catalysts"))) else f"<div class='unavailable'>{UNAVAILABLE}</div>"
    relative = _dict(data.get("relative_strength"))
    relative_panel = (_svg_line(relative.get("asset"), "Asset relative strength")
                      + _svg_line(relative.get("matched_controls"), "Matched-control relative strength")) if (
                          len(_list(relative.get("asset"))) >= 2 and len(_list(relative.get("matched_controls"))) >= 2) else f"<div class='unavailable'>{UNAVAILABLE}</div>"
    flows = _dict(data.get("flow_oi_funding"))
    flow_panel = "".join(f"<b>{_esc(name)}</b>{_svg_line(flows.get(key), name)}" for key, name in
                         (("flow", "Flow"), ("oi", "Open interest"), ("funding", "Funding"))) if (
                             all(len(_list(flows.get(key))) >= 2 for key in ("flow", "oi", "funding"))) else f"<div class='unavailable'>{UNAVAILABLE}</div>"
    unlocks = _list(data.get("supply_unlock_timeline"))
    unlock_panel = "".join(_field(_dict(event).get("date"), _dict(event).get("event")) for event in unlocks) if (
        unlocks and all(_str(_dict(event).get("date")) and _str(_dict(event).get("event")) for event in unlocks)) else f"<div class='unavailable'>{UNAVAILABLE}</div>"
    steps = [_str(x) for x in _list(data.get("causal_chain_steps")) if _str(x)]
    chain_panel = "<div class='flow'>" + "<span>→</span>".join(f"<b>{_esc(step)}</b>" for step in steps) + "</div>" if len(steps) >= 3 else f"<div class='unavailable'>{UNAVAILABLE}</div>"
    for_against = _field("For", card.get("evidence_for")) + _field("Against", card.get("evidence_against"))
    visuals = "".join(_visual_panel(name, content) for name, content in (
        ("Price, volume and catalysts", price_panel), ("Relative strength vs controls", relative_panel),
        ("Flow, OI and funding", flow_panel), ("Supply and unlocks", unlock_panel),
        ("Causal chain", chain_panel), ("Evidence for vs against", for_against)))
    return (f"<article class='card'><div class='tag'>PROMISING RESEARCH / NOT LIVE</div><h3>{_esc(card['title'])}</h3>"
            f"<p>{_esc(card['causal_mechanism'])}</p><div class='quick'><strong>2x: {_esc(card['two_x_price'])}</strong>"
            f"<span>within {_esc(card['horizon_days'])} days · research target, no validated forecast</span></div>"
            f"<details><summary>Evidence, visuals and research report</summary><dl class='facts'>"
            + "".join(_field(k, v or UNAVAILABLE) for k, v in rows) + "</dl><div class='visual-grid'>" + visuals
            + "</div><h4>Research report</h4>" + _report(card) + "</details></article>")


def _research_html(card: dict) -> str:
    history = "<span class='history'>RETROSPECTIVE CASE · NOT A PRIOR PREDICTION</span>" if card["retrospective"] else "<span class='history'>CURRENT RESEARCH · NO FORECAST</span>"
    supportive = card["for"][0] if card["for"] else UNAVAILABLE
    against = card["against"][0] if card["against"] else (card["unknowns"][0] if card["unknowns"] else UNAVAILABLE)
    return (f"<article class='card research'><div class='tag muted'>NOT YET PROMISING — RESEARCH ONLY</div>"
            f"{history}<h3>{_esc(card['title'])}</h3><p>{_esc(card['why'])}</p>"
            f"<div class='short'><b>Supports:</b> {_esc(supportive)}</div><div class='short'><b>Against:</b> {_esc(against)}</div>"
            f"<div class='next'><b>Next test:</b> {_esc(card['next_test'])}</div>"
            f"<details><summary>Why it matters and research report</summary><dl class='facts'>"
            + _field("Learned", card["inference"]) + _field("Missing", card["unknowns"] or UNAVAILABLE)
            + _field("Promotion condition", card["promote_if"]) + _field("Disappears if", card["drop_if"])
            + _field("Status", card["decision"]) + _field("Last updated", card["updated"])
            + "</dl><h4>Research report</h4>" + _report(card) + "</details></article>")


def render_results_html(snapshot: dict) -> str:
    strategies = _list(snapshot.get("strategies"))[:STRATEGY_LIMIT]
    two_x = _list(snapshot.get("candidates_2x"))[:TWO_X_LIMIT]
    research = _list(snapshot.get("closest_research"))[:RESEARCH_LIMIT]
    strategy_cards = "".join(_strategy_html(x) for x in strategies) or "<div class='empty'>No promising strategies currently clear the evidence bar.</div>"
    two_x_cards = "".join(_two_x_html(x) for x in two_x) or "<div class='empty'>No promising 90-day 2x+ candidates currently clear the evidence bar.</div>"
    research_cards = "".join(_research_html(x) for x in research) or "<div class='empty'>No fresh, sufficiently documented research case is close enough to show.</div>"
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<meta http-equiv='refresh' content='300'><title>Promising Results</title><style>
:root{{--bg:#071019;--panel:#101e2b;--line:#2a4155;--ink:#eef5fa;--muted:#a0b4c3;--accent:#80d9b4;--amber:#e7bb6a}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Arial,sans-serif}}
.wrap{{max-width:1180px;margin:auto;padding:28px 18px 60px}}header{{display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;align-items:start}}
h1{{font-size:clamp(28px,4vw,42px);margin:0}}h2{{font-size:21px;margin:0 0 4px}}h3{{font-size:18px;margin:8px 0}}h4{{font-size:14px;margin:16px 0 6px}}
p{{margin:6px 0 12px;color:#cfdae3}}.sub,.section-note{{color:var(--muted)}}nav{{display:flex;gap:8px;flex-wrap:wrap}}nav a{{color:#c5e5f8;text-decoration:none;padding:8px 11px;border:1px solid var(--line);border-radius:9px}}nav a[aria-current]{{background:#dff2eb;color:#08221a}}
.hero{{border:1px solid var(--line);background:linear-gradient(120deg,#122b34,#101925);border-radius:16px;padding:20px;margin:22px 0;display:flex;justify-content:space-between;gap:15px;flex-wrap:wrap}}.counts{{display:flex;gap:22px}}.counts strong{{display:block;font-size:28px;color:var(--accent)}}
section{{margin-top:34px}}.section-note{{font-size:13px;margin-bottom:12px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:12px}}
.card,.empty{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}}.empty{{color:var(--muted);border-style:dashed;grid-column:1/-1}}
.tag{{font-size:11px;font-weight:800;letter-spacing:.07em;color:var(--accent)}}.tag.muted{{color:var(--amber)}}.history{{display:block;font-size:10px;color:var(--muted);margin-top:3px}}.quick{{display:flex;gap:8px;align-items:baseline;flex-wrap:wrap;padding:10px 0;border-top:1px solid var(--line)}}.quick strong{{color:var(--accent)}}.quick span,.short,.next{{font-size:12px;color:#bdccd7}}.short{{margin:5px 0}}.next{{margin:12px 0;padding:10px;background:#152737;border-radius:8px}}.source-links{{font-size:12px;margin:12px 0}}.source-links a{{color:#b4dfef}}.breakdown{{display:grid;gap:6px}}
details{{border-top:1px solid var(--line);margin-top:12px;padding-top:10px}}summary{{cursor:pointer;color:#b4dfef;font-weight:700}}.facts,.report{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin:14px 0}}.field{{border:1px solid #2a4052;border-radius:8px;padding:9px;overflow-wrap:anywhere}}dt{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}}dd{{margin:4px 0 0;font-size:12px}}.visual-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px}}.visual{{border:1px solid var(--line);border-radius:8px;padding:10px}}.visual h4{{margin:0 0 8px}}svg{{width:100%;height:auto}}.unavailable{{font-size:11px;color:var(--muted);padding:12px;border:1px dashed #405266;border-radius:7px}}.flow{{display:flex;flex-wrap:wrap;gap:7px;align-items:center;font-size:11px}}.flow b{{background:#153344;padding:7px;border-radius:6px}}.flow span{{color:var(--accent)}}footer{{border-top:1px solid var(--line);margin-top:36px;padding-top:15px;color:var(--muted);font-size:11px}}
</style></head><body><div class='wrap'><header><div><h1>Promising Results</h1><div class='sub'>Only evidence that clears a strict research presentation bar appears above the research frontier.</div></div>
<nav aria-label='Dashboard navigation'><a href="/dashboard">Mission Control</a><a href="/dashboard/results" aria-current='page'>Promising Results</a><a href="/dashboard/money">Money Intelligence</a></nav></header>
<div class='hero'><div><strong>Current research picture</strong><div class='sub'>Research display only. No trade, broker, or promotion authority.</div></div><div class='counts'><div><strong>{len(strategies)}</strong>strategies</div><div><strong>{len(two_x)}</strong>2x candidates</div></div></div>
<section><h2>Promising strategies</h2><div class='section-note'>{_esc(snapshot.get('strategy_rule'))}</div><div class='cards'>{strategy_cards}</div></section>
<section><h2>Promising 90-day 2x+ candidates</h2><div class='section-note'>Strong forward research only. No probability or validated forecast is inferred from narrative.</div><div class='cards'>{two_x_cards}</div></section>
<section><h2>Closest interesting research</h2><div class='section-note'>Lower confidence, high information cases. Retrospective moves are visually separated from current research.</div><div class='cards'>{research_cards}</div></section>
<footer>As of {_esc(snapshot.get('as_of'))} · read-only canonical artifacts · missing or stale evidence stays hidden.</footer></div></body></html>"""


def results_dashboard_page(request: Any):
    from fastapi.responses import HTMLResponse, RedirectResponse
    from dashboard import _authorized

    if not _authorized(request):
        return RedirectResponse("/dashboard/login", status_code=303)
    return HTMLResponse(render_results_html(build_results_snapshot()))
