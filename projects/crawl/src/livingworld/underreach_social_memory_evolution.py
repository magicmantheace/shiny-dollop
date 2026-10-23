"""Event-linked deterministic social memory for Underreach Slice 30C.2.

30C.1 established simulation-owned directed relationship state. 30C.2 makes
that state evolve only from qualifying canonical Ledger events and stores
structured social-memory threads that retain the real source event IDs.

This module deliberately does not execute social intents, form parties, or
generate prose/dialogue. Memory confidence and importance may decay with
canonical time, but relationship dimensions do not silently decay: relationship
truth changes only because a canonical event supplied a structured social fact.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict

from .crawl_domain import CrawlEvent
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .runtime_checkpoint import payload_digest
from .underreach_domain import Descent
from .underreach_social_state import (
    METADATA_KEY as SOCIAL_STATE_METADATA_KEY,
    RELATIONSHIP_DIMENSIONS,
    SocialStateService,
    build_social_state_snapshot,
    validate_social_state,
)


PROTOCOL = "underreach.social-memory-evolution.v1"
IMPLEMENTATION_VERSION = "30c2.1"
METADATA_KEY = "_social_memory_evolution"
SOCIAL_MEMORY_INITIALIZED_EVENT = "SOCIAL_MEMORY_EVOLUTION_INITIALIZED"
SOCIAL_MEMORY_RECORDED_EVENT = "SOCIAL_MEMORY_RECORDED"
SOCIAL_MEMORY_REINFORCED_EVENT = "SOCIAL_MEMORY_REINFORCED"
SOCIAL_MEMORY_DECAY_EVENT = "SOCIAL_MEMORY_DECAY_APPLIED"
VALUE_PRECISION = 6
REINFORCEMENT_IMPORTANCE_BOOST = 0.04
REINFORCEMENT_CONFIDENCE_BOOST = 0.06


class SocialMemoryEvolutionError(ValueError):
    """Raised when an operation violates the 30C.2 memory/evolution contract."""


@dataclass(frozen=True)
class SocialFactRule:
    relationship_deltas: dict[str, float]
    importance: float
    confidence: float
    decay_rate: float


SOCIAL_FACT_RULES: dict[str, SocialFactRule] = {
    "rescued": SocialFactRule(
        {"trust": 0.18, "respect": 0.12, "affection": 0.06, "gratitude": 0.24, "familiarity": 0.08},
        0.90, 1.00, 0.0010,
    ),
    "shared_resource": SocialFactRule(
        {"trust": 0.10, "affection": 0.04, "gratitude": 0.14, "familiarity": 0.06},
        0.62, 0.96, 0.0020,
    ),
    "healed": SocialFactRule(
        {"trust": 0.13, "respect": 0.07, "gratitude": 0.18, "familiarity": 0.05},
        0.70, 0.98, 0.0016,
    ),
    "protected": SocialFactRule(
        {"trust": 0.16, "respect": 0.14, "affection": 0.05, "gratitude": 0.16, "familiarity": 0.06},
        0.78, 0.98, 0.0014,
    ),
    "abandoned": SocialFactRule(
        {"trust": -0.24, "respect": -0.08, "affection": -0.08, "resentment": 0.25, "rivalry": 0.08, "familiarity": 0.06},
        0.84, 0.99, 0.0010,
    ),
    "betrayed": SocialFactRule(
        {"trust": -0.60, "respect": -0.20, "affection": -0.25, "fear": 0.10, "resentment": 0.55, "rivalry": 0.32, "familiarity": 0.10},
        1.00, 1.00, 0.0005,
    ),
    "stole_loot": SocialFactRule(
        {"trust": -0.34, "respect": -0.12, "resentment": 0.34, "rivalry": 0.22, "familiarity": 0.07},
        0.86, 1.00, 0.0009,
    ),
    "fought_beside": SocialFactRule(
        {"trust": 0.07, "respect": 0.10, "familiarity": 0.08},
        0.55, 0.94, 0.0022,
    ),
    "caused_injury": SocialFactRule(
        {"trust": -0.16, "fear": 0.10, "resentment": 0.18, "rivalry": 0.10, "familiarity": 0.05},
        0.78, 0.99, 0.0011,
    ),
    "prevented_injury": SocialFactRule(
        {"trust": 0.12, "respect": 0.12, "gratitude": 0.15, "familiarity": 0.05},
        0.72, 0.98, 0.0015,
    ),
    "accepted_aid": SocialFactRule(
        {"trust": 0.08, "gratitude": 0.10, "familiarity": 0.04},
        0.48, 0.94, 0.0025,
    ),
    "refused_aid": SocialFactRule(
        {"trust": -0.10, "resentment": 0.10, "familiarity": 0.04},
        0.55, 0.95, 0.0021,
    ),
    "kept_promise": SocialFactRule(
        {"trust": 0.16, "respect": 0.10, "gratitude": 0.08, "familiarity": 0.05},
        0.72, 0.99, 0.0014,
    ),
    "violated_promise": SocialFactRule(
        {"trust": -0.30, "respect": -0.16, "resentment": 0.24, "rivalry": 0.10, "familiarity": 0.06},
        0.88, 1.00, 0.0009,
    ),
    "witnessed_bravery": SocialFactRule(
        {"respect": 0.14, "familiarity": 0.03},
        0.58, 0.92, 0.0024,
    ),
    "witnessed_retreat": SocialFactRule(
        {"respect": -0.06, "fear": 0.04, "familiarity": 0.03},
        0.42, 0.88, 0.0030,
    ),
    "witnessed_sacrifice": SocialFactRule(
        {"respect": 0.20, "affection": 0.08, "gratitude": 0.10, "familiarity": 0.04},
        0.90, 0.99, 0.0008,
    ),
    "witnessed_selfishness": SocialFactRule(
        {"trust": -0.12, "respect": -0.10, "resentment": 0.12, "familiarity": 0.04},
        0.65, 0.94, 0.0018,
    ),
}

# Event types with unambiguous actor -> affected-target semantics. Explicit
# ``social_facts`` in event.data takes precedence and is required for events
# whose role semantics are ambiguous.
_DIRECT_EVENT_FACTS: dict[str, str] = {
    "RESCUE": "rescued",
    "SHARED_RESOURCE": "shared_resource",
    "HEALED": "healed",
    "PROTECTED": "protected",
    "ABANDONED": "abandoned",
    "BETRAYAL": "betrayed",
    "LOOT_STOLEN": "stole_loot",
    "INJURY_CAUSED": "caused_injury",
    "INJURY_PREVENTED": "prevented_injury",
    "AID_ACCEPTED": "accepted_aid",
    "AID_REFUSED": "refused_aid",
    "PROMISE_KEPT": "kept_promise",
    "PROMISE_VIOLATED": "violated_promise",
}

_WITNESS_EVENT_FACTS: dict[str, str] = {
    "WITNESSED_BRAVERY": "witnessed_bravery",
    "WITNESSED_RETREAT": "witnessed_retreat",
    "WITNESSED_SACRIFICE": "witnessed_sacrifice",
    "WITNESSED_SELFISHNESS": "witnessed_selfishness",
}


class SocialMemoryState(BaseModel):
    """Immutable read model for one event-linked social-memory thread."""

    model_config = ConfigDict(frozen=True)

    memory_id: str
    observer_descender_id: str
    subject_descender_id: str
    memory_type: str
    source_event_ids: tuple[str, ...]
    importance: float
    confidence: float
    decay_rate: float
    created_tick: int
    last_reinforced_tick: int
    last_decay_tick: int
    reinforcement_count: int


class SocialEventProcessingResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_event_id: str
    qualifying: bool
    processed: bool
    duplicate: bool
    fact_count: int
    memory_ids: tuple[str, ...] = ()
    memory_event_ids: tuple[str, ...] = ()
    relationship_event_ids: tuple[str, ...] = ()


class SocialMemoryDecayResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_tick: int
    affected_memory_count: int
    changed_memory_count: int
    ledger_event_id: str | None = None


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _rounded(value: float) -> float:
    if not math.isfinite(float(value)):
        raise SocialMemoryEvolutionError("social memory numeric value must be finite")
    return round(float(value), VALUE_PRECISION)


def _unit(value: float) -> float:
    return _rounded(max(0.0, min(1.0, float(value))))


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise SocialMemoryEvolutionError("Descent is missing 30C.2 social-memory metadata")
    return value


def _memory_model(record: dict[str, Any]) -> SocialMemoryState:
    return SocialMemoryState(
        memory_id=str(record["memory_id"]),
        observer_descender_id=str(record["observer_descender_id"]),
        subject_descender_id=str(record["subject_descender_id"]),
        memory_type=str(record["memory_type"]),
        source_event_ids=tuple(record["source_event_ids"]),
        importance=float(record["importance"]),
        confidence=float(record["confidence"]),
        decay_rate=float(record["decay_rate"]),
        created_tick=int(record["created_tick"]),
        last_reinforced_tick=int(record["last_reinforced_tick"]),
        last_decay_tick=int(record["last_decay_tick"]),
        reinforcement_count=int(record["reinforcement_count"]),
    )


def _validate_memory_record(descent: Descent, memory_id: str, record: Any) -> None:
    if not isinstance(record, dict):
        raise SocialMemoryEvolutionError("social-memory record is invalid")
    required = {
        "memory_id", "observer_descender_id", "subject_descender_id", "memory_type",
        "source_event_ids", "importance", "confidence", "decay_rate", "created_tick",
        "last_reinforced_tick", "last_decay_tick", "reinforcement_count",
    }
    if set(record) != required:
        raise SocialMemoryEvolutionError("social-memory record shape changed")
    if record["memory_id"] != memory_id:
        raise SocialMemoryEvolutionError("social-memory key does not match memory_id")
    observer = str(record["observer_descender_id"])
    subject = str(record["subject_descender_id"])
    if observer == subject or observer not in descent.participants or subject not in descent.participants:
        raise SocialMemoryEvolutionError("social-memory endpoints are invalid")
    memory_type = str(record["memory_type"])
    rule = SOCIAL_FACT_RULES.get(memory_type)
    if rule is None:
        raise SocialMemoryEvolutionError("social-memory type escaped canonical vocabulary")
    expected_id = _stable_id("social_memory", descent.id, observer, subject, memory_type)
    if memory_id != expected_id:
        raise SocialMemoryEvolutionError("social-memory deterministic identity mismatch")
    source_ids = record["source_event_ids"]
    if not isinstance(source_ids, list) or not source_ids or len(source_ids) != len(set(source_ids)):
        raise SocialMemoryEvolutionError("social-memory source-event history is invalid")
    if any(event_id not in descent.history_event_ids for event_id in source_ids):
        raise SocialMemoryEvolutionError("social memory references missing canonical Ledger history")
    if _rounded(record["importance"]) != record["importance"] or not 0.0 <= float(record["importance"]) <= 1.0:
        raise SocialMemoryEvolutionError("social-memory importance is invalid")
    if _rounded(record["confidence"]) != record["confidence"] or not 0.0 <= float(record["confidence"]) <= 1.0:
        raise SocialMemoryEvolutionError("social-memory confidence is invalid")
    if _rounded(record["decay_rate"]) != record["decay_rate"] or float(record["decay_rate"]) < 0.0:
        raise SocialMemoryEvolutionError("social-memory decay rate is invalid")
    created = int(record["created_tick"])
    reinforced = int(record["last_reinforced_tick"])
    decayed = int(record["last_decay_tick"])
    if created < 0 or reinforced < created or decayed < created:
        raise SocialMemoryEvolutionError("social-memory tick history is invalid")
    if reinforced > descent.current_tick or decayed > descent.current_tick:
        raise SocialMemoryEvolutionError("social-memory tick cannot exceed canonical Descent time")
    if int(record["reinforcement_count"]) != len(source_ids) or int(record["reinforcement_count"]) < 1:
        raise SocialMemoryEvolutionError("social-memory reinforcement count diverged")


def validate_social_memory_evolution(descent: Descent) -> bool:
    """Validate 30C.2 while preserving the full accepted 30C.1 contract."""
    validate_social_state(descent)
    metadata = _metadata(descent)
    if metadata.get("protocol") != PROTOCOL or metadata.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise SocialMemoryEvolutionError("social-memory protocol or version mismatch")
    if metadata.get("authoritative") is not True or metadata.get("canonical_owner") != "deterministic_simulation":
        raise SocialMemoryEvolutionError("social-memory authority boundary changed")
    if metadata.get("extends_slice") != "30C.1" or metadata.get("relationship_protocol") != "underreach.social-state.v1":
        raise SocialMemoryEvolutionError("social-memory source-slice contract changed")
    if metadata.get("social_reasoning_can_mutate") is not False:
        raise SocialMemoryEvolutionError("social reasoning cannot directly mutate memory/relationship truth")
    if metadata.get("narrative_can_create_memory") is not False:
        raise SocialMemoryEvolutionError("generated narrative cannot create canonical social memory")
    if metadata.get("presentation_feedback_allowed") is not False:
        raise SocialMemoryEvolutionError("presentation feedback cannot mutate canonical social memory")
    if metadata.get("relationship_time_decay_enabled") is not False:
        raise SocialMemoryEvolutionError("30C.2 cannot silently decay relationship truth")

    initialized = metadata.get("initialized_event_id")
    if not isinstance(initialized, str) or initialized not in descent.history_event_ids:
        raise SocialMemoryEvolutionError("social-memory initialization is not Ledger bound")
    processed = metadata.get("processed_source_event_ids")
    if not isinstance(processed, list) or len(processed) != len(set(processed)):
        raise SocialMemoryEvolutionError("processed social source-event trace is invalid")
    if any(event_id not in descent.history_event_ids for event_id in processed):
        raise SocialMemoryEvolutionError("processed social source event is missing from Ledger")
    if int(metadata.get("processed_source_event_count", -1)) != len(processed):
        raise SocialMemoryEvolutionError("processed social source-event count diverged")
    last_index = int(metadata.get("last_processed_source_history_index", -1))
    if processed:
        actual_indices = [descent.history_event_ids.index(event_id) for event_id in processed]
        if actual_indices != sorted(actual_indices) or last_index != actual_indices[-1]:
            raise SocialMemoryEvolutionError("processed social events are not in canonical Ledger order")
    elif last_index != -1:
        raise SocialMemoryEvolutionError("empty social source trace has a non-empty cursor")

    memories = metadata.get("memories")
    if not isinstance(memories, dict):
        raise SocialMemoryEvolutionError("social-memory storage is invalid")
    for memory_id, record in memories.items():
        _validate_memory_record(descent, memory_id, record)
    if int(metadata.get("memory_count", -1)) != len(memories):
        raise SocialMemoryEvolutionError("social-memory count diverged from storage")

    memory_event_ids = metadata.get("memory_event_ids")
    decay_event_ids = metadata.get("decay_event_ids")
    if not isinstance(memory_event_ids, list) or not isinstance(decay_event_ids, list):
        raise SocialMemoryEvolutionError("social-memory Ledger traces are invalid")
    if len(memory_event_ids) != len(set(memory_event_ids)) or len(decay_event_ids) != len(set(decay_event_ids)):
        raise SocialMemoryEvolutionError("social-memory Ledger traces contain duplicate IDs")
    if any(event_id not in descent.history_event_ids for event_id in [*memory_event_ids, *decay_event_ids]):
        raise SocialMemoryEvolutionError("social-memory Ledger event is missing from canonical history")
    return True


def _explicit_facts(event: CrawlEvent) -> list[tuple[str, str, str]] | None:
    raw = event.data.get("social_facts")
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise SocialMemoryEvolutionError("event social_facts must be a list")
    values: list[tuple[str, str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise SocialMemoryEvolutionError("event social fact must be structured data")
        observer = item.get("observer_descender_id")
        subject = item.get("subject_descender_id")
        memory_type = item.get("memory_type")
        if not isinstance(observer, str) or not isinstance(subject, str) or not isinstance(memory_type, str):
            raise SocialMemoryEvolutionError("event social fact is missing canonical identifiers")
        values.append((observer, subject, memory_type))
    return values


def _event_facts(event: CrawlEvent) -> list[tuple[str, str, str]]:
    if event.event_type.upper().startswith("SOCIAL_"):
        return []
    explicit = _explicit_facts(event)
    if explicit is not None:
        return sorted(explicit)
    event_type = event.event_type.upper()
    if event_type == "FOUGHT_BESIDE" and len(event.actor_ids) == 2:
        left, right = event.actor_ids
        return sorted([(left, right, "fought_beside"), (right, left, "fought_beside")])
    memory_type = _DIRECT_EVENT_FACTS.get(event_type)
    if memory_type is not None and len(event.actor_ids) >= 2:
        actor, affected = event.actor_ids[0], event.actor_ids[1]
        return [(affected, actor, memory_type)]
    memory_type = _WITNESS_EVENT_FACTS.get(event_type)
    if memory_type is not None and len(event.actor_ids) >= 2:
        observer, subject = event.actor_ids[0], event.actor_ids[1]
        return [(observer, subject, memory_type)]
    return []


def _validate_facts(descent: Descent, facts: list[tuple[str, str, str]]) -> None:
    if len(facts) != len(set(facts)):
        raise SocialMemoryEvolutionError("one source event cannot contain duplicate social facts")
    for observer, subject, memory_type in facts:
        if observer == subject:
            raise SocialMemoryEvolutionError("social fact cannot create a self-memory")
        if observer not in descent.participants or subject not in descent.participants:
            raise SocialMemoryEvolutionError("social fact references a non-participating Descender")
        rule = SOCIAL_FACT_RULES.get(memory_type)
        if rule is None:
            raise SocialMemoryEvolutionError(f"unknown canonical social memory type {memory_type!r}")
        if any(dimension not in RELATIONSHIP_DIMENSIONS for dimension in rule.relationship_deltas):
            raise SocialMemoryEvolutionError("social fact rule escaped canonical relationship dimensions")


def _decay_record_to_tick(record: dict[str, Any], target_tick: int) -> bool:
    previous_tick = int(record["last_decay_tick"])
    if target_tick <= previous_tick:
        return False
    elapsed = target_tick - previous_tick
    rate = float(record["decay_rate"])
    old_confidence = float(record["confidence"])
    old_importance = float(record["importance"])
    record["confidence"] = _unit(old_confidence - rate * elapsed)
    record["importance"] = _unit(old_importance - rate * 0.5 * elapsed)
    record["last_decay_tick"] = int(target_tick)
    return record["confidence"] != old_confidence or record["importance"] != old_importance


def build_social_memory_snapshot(descent: Descent) -> dict[str, Any]:
    validate_social_memory_evolution(descent)
    metadata = _metadata(descent)
    memories = [dict(metadata["memories"][memory_id]) for memory_id in sorted(metadata["memories"])]
    body = {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "social_reasoning_can_mutate": False,
        "narrative_can_create_memory": False,
        "presentation_feedback_allowed": False,
        "relationship_time_decay_enabled": False,
        "descent_id": descent.id,
        "seed": descent.seed,
        "current_tick": descent.current_tick,
        "current_stratum_number": descent.current_floor,
        "memory_count": metadata["memory_count"],
        "memories": memories,
        "memory_state_digest": payload_digest(memories),
        "processed_source_event_ids": list(metadata["processed_source_event_ids"]),
        "processed_source_event_ids_digest": payload_digest(list(metadata["processed_source_event_ids"])),
        "memory_event_ids": list(metadata["memory_event_ids"]),
        "decay_event_ids": list(metadata["decay_event_ids"]),
        "relationship_snapshot_digest": build_social_state_snapshot(descent)["digest"],
        "relationship_state_digest": build_social_state_snapshot(descent)["relationship_state_digest"],
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
        "initialized_event_id": metadata["initialized_event_id"],
    }
    return {**body, "digest": payload_digest(body)}


class SocialMemoryEvolutionService:
    """Simulation-owned event-to-memory/relationship evolution service."""

    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence
        self.lifecycle = CrawlLifecycleService(persistence)
        self.social = SocialStateService(persistence)

    def initialize(self, descent: Descent) -> Descent:
        if SOCIAL_STATE_METADATA_KEY not in descent.modifiers:
            self.social.initialize(descent)
        validate_social_state(descent)
        if METADATA_KEY in descent.modifiers:
            validate_social_memory_evolution(descent)
            return descent
        metadata = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "extends_slice": "30C.1",
            "relationship_protocol": "underreach.social-state.v1",
            "social_reasoning_can_mutate": False,
            "narrative_can_create_memory": False,
            "presentation_feedback_allowed": False,
            "relationship_time_decay_enabled": False,
            "memories": {},
            "memory_count": 0,
            "processed_source_event_ids": [],
            "processed_source_event_count": 0,
            "last_processed_source_history_index": -1,
            "memory_event_ids": [],
            "decay_event_ids": [],
            "initialized_event_id": None,
        }
        descent.modifiers[METADATA_KEY] = metadata
        event = self.lifecycle.record_event(
            descent,
            SOCIAL_MEMORY_INITIALIZED_EVENT,
            "Event-linked deterministic social memory evolution initialized.",
            actor_ids=sorted(descent.participants),
            data={
                "protocol": PROTOCOL,
                "implementation_version": IMPLEMENTATION_VERSION,
                "relationship_protocol": "underreach.social-state.v1",
                "state_changes": {"social_memory_evolution_initialized": True},
            },
        )
        metadata["initialized_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_social_memory_evolution(descent)
        return descent

    def get_memory(
        self,
        descent: Descent,
        observer_descender_id: str,
        subject_descender_id: str,
        memory_type: str,
    ) -> SocialMemoryState | None:
        validate_social_memory_evolution(descent)
        memory_id = _stable_id("social_memory", descent.id, observer_descender_id, subject_descender_id, memory_type)
        record = _metadata(descent)["memories"].get(memory_id)
        return _memory_model(record) if isinstance(record, dict) else None

    def memories_for(self, descent: Descent, observer_descender_id: str) -> tuple[SocialMemoryState, ...]:
        validate_social_memory_evolution(descent)
        if observer_descender_id not in descent.participants:
            raise SocialMemoryEvolutionError("memory observer is not a participating Descender")
        records = [
            _memory_model(record)
            for _, record in sorted(_metadata(descent)["memories"].items())
            if record["observer_descender_id"] == observer_descender_id
        ]
        return tuple(records)

    def process_event(self, descent: Descent, event: CrawlEvent) -> SocialEventProcessingResult:
        validate_social_memory_evolution(descent)
        if event.crawl_id != descent.id or event.id not in descent.history_event_ids:
            raise SocialMemoryEvolutionError("social source event must belong to canonical Descent Ledger history")
        if event.tick > descent.current_tick:
            raise SocialMemoryEvolutionError("social source event cannot be in the canonical future")
        metadata = _metadata(descent)
        if event.id in metadata["processed_source_event_ids"]:
            return SocialEventProcessingResult(
                source_event_id=event.id,
                qualifying=True,
                processed=False,
                duplicate=True,
                fact_count=len(_event_facts(event)),
            )

        facts = _event_facts(event)
        if not facts:
            return SocialEventProcessingResult(
                source_event_id=event.id,
                qualifying=False,
                processed=False,
                duplicate=False,
                fact_count=0,
            )
        _validate_facts(descent, facts)
        history_index = descent.history_event_ids.index(event.id)
        if history_index <= int(metadata["last_processed_source_history_index"]):
            raise SocialMemoryEvolutionError("qualifying social source events must be processed in canonical Ledger order")

        memory_ids: list[str] = []
        memory_event_ids: list[str] = []
        relationship_event_ids: list[str] = []
        memories: dict[str, Any] = metadata["memories"]

        for observer, subject, memory_type in facts:
            rule = SOCIAL_FACT_RULES[memory_type]
            memory_id = _stable_id("social_memory", descent.id, observer, subject, memory_type)
            record = memories.get(memory_id)
            reinforced = isinstance(record, dict)
            if record is None:
                record = {
                    "memory_id": memory_id,
                    "observer_descender_id": observer,
                    "subject_descender_id": subject,
                    "memory_type": memory_type,
                    "source_event_ids": [event.id],
                    "importance": _unit(rule.importance),
                    "confidence": _unit(rule.confidence),
                    "decay_rate": _rounded(rule.decay_rate),
                    "created_tick": int(event.tick),
                    "last_reinforced_tick": int(event.tick),
                    "last_decay_tick": int(event.tick),
                    "reinforcement_count": 1,
                }
                memories[memory_id] = record
                metadata["memory_count"] = len(memories)
            else:
                _decay_record_to_tick(record, int(event.tick))
                record["source_event_ids"].append(event.id)
                record["importance"] = _unit(max(float(record["importance"]), rule.importance) + REINFORCEMENT_IMPORTANCE_BOOST)
                record["confidence"] = _unit(max(float(record["confidence"]), rule.confidence) + REINFORCEMENT_CONFIDENCE_BOOST)
                record["last_reinforced_tick"] = int(event.tick)
                record["last_decay_tick"] = max(int(record["last_decay_tick"]), int(event.tick))
                record["reinforcement_count"] = len(record["source_event_ids"])

            fact_relationship_events: list[str] = []
            for dimension, delta in sorted(rule.relationship_deltas.items()):
                result = self.social.adjust_dimension(
                    descent,
                    observer,
                    subject,
                    dimension,
                    delta,
                    reason_code=f"social_memory.{memory_type}",
                    source_event_id=event.id,
                )
                if result.ledger_event_id is not None:
                    fact_relationship_events.append(result.ledger_event_id)
                    relationship_event_ids.append(result.ledger_event_id)

            memory_event = self.lifecycle.record_event(
                descent,
                SOCIAL_MEMORY_REINFORCED_EVENT if reinforced else SOCIAL_MEMORY_RECORDED_EVENT,
                "Structured canonical social memory updated from a real Ledger event.",
                floor_number=event.floor_number,
                actor_ids=[observer, subject],
                location_id=event.location_id,
                data={
                    "protocol": PROTOCOL,
                    "memory_id": memory_id,
                    "observer_descender_id": observer,
                    "subject_descender_id": subject,
                    "memory_type": memory_type,
                    "source_event_id": event.id,
                    "source_event_type": event.event_type,
                    "reinforced": reinforced,
                    "reinforcement_count": record["reinforcement_count"],
                    "importance": record["importance"],
                    "confidence": record["confidence"],
                    "relationship_event_ids": fact_relationship_events,
                    "state_changes": {
                        "social_memory": {
                            "memory_id": memory_id,
                            "reinforcement_count": record["reinforcement_count"],
                        }
                    },
                },
            )
            metadata["memory_event_ids"].append(memory_event.id)
            memory_ids.append(memory_id)
            memory_event_ids.append(memory_event.id)

        metadata["processed_source_event_ids"].append(event.id)
        metadata["processed_source_event_count"] = len(metadata["processed_source_event_ids"])
        metadata["last_processed_source_history_index"] = history_index
        self.lifecycle.save(descent)
        validate_social_memory_evolution(descent)
        return SocialEventProcessingResult(
            source_event_id=event.id,
            qualifying=True,
            processed=True,
            duplicate=False,
            fact_count=len(facts),
            memory_ids=tuple(memory_ids),
            memory_event_ids=tuple(memory_event_ids),
            relationship_event_ids=tuple(relationship_event_ids),
        )

    def process_history(self, descent: Descent, events: Iterable[CrawlEvent]) -> tuple[SocialEventProcessingResult, ...]:
        """Process a supplied canonical Ledger slice in exact history order."""
        validate_social_memory_evolution(descent)
        by_id = {event.id: event for event in events}
        ordered = [by_id[event_id] for event_id in descent.history_event_ids if event_id in by_id]
        return tuple(self.process_event(descent, event) for event in ordered if _event_facts(event))

    def advance_decay(self, descent: Descent, target_tick: int | None = None) -> SocialMemoryDecayResult:
        """Decay memory salience/confidence without inventing relationship changes."""
        validate_social_memory_evolution(descent)
        tick = descent.current_tick if target_tick is None else int(target_tick)
        if tick < 0 or tick > descent.current_tick:
            raise SocialMemoryEvolutionError("memory decay target must be within canonical elapsed time")
        metadata = _metadata(descent)
        affected = 0
        changed = 0
        for memory_id in sorted(metadata["memories"]):
            record = metadata["memories"][memory_id]
            if tick > int(record["last_decay_tick"]):
                affected += 1
                if _decay_record_to_tick(record, tick):
                    changed += 1
        if affected == 0:
            return SocialMemoryDecayResult(target_tick=tick, affected_memory_count=0, changed_memory_count=0)
        event = self.lifecycle.record_event(
            descent,
            SOCIAL_MEMORY_DECAY_EVENT,
            "Deterministic social-memory salience decay applied to canonical elapsed time.",
            actor_ids=sorted(descent.participants),
            data={
                "protocol": PROTOCOL,
                "target_tick": tick,
                "affected_memory_count": affected,
                "changed_memory_count": changed,
                "relationship_state_changed": False,
                "state_changes": {"social_memory_decay_tick": tick},
            },
        )
        metadata["decay_event_ids"].append(event.id)
        self.lifecycle.save(descent)
        validate_social_memory_evolution(descent)
        return SocialMemoryDecayResult(
            target_tick=tick,
            affected_memory_count=affected,
            changed_memory_count=changed,
            ledger_event_id=event.id,
        )


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "METADATA_KEY",
    "SOCIAL_FACT_RULES",
    "SocialMemoryEvolutionError",
    "SocialMemoryState",
    "SocialEventProcessingResult",
    "SocialMemoryDecayResult",
    "SocialMemoryEvolutionService",
    "validate_social_memory_evolution",
    "build_social_memory_snapshot",
]
