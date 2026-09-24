"""Deployment-durable Supabase adapter for causal-repricing research memory.

The adapter stores digest-bound immutable versions through a service-role-only
optimistic append RPC. It never falls back to an empty or ephemeral local state.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
import json
from typing import TypeVar

import db

from money_intelligence_causal_memory import (
    CausalMemoryError,
    CausalRepricingMemory,
    FrozenHypothesis,
    _legacy_unsigned_causal_memory_document,
    _parse_time,
    _trusted_causal_memory_document,
)


TABLE = "money_intelligence_causal_memory_versions"
APPEND_RPC = "append_money_intelligence_causal_memory_version_v1"
MAX_DOCUMENT_BYTES = 2_000_000
MAX_APPEND_ATTEMPTS = 3
MAX_LEGACY_MIGRATION_VERSIONS = 1_000
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
    def _require_immutable_transition(
        previous: CausalRepricingMemory,
        current: CausalRepricingMemory,
    ) -> None:
        if (
            any(
                current.hypotheses.get(key) != value
                for key, value in previous.hypotheses.items()
            )
            or any(
                current.observations.get(key) != value
                for key, value in previous.observations.items()
            )
            or any(
                current.events.get(key) != value
                for key, value in previous.events.items()
            )
            or not previous.rejected_fingerprints <= current.rejected_fingerprints
            or current.half_life_days != previous.half_life_days
            or current.legacy_underdeclared_hypotheses
            != previous.legacy_underdeclared_hypotheses
            or current.registration_log[: len(previous.registration_log)]
            != previous.registration_log
        ):
            raise CausalMemoryError("durable causal-memory history is immutable")

    def _require_prior_durable_plan(
        self,
        previous: CausalRepricingMemory | None,
        current: CausalRepricingMemory,
    ) -> None:
        """A server-timed plan must precede the start of its outcome units."""
        prior_hypotheses = previous.hypotheses if previous is not None else {}
        prior_observations = previous.observations if previous is not None else {}
        prior_events = previous.events if previous is not None else {}
        if previous is not None:
            self._require_immutable_transition(previous, current)
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

        for hypothesis in prior_hypotheses.values():
            if not hypothesis.evaluation_units:
                continue
            new_support = any(
                event.hypothesis_id == hypothesis.hypothesis_id
                and event.event_id not in prior_events
                and event.kind == "support"
                and event.confirmatory
                for event in current.events.values()
            )
            new_overlap = any(
                observation.observation_id not in prior_observations
                and observation.subject_id == subject
                and _parse_time(observation.observed_at)
                < _parse_time(start) + timedelta(hours=window)
                and _parse_time(start)
                < _parse_time(observation.observed_at)
                + timedelta(hours=observation.measurement_window_hours)
                for observation in current.observations.values()
                for subject, start, window in hypothesis.evaluation_units
            )
            if not (new_support or new_overlap):
                continue
            committed_at = self._read_plan_commit(hypothesis)
            if any(
                committed_at >= _parse_time(start)
                for _, start, _ in hypothesis.evaluation_units
            ):
                raise CausalMemoryError(
                    "server-recorded plan commit must precede outcome-unit starts"
                )

    def _read_plan_commit(self, hypothesis: FrozenHypothesis) -> datetime:
        """Read the first immutable version containing this exact frozen plan."""
        hypothesis_id = hypothesis.hypothesis_id
        try:
            response = db.http.get(
                f"{db.SUPABASE_URL}/rest/v1/{TABLE}",
                headers=db.headers(),
                params={
                    "select": "sequence,content_digest,parent_digest,payload,created_at",
                    "payload": "cs." + json.dumps(
                        {"hypotheses": [{"hypothesis_id": hypothesis_id}]},
                        separators=(",", ":"),
                    ),
                    "order": "sequence.asc",
                    "limit": "1",
                },
            )
        except Exception as exc:
            raise CausalMemoryError("Supabase causal plan receipt read failed") from exc
        if response.status_code >= 300:
            self._failure("plan receipt read", response)
        try:
            rows = response.json()
        except Exception as exc:
            raise CausalMemoryError("Supabase causal plan receipt is invalid") from exc
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise CausalMemoryError("Supabase causal plan receipt is missing")
        row = rows[0]
        payload = row.get("payload")
        if (
            type(row.get("sequence")) is not int
            or row["sequence"] <= 0
            or not _valid_digest(row.get("content_digest"))
            or (
                row.get("parent_digest") is not None
                and not _valid_digest(row.get("parent_digest"))
            )
            or not isinstance(payload, dict)
            or payload.get("content_digest") != row["content_digest"]
            or not isinstance(row.get("created_at"), str)
            or _document_bytes(payload) > MAX_DOCUMENT_BYTES
        ):
            raise CausalMemoryError("Supabase causal plan receipt is invalid")
        registered = self.document_to_memory(payload).hypotheses.get(hypothesis_id)
        if registered != hypothesis:
            raise CausalMemoryError("Supabase causal plan receipt changed after registration")
        try:
            return _parse_time(row["created_at"])
        except CausalMemoryError as exc:
            raise CausalMemoryError("Supabase causal plan receipt is invalid") from exc

    def _read_head(self) -> dict[str, object] | None:
        try:
            response = db.http.get(
                f"{db.SUPABASE_URL}/rest/v1/{TABLE}",
                headers=db.headers(),
                params={
                    "select": "sequence,content_digest,parent_digest,payload,created_at",
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
        head_payload = rows[0].get("payload") if isinstance(rows[0], dict) else None
        head_sequence = rows[0].get("sequence") if isinstance(rows[0], dict) else None
        unattested_head = (
            isinstance(head_payload, dict)
            and "authority_attestation" not in head_payload
            and type(head_sequence) is int
        )
        if unattested_head and self._prior_attested_boundary_exists(head_sequence):
            raise CausalMemoryError(
                "authenticated durable causal-memory attested boundary cannot be removed"
            )

        validated: list[dict[str, object]] = []
        for row in rows:
            if not isinstance(row, dict):
                raise CausalMemoryError("Supabase causal memory integrity failure")
            sequence = row.get("sequence")
            digest = row.get("content_digest")
            parent = row.get("parent_digest")
            payload = row.get("payload")
            committed_at = row.get("created_at")
            if (
                type(sequence) is not int
                or sequence <= 0
                or not _valid_digest(digest)
                or (parent is not None and not _valid_digest(parent))
                or not isinstance(payload, dict)
                or not isinstance(committed_at, str)
                or payload.get("content_digest") != digest
                or _document_bytes(payload) > MAX_DOCUMENT_BYTES
            ):
                raise CausalMemoryError("Supabase causal memory integrity failure")
            trusted_document = _trusted_causal_memory_document(payload)
            legacy_unsigned = _legacy_unsigned_causal_memory_document(payload)
            if not trusted_document and not legacy_unsigned:
                raise CausalMemoryError(
                    "authenticated durable causal-memory boundary failed"
                )
            try:
                _parse_time(committed_at)
            except CausalMemoryError as exc:
                raise CausalMemoryError("Supabase causal memory integrity failure") from exc
            self.document_to_memory(payload)
            validated.append(row)

        if len(validated) == 2:
            newest, previous = validated
            if (
                newest["sequence"] <= previous["sequence"]
                or newest["parent_digest"] != previous["content_digest"]
            ):
                raise CausalMemoryError("Supabase causal memory version-chain failure")
            # The server append chain, rather than the caller-recomputable payload
            # digest, is the authority for monotonic scientific state. Validate
            # every observed head transition even when it bypassed this adapter's
            # normal transact() path.
            self._require_prior_durable_plan(
                self.document_to_memory(previous["payload"]),
                self.document_to_memory(newest["payload"]),
            )
        # Until the first authenticated boundary exists, the latest two rows
        # cannot prove that an older v1 acceptance marker was removed and then
        # hidden by a marker-free cover version. Replay the complete bounded
        # append-only history for every unattested head, not only a head that
        # still advertises its legacy marker.
        if unattested_head:
            self._validate_legacy_unsigned_history(validated[0])
        return validated[0]

    def _prior_attested_boundary_exists(self, head_sequence: int) -> bool:
        """Anchor the signature-required state in append-only server history."""
        try:
            response = db.http.get(
                f"{db.SUPABASE_URL}/rest/v1/{TABLE}",
                headers=db.headers(),
                params={
                    "select": "sequence,content_digest,payload",
                    "payload->>authority_attestation": "not.is.null",
                    "order": "sequence.desc",
                    "limit": "1",
                },
            )
        except Exception as exc:
            raise CausalMemoryError("causal-memory attested-boundary read failed") from exc
        if response.status_code >= 300:
            self._failure("attested-boundary read", response)
        try:
            rows = response.json()
        except Exception as exc:
            raise CausalMemoryError("causal-memory attested boundary is invalid") from exc
        if not isinstance(rows, list) or len(rows) > 1:
            raise CausalMemoryError("causal-memory attested boundary is invalid")
        if not rows:
            return False
        row = rows[0]
        payload = row.get("payload") if isinstance(row, dict) else None
        if (
            not isinstance(row, dict)
            or type(row.get("sequence")) is not int
            or not 0 < row["sequence"] < head_sequence
            or not _valid_digest(row.get("content_digest"))
            or not isinstance(payload, dict)
            or not isinstance(payload.get("authority_attestation"), str)
            or not payload["authority_attestation"].startswith(
                "causal-memory-document-v1:"
            )
        ):
            raise CausalMemoryError("causal-memory attested boundary is invalid")
        return True

    def _validate_legacy_unsigned_history(self, head: dict[str, object]) -> None:
        """One-time bounded validation before quarantined v1 state is re-signed."""
        if int(head["sequence"]) > MAX_LEGACY_MIGRATION_VERSIONS:
            raise CausalMemoryError("legacy causal-memory history exceeds migration bound")
        try:
            response = db.http.get(
                f"{db.SUPABASE_URL}/rest/v1/{TABLE}",
                headers=db.headers(),
                params={
                    "select": "sequence,content_digest,parent_digest,payload,created_at",
                    "order": "sequence.asc",
                    "limit": str(MAX_LEGACY_MIGRATION_VERSIONS),
                },
            )
        except Exception as exc:
            raise CausalMemoryError("legacy causal-memory history read failed") from exc
        if response.status_code >= 300:
            self._failure("legacy history read", response)
        try:
            rows = response.json()
        except Exception as exc:
            raise CausalMemoryError("legacy causal-memory history is invalid") from exc
        if (
            not isinstance(rows, list)
            or len(rows) != int(head["sequence"])
            or not rows
        ):
            raise CausalMemoryError("legacy causal-memory history is incomplete")
        previous_row: dict[str, object] | None = None
        previous_memory: CausalRepricingMemory | None = None
        attested_boundary_seen = False
        for expected_sequence, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                raise CausalMemoryError("legacy causal-memory history is invalid")
            payload = row.get("payload")
            if (
                row.get("sequence") != expected_sequence
                or not _valid_digest(row.get("content_digest"))
                or not isinstance(payload, dict)
                or payload.get("content_digest") != row["content_digest"]
                or _document_bytes(payload) > MAX_DOCUMENT_BYTES
                or (
                    previous_row is None
                    and row.get("parent_digest") is not None
                )
                or (
                    previous_row is not None
                    and row.get("parent_digest") != previous_row["content_digest"]
                )
                or (
                    not _trusted_causal_memory_document(payload)
                    and not _legacy_unsigned_causal_memory_document(payload)
                )
            ):
                raise CausalMemoryError("legacy causal-memory history is invalid")
            trusted_document = _trusted_causal_memory_document(payload)
            if attested_boundary_seen and not trusted_document:
                raise CausalMemoryError("legacy causal-memory history is invalid")
            attested_boundary_seen = attested_boundary_seen or (
                "authority_attestation" in payload and trusted_document
            )
            current_memory = self.document_to_memory(payload)
            if previous_memory is not None:
                self._require_immutable_transition(previous_memory, current_memory)
            previous_row = row
            previous_memory = current_memory
        if previous_row["content_digest"] != head["content_digest"]:
            raise CausalMemoryError("legacy causal-memory history head mismatch")

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
            or not _trusted_causal_memory_document(document)
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
