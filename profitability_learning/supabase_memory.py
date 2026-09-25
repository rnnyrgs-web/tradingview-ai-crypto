"""Append-only profitability memory on the already-approved Supabase channel."""

from __future__ import annotations

import db

from .contracts import SAFE, canonical, fingerprint
from .evolution import validate_proposal
from .memory import (
    MAX_EVENT_BYTES,
    MAX_EVENTS,
    _legacy_event,
    _prepare_completion,
    _snapshot,
    _validated_archive_events,
    _validate_event,
)


TABLE = "profitability_learning_events"
APPEND_RPC = "append_profitability_learning_event_v2"
MAX_APPEND_ATTEMPTS = 3


class SupabaseMemory:
    """Service-role-only event memory with atomic immutable append semantics."""

    def __init__(self):
        if not db.configured():
            raise ValueError("Supabase profitability memory is not configured")

    @staticmethod
    def _failure(operation, response):
        raise ValueError(f"Supabase profitability memory {operation} failed: {response.status_code}")

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
            raise ValueError("Supabase profitability memory read failed") from exc
        if response.status_code >= 300:
            self._failure("read", response)
        rows = response.json()
        if not isinstance(rows, list):
            raise ValueError("Supabase profitability memory returned invalid rows")
        if len(rows) > MAX_EVENTS:
            raise ValueError("research memory capacity exceeded; archive before continuation")
        events, last_sequence = [], 0
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Supabase profitability memory integrity failure")
            sequence = row.get("sequence")
            ident, kind = row.get("event_id"), row.get("event_kind")
            digest, payload = row.get("digest"), row.get("payload")
            if (type(sequence) is not int or sequence <= last_sequence
                    or not isinstance(payload, dict) or len(canonical(payload).encode()) > MAX_EVENT_BYTES
                    or kind not in {"experiment", "proposal", "legacy"}
                    or fingerprint(payload) != digest):
                raise ValueError("Supabase profitability memory integrity failure")
            _validate_event(ident, kind, payload)
            events.append({"id": ident, "kind": kind, "digest": digest, "payload": payload})
            last_sequence = sequence
        return events, (len(events), last_sequence)

    def _read(self):
        return self._read_versioned()[0]

    def _insert(self, ident, kind, payload, expected_version):
        _validate_event(ident, kind, payload)
        raw = canonical(payload)
        if len(raw.encode()) > MAX_EVENT_BYTES:
            raise ValueError("learning artifact exceeds memory capacity")
        try:
            response = db.http.post(
                f"{db.SUPABASE_URL}/rest/v1/rpc/{APPEND_RPC}",
                headers=db.headers(),
                json={
                    "p_event_id": ident,
                    "p_event_kind": kind,
                    "p_digest": fingerprint(payload),
                    "p_payload": payload,
                    "p_expected_count": expected_version[0],
                    "p_expected_sequence": expected_version[1],
                },
            )
        except Exception as exc:
            raise ValueError("Supabase profitability memory append failed") from exc
        if response.status_code >= 300:
            self._failure("append", response)
        status = response.json()
        if status not in {"APPENDED", "EXISTS", "STALE"}:
            raise ValueError("Supabase profitability memory append returned invalid status")
        return status

    def snapshot(self):
        return _snapshot(self._read())

    def complete(self, experiment, *, ablation=None):
        for _ in range(MAX_APPEND_ATTEMPTS):
            events, version = self._read_versioned()
            result, is_new = _prepare_completion(events, experiment, ablation=ablation)
            if not is_new or self._insert(result["experiment_id"], "experiment", result, version) != "STALE":
                return result
        raise ValueError("Supabase profitability memory changed during completion")

    def save_proposal(self, proposal):
        for _ in range(MAX_APPEND_ATTEMPTS):
            events, version = self._read_versioned()
            validate_proposal(proposal, _snapshot(events))
            if self._insert(proposal["proposal_id"], "proposal", proposal, version) != "STALE":
                return proposal
        raise ValueError("Supabase profitability memory changed during proposal save")

    def record_legacy(self, lesson):
        event_id, payload = _legacy_event(lesson)
        for _ in range(MAX_APPEND_ATTEMPTS):
            _, version = self._read_versioned()
            if self._insert(event_id, "legacy", payload, version) != "STALE":
                return payload
        raise ValueError("Supabase profitability memory changed during legacy save")

    def export(self):
        events = self._read()
        return {"schema_version": 1, "events": events, "sha256": fingerprint(events), **SAFE}

    def import_archive(self, archive):
        validated = _validated_archive_events(archive, self._read())
        for event in validated:
            for _ in range(MAX_APPEND_ATTEMPTS):
                current, version = self._read_versioned()
                existing = next(
                    (row for row in current if row["id"] == event["id"]), None
                )
                if existing is not None:
                    if (existing["kind"] != event["kind"]
                            or existing["digest"] != event["digest"]):
                        raise ValueError("immutable learning artifact conflict")
                    break
                if event["kind"] == "proposal":
                    validate_proposal(event["payload"], _snapshot(current))
                if self._insert(event["id"], event["kind"], event["payload"], version) != "STALE":
                    break
            else:
                raise ValueError("Supabase profitability memory changed during archive import")
