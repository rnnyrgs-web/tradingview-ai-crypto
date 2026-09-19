"""Point-in-time Money Intelligence causal-repricing research memory.

This module is intentionally research-only.  It provides a deterministic,
append-only evidence contract for causal/repricing hypotheses without granting
broker, trading, OOS-opening, or promotion authority.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Iterable, Literal


SCHEMA_VERSION = 1
EPISTEMIC_LEVELS = {"fact", "inference"}
EVIDENCE_KINDS = {"support", "contradiction"}
RESEARCH_LANES = {"big_move", "strategy_component"}
RELATIVE_IMPACT_RATIOS = {"flow_float", "flow_liquidity"}


class CausalMemoryError(ValueError):
    """Raised when the scientific contract would be violated."""


class ReplayConflictError(CausalMemoryError):
    """Raised when an immutable event id is replayed with different content."""


def _parse_time(value: str) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise CausalMemoryError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CausalMemoryError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _normalise_time(value: str) -> str:
    return _parse_time(value).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _normalise_tuple(values: Iterable[str], *, field_name: str) -> tuple[str, ...]:
    cleaned = tuple(str(value).strip() for value in values)
    if any(not value for value in cleaned):
        raise CausalMemoryError(f"{field_name} cannot contain blank values")
    if len(set(cleaned)) != len(cleaned):
        raise CausalMemoryError(f"{field_name} cannot contain duplicates")
    return cleaned


@dataclass(frozen=True)
class PointInTimeObservation:
    observation_id: str
    metric_name: str
    value: float
    unit: str
    observed_at: str
    available_at: str
    retrieved_at: str
    source_id: str
    revision_id: str = ""
    provenance_uri: str = ""

    def __post_init__(self) -> None:
        if not self.observation_id.strip() or not self.metric_name.strip():
            raise CausalMemoryError("observation_id and metric_name are required")
        if not math.isfinite(float(self.value)):
            raise CausalMemoryError("observation value must be finite")
        if not self.source_id.strip():
            raise CausalMemoryError("source_id is required")
        observed = _parse_time(self.observed_at)
        available = _parse_time(self.available_at)
        retrieved = _parse_time(self.retrieved_at)
        if not observed <= available <= retrieved:
            raise CausalMemoryError(
                "point-in-time chronology requires observed_at <= available_at <= retrieved_at"
            )
        object.__setattr__(self, "observed_at", _normalise_time(self.observed_at))
        object.__setattr__(self, "available_at", _normalise_time(self.available_at))
        object.__setattr__(self, "retrieved_at", _normalise_time(self.retrieved_at))
        object.__setattr__(self, "value", float(self.value))


@dataclass(frozen=True)
class EpistemicClaim:
    claim_id: str
    level: Literal["fact", "inference"]
    text: str
    created_at: str
    source_observation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.level not in EPISTEMIC_LEVELS:
            raise CausalMemoryError(
                "claims may be fact or inference only; hypotheses require a frozen hypothesis contract"
            )
        if not self.claim_id.strip() or not self.text.strip():
            raise CausalMemoryError("claim_id and text are required")
        object.__setattr__(self, "created_at", _normalise_time(self.created_at))
        object.__setattr__(
            self,
            "source_observation_ids",
            _normalise_tuple(self.source_observation_ids, field_name="source_observation_ids"),
        )


@dataclass(frozen=True)
class FrozenHypothesis:
    hypothesis_id: str
    statement: str
    mechanism_chain: tuple[str, ...]
    direction: Literal["positive", "negative"]
    horizon_hours: int
    falsifier: str
    matched_controls: tuple[str, ...]
    lanes: tuple[str, ...]
    created_at: str
    source_observation_ids: tuple[str, ...]
    family_id: str
    family_size: int = 1
    alpha: float = 0.05

    def __post_init__(self) -> None:
        if not self.hypothesis_id.strip() or not self.statement.strip():
            raise CausalMemoryError("hypothesis_id and statement are required")
        if self.direction not in {"positive", "negative"}:
            raise CausalMemoryError("direction must be positive or negative")
        if self.horizon_hours <= 0:
            raise CausalMemoryError("horizon_hours must be positive")
        if not self.falsifier.strip():
            raise CausalMemoryError("a predeclared falsifier is required")
        if not self.family_id.strip() or self.family_size <= 0:
            raise CausalMemoryError("family_id and positive family_size are required")
        if not 0.0 < float(self.alpha) < 1.0:
            raise CausalMemoryError("alpha must be between zero and one")
        chain = _normalise_tuple(self.mechanism_chain, field_name="mechanism_chain")
        if not chain:
            raise CausalMemoryError("mechanism_chain cannot be empty")
        controls = _normalise_tuple(self.matched_controls, field_name="matched_controls")
        lanes = _normalise_tuple(self.lanes, field_name="lanes")
        if not lanes or not set(lanes).issubset(RESEARCH_LANES):
            raise CausalMemoryError("lanes must be research-only Big-Move/strategy-component lanes")
        sources = _normalise_tuple(
            self.source_observation_ids, field_name="source_observation_ids"
        )
        if not sources:
            raise CausalMemoryError("a hypothesis requires point-in-time source observations")
        object.__setattr__(self, "mechanism_chain", chain)
        object.__setattr__(self, "matched_controls", controls)
        object.__setattr__(self, "lanes", lanes)
        object.__setattr__(self, "source_observation_ids", sources)
        object.__setattr__(self, "created_at", _normalise_time(self.created_at))
        object.__setattr__(self, "alpha", float(self.alpha))

    @property
    def fingerprint(self) -> str:
        # Deliberately exclude created_at: changing only a timestamp may not evade an
        # exact rejected-fingerprint veto.  Fresh point-in-time provenance/design does.
        frozen_design = {
            "schema_version": SCHEMA_VERSION,
            "statement": self.statement,
            "mechanism_chain": list(self.mechanism_chain),
            "direction": self.direction,
            "horizon_hours": self.horizon_hours,
            "falsifier": self.falsifier,
            "matched_controls": list(self.matched_controls),
            "lanes": list(self.lanes),
            "source_observation_ids": list(self.source_observation_ids),
            "family_id": self.family_id,
            "family_size": self.family_size,
            "alpha": self.alpha,
        }
        return f"mi-causal-v1:{_sha256(frozen_design)}"


@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str
    hypothesis_id: str
    evaluated_at: str
    kind: Literal["support", "contradiction"]
    matched_controls: tuple[str, ...]
    source_observation_ids: tuple[str, ...]
    weight: float = 1.0
    confirmatory: bool = True
    p_value: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.hypothesis_id.strip():
            raise CausalMemoryError("event_id and hypothesis_id are required")
        if self.kind not in EVIDENCE_KINDS:
            raise CausalMemoryError("evidence kind must be support or contradiction")
        if not math.isfinite(float(self.weight)) or float(self.weight) <= 0:
            raise CausalMemoryError("evidence weight must be finite and positive")
        if self.p_value is not None and not 0.0 <= float(self.p_value) <= 1.0:
            raise CausalMemoryError("p_value must be in [0, 1]")
        object.__setattr__(self, "evaluated_at", _normalise_time(self.evaluated_at))
        object.__setattr__(
            self,
            "matched_controls",
            _normalise_tuple(self.matched_controls, field_name="matched_controls"),
        )
        object.__setattr__(
            self,
            "source_observation_ids",
            _normalise_tuple(self.source_observation_ids, field_name="source_observation_ids"),
        )
        object.__setattr__(self, "weight", float(self.weight))
        if self.p_value is not None:
            object.__setattr__(self, "p_value", float(self.p_value))


@dataclass(frozen=True)
class RelativeImpact:
    ratio_name: str
    numerator_observation_id: str | None
    denominator_observation_id: str | None
    value: float | None
    reason: str
    as_of: str


@dataclass(frozen=True)
class ConfidenceSnapshot:
    hypothesis_id: str
    as_of: str
    score: float
    decayed_net_evidence: float
    confirmatory_support_count: int
    contradiction_count: int


class CausalRepricingMemory:
    """Append-only scientific memory for point-in-time causal research."""

    def __init__(
        self,
        *,
        rejected_fingerprints: Iterable[str] = (),
        half_life_days: float = 30.0,
    ) -> None:
        if not math.isfinite(float(half_life_days)) or half_life_days <= 0:
            raise CausalMemoryError("half_life_days must be finite and positive")
        self.half_life_days = float(half_life_days)
        self.rejected_fingerprints = {str(value) for value in rejected_fingerprints}
        self.observations: dict[str, PointInTimeObservation] = {}
        self.claims: dict[str, EpistemicClaim] = {}
        self.hypotheses: dict[str, FrozenHypothesis] = {}
        self.events: dict[str, EvidenceEvent] = {}

    @staticmethod
    def _append_immutable(store: dict[str, object], key: str, value: object) -> bool:
        existing = store.get(key)
        if existing is None:
            store[key] = value
            return True
        if existing == value:
            return False
        raise ReplayConflictError(f"immutable id {key!r} replayed with different content")

    def register_observation(self, observation: PointInTimeObservation) -> bool:
        return self._append_immutable(
            self.observations, observation.observation_id, observation
        )

    def _require_sources_available(self, source_ids: Iterable[str], as_of: str) -> None:
        cutoff = _parse_time(as_of)
        source_ids = tuple(source_ids)
        if not source_ids:
            raise CausalMemoryError("source_observation_ids cannot be empty")
        for source_id in source_ids:
            observation = self.observations.get(source_id)
            if observation is None:
                raise CausalMemoryError(f"unknown source observation: {source_id}")
            if _parse_time(observation.available_at) > cutoff:
                raise CausalMemoryError(
                    f"source observation {source_id} was not point-in-time available"
                )

    def register_claim(self, claim: EpistemicClaim) -> bool:
        self._require_sources_available(claim.source_observation_ids, claim.created_at)
        return self._append_immutable(self.claims, claim.claim_id, claim)

    def register_hypothesis(self, hypothesis: FrozenHypothesis) -> bool:
        self._require_sources_available(
            hypothesis.source_observation_ids, hypothesis.created_at
        )
        if hypothesis.fingerprint in self.rejected_fingerprints:
            raise CausalMemoryError("exact rejected hypothesis fingerprint is ineligible")
        return self._append_immutable(
            self.hypotheses, hypothesis.hypothesis_id, hypothesis
        )

    def record_evidence(self, event: EvidenceEvent) -> bool:
        hypothesis = self.hypotheses.get(event.hypothesis_id)
        if hypothesis is None:
            raise CausalMemoryError(f"unknown hypothesis: {event.hypothesis_id}")
        if event.matched_controls != hypothesis.matched_controls:
            raise CausalMemoryError(
                "evidence controls must exactly match the frozen matched-control contract"
            )
        self._require_sources_available(event.source_observation_ids, event.evaluated_at)
        if _parse_time(event.evaluated_at) < _parse_time(hypothesis.created_at):
            raise CausalMemoryError("evidence cannot predate the frozen hypothesis")
        if event.kind == "support" and event.confirmatory:
            adjusted_alpha = hypothesis.alpha / hypothesis.family_size
            if event.p_value is None or event.p_value > adjusted_alpha:
                raise CausalMemoryError(
                    "confirmatory support must pass the frozen Bonferroni family threshold"
                )
        return self._append_immutable(self.events, event.event_id, event)

    def confidence(self, hypothesis_id: str, *, as_of: str) -> ConfidenceSnapshot:
        if hypothesis_id not in self.hypotheses:
            raise CausalMemoryError(f"unknown hypothesis: {hypothesis_id}")
        cutoff = _parse_time(as_of)
        net = 0.0
        support_count = 0
        contradiction_count = 0
        for event in self.events.values():
            if event.hypothesis_id != hypothesis_id:
                continue
            event_time = _parse_time(event.evaluated_at)
            if event_time > cutoff:
                continue
            age_days = max(0.0, (cutoff - event_time).total_seconds() / 86400.0)
            decayed_weight = event.weight * (0.5 ** (age_days / self.half_life_days))
            if event.kind == "contradiction":
                net -= decayed_weight
                contradiction_count += 1
            elif event.confirmatory:
                net += decayed_weight
                support_count += 1
            # Exploratory supportive evidence is retained but cannot manufacture
            # confirmatory confidence or research-lane eligibility.
        score = 0.5 + 0.5 * math.tanh(net)
        return ConfidenceSnapshot(
            hypothesis_id=hypothesis_id,
            as_of=_normalise_time(as_of),
            score=score,
            decayed_net_evidence=net,
            confirmatory_support_count=support_count,
            contradiction_count=contradiction_count,
        )

    def contradiction_ledger(
        self, hypothesis_id: str | None = None
    ) -> tuple[EvidenceEvent, ...]:
        events = [
            event
            for event in self.events.values()
            if event.kind == "contradiction"
            and (hypothesis_id is None or event.hypothesis_id == hypothesis_id)
        ]
        return tuple(sorted(events, key=lambda event: (event.evaluated_at, event.event_id)))

    def latest_metric(self, metric_name: str, *, as_of: str) -> PointInTimeObservation | None:
        cutoff = _parse_time(as_of)
        candidates = [
            observation
            for observation in self.observations.values()
            if observation.metric_name == metric_name
            and _parse_time(observation.available_at) <= cutoff
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda observation: (
                _parse_time(observation.available_at),
                _parse_time(observation.observed_at),
                observation.observation_id,
            ),
        )

    def relative_impact(
        self,
        *,
        ratio_name: str,
        numerator_metric: str,
        denominator_metric: str,
        as_of: str,
    ) -> RelativeImpact:
        if ratio_name not in RELATIVE_IMPACT_RATIOS:
            raise CausalMemoryError("relative impact ratio must be flow_float or flow_liquidity")
        normalised_as_of = _normalise_time(as_of)
        numerator = self.latest_metric(numerator_metric, as_of=normalised_as_of)
        denominator = self.latest_metric(denominator_metric, as_of=normalised_as_of)
        if numerator is None or denominator is None:
            return RelativeImpact(
                ratio_name=ratio_name,
                numerator_observation_id=(numerator.observation_id if numerator else None),
                denominator_observation_id=(denominator.observation_id if denominator else None),
                value=None,
                reason="point_in_time_input_unavailable",
                as_of=normalised_as_of,
            )
        if denominator.value <= 0:
            return RelativeImpact(
                ratio_name=ratio_name,
                numerator_observation_id=numerator.observation_id,
                denominator_observation_id=denominator.observation_id,
                value=None,
                reason="non_positive_denominator",
                as_of=normalised_as_of,
            )
        return RelativeImpact(
            ratio_name=ratio_name,
            numerator_observation_id=numerator.observation_id,
            denominator_observation_id=denominator.observation_id,
            value=numerator.value / denominator.value,
            reason="ok",
            as_of=normalised_as_of,
        )

    def research_artifact(
        self,
        hypothesis_id: str,
        *,
        lane: str,
        as_of: str,
        minimum_score: float = 0.65,
        minimum_confirmatory_support: int = 1,
    ) -> dict[str, object] | None:
        hypothesis = self.hypotheses.get(hypothesis_id)
        if hypothesis is None:
            raise CausalMemoryError(f"unknown hypothesis: {hypothesis_id}")
        if lane not in RESEARCH_LANES or lane not in hypothesis.lanes:
            raise CausalMemoryError("lane is not declared by the frozen research contract")
        if hypothesis.fingerprint in self.rejected_fingerprints:
            return None
        snapshot = self.confidence(hypothesis_id, as_of=as_of)
        if snapshot.score < minimum_score:
            return None
        if snapshot.confirmatory_support_count < minimum_confirmatory_support:
            return None
        cutoff = _parse_time(as_of)
        relevant = [
            event
            for event in self.events.values()
            if event.hypothesis_id == hypothesis_id
            and _parse_time(event.evaluated_at) <= cutoff
        ]
        supports = [
            event
            for event in relevant
            if event.kind == "support" and event.confirmatory
        ]
        contradictions = [event for event in relevant if event.kind == "contradiction"]
        latest_support = max(
            (_parse_time(event.evaluated_at) for event in supports), default=None
        )
        if latest_support is None:
            return None
        if any(_parse_time(event.evaluated_at) >= latest_support for event in contradictions):
            return None
        return {
            "schema_version": SCHEMA_VERSION,
            "lane": lane,
            "hypothesis_id": hypothesis.hypothesis_id,
            "hypothesis_fingerprint": hypothesis.fingerprint,
            "as_of": _normalise_time(as_of),
            "research_confidence": snapshot.score,
            "source_observation_ids": list(hypothesis.source_observation_ids),
            "mechanism_chain": list(hypothesis.mechanism_chain),
            "research_only": True,
            "trading_authority": False,
            "promotion_authority": False,
            "oos_opening_authority": False,
        }

    def _payload_without_digest(self) -> dict[str, object]:
        return {
            "schema_version": SCHEMA_VERSION,
            "half_life_days": self.half_life_days,
            "rejected_fingerprints": sorted(self.rejected_fingerprints),
            "observations": [
                asdict(self.observations[key]) for key in sorted(self.observations)
            ],
            "claims": [asdict(self.claims[key]) for key in sorted(self.claims)],
            "hypotheses": [
                asdict(self.hypotheses[key]) for key in sorted(self.hypotheses)
            ],
            "events": [asdict(self.events[key]) for key in sorted(self.events)],
        }

    def to_document(self) -> dict[str, object]:
        payload = self._payload_without_digest()
        return {**payload, "content_digest": _sha256(payload)}

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        encoded = (_canonical_json(self.to_document()) + "\n").encode("utf-8")
        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=str(target.parent), delete=False
            ) as handle:
                temp_path = handle.name
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, target)
            temp_path = None
        finally:
            if temp_path is not None:
                try:
                    os.unlink(temp_path)
                except FileNotFoundError:
                    pass

    @classmethod
    def load(cls, path: str | Path) -> "CausalRepricingMemory":
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CausalMemoryError("causal memory is unreadable or corrupt") from exc
        if document.get("schema_version") != SCHEMA_VERSION:
            raise CausalMemoryError("unsupported causal-memory schema version")
        supplied_digest = document.pop("content_digest", None)
        if not supplied_digest or supplied_digest != _sha256(document):
            raise CausalMemoryError("causal-memory content digest mismatch")
        memory = cls(
            rejected_fingerprints=document.get("rejected_fingerprints", []),
            half_life_days=float(document["half_life_days"]),
        )
        try:
            for raw in document.get("observations", []):
                memory.register_observation(PointInTimeObservation(**raw))
            for raw in document.get("claims", []):
                raw = dict(raw)
                raw["source_observation_ids"] = tuple(raw["source_observation_ids"])
                memory.register_claim(EpistemicClaim(**raw))
            for raw in document.get("hypotheses", []):
                raw = dict(raw)
                for field in ("mechanism_chain", "matched_controls", "lanes", "source_observation_ids"):
                    raw[field] = tuple(raw[field])
                memory.register_hypothesis(FrozenHypothesis(**raw))
            for raw in document.get("events", []):
                raw = dict(raw)
                raw["matched_controls"] = tuple(raw["matched_controls"])
                raw["source_observation_ids"] = tuple(raw["source_observation_ids"])
                memory.record_evidence(EvidenceEvent(**raw))
        except (KeyError, TypeError, CausalMemoryError) as exc:
            raise CausalMemoryError("causal memory failed scientific-contract validation") from exc
        return memory
