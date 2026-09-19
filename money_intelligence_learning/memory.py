"""Transactional append-only local memory for Money Intelligence research."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

from profitability_learning.contracts import canonical, fingerprint

from .contracts import validate_evidence, validate_mechanism
from .evolution import evolve_mechanism


MAX_EVENTS = 10_000
MAX_EVENT_BYTES = 4_000_000


def _validate_event(ident, kind, payload, contracts=None):
    if kind == "mechanism":
        validate_mechanism(payload)
        if ident != payload["contract_id"]:
            raise ValueError("mechanism event identity mismatch")
    elif kind == "evidence":
        contract = (contracts or {}).get(payload.get("mechanism_id"))
        if contract is None:
            raise ValueError("evidence references unknown mechanism")
        validate_evidence(payload, contract=contract)
        if ident != payload["evidence_id"]:
            raise ValueError("evidence event identity mismatch")
    else:
        raise ValueError("unknown Money Intelligence event kind")


def snapshot_from_events(events, *, as_of):
    contracts = {}
    evidence = []
    for event in events:
        if event["kind"] == "mechanism":
            contract = event["payload"]
            mechanism_id = contract["mechanism_id"]
            if mechanism_id in contracts and contracts[mechanism_id] != contract:
                raise ValueError("multiple active contracts for mechanism")
            contracts[mechanism_id] = contract
    for event in events:
        _validate_event(event["id"], event["kind"], event["payload"], contracts)
        if event["kind"] == "evidence":
            evidence.append(event["payload"])
    mechanisms = {}
    for mechanism_id, contract in sorted(contracts.items()):
        rows = [row for row in evidence if row["mechanism_id"] == mechanism_id]
        mechanisms[mechanism_id] = {
            "contract": deepcopy(contract),
            "state": evolve_mechanism(contract, rows, as_of=as_of),
        }
    return {
        "schema_version": 1,
        "as_of": as_of,
        "mechanisms": mechanisms,
        "evidence": deepcopy(evidence),
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
    }


class Memory:
    def __init__(self, path, *, create=True):
        self.path = Path(path)
        if not create and not self.path.is_file():
            raise ValueError("configured Money Intelligence memory missing; refusing to reset")
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            if create:
                connection.execute(
                    "create table if not exists events (id text primary key, kind text not null, digest text not null, payload text not null)"
                )
            connection.execute("select id from events limit 1")

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=15)
        connection.execute("pragma synchronous=full")
        return connection

    @staticmethod
    def _read(connection):
        rows = connection.execute(
            "select id, kind, digest, payload from events order by rowid limit ?", (MAX_EVENTS + 1,)
        ).fetchall()
        if len(rows) > MAX_EVENTS:
            raise ValueError("Money Intelligence memory full")
        events = []
        for ident, kind, digest, raw in rows:
            if len(raw.encode()) > MAX_EVENT_BYTES:
                raise ValueError("Money Intelligence memory integrity failure")
            try:
                payload = json.loads(raw)
                if fingerprint(payload) != digest:
                    raise ValueError("digest mismatch")
            except (TypeError, ValueError) as exc:
                raise ValueError("Money Intelligence memory integrity failure") from exc
            events.append({"id": ident, "kind": kind, "digest": digest, "payload": payload})
        snapshot_from_events(events, as_of="9999-12-31T00:00:00+00:00")
        return events

    @staticmethod
    def _insert(connection, ident, kind, payload):
        raw, digest = canonical(payload), fingerprint(payload)
        if len(raw.encode()) > MAX_EVENT_BYTES:
            raise ValueError("Money Intelligence event exceeds capacity")
        old = connection.execute("select kind, digest from events where id = ?", (ident,)).fetchone()
        if old:
            if old != (kind, digest):
                raise ValueError("immutable Money Intelligence event conflict")
            return False
        if connection.execute("select count(*) from events").fetchone()[0] >= MAX_EVENTS:
            raise ValueError("Money Intelligence memory full")
        connection.execute("insert into events(id, kind, digest, payload) values (?, ?, ?, ?)", (ident, kind, digest, raw))
        return True

    def freeze(self, contract):
        validate_mechanism(contract)
        with self._connect() as connection:
            connection.execute("begin immediate")
            events = self._read(connection)
            contracts = {row["payload"]["mechanism_id"]: row["payload"] for row in events if row["kind"] == "mechanism"}
            old = contracts.get(contract["mechanism_id"])
            if old is not None and old != contract:
                raise ValueError("immutable mechanism contract conflict")
            self._insert(connection, contract["contract_id"], "mechanism", contract)
        return contract

    def append_evidence(self, payload):
        with self._connect() as connection:
            connection.execute("begin immediate")
            events = self._read(connection)
            old = next((row for row in events if row["id"] == payload.get("evidence_id")), None)
            if old is not None and old["digest"] != fingerprint(payload):
                raise ValueError("immutable Money Intelligence event conflict")
            contracts = {row["payload"]["mechanism_id"]: row["payload"] for row in events if row["kind"] == "mechanism"}
            contract = contracts.get(payload.get("mechanism_id"))
            if contract is None:
                raise ValueError("evidence references unknown mechanism")
            validate_evidence(payload, contract=contract)
            existing_keys = {
                row["payload"]["independence_key"]
                for row in events
                if row["kind"] == "evidence" and row["payload"]["mechanism_id"] == payload["mechanism_id"]
            }
            if old is None and payload["independence_key"] in existing_keys:
                raise ValueError("duplicate independence key")
            self._insert(connection, payload["evidence_id"], "evidence", payload)
        return payload

    def snapshot(self, *, as_of):
        with self._connect() as connection:
            events = self._read(connection)
        return snapshot_from_events(events, as_of=as_of)
