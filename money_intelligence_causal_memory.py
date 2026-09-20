"""Point-in-time Money Intelligence causal-repricing research memory.

Research-only scientific memory. It grants no broker, trading, OOS-opening, or
promotion authority. Hypotheses are frozen before outcomes and evidence is
append-only, chronology checked, provenance bound, and replay safe.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Iterable, Literal


SCHEMA_VERSION = 2
EPISTEMIC_LEVELS = {"fact", "inference"}
EVIDENCE_KINDS = {"support", "contradiction"}
RESEARCH_LANES = {"big_move", "strategy_component"}
RELATIVE_IMPACT_RATIOS = {"flow_float", "flow_liquidity"}
TRUSTED_EVALUATION_IMPLEMENTATION = "paired-sign-exact-independent-units-v2"
LEGACY_UNVERIFIED_IMPLEMENTATION = "legacy-unverified-v0"
PROJECT_TESTING_PROTOCOL = "global-sequential-bonferroni-v1"
PROJECT_ALPHA = 0.05
TRUSTED_EVALUATION_METHODS = {
    "matched_control_mean_difference_v1",
    "matched_mean_diff_v1",
}


class CausalMemoryError(ValueError):
    """Raised when the scientific contract would be violated."""


class ReplayConflictError(CausalMemoryError):
    """Raised when an immutable id is replayed with different content."""


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
    subject_id: str
    currency: str
    measurement_window_hours: int
    venue: str
    max_age_hours: int
    revision_id: str = ""
    provenance_uri: str = ""

    def __post_init__(self) -> None:
        if not self.observation_id.strip() or not self.metric_name.strip():
            raise CausalMemoryError("observation_id and metric_name are required")
        if not math.isfinite(float(self.value)):
            raise CausalMemoryError("observation value must be finite")
        if not all(
            value.strip()
            for value in (
                self.source_id,
                self.subject_id,
                self.currency,
                self.unit,
                self.venue,
            )
        ):
            raise CausalMemoryError(
                "source_id, subject_id, currency, unit, and venue are required"
            )
        if self.measurement_window_hours <= 0 or self.max_age_hours <= 0:
            raise CausalMemoryError(
                "measurement_window_hours and max_age_hours must be positive"
            )
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

    @property
    def provenance_fingerprint(self) -> str:
        return _sha256(asdict(self))


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
    evaluation_method: str
    family_size: int = 1
    alpha: float = 0.05
    # Pre-outcome economic units for the sole confirmatory look. Empty plans
    # remain eligible for exploratory research but cannot claim confirmation.
    evaluation_units: tuple[tuple[str, str, int], ...] = ()
    # Exact outcome/control observation identities, aligned one-for-one with
    # evaluation_units and frozen before either side of a pair is observed.
    evaluation_pairs: tuple[tuple[str, str], ...] = ()
    # Each ordered pair freezes (metric, source, provenance URI) for its
    # outcome and control. IDs alone do not constrain post-outcome selection.
    evaluation_selectors: tuple[
        tuple[tuple[str, str, str], tuple[str, str, str]], ...
    ] = ()

    def __post_init__(self) -> None:
        if not self.hypothesis_id.strip() or not self.statement.strip():
            raise CausalMemoryError("hypothesis_id and statement are required")
        if self.direction not in {"positive", "negative"}:
            raise CausalMemoryError("direction must be positive or negative")
        if self.horizon_hours <= 0:
            raise CausalMemoryError("horizon_hours must be positive")
        if not self.falsifier.strip():
            raise CausalMemoryError("a predeclared falsifier is required")
        if (
            not self.family_id.strip()
            or not self.evaluation_method.strip()
            or self.family_size <= 0
        ):
            raise CausalMemoryError(
                "family_id, evaluation_method, and positive family_size are required"
            )
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
        planned_units = []
        for raw in self.evaluation_units:
            if not isinstance(raw, (tuple, list)) or len(raw) != 3:
                raise CausalMemoryError(
                    "evaluation units must contain subject, start, window"
                )
            subject, start, window = raw
            if (
                not isinstance(subject, str)
                or not subject.strip()
                or type(window) is not int
                or window <= 0
            ):
                raise CausalMemoryError(
                    "evaluation units require subject and positive window"
                )
            if window != self.horizon_hours:
                raise CausalMemoryError(
                    "evaluation-unit window must match frozen hypothesis horizon"
                )
            start = _normalise_time(start)
            if _parse_time(start) < _parse_time(self.created_at):
                raise CausalMemoryError("evaluation units must begin after hypothesis freeze")
            planned_units.append((subject.strip(), start, window))
        if len(set(planned_units)) != len(planned_units):
            raise CausalMemoryError("evaluation units cannot contain duplicates")
        object.__setattr__(self, "evaluation_units", tuple(planned_units))
        planned_pairs = []
        for raw in self.evaluation_pairs:
            if not isinstance(raw, (tuple, list)) or len(raw) != 2:
                raise CausalMemoryError(
                    "evaluation pairs must contain outcome and control observation ids"
                )
            outcome_id, control_id = raw
            if (
                not isinstance(outcome_id, str)
                or not outcome_id.strip()
                or not isinstance(control_id, str)
                or not control_id.strip()
                or outcome_id.strip() == control_id.strip()
            ):
                raise CausalMemoryError(
                    "evaluation pairs require distinct outcome and control observation ids"
                )
            planned_pairs.append((outcome_id.strip(), control_id.strip()))
        if planned_pairs and len(planned_pairs) != len(planned_units):
            raise CausalMemoryError(
                "evaluation pairs must align one-for-one with evaluation units"
            )
        planned_ids = [identifier for pair in planned_pairs for identifier in pair]
        if len(set(planned_ids)) != len(planned_ids):
            raise CausalMemoryError("evaluation pair observation ids cannot be reused")
        object.__setattr__(self, "evaluation_pairs", tuple(planned_pairs))
        planned_selectors = []
        for raw_pair in self.evaluation_selectors:
            if not isinstance(raw_pair, (tuple, list)) or len(raw_pair) != 2:
                raise CausalMemoryError("evaluation selectors require outcome and control")
            selectors = []
            for raw_selector in raw_pair:
                if not isinstance(raw_selector, (tuple, list)) or len(raw_selector) != 3:
                    raise CausalMemoryError(
                        "evaluation selectors require metric, source, and provenance URI"
                    )
                if any(
                    not isinstance(value, str) or not value.strip()
                    for value in raw_selector
                ):
                    raise CausalMemoryError("evaluation selector fields cannot be blank")
                selectors.append(tuple(value.strip() for value in raw_selector))
            planned_selectors.append(tuple(selectors))
        if planned_selectors and len(planned_selectors) != len(planned_pairs):
            raise CausalMemoryError("evaluation selectors must align with frozen pairs")
        object.__setattr__(self, "evaluation_selectors", tuple(planned_selectors))

    @property
    def fingerprint(self) -> str:
        """Frozen design fingerprint; timestamp-only changes cannot evade rejection."""
        design = {
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
            "evaluation_method": self.evaluation_method,
            "family_size": self.family_size,
            "alpha": self.alpha,
        }
        if self.evaluation_units:
            design["evaluation_units"] = list(self.evaluation_units)
        if self.evaluation_pairs:
            design["evaluation_pairs"] = list(self.evaluation_pairs)
        if self.evaluation_selectors:
            design["evaluation_selectors"] = list(self.evaluation_selectors)
        return f"mi-causal-v1:{_sha256(design)}"


@dataclass(frozen=True)
class EvidenceEvent:
    event_id: str
    hypothesis_id: str
    evaluated_at: str
    kind: Literal["support", "contradiction"]
    matched_controls: tuple[str, ...]
    outcome_observation_ids: tuple[str, ...]
    control_observation_ids: tuple[str, ...]
    evaluation_method: str
    sample_size: int
    evaluation_implementation: str = TRUSTED_EVALUATION_IMPLEMENTATION
    confirmatory: bool = True
    p_value: float | None = None
    note: str = ""

    def __post_init__(self) -> None:
        if not self.event_id.strip() or not self.hypothesis_id.strip():
            raise CausalMemoryError("event_id and hypothesis_id are required")
        if self.kind not in EVIDENCE_KINDS:
            raise CausalMemoryError("evidence kind must be support or contradiction")
        if (
            not self.evaluation_method.strip()
            or not self.evaluation_implementation.strip()
            or self.sample_size <= 0
        ):
            raise CausalMemoryError(
                "evaluation_method, evaluation_implementation, and positive sample_size are required"
            )
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
            "outcome_observation_ids",
            _normalise_tuple(
                self.outcome_observation_ids, field_name="outcome_observation_ids"
            ),
        )
        object.__setattr__(
            self,
            "control_observation_ids",
            _normalise_tuple(
                self.control_observation_ids, field_name="control_observation_ids"
            ),
        )
        if set(self.outcome_observation_ids) & set(self.control_observation_ids):
            raise CausalMemoryError("outcome and control observations must be disjoint")
        if not self.outcome_observation_ids or not self.control_observation_ids:
            raise CausalMemoryError(
                "outcome_observation_ids and control_observation_ids cannot be empty"
            )
        if self.p_value is not None:
            object.__setattr__(self, "p_value", float(self.p_value))

    @property
    def evidence_weight(self) -> float:
        """Bounded scoring weight; callers cannot tune confidence magnitude."""
        return 1.0

    @property
    def fingerprint(self) -> str:
        return "mi-evidence-v1:" + _sha256(asdict(self))


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
        # Immutable registration order is the project-wide testing ledger.
        # Slot i spends at most alpha / (i * (i + 1)); the infinite sum is
        # alpha, independent of family labels or the eventual search count.
        self.hypothesis_order: list[str] = []
        self.event_order: list[str] = []
        self.registration_log: list[dict[str, str]] = []
        # Digest-bound identities of historical underdeclared families. They
        # remain auditable but can never authorize a fresh sibling or support.
        self.legacy_underdeclared_hypotheses: set[str] = set()

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
        added = self._append_immutable(
            self.observations, observation.observation_id, observation
        )
        if added:
            self.registration_log.append(
                {"kind": "observation", "id": observation.observation_id}
            )
        return added

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
            if _parse_time(observation.retrieved_at) > cutoff:
                raise CausalMemoryError(
                    f"source observation {source_id} was not yet retrieved by the system"
                )

    def register_claim(self, claim: EpistemicClaim) -> bool:
        self._require_sources_available(claim.source_observation_ids, claim.created_at)
        return self._append_immutable(self.claims, claim.claim_id, claim)

    def effective_fingerprint(self, hypothesis: FrozenHypothesis) -> str:
        """Bind a frozen design to the exact PIT source provenance it consumed."""
        source_provenance: list[str] = []
        for source_id in hypothesis.source_observation_ids:
            observation = self.observations.get(source_id)
            if observation is None:
                raise CausalMemoryError(f"unknown source observation: {source_id}")
            source_provenance.append(observation.provenance_fingerprint)
        return "mi-causal-pit-v1:" + _sha256(
            {
                "design_fingerprint": hypothesis.fingerprint,
                "source_provenance": source_provenance,
            }
        )

    @staticmethod
    def _rejection_variants(
        hypothesis: FrozenHypothesis,
    ) -> tuple[FrozenHypothesis, ...]:
        variants = [hypothesis]
        # Pair identity was added after planned-unit identity. Preserve rejected
        # memory across that schema strengthening instead of treating the new
        # field as scientific novelty.
        if hypothesis.evaluation_pairs:
            variants.append(
                replace(hypothesis, evaluation_pairs=(), evaluation_selectors=())
            )
        if hypothesis.evaluation_selectors:
            variants.append(replace(hypothesis, evaluation_selectors=()))
        if (
            hypothesis.evaluation_units
            or hypothesis.evaluation_pairs
            or hypothesis.evaluation_selectors
        ):
            variants.append(
                replace(
                    hypothesis,
                    evaluation_units=(), evaluation_pairs=(), evaluation_selectors=(),
                )
            )
        return tuple({variant.fingerprint: variant for variant in variants}.values())

    def _is_rejected(self, hypothesis: FrozenHypothesis) -> bool:
        return any(
            variant.fingerprint in self.rejected_fingerprints
            or self.effective_fingerprint(variant) in self.rejected_fingerprints
            for variant in self._rejection_variants(hypothesis)
        )

    def register_hypothesis(
        self, hypothesis: FrozenHypothesis, *, _restore_legacy_undercount: bool = False
    ) -> bool:
        self._require_sources_available(
            hypothesis.source_observation_ids, hypothesis.created_at
        )
        if self._is_rejected(hypothesis):
            raise CausalMemoryError("exact rejected hypothesis fingerprint is ineligible")
        if hypothesis.hypothesis_id in self.hypotheses:
            return self._append_immutable(
                self.hypotheses, hypothesis.hypothesis_id, hypothesis
            )
        for subject, start, window in hypothesis.evaluation_units:
            planned_start = _parse_time(start)
            planned_end = planned_start + timedelta(hours=window)
            for observation in self.observations.values():
                if observation.subject_id != subject:
                    continue
                observed_start = _parse_time(observation.observed_at)
                observed_end = observed_start + timedelta(
                    hours=observation.measurement_window_hours
                )
                if planned_start < observed_end and observed_start < planned_end:
                    raise CausalMemoryError(
                        "evaluation plan cannot be frozen after its economic units are observed"
                    )
        family_members = [
            member
            for member in self.hypotheses.values()
            if member.family_id == hypothesis.family_id
            and member.hypothesis_id != hypothesis.hypothesis_id
        ]
        family_members.append(hypothesis)
        actual_family_size = len(family_members)
        if any(
            member.family_size < actual_family_size for member in family_members
        ) and not (
            _restore_legacy_undercount
            and hypothesis.hypothesis_id in self.legacy_underdeclared_hypotheses
            and not hypothesis.evaluation_units
            and not hypothesis.evaluation_pairs
            and not hypothesis.evaluation_selectors
        ):
            raise CausalMemoryError(
                "family_size cannot undercount registered hypotheses in the family"
            )
        added = self._append_immutable(
            self.hypotheses, hypothesis.hypothesis_id, hypothesis
        )
        if added:
            self.hypothesis_order.append(hypothesis.hypothesis_id)
            self.registration_log.append(
                {"kind": "hypothesis", "id": hypothesis.hypothesis_id}
            )
        return added

    def _project_threshold(self, hypothesis: FrozenHypothesis) -> float:
        slot = self.hypothesis_order.index(hypothesis.hypothesis_id) + 1
        return min(
            hypothesis.alpha / hypothesis.family_size,
            PROJECT_ALPHA / (slot * (slot + 1)),
        )

    def reject_hypothesis(self, hypothesis_id: str) -> tuple[str, str]:
        """Persist both frozen-design and provenance-bound rejection fingerprints."""
        hypothesis = self.hypotheses.get(hypothesis_id)
        if hypothesis is None:
            raise CausalMemoryError(f"unknown hypothesis: {hypothesis_id}")
        design = hypothesis.fingerprint
        effective = self.effective_fingerprint(hypothesis)
        for variant in self._rejection_variants(hypothesis):
            self.rejected_fingerprints.update(
                (variant.fingerprint, self.effective_fingerprint(variant))
            )
        return design, effective

    @staticmethod
    def _paired_sign_p_value(*, wins: int, non_ties: int) -> float:
        """Exact one-sided paired sign-test tail under p=0.5."""
        if non_ties <= 0:
            return 1.0
        return sum(
            math.comb(non_ties, count)
            for count in range(wins, non_ties + 1)
        ) / float(2**non_ties)

    def _verified_evaluation(
        self,
        event: EvidenceEvent,
        hypothesis: FrozenHypothesis,
    ) -> dict[str, object]:
        if event.evaluation_method not in TRUSTED_EVALUATION_METHODS:
            raise CausalMemoryError("unsupported confirmatory evaluation method")
        if event.evaluation_implementation != TRUSTED_EVALUATION_IMPLEMENTATION:
            raise CausalMemoryError("unsupported evaluation implementation")
        if len(event.outcome_observation_ids) != len(event.control_observation_ids):
            raise CausalMemoryError(
                "trusted paired evaluation requires equal outcome and control counts"
            )

        independent_units: list[dict[str, object]] = []
        unit_fingerprints: set[str] = set()
        intervals_by_subject: dict[str, list[tuple[datetime, datetime]]] = {}
        for outcome_id, control_id in zip(
            event.outcome_observation_ids,
            event.control_observation_ids,
            strict=True,
        ):
            outcome = self.observations[outcome_id]
            control = self.observations[control_id]
            outcome_unit = {
                "subject_id": outcome.subject_id,
                "observed_at": outcome.observed_at,
                "measurement_window_hours": outcome.measurement_window_hours,
            }
            control_unit = {
                "subject_id": control.subject_id,
                "observed_at": control.observed_at,
                "measurement_window_hours": control.measurement_window_hours,
            }
            if outcome_unit != control_unit:
                raise CausalMemoryError(
                    "each outcome/control pair must represent the same economic unit"
                )
            unit_fingerprint = _sha256(outcome_unit)
            if unit_fingerprint in unit_fingerprints:
                raise CausalMemoryError(
                    "matched pairs must represent distinct independent economic units"
                )
            unit_fingerprints.add(unit_fingerprint)
            independent_units.append(
                {
                    **outcome_unit,
                    "unit_fingerprint": unit_fingerprint,
                }
            )
            interval_start = _parse_time(outcome.observed_at)
            interval_end = interval_start + timedelta(
                hours=outcome.measurement_window_hours
            )
            # A venue or display-unit relabel cannot split one subject's realization.
            intervals_by_subject.setdefault(outcome.subject_id, []).append(
                (interval_start, interval_end)
            )

        for intervals in intervals_by_subject.values():
            ordered = sorted(intervals)
            if any(
                current_start < previous_end
                for (_, previous_end), (current_start, _) in zip(
                    ordered, ordered[1:], strict=False
                )
            ):
                raise CausalMemoryError(
                    "temporal independent economic units must use non-overlapping windows"
                )

        independent_unit_count = len(unit_fingerprints)
        if event.sample_size != independent_unit_count:
            raise CausalMemoryError(
                "sample_size must equal the number of verified independent economic units"
            )

        differences = [
            self.observations[outcome_id].value
            - self.observations[control_id].value
            for outcome_id, control_id in zip(
                event.outcome_observation_ids,
                event.control_observation_ids,
                strict=True,
            )
        ]
        directional = [
            difference if hypothesis.direction == "positive" else -difference
            for difference in differences
        ]
        wins = sum(value > 0 for value in directional)
        non_ties = sum(value != 0 for value in directional)
        p_value = self._paired_sign_p_value(wins=wins, non_ties=non_ties)
        if event.p_value is not None and not math.isclose(
            event.p_value, p_value, rel_tol=1e-12, abs_tol=1e-12
        ):
            raise CausalMemoryError(
                "caller p_value does not match the recomputed p_value"
            )

        payload = {
            "evaluation_implementation": TRUSTED_EVALUATION_IMPLEMENTATION,
            "independent_unit_contract": "economic-realization-nonoverlap-v2",
            "evaluation_method": event.evaluation_method,
            "hypothesis_id": hypothesis.hypothesis_id,
            "family_id": hypothesis.family_id,
            "family_size": hypothesis.family_size,
            "alpha": hypothesis.alpha,
            "direction": hypothesis.direction,
            "matched_controls": list(event.matched_controls),
            "sample_size": independent_unit_count,
            "independent_units": independent_units,
            "non_tie_count": non_ties,
            "directional_win_count": wins,
            "verified_p_value": p_value,
            "outcome_inputs": [
                {
                    "observation_id": source_id,
                    "provenance_fingerprint": self.observations[
                        source_id
                    ].provenance_fingerprint,
                }
                for source_id in event.outcome_observation_ids
            ],
            "control_inputs": [
                {
                    "observation_id": source_id,
                    "provenance_fingerprint": self.observations[
                        source_id
                    ].provenance_fingerprint,
                }
                for source_id in event.control_observation_ids
            ],
        }
        return {
            **payload,
            "verified_fingerprint": "mi-verified-evidence-v3:" + _sha256(payload),
        }

    def record_evidence(
        self,
        event: EvidenceEvent,
        *,
        _allow_legacy_unverified: bool = False,
    ) -> bool:
        existing = self.events.get(event.event_id)
        if existing is not None:
            if existing == event:
                return False
            raise ReplayConflictError(
                f"immutable id {event.event_id!r} replayed with different content"
            )
        hypothesis = self.hypotheses.get(event.hypothesis_id)
        if hypothesis is None:
            raise CausalMemoryError(f"unknown hypothesis: {event.hypothesis_id}")
        if event.matched_controls != hypothesis.matched_controls:
            raise CausalMemoryError(
                "evidence controls must exactly match the frozen matched-control contract"
            )
        if event.evaluation_method != hypothesis.evaluation_method:
            raise CausalMemoryError(
                "evidence evaluation method must match the frozen hypothesis contract"
            )
        evaluation_sources = (
            event.outcome_observation_ids + event.control_observation_ids
        )
        formation_sources = set(hypothesis.source_observation_ids)
        if formation_sources & set(evaluation_sources):
            raise CausalMemoryError(
                "confirmatory evidence cannot reuse hypothesis-formation observations"
            )
        self._require_sources_available(evaluation_sources, event.evaluated_at)
        if _parse_time(event.evaluated_at) < _parse_time(hypothesis.created_at):
            raise CausalMemoryError("evidence cannot predate the frozen hypothesis")
        frozen_at = _parse_time(hypothesis.created_at)
        for source_id in evaluation_sources:
            observation = self.observations[source_id]
            if _parse_time(observation.observed_at) < frozen_at:
                raise CausalMemoryError(
                    "outcome/control observations must begin after hypothesis freeze"
                )
        observations = [
            self.observations[source_id] for source_id in evaluation_sources
        ]
        comparison_keys = {
            (
                observation.currency,
                observation.unit,
                observation.measurement_window_hours,
                observation.venue,
            )
            for observation in observations
        }
        if len(comparison_keys) != 1:
            raise CausalMemoryError(
                "outcome/control observations must be unit, window, and venue comparable"
            )
        outcome_mean = sum(
            self.observations[source_id].value
            for source_id in event.outcome_observation_ids
        ) / len(event.outcome_observation_ids)
        control_mean = sum(
            self.observations[source_id].value
            for source_id in event.control_observation_ids
        ) / len(event.control_observation_ids)
        observed_effect = outcome_mean - control_mean
        supports_direction = (
            observed_effect > 0
            if hypothesis.direction == "positive"
            else observed_effect < 0
        )
        if (event.kind == "support") != supports_direction:
            raise CausalMemoryError(
                "evidence kind conflicts with the observed effect direction"
            )
        if event.evaluation_implementation == LEGACY_UNVERIFIED_IMPLEMENTATION:
            if not _allow_legacy_unverified or event.confirmatory:
                raise CausalMemoryError(
                    "legacy unverified evidence is restore-only and non-confirmatory"
                )
            verification = None
        else:
            verification = self._verified_evaluation(event, hypothesis)
        for existing in self.events.values():
            if (
                frozenset(existing.outcome_observation_ids)
                == frozenset(event.outcome_observation_ids)
                and frozenset(existing.control_observation_ids)
                == frozenset(event.control_observation_ids)
            ):
                raise CausalMemoryError(
                    "evaluation observations already consumed by another evidence event"
                )
            if verification is not None:
                # Events and their observations are the durable global consumption
                # ledger. Rebuild it on every write/restart, including legacy events;
                # neither a new hypothesis/family nor a new representation resets it.
                for current_unit in verification["independent_units"]:
                    current_start = _parse_time(current_unit["observed_at"])
                    current_end = current_start + timedelta(
                        hours=current_unit["measurement_window_hours"]
                    )
                    for source_id in (
                        existing.outcome_observation_ids
                        + existing.control_observation_ids
                    ):
                        consumed = self.observations[source_id]
                        if consumed.subject_id != current_unit["subject_id"]:
                            continue
                        consumed_start = _parse_time(consumed.observed_at)
                        consumed_end = consumed_start + timedelta(
                            hours=consumed.measurement_window_hours
                        )
                        if current_start < consumed_end and consumed_start < current_end:
                            raise CausalMemoryError(
                                "verified independent units already consumed by another evidence event"
                            )
        if event.kind == "support" and event.confirmatory and any(
            prior.hypothesis_id == event.hypothesis_id
            for prior in self.events.values()
        ):
            raise CausalMemoryError(
                "repeated confirmatory looks require a new project-wide test slot"
            )
        if event.kind == "support" and event.confirmatory:
            if not hypothesis.evaluation_units:
                raise CausalMemoryError(
                    "confirmatory support requires a pre-outcome evaluation plan"
                )
            if not hypothesis.evaluation_pairs:
                raise CausalMemoryError(
                    "confirmatory support requires frozen outcome/control pairs"
                )
            if not hypothesis.evaluation_selectors:
                raise CausalMemoryError(
                    "confirmatory support requires frozen observation provenance"
                )
            submitted_pairs = tuple(
                zip(
                    event.outcome_observation_ids,
                    event.control_observation_ids,
                    strict=True,
                )
            )
            if submitted_pairs != hypothesis.evaluation_pairs:
                raise CausalMemoryError(
                    "confirmatory evidence must match the frozen outcome/control pairs"
                )
            for (outcome_id, control_id), (outcome_selector, control_selector) in zip(
                submitted_pairs, hypothesis.evaluation_selectors, strict=True
            ):
                for observation_id, selector in (
                    (outcome_id, outcome_selector), (control_id, control_selector)
                ):
                    observation = self.observations[observation_id]
                    actual_selector = (
                        observation.metric_name,
                        observation.source_id,
                        observation.provenance_uri,
                    )
                    if actual_selector != selector:
                        raise CausalMemoryError(
                            "confirmatory evidence must match frozen observation provenance"
                        )
            actual_units = (
                {
                    (
                        unit["subject_id"],
                        unit["observed_at"],
                        unit["measurement_window_hours"],
                    )
                    for unit in verification["independent_units"]
                }
                if verification is not None
                else set()
            )
            if actual_units != set(hypothesis.evaluation_units):
                raise CausalMemoryError(
                    "confirmatory evidence must match the frozen evaluation units"
                )
            adjusted_alpha = self._project_threshold(hypothesis)
            if event.p_value is None:
                raise CausalMemoryError(
                    "confirmatory support requires the recomputed p_value assertion"
                )
            if verification is None or verification["verified_p_value"] > adjusted_alpha:
                raise CausalMemoryError(
                    "confirmatory support must pass the frozen Bonferroni family and project-wide thresholds"
                )
        added = self._append_immutable(self.events, event.event_id, event)
        if added:
            self.event_order.append(event.event_id)
            self.registration_log.append({"kind": "event", "id": event.event_id})
        return added

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
            decayed_weight = event.evidence_weight * (
                0.5 ** (age_days / self.half_life_days)
            )
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

    def latest_metric(
        self,
        metric_name: str,
        *,
        as_of: str,
        subject_id: str | None = None,
    ) -> PointInTimeObservation | None:
        cutoff = _parse_time(as_of)
        candidates = [
            observation
            for observation in self.observations.values()
            if observation.metric_name == metric_name
            and _parse_time(observation.available_at) <= cutoff
            and _parse_time(observation.retrieved_at) <= cutoff
            and (subject_id is None or observation.subject_id == subject_id)
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
        subject_id: str,
        as_of: str,
    ) -> RelativeImpact:
        if ratio_name not in RELATIVE_IMPACT_RATIOS:
            raise CausalMemoryError(
                "relative impact ratio must be flow_float or flow_liquidity"
            )
        normalised_as_of = _normalise_time(as_of)
        numerator = self.latest_metric(
            numerator_metric,
            as_of=normalised_as_of,
            subject_id=subject_id,
        )
        denominator = self.latest_metric(
            denominator_metric,
            as_of=normalised_as_of,
            subject_id=subject_id,
        )
        if numerator is None or denominator is None:
            unscoped_numerator = self.latest_metric(
                numerator_metric, as_of=normalised_as_of
            )
            unscoped_denominator = self.latest_metric(
                denominator_metric, as_of=normalised_as_of
            )
            wrong_subject_exists = (
                numerator is None
                and unscoped_numerator is not None
                and unscoped_numerator.subject_id != subject_id
            ) or (
                denominator is None
                and unscoped_denominator is not None
                and unscoped_denominator.subject_id != subject_id
            )
            return RelativeImpact(
                ratio_name=ratio_name,
                numerator_observation_id=(numerator.observation_id if numerator else None),
                denominator_observation_id=(denominator.observation_id if denominator else None),
                value=None,
                reason=(
                    "subject_mismatch"
                    if wrong_subject_exists
                    else "point_in_time_input_unavailable"
                ),
                as_of=normalised_as_of,
            )
        if numerator.subject_id != subject_id or denominator.subject_id != subject_id:
            return RelativeImpact(
                ratio_name=ratio_name,
                numerator_observation_id=numerator.observation_id,
                denominator_observation_id=denominator.observation_id,
                value=None,
                reason="subject_mismatch",
                as_of=normalised_as_of,
            )
        if (
            numerator.currency != denominator.currency
            or numerator.unit != denominator.unit
        ):
            return RelativeImpact(
                ratio_name=ratio_name,
                numerator_observation_id=numerator.observation_id,
                denominator_observation_id=denominator.observation_id,
                value=None,
                reason="currency_or_unit_mismatch",
                as_of=normalised_as_of,
            )
        if numerator.measurement_window_hours != denominator.measurement_window_hours:
            return RelativeImpact(
                ratio_name=ratio_name,
                numerator_observation_id=numerator.observation_id,
                denominator_observation_id=denominator.observation_id,
                value=None,
                reason="measurement_window_mismatch",
                as_of=normalised_as_of,
            )
        if numerator.venue != denominator.venue:
            return RelativeImpact(
                ratio_name=ratio_name,
                numerator_observation_id=numerator.observation_id,
                denominator_observation_id=denominator.observation_id,
                value=None,
                reason="venue_mismatch",
                as_of=normalised_as_of,
            )
        cutoff = _parse_time(normalised_as_of)
        if any(
            (cutoff - _parse_time(observation.observed_at)).total_seconds()
            > observation.max_age_hours * 3600
            for observation in (numerator, denominator)
        ):
            return RelativeImpact(
                ratio_name=ratio_name,
                numerator_observation_id=numerator.observation_id,
                denominator_observation_id=denominator.observation_id,
                value=None,
                reason="stale_input",
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
        if self._is_rejected(hypothesis):
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
        evidence_events: list[dict[str, object]] = []
        for event in sorted(relevant, key=lambda item: (item.evaluated_at, item.event_id)):
            outcome_mean = sum(
                self.observations[source_id].value
                for source_id in event.outcome_observation_ids
            ) / len(event.outcome_observation_ids)
            control_mean = sum(
                self.observations[source_id].value
                for source_id in event.control_observation_ids
            ) / len(event.control_observation_ids)
            if event.evaluation_implementation == LEGACY_UNVERIFIED_IMPLEMENTATION:
                verification = {
                    "verified_fingerprint": "mi-unverified-legacy-evidence-v0:"
                    + _sha256(
                        {
                            "raw_event_fingerprint": event.fingerprint,
                            "outcome_provenance": [
                                self.observations[source_id].provenance_fingerprint
                                for source_id in event.outcome_observation_ids
                            ],
                            "control_provenance": [
                                self.observations[source_id].provenance_fingerprint
                                for source_id in event.control_observation_ids
                            ],
                        }
                    ),
                    "verified_p_value": None,
                }
            else:
                verification = self._verified_evaluation(event, hypothesis)
            verified_p_value = verification["verified_p_value"]
            evidence_events.append(
                {
                    "event_id": event.event_id,
                    "event_fingerprint": verification["verified_fingerprint"],
                    "raw_event_fingerprint": event.fingerprint,
                    "kind": event.kind,
                    "evaluated_at": event.evaluated_at,
                    "confirmatory": event.confirmatory,
                    "evaluation_method": event.evaluation_method,
                    "evaluation_implementation": event.evaluation_implementation,
                    "independent_unit_contract": verification.get(
                        "independent_unit_contract"
                    ),
                    "independent_units": verification.get("independent_units", []),
                    "sample_size": event.sample_size,
                    "matched_controls": list(event.matched_controls),
                    "outcome_observation_ids": list(event.outcome_observation_ids),
                    "control_observation_ids": list(event.control_observation_ids),
                    "outcome_provenance_fingerprints": [
                        self.observations[source_id].provenance_fingerprint
                        for source_id in event.outcome_observation_ids
                    ],
                    "control_provenance_fingerprints": [
                        self.observations[source_id].provenance_fingerprint
                        for source_id in event.control_observation_ids
                    ],
                    "raw_p_value": event.p_value,
                    "verified_p_value": verified_p_value,
                    "adjusted_p_value": (
                        min(
                            1.0,
                            float(verified_p_value)
                            * max(
                                hypothesis.family_size,
                                (
                                    self.hypothesis_order.index(hypothesis.hypothesis_id)
                                    + 1
                                )
                                * (
                                    self.hypothesis_order.index(hypothesis.hypothesis_id)
                                    + 2
                                ),
                            ),
                        )
                        if verified_p_value is not None
                        else None
                    ),
                    "bounded_evidence_weight": event.evidence_weight,
                    "observed_effect": outcome_mean - control_mean,
                }
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "lane": lane,
            "hypothesis_id": hypothesis.hypothesis_id,
            "hypothesis_fingerprint": self.effective_fingerprint(hypothesis),
            "design_fingerprint": hypothesis.fingerprint,
            "as_of": _normalise_time(as_of),
            "research_confidence": snapshot.score,
            "source_observation_ids": list(hypothesis.source_observation_ids),
            "formation_provenance_fingerprints": [
                self.observations[source_id].provenance_fingerprint
                for source_id in hypothesis.source_observation_ids
            ],
            "mechanism_chain": list(hypothesis.mechanism_chain),
            "frozen_test_contract": {
                "falsifier": hypothesis.falsifier,
                "matched_controls": list(hypothesis.matched_controls),
                "family_id": hypothesis.family_id,
                "family_size": hypothesis.family_size,
                "alpha": hypothesis.alpha,
                "project_testing_protocol": PROJECT_TESTING_PROTOCOL,
                "project_test_slot": self.hypothesis_order.index(hypothesis_id) + 1,
                "project_alpha": PROJECT_ALPHA,
                "confirmatory_p_threshold": self._project_threshold(hypothesis),
                "evaluation_units": [list(unit) for unit in hypothesis.evaluation_units],
                "evaluation_pairs": [list(pair) for pair in hypothesis.evaluation_pairs],
                "evaluation_selectors": [
                    [list(selector) for selector in pair]
                    for pair in hypothesis.evaluation_selectors
                ],
                "evaluation_method": hypothesis.evaluation_method,
                "direction": hypothesis.direction,
                "horizon_hours": hypothesis.horizon_hours,
            },
            "evidence_events": evidence_events,
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
            "project_testing_protocol": PROJECT_TESTING_PROTOCOL,
            "hypothesis_order": list(self.hypothesis_order),
            "event_order": list(self.event_order),
            "registration_log": list(self.registration_log),
            "legacy_underdeclared_hypotheses": sorted(self.legacy_underdeclared_hypotheses),
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
    def from_document(cls, document: object) -> "CausalRepricingMemory":
        """Validate and restore one digest-bound durable memory document."""
        if not isinstance(document, dict):
            raise CausalMemoryError("causal memory document must be an object")
        document = dict(document)
        if document.get("schema_version") != SCHEMA_VERSION:
            raise CausalMemoryError("unsupported causal-memory schema version")
        supplied_digest = document.pop("content_digest", None)
        if not supplied_digest or supplied_digest != _sha256(document):
            raise CausalMemoryError("causal-memory content digest mismatch")

        protocol = document.get("project_testing_protocol")
        if protocol not in (None, PROJECT_TESTING_PROTOCOL):
            raise CausalMemoryError("unsupported project-wide testing protocol")
        if protocol is None and any(
            key in document
            for key in ("hypothesis_order", "event_order", "registration_log")
        ):
            raise CausalMemoryError("incomplete project-wide testing ledger")
        # Historical hypotheses must remain loadable after later rejection. Rejection
        # blocks fresh admission and lane emission; it must not make durable memory
        # unrecoverable after a restart.
        persisted_rejected = tuple(str(value) for value in document.get("rejected_fingerprints", []))
        try:
            observation_rows = document.get("observations", [])
            hypothesis_rows = document.get("hypotheses", [])
            event_rows = document.get("events", [])
            memory = cls(half_life_days=float(document["half_life_days"]))
            family_counts: dict[str, int] = {}
            for raw in hypothesis_rows:
                family = raw["family_id"]
                family_counts[family] = family_counts.get(family, 0) + 1
            underdeclared = {
                raw["hypothesis_id"] for raw in hypothesis_rows
                if raw["family_size"] < family_counts[raw["family_id"]]
            }
            marker = document.get("legacy_underdeclared_hypotheses", [])
            if protocol is None:
                if marker:
                    raise CausalMemoryError("legacy document cannot assert migration markers")
            elif (
                not isinstance(marker, list)
                or marker != sorted(underdeclared)
                or any(
                    raw.get("evaluation_units") or raw.get("evaluation_pairs")
                    or raw.get("evaluation_selectors")
                    for raw in hypothesis_rows
                    if raw["hypothesis_id"] in underdeclared
                )
            ):
                raise CausalMemoryError("invalid legacy family migration marker")
            memory.legacy_underdeclared_hypotheses = underdeclared
            if protocol is not None:
                order = document["registration_log"]
                hypothesis_order = document["hypothesis_order"]
                event_order = document["event_order"]
                rows = {
                    "observation": (observation_rows, "observation_id"),
                    "hypothesis": (hypothesis_rows, "hypothesis_id"),
                    "event": (event_rows, "event_id"),
                }
                if (
                    not isinstance(order, list)
                    or not isinstance(hypothesis_order, list)
                    or not isinstance(event_order, list)
                    or any(not isinstance(value, list) for value, _ in rows.values())
                    or any(
                        not isinstance(raw, dict) or type(raw.get(key)) is not str
                        for value, key in rows.values()
                        for raw in value
                    )
                    or any(
                        not isinstance(item, dict)
                        or set(item) != {"kind", "id"}
                        or item["kind"] not in rows
                        or type(item["id"]) is not str
                        for item in order
                    )
                ):
                    raise CausalMemoryError("invalid project-wide testing ledger")
                expected = [
                    (kind, raw[key])
                    for kind, (value, key) in rows.items()
                    for raw in value
                ]
                actual = [(item["kind"], item["id"]) for item in order]
                if (
                    len(actual) != len(expected)
                    or len(set(actual)) != len(actual)
                    or set(actual) != set(expected)
                    or [ident for kind, ident in actual if kind == "hypothesis"]
                    != hypothesis_order
                    or [ident for kind, ident in actual if kind == "event"]
                    != event_order
                ):
                    raise CausalMemoryError("invalid project-wide testing ledger")
                by_kind = {
                    kind: {raw[key]: raw for raw in value}
                    for kind, (value, key) in rows.items()
                }
            else:
                if any(raw.get("evaluation_units") for raw in hypothesis_rows):
                    raise CausalMemoryError("legacy document cannot carry a new evaluation plan")
                actual = (
                    [("observation", raw["observation_id"]) for raw in observation_rows]
                    + [("hypothesis", raw["hypothesis_id"]) for raw in hypothesis_rows]
                    + [("event", raw["event_id"]) for raw in event_rows]
                )
                by_kind = {
                    "observation": {raw["observation_id"]: raw for raw in observation_rows},
                    "hypothesis": {raw["hypothesis_id"]: raw for raw in hypothesis_rows},
                    "event": {raw["event_id"]: raw for raw in event_rows},
                }
            for kind, ident in actual:
                raw = by_kind[kind][ident]
                if kind == "observation":
                    memory.register_observation(PointInTimeObservation(**raw))
                    continue
                if kind == "hypothesis":
                    raw = dict(raw)
                    for field in (
                        "mechanism_chain", "matched_controls", "lanes",
                        "source_observation_ids",
                    ):
                        raw[field] = tuple(raw[field])
                    if "evaluation_units" in raw:
                        raw["evaluation_units"] = tuple(
                            tuple(unit) for unit in raw["evaluation_units"]
                        )
                    if "evaluation_pairs" in raw:
                        raw["evaluation_pairs"] = tuple(
                            tuple(pair) for pair in raw["evaluation_pairs"]
                        )
                    if "evaluation_selectors" in raw:
                        raw["evaluation_selectors"] = tuple(
                            tuple(tuple(selector) for selector in pair)
                            for pair in raw["evaluation_selectors"]
                        )
                    memory.register_hypothesis(
                        FrozenHypothesis(**raw),
                        _restore_legacy_undercount=raw["hypothesis_id"] in underdeclared,
                    )
                    continue
                raw = dict(raw)
                raw["matched_controls"] = tuple(raw["matched_controls"])
                raw["outcome_observation_ids"] = tuple(
                    raw["outcome_observation_ids"]
                )
                raw["control_observation_ids"] = tuple(
                    raw["control_observation_ids"]
                )
                missing_evaluation_implementation = (
                    "evaluation_implementation" not in raw
                )
                if missing_evaluation_implementation:
                    # Schema-v2 durable rows predate trusted statistical
                    # verification. Preserve them for audit/contradiction history,
                    # but never let them manufacture confirmatory confidence.
                    raw["evaluation_implementation"] = (
                        LEGACY_UNVERIFIED_IMPLEMENTATION
                    )
                    raw["confirmatory"] = False
                    raw["p_value"] = None
                if protocol is None:
                    # Existing schema-v2 rows had only caller-chosen family labels.
                    # Preserve their audit trail but remove unsupported
                    # confirmatory authority during durable migration.
                    raw["confirmatory"] = False
                elif raw.get("kind") == "support" and not memory.hypotheses[
                    raw["hypothesis_id"]
                ].evaluation_selectors:
                    raw["confirmatory"] = False
                legacy_unverified = (
                    raw.get("evaluation_implementation")
                    == LEGACY_UNVERIFIED_IMPLEMENTATION
                )
                memory.record_evidence(
                    EvidenceEvent(**raw),
                    _allow_legacy_unverified=legacy_unverified,
                )
            for raw in document.get("claims", []):
                raw = dict(raw)
                raw["source_observation_ids"] = tuple(raw["source_observation_ids"])
                memory.register_claim(EpistemicClaim(**raw))
            memory.rejected_fingerprints.update(persisted_rejected)
        except (KeyError, TypeError, ValueError, CausalMemoryError) as exc:
            raise CausalMemoryError(
                "causal memory failed scientific-contract validation"
            ) from exc
        return memory

    @classmethod
    def load(cls, path: str | Path) -> "CausalRepricingMemory":
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CausalMemoryError("causal memory is unreadable or corrupt") from exc
        return cls.from_document(document)
