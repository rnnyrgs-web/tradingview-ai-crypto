"""Deployment-durable Supabase adapter for causal-repricing research memory.

The adapter stores digest-bound immutable versions through a service-role-only
optimistic append RPC. It never falls back to an empty or ephemeral local state.
"""

from __future__ import annotations

from collections.abc import Callable
import json
from typing import TypeVar

import db

from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
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
            result = mutation(memory)
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
