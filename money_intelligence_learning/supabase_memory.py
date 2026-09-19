"""Service-role-only Money Intelligence memory on approved Supabase storage."""

from __future__ import annotations

import db

from profitability_learning.contracts import canonical, fingerprint

from .contracts import validate_evidence, validate_mechanism
from .memory import MAX_EVENT_BYTES, MAX_EVENTS, snapshot_from_events


TABLE = "money_intelligence_learning_events"
APPEND_RPC = "append_money_intelligence_learning_event"
MAX_APPEND_ATTEMPTS = 3


class SupabaseMemory:
    def __init__(self):
        if not db.configured():
            raise ValueError("Supabase Money Intelligence memory is not configured")

    @staticmethod
    def _failure(operation, response):
        raise ValueError(f"Supabase Money Intelligence memory {operation} failed: {response.status_code}")

    def _read_versioned(self):
        try:
            response = db.http.get(
                f"{db.SUPABASE_URL}/rest/v1/{TABLE}",
                headers=db.headers(),
                params={
                    "select": "sequence,event_id,event_kind,digest,payload",
                    "order": "sequence.asc",
                    "limit": str(MAX_EVENTS + 1),
                },
            )
        except Exception as exc:
            raise ValueError("Supabase Money Intelligence memory read failed") from exc
        if response.status_code >= 300:
            self._failure("read", response)
        rows = response.json()
        if not isinstance(rows, list) or len(rows) > MAX_EVENTS:
            raise ValueError("Supabase Money Intelligence memory integrity failure")
        events, last_sequence = [], 0
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Supabase Money Intelligence memory integrity failure")
            sequence = row.get("sequence")
            ident, kind = row.get("event_id"), row.get("event_kind")
            digest, payload = row.get("digest"), row.get("payload")
            if (
                type(sequence) is not int
                or sequence <= last_sequence
                or kind not in {"mechanism", "evidence"}
                or not isinstance(payload, dict)
                or len(canonical(payload).encode()) > MAX_EVENT_BYTES
                or fingerprint(payload) != digest
            ):
                raise ValueError("Supabase Money Intelligence memory integrity failure")
            events.append({"id": ident, "kind": kind, "digest": digest, "payload": payload})
            last_sequence = sequence
        snapshot_from_events(events, as_of="9999-12-31T00:00:00+00:00")
        return events, (len(events), last_sequence)

    def _append(self, ident, kind, payload, version):
        raw = canonical(payload)
        if len(raw.encode()) > MAX_EVENT_BYTES:
            raise ValueError("Money Intelligence event exceeds capacity")
        try:
            response = db.http.post(
                f"{db.SUPABASE_URL}/rest/v1/rpc/{APPEND_RPC}",
                headers=db.headers(),
                json={
                    "p_event_id": ident,
                    "p_event_kind": kind,
                    "p_digest": fingerprint(payload),
                    "p_payload": payload,
                    "p_expected_count": version[0],
                    "p_expected_sequence": version[1],
                },
            )
        except Exception as exc:
            raise ValueError("Supabase Money Intelligence memory append failed") from exc
        if response.status_code >= 300:
            self._failure("append", response)
        status = response.json()
        if status not in {"APPENDED", "EXISTS", "STALE"}:
            raise ValueError("Supabase Money Intelligence memory append returned invalid status")
        return status

    def freeze(self, contract):
        validate_mechanism(contract)
        for _ in range(MAX_APPEND_ATTEMPTS):
            events, version = self._read_versioned()
            current = [row for row in events if row["kind"] == "mechanism" and row["payload"]["mechanism_id"] == contract["mechanism_id"]]
            if current:
                if current[0]["payload"] != contract:
                    raise ValueError("immutable mechanism contract conflict")
                return contract
            if self._append(contract["contract_id"], "mechanism", contract, version) != "STALE":
                return contract
        raise ValueError("Supabase Money Intelligence memory changed during append")

    def append_evidence(self, payload):
        for _ in range(MAX_APPEND_ATTEMPTS):
            events, version = self._read_versioned()
            old = next((row for row in events if row["id"] == payload.get("evidence_id")), None)
            if old is not None:
                if old["digest"] != fingerprint(payload):
                    raise ValueError("immutable Money Intelligence event conflict")
                return payload
            contract = next(
                (
                    row["payload"]
                    for row in events
                    if row["kind"] == "mechanism" and row["payload"]["mechanism_id"] == payload.get("mechanism_id")
                ),
                None,
            )
            if contract is None:
                raise ValueError("evidence references unknown mechanism")
            validate_evidence(payload, contract=contract)
            if any(
                row["kind"] == "evidence"
                and row["payload"]["mechanism_id"] == payload["mechanism_id"]
                and row["payload"]["independence_key"] == payload["independence_key"]
                for row in events
            ):
                raise ValueError("duplicate independence key")
            if self._append(payload["evidence_id"], "evidence", payload, version) != "STALE":
                return payload
        raise ValueError("Supabase Money Intelligence memory changed during append")

    def snapshot(self, *, as_of):
        events, _ = self._read_versioned()
        return snapshot_from_events(events, as_of=as_of)
