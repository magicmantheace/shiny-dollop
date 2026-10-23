"""Read-only canonical media export for Underreach Phase 30.5 Slice 1.

30.5.1 establishes a strict one-way membrane from accepted deterministic
simulation truth into presentation-safe media envelopes. The exporter may read
canonical state and canonical Ledger events, but it never writes to Crawl state,
the Ledger, media persistence, providers, Unreal, or generated presentation
artifacts.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from .crawl_domain import CrawlEvent
from .crawl_persistence import CrawlPersistence
from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_domain import Descent
from .underreach_group_social_orchestration import (
    METADATA_KEY as GROUP_SOCIAL_METADATA_KEY,
    validate_group_social_orchestration,
)


PROTOCOL = "underreach.media-envelope.v1"
IMPLEMENTATION_VERSION = "30.5.1"
PHASE = "30.5"
MAX_SOURCE_EVENTS = 32
MAX_CONTEXT_ACTORS = 16
MAX_FACT_LEAVES_PER_EVENT = 256
MAX_CONTEXT_ITEMS = 128


class MediaEventExportError(ValueError):
    """Raised when a requested export violates the 30.5.1 read-only contract."""


class AllowedFact(BaseModel):
    """One normalized fact that later narrative verification may cite."""

    model_config = ConfigDict(frozen=True)

    fact_id: str
    scope: str
    subject: str
    predicate: str
    value: Any = None
    source_event_ids: tuple[str, ...] = ()


class MediaEnvelope(BaseModel):
    """Immutable presentation-safe export of canonical Ledger truth."""

    model_config = ConfigDict(frozen=True)

    schema: str = PROTOCOL
    exporter_version: str = IMPLEMENTATION_VERSION
    phase: str = PHASE
    envelope_id: str
    idempotency_key: str
    crawl_id: str
    seed: str
    export_tick: int = Field(ge=0)
    stratum: int | None = Field(default=None, ge=1)
    strata: tuple[int, ...] = ()
    sector: str | None = None
    source_event_ids: tuple[str, ...]
    source_event_types: tuple[str, ...]
    source_event_digest: str
    delver_ids: tuple[str, ...]
    participant_context: dict[str, Any]
    item_context: tuple[dict[str, Any], ...]
    social_context: dict[str, Any]
    party_context: dict[str, Any]
    combat_context: dict[str, Any]
    semantic_context: tuple[dict[str, Any], ...]
    visual_identity_refs: tuple[str, ...] = ()
    allowed_facts: tuple[AllowedFact, ...]
    canonical_fingerprint: str
    canonical_state_digest: str
    history_prefix_count: int = Field(ge=1)
    history_prefix_last_event_id: str
    history_prefix_digest: str
    context_truncated: bool = False
    presentation_can_mutate_simulation: bool = False
    unreal_dependency: bool = False
    cloud_ai_dependency: bool = False
    paid_ai_dependency: bool = False
    digest: str


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _full_state_digest(descent: Descent) -> str:
    return payload_digest(descent.model_dump(mode="json"))


def _assert_no_mutation(
    descent: Descent,
    *,
    before_json: str,
    before_fingerprint: str,
    before_history: tuple[str, ...],
) -> None:
    if canonical_json(descent.model_dump(mode="json")) != before_json:
        raise MediaEventExportError("media export mutated canonical Descent state")
    if descent.fingerprint() != before_fingerprint:
        raise MediaEventExportError("media export changed canonical simulation fingerprint")
    if tuple(descent.history_event_ids) != before_history:
        raise MediaEventExportError("media export changed canonical Ledger history")


def _ordered_source_ids(descent: Descent, event_ids: Iterable[str]) -> list[str]:
    supplied = list(event_ids)
    if not supplied:
        raise MediaEventExportError("media export requires at least one canonical source event")
    if len(supplied) > MAX_SOURCE_EVENTS:
        raise MediaEventExportError(f"media export supports at most {MAX_SOURCE_EVENTS} source events")
    if len(supplied) != len(set(supplied)):
        raise MediaEventExportError("media export source event IDs must be unique")
    positions = {event_id: index for index, event_id in enumerate(descent.history_event_ids)}
    missing = [event_id for event_id in supplied if event_id not in positions]
    if missing:
        raise MediaEventExportError(f"media export references missing canonical Ledger event: {missing[0]}")
    return sorted(supplied, key=lambda event_id: positions[event_id])


def _load_events(
    persistence: CrawlPersistence,
    descent: Descent,
    event_ids: list[str],
) -> list[CrawlEvent]:
    events = persistence.events_by_ids(event_ids)
    if len(events) != len(event_ids):
        raise MediaEventExportError("canonical Ledger export is incomplete")
    for event, event_id in zip(events, event_ids, strict=True):
        if event.id != event_id or event.crawl_id != descent.id:
            raise MediaEventExportError("canonical Ledger event identity does not match Descent")
    return events


def _json_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _flatten_json(prefix: str, value: Any, output: list[tuple[str, Any]], *, limit: int) -> None:
    if len(output) >= limit:
        return
    if _json_scalar(value):
        output.append((prefix, value))
        return
    if isinstance(value, dict):
        for key in sorted(value):
            if len(output) >= limit:
                break
            child = f"{prefix}.{key}" if prefix else str(key)
            _flatten_json(child, value[key], output, limit=limit)
        return
    if isinstance(value, (list, tuple)):
        if all(_json_scalar(item) for item in value):
            output.append((prefix, list(value)))
            return
        for index, item in enumerate(value):
            if len(output) >= limit:
                break
            _flatten_json(f"{prefix}[{index}]", item, output, limit=limit)
        return
    output.append((prefix, str(value)))


def _fact(
    *,
    scope: str,
    subject: str,
    predicate: str,
    value: Any,
    source_event_ids: Iterable[str],
) -> AllowedFact:
    provenance = tuple(source_event_ids)
    body = {
        "scope": scope,
        "subject": subject,
        "predicate": predicate,
        "value": value,
        "source_event_ids": list(provenance),
    }
    return AllowedFact(
        fact_id=_stable_id("media_fact", payload_digest(body)),
        scope=scope,
        subject=subject,
        predicate=predicate,
        value=value,
        source_event_ids=provenance,
    )


def _event_allowed_facts(events: list[CrawlEvent]) -> list[AllowedFact]:
    facts: list[AllowedFact] = []
    for event in events:
        provenance = (event.id,)
        facts.extend(
            [
                _fact(scope="event", subject=event.id, predicate="event_type", value=event.event_type, source_event_ids=provenance),
                _fact(scope="event", subject=event.id, predicate="tick", value=event.tick, source_event_ids=provenance),
                _fact(scope="event", subject=event.id, predicate="stratum", value=event.floor_number, source_event_ids=provenance),
                _fact(scope="event", subject=event.id, predicate="sector", value=event.location_id, source_event_ids=provenance),
                _fact(scope="event", subject=event.id, predicate="actor_ids", value=list(event.actor_ids), source_event_ids=provenance),
                _fact(scope="event", subject=event.id, predicate="canonical_summary", value=event.summary, source_event_ids=provenance),
            ]
        )
        leaves: list[tuple[str, Any]] = []
        _flatten_json("data", event.data, leaves, limit=MAX_FACT_LEAVES_PER_EVENT)
        for path, value in leaves:
            facts.append(
                _fact(
                    scope="event",
                    subject=event.id,
                    predicate=path,
                    value=value,
                    source_event_ids=provenance,
                )
            )
    unique = {fact.fact_id: fact for fact in facts}
    return [unique[fact_id] for fact_id in sorted(unique)]


def _participant_context(descent: Descent, actor_ids: list[str]) -> tuple[dict[str, Any], bool]:
    selected = actor_ids[:MAX_CONTEXT_ACTORS]
    context: dict[str, Any] = {}
    for npc_id in selected:
        participant = descent.participants.get(npc_id)
        if participant is None:
            continue
        gameplay = participant.gameplay
        context[npc_id] = {
            "as_of_export_tick": descent.current_tick,
            "status": participant.status.value,
            "current_stratum": participant.current_floor,
            "current_sector": participant.current_location_id,
            "health": participant.health,
            "current_party_id": participant.current_party_id,
            "current_objective": participant.current_objective,
            "stamina": gameplay.stamina,
            "injuries": [item.model_dump(mode="json") for item in gameplay.injuries],
            "status_effects": dict(sorted(gameplay.status_effects.items())),
            "equipment": dict(sorted(gameplay.equipment.items())),
            "progression": gameplay.progression.model_dump(mode="json"),
            "kills": gameplay.kills,
            "damage_dealt": gameplay.damage_dealt,
            "damage_taken": gameplay.damage_taken,
            "encounters_survived": gameplay.encounters_survived,
        }
    return context, len(actor_ids) > len(selected)


def _referenced_item_ids(events: list[CrawlEvent]) -> set[str]:
    found: set[str] = set()

    def visit(key: str, value: Any) -> None:
        lower = key.lower()
        if isinstance(value, str) and "item" in lower:
            found.add(value)
        elif isinstance(value, list) and "item" in lower:
            found.update(item for item in value if isinstance(item, str))
        elif isinstance(value, dict):
            for child_key, child_value in value.items():
                visit(str(child_key), child_value)

    for event in events:
        for key, value in event.data.items():
            visit(str(key), value)
    return found


def _item_context(descent: Descent, actor_ids: list[str], events: list[CrawlEvent]) -> tuple[tuple[dict[str, Any], ...], bool]:
    wanted = _referenced_item_ids(events)
    for npc_id in actor_ids[:MAX_CONTEXT_ACTORS]:
        participant = descent.participants.get(npc_id)
        if participant is not None:
            wanted.update(participant.gameplay.inventory_item_ids)
    ordered = sorted(item_id for item_id in wanted if item_id in descent.items)
    truncated = len(ordered) > MAX_CONTEXT_ITEMS
    values = []
    for item_id in ordered[:MAX_CONTEXT_ITEMS]:
        item = descent.items[item_id]
        values.append(
            {
                "id": item.id,
                "name": item.name,
                "category": item.category.value,
                "rarity": item.rarity.value,
                "slot": item.slot.value if item.slot is not None else None,
                "owner_descender_id": item.owner_npc_id,
                "sector": item.location_id,
                "encounter_id": item.encounter_id,
                "important": item.important,
                "provenance_event_ids": list(item.provenance_event_ids),
            }
        )
    return tuple(values), truncated


def _social_context(descent: Descent, actor_ids: list[str]) -> dict[str, Any]:
    actors = actor_ids[:MAX_CONTEXT_ACTORS]
    state = descent.modifiers.get("_social_state")
    memory = descent.modifiers.get("_social_memory_evolution")
    relationships: list[dict[str, Any]] = []
    if isinstance(state, dict):
        edges = state.get("edges", {})
        if isinstance(edges, dict):
            actor_set = set(actors)
            for source in sorted(actor_set):
                by_target = edges.get(source, {})
                if not isinstance(by_target, dict):
                    continue
                for target in sorted(actor_set):
                    values = by_target.get(target)
                    if source == target or not isinstance(values, dict):
                        continue
                    relationships.append(
                        {
                            "source_descender_id": source,
                            "target_descender_id": target,
                            **{key: values[key] for key in sorted(values)},
                        }
                    )
    memories: list[dict[str, Any]] = []
    if isinstance(memory, dict):
        stored = memory.get("memories", {})
        if isinstance(stored, dict):
            actor_set = set(actors)
            for memory_id in sorted(stored):
                record = stored[memory_id]
                if not isinstance(record, dict):
                    continue
                if record.get("observer_descender_id") in actor_set or record.get("subject_descender_id") in actor_set:
                    memories.append(dict(record))
    return {
        "as_of_export_tick": descent.current_tick,
        "relationships": relationships,
        "relationship_digest": payload_digest(relationships),
        "memories": memories,
        "memory_digest": payload_digest(memories),
    }


def _party_context(descent: Descent, actor_ids: list[str]) -> dict[str, Any]:
    actor_set = set(actor_ids[:MAX_CONTEXT_ACTORS])
    parties: list[dict[str, Any]] = []
    selected_party_ids: set[str] = set()
    for party_id in sorted(descent.parties):
        party = descent.parties[party_id]
        if actor_set.intersection(party.member_npc_ids):
            selected_party_ids.add(party_id)
            parties.append(party.model_dump(mode="json"))
    alliances: list[dict[str, Any]] = []
    metadata = descent.modifiers.get("_parties_alliances_leadership")
    if isinstance(metadata, dict):
        stored = metadata.get("alliances", {})
        if isinstance(stored, dict):
            for alliance_id in sorted(stored):
                alliance = stored[alliance_id]
                if isinstance(alliance, dict) and selected_party_ids.intersection(alliance.get("party_ids", [])):
                    alliances.append(dict(alliance))
    return {
        "as_of_export_tick": descent.current_tick,
        "parties": parties,
        "party_digest": payload_digest(parties),
        "alliances": alliances,
        "alliance_digest": payload_digest(alliances),
    }


def _combat_context(descent: Descent, actor_ids: list[str], events: list[CrawlEvent]) -> dict[str, Any]:
    actor_set = set(actor_ids[:MAX_CONTEXT_ACTORS])
    locations = {event.location_id for event in events if event.location_id is not None}
    referenced: set[str] = set()
    for event in events:
        for key in ("encounter_id", "target_encounter_id"):
            value = event.data.get(key)
            if isinstance(value, str):
                referenced.add(value)
    encounters: list[dict[str, Any]] = []
    for encounter_id in sorted(descent.encounters):
        encounter = descent.encounters[encounter_id]
        if (
            encounter_id in referenced
            or actor_set.intersection(encounter.participant_npc_ids)
            or encounter.location_id in locations
        ):
            encounters.append(encounter.model_dump(mode="json"))
    return {
        "as_of_export_tick": descent.current_tick,
        "encounters": encounters,
        "encounter_digest": payload_digest(encounters),
    }


def _semantic_context(events: list[CrawlEvent]) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "event_id": event.id,
            "event_type": event.event_type,
            "semantic": dict(event.data.get("semantic", {})) if isinstance(event.data.get("semantic"), dict) else {},
        }
        for event in events
    )


def validate_media_envelope(envelope: MediaEnvelope) -> bool:
    if envelope.schema != PROTOCOL or envelope.exporter_version != IMPLEMENTATION_VERSION:
        raise MediaEventExportError("media envelope protocol/version mismatch")
    if envelope.phase != PHASE:
        raise MediaEventExportError("media envelope phase must remain the string '30.5'")
    if envelope.presentation_can_mutate_simulation is not False:
        raise MediaEventExportError("presentation cannot mutate canonical simulation truth")
    if envelope.unreal_dependency or envelope.cloud_ai_dependency or envelope.paid_ai_dependency:
        raise MediaEventExportError("30.5.1 cannot depend on Unreal, cloud AI, or paid AI")
    if not envelope.source_event_ids or len(envelope.source_event_ids) != len(set(envelope.source_event_ids)):
        raise MediaEventExportError("media envelope source-event provenance is invalid")
    if len(envelope.source_event_ids) > MAX_SOURCE_EVENTS:
        raise MediaEventExportError("media envelope source-event window is too large")
    if envelope.history_prefix_last_event_id not in envelope.source_event_ids and envelope.history_prefix_count < len(envelope.source_event_ids):
        raise MediaEventExportError("media envelope history-prefix metadata is inconsistent")
    fact_ids = [fact.fact_id for fact in envelope.allowed_facts]
    if len(fact_ids) != len(set(fact_ids)):
        raise MediaEventExportError("media envelope allowed-fact IDs must be unique")
    source_set = set(envelope.source_event_ids)
    for fact in envelope.allowed_facts:
        if not set(fact.source_event_ids).issubset(source_set):
            raise MediaEventExportError("allowed fact references event outside envelope provenance")
    body = envelope.model_dump(mode="json", exclude={"digest"})
    if envelope.digest != payload_digest(body):
        raise MediaEventExportError("media envelope digest mismatch")
    return True


class CanonicalMediaEventExporter:
    """Read-only exporter from canonical simulation truth into media envelopes."""

    def __init__(self, persistence: CrawlPersistence) -> None:
        self.persistence = persistence

    def export_event(self, descent: Descent, event_id: str) -> MediaEnvelope:
        return self.export_events(descent, [event_id])

    def export_events(self, descent: Descent, event_ids: Iterable[str]) -> MediaEnvelope:
        # The media membrane is also used by the accepted base Alpha runtime,
        # which can legitimately predate 30C.6 social orchestration. Whenever
        # social orchestration metadata exists it remains strictly validated;
        # its absence must not make otherwise canonical Ledger truth unexportable.
        if GROUP_SOCIAL_METADATA_KEY in descent.modifiers:
            validate_group_social_orchestration(descent)
        before_json = canonical_json(descent.model_dump(mode="json"))
        before_fingerprint = descent.fingerprint()
        before_history = tuple(descent.history_event_ids)
        before_state_digest = _full_state_digest(descent)

        ordered_ids = _ordered_source_ids(descent, event_ids)
        events = _load_events(self.persistence, descent, ordered_ids)
        last_index = descent.history_event_ids.index(ordered_ids[-1])
        history_prefix = list(descent.history_event_ids[: last_index + 1])
        actor_ids = sorted({actor_id for event in events for actor_id in event.actor_ids})
        participant_context, actor_truncated = _participant_context(descent, actor_ids)
        item_context, item_truncated = _item_context(descent, actor_ids, events)
        social_context = _social_context(descent, actor_ids)
        party_context = _party_context(descent, actor_ids)
        combat_context = _combat_context(descent, actor_ids, events)
        semantic_context = _semantic_context(events)
        facts = tuple(_event_allowed_facts(events))
        strata = tuple(sorted({event.floor_number for event in events if event.floor_number is not None}))
        sectors = sorted({event.location_id for event in events if event.location_id is not None})
        source_event_digest = payload_digest([event.model_dump(mode="json") for event in events])
        history_prefix_digest = payload_digest(history_prefix)
        idempotency_body = {
            "protocol": PROTOCOL,
            "exporter_version": IMPLEMENTATION_VERSION,
            "crawl_id": descent.id,
            "source_event_ids": ordered_ids,
            "source_event_digest": source_event_digest,
            "canonical_fingerprint": before_fingerprint,
            "canonical_state_digest": before_state_digest,
            "history_prefix_digest": history_prefix_digest,
        }
        idempotency_key = payload_digest(idempotency_body)
        envelope_id = _stable_id("media_envelope", descent.id, idempotency_key)
        body = {
            "schema": PROTOCOL,
            "exporter_version": IMPLEMENTATION_VERSION,
            "phase": PHASE,
            "envelope_id": envelope_id,
            "idempotency_key": idempotency_key,
            "crawl_id": descent.id,
            "seed": descent.seed,
            "export_tick": descent.current_tick,
            "stratum": strata[-1] if strata else None,
            "strata": list(strata),
            "sector": sectors[0] if len(sectors) == 1 else None,
            "source_event_ids": ordered_ids,
            "source_event_types": [event.event_type for event in events],
            "source_event_digest": source_event_digest,
            "delver_ids": actor_ids,
            "participant_context": participant_context,
            "item_context": list(item_context),
            "social_context": social_context,
            "party_context": party_context,
            "combat_context": combat_context,
            "semantic_context": list(semantic_context),
            "visual_identity_refs": [],
            "allowed_facts": [fact.model_dump(mode="json") for fact in facts],
            "canonical_fingerprint": before_fingerprint,
            "canonical_state_digest": before_state_digest,
            "history_prefix_count": len(history_prefix),
            "history_prefix_last_event_id": history_prefix[-1],
            "history_prefix_digest": history_prefix_digest,
            "context_truncated": actor_truncated or item_truncated,
            "presentation_can_mutate_simulation": False,
            "unreal_dependency": False,
            "cloud_ai_dependency": False,
            "paid_ai_dependency": False,
        }
        envelope = MediaEnvelope.model_validate({**body, "digest": payload_digest(body)})
        validate_media_envelope(envelope)
        _assert_no_mutation(
            descent,
            before_json=before_json,
            before_fingerprint=before_fingerprint,
            before_history=before_history,
        )
        if _full_state_digest(descent) != before_state_digest:
            raise MediaEventExportError("media export changed canonical state digest")
        return envelope


__all__ = [
    "PROTOCOL",
    "IMPLEMENTATION_VERSION",
    "PHASE",
    "MAX_SOURCE_EVENTS",
    "AllowedFact",
    "MediaEnvelope",
    "MediaEventExportError",
    "CanonicalMediaEventExporter",
    "validate_media_envelope",
]
