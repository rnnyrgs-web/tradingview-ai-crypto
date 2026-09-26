"""Transactional append-only event memory. Configured corruption is never reset."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from .analytics import analyze
from .contracts import (DEVELOPMENT, SAFE, UNVERIFIED_FAVORABLE_EVIDENCE,
                        VERIFIED_FAVORABLE_EVIDENCE, canonical, fingerprint,
                        timestamp, text, experiment_id, validate_contract,
                        number, integer, strategy_semantic_fingerprint)
from .development import component_effects, mine_conditions
from .risk_policy import SUCCESS_BLOCKING_RISK_FLAGS

MAX_EVENT_BYTES = 16_000_000
MAX_EVENTS = 10_000
REJECTED_REGISTRY = Path(__file__).resolve().parents[1] / "orchestration/rejected_fingerprints.json"


def _verified_favorable_evidence(record):
    return record.get("favorable_evidence_provenance") == VERIFIED_FAVORABLE_EVIDENCE


def _canonical_rejections():
    # Read-only canonical negative memory. Missing/malformed registry fails closed.
    registry = json.loads(REJECTED_REGISTRY.read_text(encoding="utf-8"))
    entries = registry.get("entries")
    if not isinstance(entries, list):
        raise ValueError("canonical rejection registry malformed")
    return {text(row.get("fingerprint_id"), "rejected fingerprint") for row in entries}


def _validate_event(ident, kind, payload):
    if (not isinstance(payload, dict) or payload.get("schema_version") != 1
            or any(payload.get(k) is not v for k, v in SAFE.items())):
        raise ValueError("research memory schema or authority violation")
    if kind == "experiment":
        c = validate_contract(payload.get("contract"))
        required = {"experiment_id", "contract", "outcome", "source_status", "development_learning_allowed",
                    "metrics", "attribution", "risk_flags", "concentration", "economic_assessment",
                    "failure_reasons", "component_evidence", "interaction_evidence", "unavailable_metrics",
                    "input_digest", "conditional_hypotheses", "next_research_question", "successor_hypotheses"}
        if (ident != experiment_id(c) or payload.get("experiment_id") != ident
                or not required <= payload.keys()
                or payload.get("outcome") not in {"LEARN_AND_PIVOT", "MECHANISM_DEAD", "INFRA_DATA_FAILURE", "INCONCLUSIVE", "SUCCESS_LEARN"}
                or payload.get("source_status") not in {"PASSED", "REJECTED", "INFRA_DATA_FAILURE", "INCONCLUSIVE"}
                or not isinstance(payload.get("metrics"), dict)
                or not isinstance(payload.get("component_evidence"), list)):
            raise ValueError("experiment memory schema mismatch")
        try:
            provenance = payload.get("favorable_evidence_provenance")
            # The generic completion API has no trusted executor boundary.  It
            # may persist caller results for audit and negative vetoes, but it
            # cannot mint a self-asserted receipt that grants favorable weight.
            # Missing values are accepted only for backward-compatible reads
            # and are interpreted as unverified by every consumer.
            if (provenance is not None
                    and provenance != UNVERIFIED_FAVORABLE_EVIDENCE):
                raise ValueError("favorable evidence provenance is not verifier issued")
            text(payload["input_digest"], "input digest")
            text(payload["next_research_question"], "next research question")
            if payload["development_learning_allowed"] is not (c["split"] in DEVELOPMENT):
                raise ValueError("partition mismatch")
            for key in ("attribution", "concentration"):
                if not isinstance(payload[key], dict):
                    raise ValueError("object required")
            for key in ("risk_flags", "failure_reasons", "unavailable_metrics"):
                if not isinstance(payload[key], list) or any(not isinstance(x, str) for x in payload[key]):
                    raise ValueError("text list required")
            for key in ("conditional_hypotheses", "successor_hypotheses", "interaction_evidence"):
                if not isinstance(payload[key], list) or any(not isinstance(x, dict) for x in payload[key]):
                    raise ValueError("object list required")
            metrics = payload["metrics"]
            if metrics:
                for key in ("sample_count", "independent_event_count"):
                    integer(metrics[key], key, 0, 100_000)
                for key in ("compounded_net_return", "net_pnl", "max_drawdown"):
                    number(metrics[key], key)
                if metrics["after_cost_expectancy_money"] is not None:
                    number(metrics["after_cost_expectancy_money"], "expectancy")
            elif payload["source_status"] != "INFRA_DATA_FAILURE":
                raise ValueError("economic metrics missing")
            for effect in payload["component_evidence"]:
                if effect["component_fingerprint"] != fingerprint(effect["component"]):
                    raise ValueError("component mismatch")
                integer(effect["independent_event_count"], "event count", 0, 100_000)
                for key in ("delta_compounded_return", "delta_max_drawdown", "delta_tail_loss_money",
                            "delta_costs_money", "delta_capital_utilization"):
                    number(effect[key], key)
            for effect in payload["interaction_evidence"]:
                if not isinstance(effect["component_fingerprints"], list) or len(effect["component_fingerprints"]) != 2:
                    raise ValueError("interaction components missing")
                number(effect["delta_compounded_return"], "interaction delta")
            for h in payload["successor_hypotheses"]:
                if h["strategy_fingerprint"] != fingerprint(h["strategy"]) or any(h.get(k) is not v for k, v in SAFE.items()):
                    raise ValueError("unsafe successor")
                for key in ("hypothesis_id", "semantic_id", "economic_reason", "status"):
                    text(h[key], key)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("experiment nested schema mismatch") from exc
    elif kind == "proposal":
        validate_contract(payload.get("contract"))
        if ident != payload.get("proposal_id") or not {"semantic_id", "economic_reason", "falsifier", "ancestry", "status"} <= payload.keys():
            raise ValueError("proposal schema mismatch")
    elif kind == "legacy":
        if (ident != "legacy-" + str(payload.get("source_digest"))
                or not {"source_fingerprint", "source_outcome", "outcome", "evidence_summary", "limitations"} <= payload.keys()):
            raise ValueError("legacy schema mismatch")
    else:
        raise ValueError("unknown memory schema")
    canonical(payload)


def _independent(records):
    selected = []
    for r in sorted(records, key=lambda r: (timestamp(r["contract"]["end"]), r["experiment_id"])):
        c = r["contract"]
        if all(timestamp(c["start"]) > timestamp(old["contract"]["end"])
               or timestamp(c["end"]) < timestamp(old["contract"]["start"]) for old in selected):
            selected.append(r)
    return selected


def _snapshot(events):
    records = [e["payload"] for e in events if e["kind"] == "experiment"]
    legacy = [e["payload"] for e in events if e["kind"] == "legacy"]
    proposals = [e["payload"] for e in events if e["kind"] == "proposal"]
    families, semantic_strategies, components, interactions = {}, {}, {}, {}
    rejected = _canonical_rejections()
    rejected_semantic = set()
    semantic_by_fingerprint = {}
    for r in records:
        c = r["contract"]
        semantic = strategy_semantic_fingerprint(c["strategy"])
        semantic_by_fingerprint[c["strategy_fingerprint"]] = semantic
        enough_risk_evidence = bool(
            r["metrics"]
            and r["metrics"]["independent_event_count"] >= c["minimum_events"]
        )
        risk_rejected = (
            "CATASTROPHIC_LOSS" in r["risk_flags"]
            or (enough_risk_evidence
                and SUCCESS_BLOCKING_RISK_FLAGS.intersection(r["risk_flags"]))
        )
        if (r["source_status"] == "REJECTED"
                or r["outcome"] in {"LEARN_AND_PIVOT", "MECHANISM_DEAD"}
                or risk_rejected):
            rejected.add(c["strategy_fingerprint"])
            rejected_semantic.add(semantic)
        family = families.setdefault(c["family"], {"records": []})
        family["records"].append(r)
        semantic_row = semantic_strategies.setdefault(
            semantic,
            {"records": [], "families": set(), "mechanisms": set(),
             "exact_fingerprints": set()},
        )
        semantic_row["records"].append(r)
        semantic_row["families"].add(c["family"])
        semantic_row["mechanisms"].add(c["strategy"]["mechanism"])
        semantic_row["exact_fingerprints"].add(c["strategy_fingerprint"])
        effects = {x["component_fingerprint"]: x for x in r["component_evidence"]}
        for comp in c["strategy"]["components"]:
            key = fingerprint(comp)
            row = components.setdefault(key, {"component": comp, "strategies": {}, "observations": [],
                "evidence_level": "UNPROVEN", "uncertainty": "Co-occurrence is not causal contribution.",
                "last_validated_date": None, "decay_status": "UNKNOWN_REQUIRES_FRESH_REPLICATION"})
            row["strategies"].setdefault(c["strategy_fingerprint"], []).append(r["experiment_id"])
            effect = effects.get(key)
            row["observations"].append({"experiment_id": r["experiment_id"], "split": c["split"],
                "start": c["start"], "end": c["end"], "minimum_events": c["minimum_events"],
                "assets": c["strategy"]["assets"], "timeframe": c["strategy"]["timeframe"],
                "outcome": r["outcome"], "effect": effect, "attribution": r["attribution"],
                "favorable_evidence_verified": _verified_favorable_evidence(r),
                "observed_at": c["outcomes_observed_at"],
                "sample_count": r["metrics"].get("sample_count", 0),
                "independent_event_count": r["metrics"].get("independent_event_count", 0)})
            if effect:
                row["evidence_level"] = "DEVELOPMENT_ASSOCIATION"
        for interaction in r["interaction_evidence"]:
            key = fingerprint(sorted(interaction["component_fingerprints"]))
            interactions.setdefault(key, []).append({**interaction,
                "experiment_id": r["experiment_id"],
                "favorable_evidence_verified": _verified_favorable_evidence(r)})
    for family in families.values():
        eligible = [r for r in family.pop("records") if r["metrics"]
            and r["metrics"]["independent_event_count"] >= r["contract"]["minimum_events"]]
        independent = _independent(eligible)
        development = _independent([r for r in eligible if r["contract"]["split"] in DEVELOPMENT])
        family.update({
            "independent_experiments": len(independent),
            "development_failures": sum(r["source_status"] == "REJECTED" for r in development),
            "promising_development": sum(_verified_favorable_evidence(r)
                and r["source_status"] == "PASSED" and r["metrics"]["net_pnl"] > 0
                and r["contract"]["strategy_fingerprint"] not in rejected
                and strategy_semantic_fingerprint(r["contract"]["strategy"]) not in rejected_semantic
                and not SUCCESS_BLOCKING_RISK_FLAGS.intersection(r["risk_flags"]) for r in development),
            "mechanism_dead": any(r["outcome"] == "MECHANISM_DEAD" for r in development),
            "infra_blocked": False,
        })
    for semantic, row in semantic_strategies.items():
        eligible = [r for r in row.pop("records") if r["metrics"]
            and r["metrics"]["independent_event_count"] >= r["contract"]["minimum_events"]]
        independent = _independent(eligible)
        development = _independent([r for r in eligible if r["contract"]["split"] in DEVELOPMENT])
        row.update({
            "semantic_fingerprint": semantic,
            "families": sorted(row["families"]),
            "mechanisms": sorted(row["mechanisms"]),
            "exact_fingerprints": sorted(row["exact_fingerprints"]),
            "independent_experiments": len(independent),
            "development_failures": sum(r["source_status"] == "REJECTED" for r in development),
            "promising_development": sum(_verified_favorable_evidence(r)
                and r["source_status"] == "PASSED" and r["metrics"]["net_pnl"] > 0
                and r["contract"]["strategy_fingerprint"] not in rejected
                and semantic not in rejected_semantic
                and not SUCCESS_BLOCKING_RISK_FLAGS.intersection(r["risk_flags"])
                for r in development),
            "mechanism_dead": any(r["outcome"] == "MECHANISM_DEAD" for r in development),
            "infra_blocked": any(r["outcome"] == "INFRA_DATA_FAILURE" for r in eligible),
        })
    for r in records:
        if r["outcome"] == "INFRA_DATA_FAILURE":
            families[r["contract"]["family"]]["infra_blocked"] = True
    return {"schema_version": 1, "experiments": records, "legacy_outcomes": legacy,
            "proposals": proposals, "families": families,
            "semantic_strategies": semantic_strategies,
            "strategy_semantic_by_fingerprint": semantic_by_fingerprint,
            "rejected_semantic_fingerprints": sorted(rejected_semantic),
            "components": components, "interactions": interactions,
            "rejected_fingerprints": sorted(rejected), **SAFE}


def _prepare_completion(events, experiment, *, ablation=None):
    """Build one immutable completion from a validated event snapshot.

    Storage adapters call this before their atomic append. Keeping the economic
    classification here prevents the durable Supabase path and local SQLite path
    from drifting into different scientific semantics.
    """
    result = analyze(experiment)
    c = result["contract"]
    result["favorable_evidence_provenance"] = UNVERIFIED_FAVORABLE_EVIDENCE
    result["input_digest"] = fingerprint({"experiment": experiment, "ablation": ablation})
    if ablation is not None:
        if ablation["contract"] != c:
            raise ValueError("ablation contract mismatch")
        effects = component_effects(ablation)
        full = next(x["experiment"] for x in ablation["variants"] if not x["omitted"])
        if any(full[k] != experiment[k] for k in ("trades", "equity", "status", "failure_reasons")):
            raise ValueError("ablation full strategy does not match completed experiment")
        result["component_evidence"] = effects["components"]
        result["interaction_evidence"] = effects["interactions"]
    result["conditional_hypotheses"] = mine_conditions(experiment)["conditions"] if c["split"] in DEVELOPMENT else []
    old = next((x["payload"] for x in events if x["id"] == result["experiment_id"]), None)
    if old is not None:
        if old.get("input_digest") != result["input_digest"]:
            raise ValueError("immutable experiment conflict")
        return old, False
    if result["metrics"]:
        enough = result["metrics"]["independent_event_count"] >= c["minimum_events"]
        if enough and experiment["status"] == "REJECTED":
            result["outcome"] = "LEARN_AND_PIVOT"
        elif (enough and experiment["status"] == "PASSED"
                and result["metrics"]["net_pnl"] > 0
                and not SUCCESS_BLOCKING_RISK_FLAGS.intersection(result["risk_flags"])):
            result["outcome"] = "SUCCESS_LEARN"
        elif (enough and experiment["status"] == "PASSED"
                and result["metrics"]["net_pnl"] > 0):
            result["outcome"] = "LEARN_AND_PIVOT"
        falsifier = c.get("mechanism_falsifier")
        if falsifier is not None:
            if (not isinstance(falsifier, dict) or falsifier.get("metric") != "after_cost_expectancy_money"
                    or falsifier.get("maximum") != 0 or type(falsifier.get("minimum_independent_replications")) is not int
                    or falsifier["minimum_independent_replications"] < 2):
                raise ValueError("unsupported frozen mechanism falsifier")
            prior = [x["payload"] for x in events if x["kind"] == "experiment"] + [result]
            semantic = strategy_semantic_fingerprint(c["strategy"])
            failed = [r for r in prior if strategy_semantic_fingerprint(r["contract"]["strategy"]) == semantic
                and r["contract"].get("mechanism_falsifier") == falsifier
                and r["contract"]["split"] in DEVELOPMENT and r["source_status"] == "REJECTED"
                and r["metrics"].get("independent_event_count", 0) >= r["contract"]["minimum_events"]
                and r["metrics"].get("after_cost_expectancy_money", 1) <= 0]
            if c["split"] in DEVELOPMENT and len(_independent(failed)) >= falsifier["minimum_independent_replications"]:
                result["outcome"] = "MECHANISM_DEAD"
    result["next_research_question"] = {
        "INFRA_DATA_FAILURE": "Establish the missing timestamp-safe data contract before testing economic edge.",
        "INCONCLUSIVE": "Resolve the stated evidence limitations with a predeclared independent sample.",
        "MECHANISM_DEAD": "Explore a materially different economic mechanism; preserve this failed mechanism.",
        "LEARN_AND_PIVOT": "Test a materially distinct mechanism or component replacement on fresh chronological data.",
        "SUCCESS_LEARN": "Replicate the frozen economic mechanism independently; investigate return concentration.",
    }[result["outcome"]]
    from .evolution import generate_hypotheses
    result["successor_hypotheses"] = generate_hypotheses(result)
    _validate_event(result["experiment_id"], "experiment", result)
    return result, True


def _legacy_event(lesson):
    """Normalize sparse legacy evidence identically for every durable backend."""
    ident = text(lesson.get("fingerprint"), "legacy fingerprint")
    outcome = lesson.get("outcome")
    if not isinstance(outcome, str):
        raise ValueError("legacy outcome required")
    payload = {"schema_version": 1, "source_fingerprint": ident,
        "experiment_id": (lesson.get("evidence_summary") or {}).get("experiment_id") if isinstance(lesson.get("evidence_summary"), dict) else None,
        "source_digest": fingerprint(lesson), "source_outcome": outcome,
        "outcome": "INFRA_DATA_FAILURE" if outcome in {"infra_data_failure", "insufficient_history"} else "INCONCLUSIVE",
        "hypothesis": lesson.get("hypothesis"), "evidence_summary": lesson.get("evidence_summary"),
        "limitations": ["Missing frozen economic contract, full trade costs, reconciled NAV and component ablations"],
        "next_research_question": lesson.get("recommended_next_test"), **SAFE}
    event_id = "legacy-" + payload["source_digest"]
    _validate_event(event_id, "legacy", payload)
    return event_id, payload


class Memory:
    def __init__(self, path, *, create=True):
        self.path = Path(path)
        if not create and not self.path.is_file():
            raise ValueError("configured research memory missing; refusing to reset")
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            if create:
                conn.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, kind TEXT NOT NULL, digest TEXT NOT NULL, payload TEXT NOT NULL)")
            conn.execute("SELECT id FROM events LIMIT 1")

    def _connect(self):
        conn = sqlite3.connect(self.path, timeout=15)
        conn.execute("PRAGMA synchronous=FULL")
        return conn

    @staticmethod
    def _read(conn):
        rows = conn.execute("SELECT id, kind, digest, payload FROM events ORDER BY rowid LIMIT ?", (MAX_EVENTS + 1,)).fetchall()
        if len(rows) > MAX_EVENTS:
            raise ValueError("research memory capacity exceeded; archive before continuation")
        events = []
        for ident, kind, digest, raw in rows:
            if len(raw) > MAX_EVENT_BYTES or kind not in {"experiment", "proposal", "legacy"}:
                raise ValueError("research memory integrity failure")
            try:
                payload = json.loads(raw)
                if fingerprint(payload) != digest:
                    raise ValueError("digest mismatch")
            except (ValueError, TypeError) as exc:
                raise ValueError("research memory integrity failure") from exc
            _validate_event(ident, kind, payload)
            events.append({"id": ident, "kind": kind, "digest": digest, "payload": payload})
        return events

    @staticmethod
    def _insert(conn, ident, kind, payload):
        _validate_event(ident, kind, payload)
        raw, digest = canonical(payload), fingerprint(payload)
        if len(raw.encode()) > MAX_EVENT_BYTES:
            raise ValueError("learning artifact exceeds memory capacity")
        old = conn.execute("SELECT kind, digest FROM events WHERE id = ?", (ident,)).fetchone()
        if old:
            if old != (kind, digest):
                raise ValueError("immutable learning artifact conflict")
            return
        if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] >= MAX_EVENTS:
            raise ValueError("memory full; archive required")
        conn.execute("INSERT INTO events (id, kind, digest, payload) VALUES (?, ?, ?, ?)", (ident, kind, digest, raw))

    def snapshot(self):
        with self._connect() as conn:
            return _snapshot(self._read(conn))

    def complete(self, experiment, *, ablation=None):
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            events = self._read(conn)
            result, is_new = _prepare_completion(events, experiment, ablation=ablation)
            if is_new:
                self._insert(conn, result["experiment_id"], "experiment", result)
        return result

    def save_proposal(self, proposal):
        from .evolution import validate_proposal
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            snapshot = _snapshot(self._read(conn))
            validate_proposal(proposal, snapshot)
            self._insert(conn, proposal["proposal_id"], "proposal", proposal)
        return proposal

    def record_legacy(self, lesson):
        """Sparse legacy outcomes never masquerade as portfolio/component evidence."""
        event_id, payload = _legacy_event(lesson)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._read(conn)
            self._insert(conn, event_id, "legacy", payload)
        return payload

    def export(self):
        with self._connect() as conn:
            events = self._read(conn)
        return {"schema_version": 1, "events": events, "sha256": fingerprint(events), **SAFE}

    def import_archive(self, archive):
        if archive.get("schema_version") != 1 or archive.get("sha256") != fingerprint(archive.get("events")):
            raise ValueError("archive integrity mismatch")
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._read(conn)
            for e in archive["events"]:
                if e["digest"] != fingerprint(e["payload"]) or e["kind"] not in {"experiment", "proposal", "legacy"}:
                    raise ValueError("archive event integrity mismatch")
                self._insert(conn, e["id"], e["kind"], e["payload"])
