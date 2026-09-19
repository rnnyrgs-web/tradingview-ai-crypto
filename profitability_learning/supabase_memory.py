"""Append-only profitability memory on the already-approved Supabase channel."""

from __future__ import annotations

from copy import deepcopy

import db

from .contracts import SAFE, canonical, fingerprint
from .evolution import validate_proposal
from .memory import (
    MAX_EVENT_BYTES,
    MAX_EVENTS,
    _legacy_event,
    _prepare_completion,
    _snapshot,
    _validate_event,
)


TABLE = "profitability_learning_events"
APPEND_RPC = "append_profitability_learning_event"


class SupabaseMemory:
    """Service-role-only event memory with atomic immutable append semantics."""

    def __init__(self):
        if not db.configured():
            raise ValueError("Supabase profitability memory is not configured")

    @staticmethod
    def _failure(operation, response):
        raise ValueError(f"Supabase profitability memory {operation} failed: {response.status_code}")

    def _read(self):
        try:
            response = db.http.get(
                f"{db.SUPABASE_URL}/rest/v1/{TABLE}",
                headers=db.headers(),
                params={
                    "select": "event_id,event_kind,digest,payload",
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
        events = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("Supabase profitability memory integrity failure")
            ident, kind = row.get("event_id"), row.get("event_kind")
            digest, payload = row.get("digest"), row.get("payload")
            if (not isinstance(payload, dict) or len(canonical(payload).encode()) > MAX_EVENT_BYTES
                    or kind not in {"experiment", "proposal", "legacy"}
                    or fingerprint(payload) != digest):
                raise ValueError("Supabase profitability memory integrity failure")
            _validate_event(ident, kind, payload)
            events.append({"id": ident, "kind": kind, "digest": digest, "payload": payload})
        return events

    def _insert(self, ident, kind, payload):
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
                },
            )
        except Exception as exc:
            raise ValueError("Supabase profitability memory append failed") from exc
        if response.status_code >= 300:
            self._failure("append", response)

    def snapshot(self):
        return _snapshot(self._read())

    def complete(self, experiment, *, ablation=None):
        result, is_new = _prepare_completion(self._read(), experiment, ablation=ablation)
        if is_new:
            self._insert(result["experiment_id"], "experiment", result)
        return result

    def save_proposal(self, proposal):
        events = self._read()
        validate_proposal(proposal, _snapshot(events))
        self._insert(proposal["proposal_id"], "proposal", proposal)
        return proposal

    def record_legacy(self, lesson):
        event_id, payload = _legacy_event(lesson)
        self._insert(event_id, "legacy", payload)
        return payload

    def export(self):
        events = self._read()
        return {"schema_version": 1, "events": events, "sha256": fingerprint(events), **SAFE}

    def import_archive(self, archive):
        events = archive.get("events")
        if archive.get("schema_version") != 1 or archive.get("sha256") != fingerprint(events):
            raise ValueError("archive integrity mismatch")
        validated = []
        for event in deepcopy(events):
            if (not isinstance(event, dict) or event.get("digest") != fingerprint(event.get("payload"))
                    or event.get("kind") not in {"experiment", "proposal", "legacy"}):
                raise ValueError("archive event integrity mismatch")
            _validate_event(event.get("id"), event["kind"], event["payload"])
            validated.append(event)
        for event in validated:
            self._insert(event["id"], event["kind"], event["payload"])
