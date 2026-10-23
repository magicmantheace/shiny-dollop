"""Deterministic canonical social relationship state for Underreach Slice 30C.1.

Phase 30B established the individual brain proposal/execution loop. 30C.1 adds
only simulation-owned directed relationship state. It does not derive social
meaning from gameplay events, execute social intents, form parties, or generate
dialogue. Those responsibilities belong to later slices.

Relationship data is stored sparsely inside ``Descent.modifiers`` so the
accepted Crawl/Descent model remains the single authoritative state tree and
existing save/checkpoint serialization carries social state automatically.
"""
from __future__ import annotations

from hashlib import sha256
import math
import re
from typing import Any

from pydantic import BaseModel, ConfigDict

from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .runtime_checkpoint import payload_digest
from .underreach_brain_driven_descent import validate_brain_driven_descent
from .underreach_domain import Descent


PROTOCOL = "underreach.social-state.v1"
IMPLEMENTATION_VERSION = "30c1.1"
METADATA_KEY = "_social_state"
RELATIONSHIP_CREATED_EVENT = "SOCIAL_RELATIONSHIP_CREATED"
RELATIONSHIP_CHANGED_EVENT = "SOCIAL_RELATIONSHIP_CHANGED"
SOCIAL_STATE_INITIALIZED_EVENT = "SOCIAL_STATE_INITIALIZED"
VALUE_PRECISION = 6
MAX_ABSOLUTE_DELTA = 2.0

RELATIONSHIP_DIMENSIONS = (
    "trust",
    "respect",
    "affection",
    "fear",
    "resentment",
    "gratitude",
    "rivalry",
    "familiarity",
)

DIMENSION_BOUNDS: dict[str, tuple[float, float]] = {
    "trust": (-1.0, 1.0),
    "respect": (-1.0, 1.0),
    "affection": (-1.0, 1.0),
    "fear": (-1.0, 1.0),
    "resentment": (-1.0, 1.0),
    "gratitude": (-1.0, 1.0),
    "rivalry": (-1.0, 1.0),
    "familiarity": (0.0, 1.0),
}

_REASON_CODE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,79}$")


class SocialStateError(ValueError):
    """Raised when an operation violates the 30C.1 social-state contract."""


class DirectedRelationshipState(BaseModel):
    """Immutable read model for one directed social edge."""

    model_config = ConfigDict(frozen=True)

    source_descender_id: str
    target_descender_id: str
    trust: float = 0.0
    respect: float = 0.0
    affection: float = 0.0
    fear: float = 0.0
    resentment: float = 0.0
    gratitude: float = 0.0
    rivalry: float = 0.0
    familiarity: float = 0.0


class RelationshipMutationResult(BaseModel):
    """Immutable result for one requested deterministic relationship update."""

    model_config = ConfigDict(frozen=True)

    source_descender_id: str
    target_descender_id: str
    dimension: str
    previous_value: float
    requested_delta: float
    resulting_value: float
    edge_created: bool
    changed: bool
    reason_code: str
    source_event_id: str | None = None
    ledger_event_id: str | None = None


def _neutral_values() -> dict[str, float]:
    return {dimension: 0.0 for dimension in RELATIONSHIP_DIMENSIONS}


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise SocialStateError("Descent is missing 30C.1 social-state metadata")
    return value


def _validate_pair(descent: Descent, source_descender_id: str, target_descender_id: str) -> None:
    if not source_descender_id or not target_descender_id:
        raise SocialStateError("relationship endpoints must be non-empty Descender IDs")
    if source_descender_id == target_descender_id:
        raise SocialStateError("self-relationships are not canonical social state")
    if source_descender_id not in descent.participants:
        raise SocialStateError(f"source Descender {source_descender_id!r} is not participating")
    if target_descender_id not in descent.participants:
        raise SocialStateError(f"target Descender {target_descender_id!r} is not participating")


def _validate_reason(reason_code: str) -> str:
    if not isinstance(reason_code, str) or not _REASON_CODE.fullmatch(reason_code):
        raise SocialStateError("reason_code must be a structured lowercase identifier")
    return reason_code


def _validate_source_event(descent: Descent, source_event_id: str | None) -> None:
    if source_event_id is not None and source_event_id not in descent.history_event_ids:
        raise SocialStateError("source_event_id must reference existing canonical Ledger history")


def _validate_dimension(dimension: str) -> tuple[float, float]:
    if dimension not in DIMENSION_BOUNDS:
        raise SocialStateError(f"unknown canonical relationship dimension {dimension!r}")
    return DIMENSION_BOUNDS[dimension]


def _normalize_number(value: object, *, label: str) -> float:
    if isinstance(value, bool):
        raise SocialStateError(f"{label} must be a finite numeric value")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SocialStateError(f"{label} must be a finite numeric value") from exc
    if not math.isfinite(number):
        raise SocialStateError(f"{label} must be finite")
    return round(number, VALUE_PRECISION)


def _clamp_dimension(dimension: str, value: float) -> float:
    lower, upper = _validate_dimension(dimension)
    return round(max(lower, min(upper, value)), VALUE_PRECISION)


def _edge_values(metadata: dict[str, Any], source_descender_id: str, target_descender_id: str) -> dict[str, float] | None:
    edges = metadata.get("edges")
    if not isinstance(edges, dict):
        raise SocialStateError("social-state edge storage is invalid")
    by_target = edges.get(source_descender_id)
    if by_target is None:
        return None
    if not isinstance(by_target, dict):
        raise SocialStateError("social-state source edge bucket is invalid")
    edge = by_target.get(target_descender_id)
    if edge is None:
        return None
    if not isinstance(edge, dict):
        raise SocialStateError("social-state relationship edge is invalid")
    return edge


def _relationship_model(
    source_descender_id: str,
    target_descender_id: str,
    values: dict[str, Any] | None,
) -> DirectedRelationshipState:
    payload = _neutral_values() if values is None else {
        dimension: float(values[dimension]) for dimension in RELATIONSHIP_DIMENSIONS
    }
    return DirectedRelationshipState(
        source_descender_id=source_descender_id,
        target_descender_id=target_descender_id,
        **payload,
    )


def _relationship_count(edges: dict[str, Any]) -> int:
    return sum(len(by_target) for by_target in edges.values() if isinstance(by_target, dict))


def validate_social_state(descent: Descent) -> bool:
    """Validate 30C.1 state while preserving the complete accepted 30B.3 contract."""
    validate_brain_driven_descent(descent)
    metadata = _metadata(descent)

    if metadata.get("protocol") != PROTOCOL:
        raise SocialStateError("social-state protocol mismatch")
    if metadata.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise SocialStateError("social-state implementation version mismatch")
    if metadata.get("authoritative") is not True:
        raise SocialStateError("social state must remain canonical simulation state")
    if metadata.get("canonical_owner") != "deterministic_simulation":
        raise SocialStateError("social state canonical owner changed")
    if metadata.get("social_reasoning_can_mutate") is not False:
        raise SocialStateError("social reasoning cannot directly mutate canonical state")
    if metadata.get("presentation_feedback_allowed") is not False:
        raise SocialStateError("presentation feedback cannot mutate canonical social state")
    if metadata.get("sparse_storage") is not True:
        raise SocialStateError("30C.1 relationship storage must remain sparse")
    if metadata.get("dimensions") != list(RELATIONSHIP_DIMENSIONS):
        raise SocialStateError("canonical social dimensions changed")

    supplied_bounds = metadata.get("dimension_bounds")
    expected_bounds = {
        dimension: [lower, upper]
        for dimension, (lower, upper) in DIMENSION_BOUNDS.items()
    }
    if supplied_bounds != expected_bounds:
        raise SocialStateError("canonical social dimension bounds changed")

    initialized_event_id = metadata.get("initialized_event_id")
    if not isinstance(initialized_event_id, str) or initialized_event_id not in descent.history_event_ids:
        raise SocialStateError("social-state initialization is not bound to the canonical Ledger")

    mutation_event_ids = metadata.get("mutation_event_ids")
    if not isinstance(mutation_event_ids, list):
        raise SocialStateError("social-state mutation Ledger trace is invalid")
    if len(mutation_event_ids) != len(set(mutation_event_ids)):
        raise SocialStateError("social-state mutation Ledger IDs must be unique")
    if any(event_id not in descent.history_event_ids for event_id in mutation_event_ids):
        raise SocialStateError("social-state mutation event is missing from canonical Ledger history")
    if int(metadata.get("mutation_count", -1)) != len(mutation_event_ids):
        raise SocialStateError("social-state mutation count diverged from Ledger trace")

    edges = metadata.get("edges")
    if not isinstance(edges, dict):
        raise SocialStateError("social-state edge storage is invalid")
    counted = 0
    for source_descender_id, by_target in edges.items():
        if source_descender_id not in descent.participants:
            raise SocialStateError("social-state edge source is not a participating Descender")
        if not isinstance(by_target, dict) or not by_target:
            raise SocialStateError("social-state source bucket must contain at least one sparse edge")
        for target_descender_id, values in by_target.items():
            _validate_pair(descent, source_descender_id, target_descender_id)
            if not isinstance(values, dict):
                raise SocialStateError("social-state relationship payload is invalid")
            if set(values) != set(RELATIONSHIP_DIMENSIONS):
                raise SocialStateError("relationship payload does not contain exactly the canonical dimensions")
            for dimension in RELATIONSHIP_DIMENSIONS:
                number = _normalize_number(values[dimension], label=dimension)
                lower, upper = DIMENSION_BOUNDS[dimension]
                if number < lower or number > upper:
                    raise SocialStateError(f"relationship dimension {dimension!r} escaped canonical bounds")
                if number != values[dimension]:
                    raise SocialStateError("relationship values must use canonical numeric precision")
            counted += 1

    if int(metadata.get("relationship_count", -1)) != counted:
        raise SocialStateError("social-state relationship count diverged from sparse edge storage")
    return True


def get_relationship(
    descent: Descent,
    source_descender_id: str,
    target_descender_id: str,
) -> DirectedRelationshipState:
    """Read one directed edge without allocating or mutating canonical state."""
    validate_social_state(descent)
    _validate_pair(descent, source_descender_id, target_descender_id)
    values = _edge_values(_metadata(descent), source_descender_id, target_descender_id)
    return _relationship_model(source_descender_id, target_descender_id, values)


def build_social_state_snapshot(descent: Descent) -> dict[str, Any]:
    """Build a deterministic ordered snapshot suitable for proofs and later observations."""
    validate_social_state(descent)
    metadata = _metadata(descent)
    relationships: list[dict[str, Any]] = []
    edges = metadata["edges"]
    for source_descender_id in sorted(edges):
        for target_descender_id in sorted(edges[source_descender_id]):
            values = edges[source_descender_id][target_descender_id]
            relationships.append(
                {
                    "source_descender_id": source_descender_id,
                    "target_descender_id": target_descender_id,
                    **{dimension: values[dimension] for dimension in RELATIONSHIP_DIMENSIONS},
                }
            )
    body = {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "social_reasoning_can_mutate": False,
        "presentation_feedback_allowed": False,
        "descent_id": descent.id,
        "seed": descent.seed,
        "current_tick": descent.current_tick,
        "relationship_count": metadata["relationship_count"],
        "relationships": relationships,
        "relationship_state_digest": payload_digest(relationships),
        "mutation_count": metadata["mutation_count"],
        "mutation_event_ids": list(metadata["mutation_event_ids"]),
        "mutation_event_ids_digest": payload_digest(list(metadata["mutation_event_ids"])),
        "initialized_event_id": metadata["initialized_event_id"],
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
    }
    return {**body, "digest": payload_digest(body)}


class SocialStateService:
    """Simulation-owned canonical relationship-state service for 30C.1."""

    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence
        self.lifecycle = CrawlLifecycleService(persistence)

    def initialize(self, descent: Descent) -> Descent:
        """Install the sparse social-state root on an accepted 30B.3 Descent."""
        validate_brain_driven_descent(descent)
        if METADATA_KEY in descent.modifiers:
            validate_social_state(descent)
            return descent

        metadata = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "social_reasoning_can_mutate": False,
            "presentation_feedback_allowed": False,
            "sparse_storage": True,
            "dimensions": list(RELATIONSHIP_DIMENSIONS),
            "dimension_bounds": {
                dimension: [lower, upper]
                for dimension, (lower, upper) in DIMENSION_BOUNDS.items()
            },
            "edges": {},
            "relationship_count": 0,
            "mutation_count": 0,
            "mutation_event_ids": [],
            "initialized_event_id": None,
        }
        descent.modifiers[METADATA_KEY] = metadata
        event = self.lifecycle.record_event(
            descent,
            SOCIAL_STATE_INITIALIZED_EVENT,
            "Deterministic social relationship state initialized.",
            actor_ids=sorted(descent.participants),
            data={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "dimensions": list(RELATIONSHIP_DIMENSIONS),
                "sparse_storage": True,
                "state_changes": {"social_state_initialized": True},
            },
        )
        metadata["initialized_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_social_state(descent)
        return descent

    def get(
        self,
        descent: Descent,
        source_descender_id: str,
        target_descender_id: str,
    ) -> DirectedRelationshipState:
        return get_relationship(descent, source_descender_id, target_descender_id)

    def ensure_relationship(
        self,
        descent: Descent,
        source_descender_id: str,
        target_descender_id: str,
        *,
        reason_code: str = "social_state.edge_initialized",
        source_event_id: str | None = None,
    ) -> DirectedRelationshipState:
        """Create one neutral sparse edge and Ledger-bind that canonical allocation."""
        validate_social_state(descent)
        _validate_pair(descent, source_descender_id, target_descender_id)
        reason = _validate_reason(reason_code)
        _validate_source_event(descent, source_event_id)
        metadata = _metadata(descent)
        existing = _edge_values(metadata, source_descender_id, target_descender_id)
        if existing is not None:
            return _relationship_model(source_descender_id, target_descender_id, existing)

        values = _neutral_values()
        edges: dict[str, Any] = metadata["edges"]
        by_target = edges.setdefault(source_descender_id, {})
        by_target[target_descender_id] = values
        metadata["relationship_count"] = int(metadata["relationship_count"]) + 1

        event = self.lifecycle.record_event(
            descent,
            RELATIONSHIP_CREATED_EVENT,
            "Canonical directed social relationship edge created.",
            actor_ids=[source_descender_id, target_descender_id],
            location_id=descent.participants[source_descender_id].current_location_id,
            data={
                "protocol": PROTOCOL,
                "source_descender_id": source_descender_id,
                "target_descender_id": target_descender_id,
                "reason_code": reason,
                "source_event_id": source_event_id,
                "relationship": dict(values),
                "relationship_impact": 0.0,
                "state_changes": {
                    "social_relationship_created": True,
                    "source_descender_id": source_descender_id,
                    "target_descender_id": target_descender_id,
                },
            },
        )
        metadata["mutation_event_ids"].append(event.id)
        metadata["mutation_count"] = len(metadata["mutation_event_ids"])
        self.lifecycle.save(descent)
        validate_social_state(descent)
        return _relationship_model(source_descender_id, target_descender_id, values)

    def adjust_dimension(
        self,
        descent: Descent,
        source_descender_id: str,
        target_descender_id: str,
        dimension: str,
        delta: float,
        *,
        reason_code: str,
        source_event_id: str | None = None,
    ) -> RelationshipMutationResult:
        """Apply one bounded deterministic relationship delta.

        An absent edge is created only when the requested update produces a
        non-neutral state. Requests that clamp to the existing value are
        side-effect free and do not append Ledger history.
        """
        validate_social_state(descent)
        _validate_pair(descent, source_descender_id, target_descender_id)
        _validate_dimension(dimension)
        reason = _validate_reason(reason_code)
        _validate_source_event(descent, source_event_id)
        requested_delta = _normalize_number(delta, label="relationship delta")
        if requested_delta < -MAX_ABSOLUTE_DELTA or requested_delta > MAX_ABSOLUTE_DELTA:
            raise SocialStateError(
                f"relationship delta must remain within [-{MAX_ABSOLUTE_DELTA}, {MAX_ABSOLUTE_DELTA}]"
            )

        metadata = _metadata(descent)
        existing = _edge_values(metadata, source_descender_id, target_descender_id)
        edge_created = existing is None
        previous_values = _neutral_values() if existing is None else dict(existing)
        previous_value = float(previous_values[dimension])
        resulting_value = _clamp_dimension(dimension, previous_value + requested_delta)
        changed = resulting_value != previous_value

        if not changed:
            return RelationshipMutationResult(
                source_descender_id=source_descender_id,
                target_descender_id=target_descender_id,
                dimension=dimension,
                previous_value=previous_value,
                requested_delta=requested_delta,
                resulting_value=resulting_value,
                edge_created=False,
                changed=False,
                reason_code=reason,
                source_event_id=source_event_id,
                ledger_event_id=None,
            )

        edges: dict[str, Any] = metadata["edges"]
        if existing is None:
            by_target = edges.setdefault(source_descender_id, {})
            by_target[target_descender_id] = previous_values
            existing = by_target[target_descender_id]
            metadata["relationship_count"] = int(metadata["relationship_count"]) + 1
        existing[dimension] = resulting_value

        event = self.lifecycle.record_event(
            descent,
            RELATIONSHIP_CHANGED_EVENT,
            "Canonical directed social relationship dimension changed.",
            actor_ids=[source_descender_id, target_descender_id],
            location_id=descent.participants[source_descender_id].current_location_id,
            data={
                "protocol": PROTOCOL,
                "source_descender_id": source_descender_id,
                "target_descender_id": target_descender_id,
                "dimension": dimension,
                "previous_value": previous_value,
                "requested_delta": requested_delta,
                "resulting_value": resulting_value,
                "edge_created": edge_created,
                "reason_code": reason,
                "source_event_id": source_event_id,
                "relationship_impact": round(resulting_value - previous_value, VALUE_PRECISION),
                "state_changes": {
                    "social_relationship": {
                        "source_descender_id": source_descender_id,
                        "target_descender_id": target_descender_id,
                        "dimension": dimension,
                        "value": resulting_value,
                    }
                },
            },
        )
        metadata["mutation_event_ids"].append(event.id)
        metadata["mutation_count"] = len(metadata["mutation_event_ids"])
        self.lifecycle.save(descent)
        validate_social_state(descent)

        return RelationshipMutationResult(
            source_descender_id=source_descender_id,
            target_descender_id=target_descender_id,
            dimension=dimension,
            previous_value=previous_value,
            requested_delta=requested_delta,
            resulting_value=resulting_value,
            edge_created=edge_created,
            changed=True,
            reason_code=reason,
            source_event_id=source_event_id,
            ledger_event_id=event.id,
        )


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "METADATA_KEY",
    "RELATIONSHIP_DIMENSIONS",
    "DIMENSION_BOUNDS",
    "SocialStateError",
    "DirectedRelationshipState",
    "RelationshipMutationResult",
    "SocialStateService",
    "validate_social_state",
    "get_relationship",
    "build_social_state_snapshot",
]
