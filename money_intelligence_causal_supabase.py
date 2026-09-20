"""Deployment-durable Supabase adapter for causal-repricing research memory.

The adapter stores digest-bound immutable versions through a service-role-only
optimistic append RPC. It never falls back to an empty or ephemeral local state.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
import json
from typing import TypeVar

import db

from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
    _parse_time,
)


TABLE = "money_intelligence_causal_memory_versions"
APPEND_RPC = "append_money_intelligence_causal_memory_version_v1"
MAX_DOCUMENT_BYTES = 2_000_000
MAX_APPEND_ATTEMPTS = 3
_HEX = frozenset("0123456789abcdef")
T = TypeVar("T")


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX


def _document_bytes(document: dict[str, object]) -> int:
    return len(
        json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
    )


class SupabaseCausalMemory:
    """Private, append-only durable state with bounded optimistic retries."""

    def __init__(self) -> None:
        if not db.configured():
            raise CausalMemoryError("Supabase causal memory is not configured")

    @staticmethod
    def _failure(operation: str, response: object) -> None:
        status = getattr(response, "status_code", "unknown")
        raise CausalMemoryError(
            f"Supabase causal memory {operation} failed: {status}"
        )

    @staticmethod
    def document_to_memory(document: object) -> CausalRepricingMemory:
        try:
            return CausalRepricingMemory.from_document(document)
        except CausalMemoryError as exc:
            raise CausalMemoryError("Supabase causal memory integrity failure") from exc

    @staticmethod
    def _require_prior_durable_plan(
        previous: CausalRepricingMemory | None,
        current: CausalRepricingMemory,
    ) -> None:
        """A plan must exist in the parent version before its outcomes arrive."""
        prior_hypotheses = previous.hypotheses if previous is not None else {}
        prior_observations = previous.observations if previous is not None else {}
        prior_events = previous.events if previous is not None else {}
        if previous is not None and (
            any(current.hypotheses.get(key) != value for key, value in prior_hypotheses.items())
            or any(current.observations.get(key) != value for key, value in prior_observations.items())
            or any(current.events.get(key) != value for key, value in prior_events.items())
            or current.registration_log[: len(previous.registration_log)]
            != previous.registration_log
        ):
            raise CausalMemoryError("durable causal-memory history is immutable")
        for hypothesis in current.hypotheses.values():
            if not hypothesis.evaluation_units or hypothesis.hypothesis_id in prior_hypotheses:
                continue
            for observation in current.observations.values():
                if observation.observation_id in prior_observations:
                    continue
                observed_start = _parse_time(observation.observed_at)
                observed_end = observed_start + timedelta(
                    hours=observation.measurement_window_hours
                )
                for subject, start, window in hypothesis.evaluation_units:
                    planned_start = _parse_time(start)
                    planned_end = planned_start + timedelta(hours=window)
                    if (
                        observation.subject_id == subject
                        and observed_start < planned_end
                        and planned_start < observed_end
                    ):
                        raise CausalMemoryError(
                            "evaluation plan must be durable before outcome observations"
                        )
            if any(
                event.hypothesis_id == hypothesis.hypothesis_id
                and event.event_id not in prior_events
                and event.kind == "support"
                and event.confirmatory
                for event in current.events.values()
            ):
                raise CausalMemoryError(
                    "evaluation plan must be durable before confirmatory support"
                )

    def _read_head(self) -> dict[str, object] | None:
        try:
            response = db.http.get(
                f"{db.SUPABASE_URL}/rest/v1/{TABLE}",
                headers=db.headers(),
                params={
                    "select": "sequence,content_digest,parent_digest,payload",
                    "order": "sequence.desc",
                    "limit": "2",
                },
            )
        except Exception as exc:
            raise CausalMemoryError("Supabase causal memory read failed") from exc
        if response.status_code >= 300:
            self._failure("read", response)
        try:
            rows = response.json()
        except Exception as exc:
            raise CausalMemoryError("Supabase causal memory returned invalid rows") from exc
        if not isinstance(rows, list) or len(rows) > 2:
            raise CausalMemoryError("Supabase causal memory returned invalid rows")
        if not rows:
            return None

        validated: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise CausalMemoryError("Supabase causal memory integrity failure")
            sequence = row.get("sequence")
            digest = row.get("content_digest")
            parent = row.get("parent_digest")
            payload = row.get("payload")
            if (
                type(sequence) is not int
                or sequence <= 0
                or not _valid_digest(digest)
                or (parent is not None and not _valid_digest(parent))
                or not isinstance(payload, dict)
                or payload.get("content_digest") != digest
                or _document_bytes(payload) > MAX_DOCUMENT_BYTES
            ):
                raise CausalMemoryError("Supabase causal memory integrity failure")
            self.document_to_memory(payload)
            validated.append(row)

        if len(validated) == 2:
            newest, previous = validated
            if (
                newest["sequence"] <= previous["sequence"]
                or newest["parent_digest"] != previous["content_digest"]
            ):
                raise CausalMemoryError("Supabase causal memory version-chain failure")
        return validated[0]

    def _append(
        self,
        document: dict[str, object],
        *,
        parent_digest: str | None,
        expected_sequence: int,
        expected_digest: str | None,
    ) -> str:
        digest = document.get("content_digest")
        if (
            not _valid_digest(digest)
            or _document_bytes(document) > MAX_DOCUMENT_BYTES
            or self.document_to_memory(document).to_document() != document
        ):
            raise CausalMemoryError("Supabase causal memory document integrity failure")
        try:
            response = db.http.post(
                f"{db.SUPABASE_URL}/rest/v1/rpc/{APPEND_RPC}",
                headers=db.headers(),
                json={
                    "p_content_digest": digest,
                    "p_parent_digest": parent_digest,
                    "p_payload": document,
                    "p_expected_sequence": expected_sequence,
                    "p_expected_digest": expected_digest,
                },
            )
        except Exception as exc:
            raise CausalMemoryError("Supabase causal memory append failed") from exc
        if response.status_code >= 300:
            self._failure("append", response)
        try:
            status = response.json()
        except Exception as exc:
            raise CausalMemoryError(
                "Supabase causal memory append returned invalid status"
            ) from exc
        if status not in {"APPENDED", "EXISTS", "STALE"}:
            raise CausalMemoryError(
                "Supabase causal memory append returned invalid status"
            )
        return status

    def initialize(self, memory: CausalRepricingMemory) -> str:
        """Create the genesis version, or accept an exact idempotent replay."""
        document = memory.to_document()
        for _ in range(MAX_APPEND_ATTEMPTS):
            head = self._read_head()
            if head is not None:
                if head["content_digest"] == document["content_digest"]:
                    return "EXISTS"
                raise CausalMemoryError("Supabase causal memory is already initialized")
            self._require_prior_durable_plan(None, memory)
            status = self._append(
                document,
                parent_digest=None,
                expected_sequence=0,
                expected_digest=None,
            )
            if status != "STALE":
                return status
        raise CausalMemoryError("Supabase causal memory changed during initialization")

    def load(self) -> CausalRepricingMemory:
        head = self._read_head()
        if head is None:
            raise CausalMemoryError("Supabase causal memory is not initialized")
        return self.document_to_memory(head["payload"])

    def transact(
        self, mutation: Callable[[CausalRepricingMemory], T]
    ) -> T:
        """Replay one deterministic mutation when a concurrent writer wins."""
        if not callable(mutation):
            raise CausalMemoryError("causal-memory mutation must be callable")
        for _ in range(MAX_APPEND_ATTEMPTS):
            head = self._read_head()
            if head is None:
                raise CausalMemoryError("Supabase causal memory is not initialized")
            memory = self.document_to_memory(head["payload"])
            previous = self.document_to_memory(head["payload"])
            result = mutation(memory)
            self._require_prior_durable_plan(previous, memory)
            document = memory.to_document()
            if document["content_digest"] == head["content_digest"]:
                return result
            status = self._append(
                document,
                parent_digest=str(head["content_digest"]),
                expected_sequence=int(head["sequence"]),
                expected_digest=str(head["content_digest"]),
            )
            if status != "STALE":
                return result
        raise CausalMemoryError("Supabase causal memory changed during transaction")
