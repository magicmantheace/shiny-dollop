"""Canonical Underreach multi-Stratum progression for Slice 30A.2.

30A.1 established the Descent run-state authority boundary. This module extends
that same mutable ``Descent``/``Crawl`` object across two or more deterministic
Strata. Existing floor generation, lifecycle mutation, persistence, and Ledger
systems remain authoritative; Unreal and other presentation systems are strictly
downstream consumers.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from typing import Any, Iterable

from .crawl_domain import CrawlStatus, FloorStatus, ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_domain import Descent


PROTOCOL = "underreach.multi-stratum-progression.v1"
IMPLEMENTATION_VERSION = "30a2.1"
SERIALIZATION_PROTOCOL = "underreach.multi-stratum-serialization.v1"
METADATA_KEY = "_multi_stratum_progression"
DEFAULT_RULESET_ID = "underreach.descent"
DEFAULT_RULESET_VERSION = IMPLEMENTATION_VERSION
MIN_STRATUM_COUNT = 2


class MultiStratumProgressionError(ValueError):
    """Raised when an operation violates the canonical 30A.2 progression contract."""


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _ordered_ids(descender_ids: Iterable[str]) -> tuple[str, ...]:
    supplied = tuple(str(value) for value in descender_ids)
    if not supplied:
        raise MultiStratumProgressionError("30A.2 requires at least one Descender")
    if any(not value for value in supplied):
        raise MultiStratumProgressionError("Descender IDs must be non-empty")
    if len(supplied) != len(set(supplied)):
        raise MultiStratumProgressionError("Descender IDs must be unique")
    return tuple(sorted(supplied))


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise MultiStratumProgressionError("Descent is missing 30A.2 progression metadata")
    if value.get("protocol") != PROTOCOL:
        raise MultiStratumProgressionError("multi-Stratum progression protocol mismatch")
    if value.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise MultiStratumProgressionError("multi-Stratum progression version mismatch")
    if value.get("authoritative") is not True:
        raise MultiStratumProgressionError("multi-Stratum progression must remain authoritative")
    if value.get("presentation_feedback_allowed") is not False:
        raise MultiStratumProgressionError("presentation feedback cannot mutate canonical progression")
    configured = int(value.get("configured_stratum_count", 0))
    if configured < MIN_STRATUM_COUNT or configured != len(descent.floors):
        raise MultiStratumProgressionError("configured Stratum count diverged from canonical state")
    ids = sorted(descent.participants)
    if value.get("ordered_descender_ids") != ids:
        raise MultiStratumProgressionError("progression roster metadata diverged")
    if value.get("roster_digest") != payload_digest(ids):
        raise MultiStratumProgressionError("progression roster digest mismatch")
    if not isinstance(value.get("transitions"), list):
        raise MultiStratumProgressionError("progression transition history is invalid")
    return value


def _stratum_digest(descent: Descent, number: int) -> str:
    return payload_digest(descent.floors[number].model_dump(mode="json"))


def _validate_transition_record(descent: Descent, record: dict[str, Any], index: int) -> None:
    from_number = index + 1
    to_number = from_number + 1
    if record.get("transition_index") != index:
        raise MultiStratumProgressionError("transition history indices are not contiguous")
    if record.get("from_stratum_number") != from_number or record.get("to_stratum_number") != to_number:
        raise MultiStratumProgressionError("transition history is not sequential")
    if record.get("from_stratum_index") != from_number - 1 or record.get("to_stratum_index") != to_number - 1:
        raise MultiStratumProgressionError("transition Stratum indices are inconsistent")
    survivors = record.get("survivor_descender_ids")
    if not isinstance(survivors, list) or survivors != sorted(survivors) or len(survivors) != len(set(survivors)):
        raise MultiStratumProgressionError("transition survivor roster is not canonical")
    if not survivors or set(survivors) - set(descent.participants):
        raise MultiStratumProgressionError("transition survivor roster references invalid Descenders")
    if record.get("survivor_count") != len(survivors):
        raise MultiStratumProgressionError("transition survivor count mismatch")
    if record.get("survivor_roster_digest") != payload_digest(survivors):
        raise MultiStratumProgressionError("transition survivor roster digest mismatch")
    if int(record.get("advance_ticks", -1)) < 0:
        raise MultiStratumProgressionError("transition advance tick count is invalid")
    if int(record.get("tick_after", -1)) - int(record.get("tick_before", -1)) != int(record["advance_ticks"]):
        raise MultiStratumProgressionError("transition tick delta mismatch")
    if record.get("arrival_sector_id") != descent.floors[to_number].entrance_location_id:
        raise MultiStratumProgressionError("transition arrival Sector is not the next Stratum entrance")
    for key in ("from_stratum_state_digest", "completed_from_stratum_state_digest", "to_stratum_state_digest"):
        if not record.get(key):
            raise MultiStratumProgressionError("transition state digests are incomplete")
    event_id = record.get("ledger_event_id")
    if not isinstance(event_id, str) or event_id not in descent.history_event_ids:
        raise MultiStratumProgressionError("transition is not bound to its canonical Ledger event")
    digest_body = {
        key: value
        for key, value in record.items()
        if key not in {"digest", "ledger_event_id"}
    }
    if record.get("digest") != payload_digest(digest_body):
        raise MultiStratumProgressionError("transition digest mismatch")


def validate_multi_stratum_descent(descent: Descent) -> bool:
    """Validate sequential Stratum lifecycle, participant placement, and history."""
    descent = Descent.model_validate(descent.model_dump(mode="python"))
    metadata = _metadata(descent)
    configured = int(metadata["configured_stratum_count"])

    if descent.ruleset_id != metadata.get("ruleset_id"):
        raise MultiStratumProgressionError("ruleset ID diverged from progression metadata")
    if descent.ruleset_version != metadata.get("ruleset_version"):
        raise MultiStratumProgressionError("ruleset version diverged from progression metadata")
    if descent.current_floor < 1 or descent.current_floor > configured:
        raise MultiStratumProgressionError("current Stratum is outside configured progression")

    statuses = {number: descent.floors[number].status for number in range(1, configured + 1)}
    if descent.status == CrawlStatus.PLANNED:
        if descent.current_floor != 1 or descent.started_at_tick is not None:
            raise MultiStratumProgressionError("planned multi-Stratum Descent must begin at Stratum 1")
        if any(status != FloorStatus.PENDING for status in statuses.values()):
            raise MultiStratumProgressionError("planned multi-Stratum Descent must keep all Strata pending")
    elif descent.status == CrawlStatus.RUNNING:
        if descent.started_at_tick is None:
            raise MultiStratumProgressionError("running Descent must have a start tick")
        active = [number for number, status in statuses.items() if status == FloorStatus.ACTIVE]
        if active != [descent.current_floor]:
            raise MultiStratumProgressionError("running Descent must have exactly its current Stratum active")
        for number in range(1, descent.current_floor):
            if statuses[number] != FloorStatus.COMPLETED:
                raise MultiStratumProgressionError("previous Strata must remain completed")
        for number in range(descent.current_floor + 1, configured + 1):
            if statuses[number] != FloorStatus.PENDING:
                raise MultiStratumProgressionError("future Strata must remain pending")
    elif descent.status in {CrawlStatus.COMPLETED, CrawlStatus.ARCHIVED}:
        if descent.current_floor != configured:
            raise MultiStratumProgressionError("completed Descent must terminate on final Stratum")
        if any(status != FloorStatus.COMPLETED for status in statuses.values()):
            raise MultiStratumProgressionError("completed Descent must preserve all Strata as completed")

    for descender_id, participant in descent.participants.items():
        if participant.current_floor < 1 or participant.current_floor > configured:
            raise MultiStratumProgressionError(f"Descender {descender_id} has invalid Stratum position")
        stratum = descent.floors[participant.current_floor]
        if participant.current_location_id not in stratum.locations:
            raise MultiStratumProgressionError(f"Descender {descender_id} has invalid canonical Sector position")
        if participant.status == ParticipationStatus.ACTIVE:
            if descent.status == CrawlStatus.PLANNED:
                if participant.current_floor != 1 or participant.current_location_id != descent.floors[1].entrance_location_id:
                    raise MultiStratumProgressionError("planned Descenders must remain at the initial entrance")
            elif descent.status == CrawlStatus.RUNNING:
                if participant.current_floor != descent.current_floor:
                    raise MultiStratumProgressionError("active Descenders must occupy the current active Stratum")
            else:
                raise MultiStratumProgressionError("completed Descent cannot retain active Descenders")
        elif participant.status == ParticipationStatus.ADVANCED:
            if descent.status not in {CrawlStatus.COMPLETED, CrawlStatus.ARCHIVED}:
                raise MultiStratumProgressionError("advanced status is only stable after final completion")
            if participant.current_floor != configured:
                raise MultiStratumProgressionError("final survivors must remain on the final Stratum")
        elif participant.status in {ParticipationStatus.DEAD, ParticipationStatus.ELIMINATED}:
            if participant.current_floor > descent.current_floor:
                raise MultiStratumProgressionError("eliminated Descender cannot exist in a future Stratum")

    transitions = metadata["transitions"]
    expected_count = max(0, descent.current_floor - 1)
    if len(transitions) != expected_count:
        raise MultiStratumProgressionError("transition history count does not match current Stratum")
    for index, record in enumerate(transitions):
        if not isinstance(record, dict):
            raise MultiStratumProgressionError("transition history entry is invalid")
        _validate_transition_record(descent, record, index)

    if len(descent.history_event_ids) != len(set(descent.history_event_ids)):
        raise MultiStratumProgressionError("canonical Ledger event IDs must remain unique")
    return True


def _snapshot_body(descent: Descent) -> dict[str, Any]:
    validate_multi_stratum_descent(descent)
    metadata = _metadata(descent)
    strata = [
        {
            "stratum_index": number - 1,
            "stratum_number": number,
            "seed": descent.floors[number].seed,
            "theme": descent.floors[number].theme,
            "status": descent.floors[number].status.value,
            "entrance_sector_id": descent.floors[number].entrance_location_id,
            "exit_sector_ids": list(descent.floors[number].exit_location_ids),
            "state_digest": _stratum_digest(descent, number),
        }
        for number in range(1, len(descent.floors) + 1)
    ]
    positions = [
        {
            "descender_id": descender_id,
            "participation_status": participant.status.value,
            "stratum_index": participant.current_floor - 1,
            "stratum_number": participant.current_floor,
            "sector_id": participant.current_location_id,
        }
        for descender_id, participant in sorted(descent.participants.items())
    ]
    counts = Counter(item["participation_status"] for item in positions)
    transitions = json.loads(canonical_json(metadata["transitions"]))
    return {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "presentation_feedback_allowed": False,
        "descent_id": descent.id,
        "seed": descent.seed,
        "ruleset_id": descent.ruleset_id,
        "ruleset_version": descent.ruleset_version,
        "status": descent.status.value,
        "current_tick": descent.current_tick,
        "started_at_tick": descent.started_at_tick,
        "configured_stratum_count": int(metadata["configured_stratum_count"]),
        "completed_stratum_count": sum(item["status"] == FloorStatus.COMPLETED.value for item in strata),
        "current_stratum_index": descent.current_floor - 1,
        "current_stratum_number": descent.current_floor,
        "multi_stratum_progression_enabled": True,
        "progression_mode": metadata["progression_mode"],
        "ordered_descender_ids": list(metadata["ordered_descender_ids"]),
        "roster_digest": metadata["roster_digest"],
        "starting_descender_count": descent.starting_crawler_count,
        "surviving_descender_count": descent.surviving_crawler_count,
        "eliminated_descender_count": descent.eliminated_crawler_count,
        "participation_status_counts": dict(sorted(counts.items())),
        "strata": strata,
        "participant_positions": positions,
        "transitions": transitions,
        "transition_history_digest": payload_digest(transitions),
        "history_event_ids": list(descent.history_event_ids),
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
    }


def build_multi_stratum_snapshot(descent: Descent) -> dict[str, Any]:
    body = _snapshot_body(descent)
    return {**body, "digest": payload_digest(body)}


def validate_multi_stratum_snapshot(snapshot: dict[str, Any], descent: Descent) -> bool:
    supplied = dict(snapshot)
    supplied_body = {key: value for key, value in supplied.items() if key != "digest"}
    if supplied.get("digest") != payload_digest(supplied_body):
        raise MultiStratumProgressionError("multi-Stratum snapshot digest mismatch")
    expected = build_multi_stratum_snapshot(descent)
    if supplied != expected:
        raise MultiStratumProgressionError("multi-Stratum snapshot does not match canonical state")
    return True


def serialize_multi_stratum_descent(descent: Descent) -> str:
    snapshot = build_multi_stratum_snapshot(descent)
    body = {
        "protocol": SERIALIZATION_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_state": descent.model_dump(mode="json"),
        "canonical_descent_fingerprint": descent.fingerprint(),
        "progression_snapshot_digest": snapshot["digest"],
        "transition_history_digest": snapshot["transition_history_digest"],
        "history_event_ids_digest": snapshot["history_event_ids_digest"],
    }
    return canonical_json({**body, "digest": payload_digest(body)})


def restore_multi_stratum_descent(value: str | dict[str, Any]) -> Descent:
    try:
        payload = json.loads(value) if isinstance(value, str) else dict(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MultiStratumProgressionError("invalid multi-Stratum serialization") from exc
    if payload.get("protocol") != SERIALIZATION_PROTOCOL:
        raise MultiStratumProgressionError("unsupported multi-Stratum serialization protocol")
    body = {key: item for key, item in payload.items() if key != "digest"}
    if payload.get("digest") != payload_digest(body):
        raise MultiStratumProgressionError("multi-Stratum serialization digest mismatch")
    try:
        descent = Descent.model_validate(payload.get("canonical_state"))
    except Exception as exc:
        raise MultiStratumProgressionError("serialized canonical Descent state is invalid") from exc
    validate_multi_stratum_descent(descent)
    snapshot = build_multi_stratum_snapshot(descent)
    if descent.fingerprint() != payload.get("canonical_descent_fingerprint"):
        raise MultiStratumProgressionError("serialized Descent fingerprint mismatch")
    if snapshot["digest"] != payload.get("progression_snapshot_digest"):
        raise MultiStratumProgressionError("serialized progression snapshot digest mismatch")
    if snapshot["transition_history_digest"] != payload.get("transition_history_digest"):
        raise MultiStratumProgressionError("serialized transition history digest mismatch")
    if snapshot["history_event_ids_digest"] != payload.get("history_event_ids_digest"):
        raise MultiStratumProgressionError("serialized Ledger ID digest mismatch")
    return descent


class MultiStratumProgressionService:
    """Authoritative sequential Stratum progression facade for 30A.2."""

    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence
        self.lifecycle = CrawlLifecycleService(persistence)

    def create(
        self,
        *,
        seed: str,
        descender_ids: Iterable[str],
        stratum_count: int = 4,
        ruleset_id: str = DEFAULT_RULESET_ID,
        ruleset_version: str = DEFAULT_RULESET_VERSION,
        descent_id: str | None = None,
    ) -> Descent:
        ids = _ordered_ids(descender_ids)
        count = int(stratum_count)
        if count < MIN_STRATUM_COUNT:
            raise MultiStratumProgressionError("30A.2 requires at least two Strata")
        roster_digest = payload_digest(list(ids))
        actual_id = descent_id or _stable_id(
            "descent", seed, ruleset_id, ruleset_version, count, roster_digest
        )
        descent = self.lifecycle.create_seeded_crawl(
            seed=str(seed),
            crawler_ids=ids,
            floor_count=count,
            ruleset_id=ruleset_id,
            ruleset_version=ruleset_version,
            crawl_id=actual_id,
        )
        descent.modifiers[METADATA_KEY] = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "presentation_feedback_allowed": False,
            "extends_slice": "30A.1",
            "ruleset_id": ruleset_id,
            "ruleset_version": ruleset_version,
            "ordered_descender_ids": list(ids),
            "roster_digest": roster_digest,
            "configured_stratum_count": count,
            "progression_mode": "sequential_exit_gate",
            "transitions": [],
        }
        self.lifecycle.record_event(
            descent,
            "MULTI_STRATUM_PROGRESSION_INITIALIZED",
            "Canonical multi-Stratum Descent progression initialized.",
            data={
                "protocol": PROTOCOL,
                "configured_stratum_count": count,
                "roster_digest": roster_digest,
                "state_changes": {"current_stratum_index": 0, "multi_stratum_progression_enabled": True},
            },
        )
        validate_multi_stratum_descent(descent)
        return descent

    def start(self, descent: Descent, *, tick: int = 0) -> Descent:
        validate_multi_stratum_descent(descent)
        self.lifecycle.start(descent, tick=tick)
        validate_multi_stratum_descent(descent)
        return descent

    def set_tick(self, descent: Descent, tick: int) -> Descent:
        validate_multi_stratum_descent(descent)
        self.lifecycle.set_tick(descent, tick)
        validate_multi_stratum_descent(descent)
        return descent

    def commit_descender_position(self, descent: Descent, descender_id: str, sector_id: str) -> Descent:
        validate_multi_stratum_descent(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise MultiStratumProgressionError("position changes require an active Descent")
        participant = descent.participants.get(descender_id)
        if participant is None:
            raise KeyError(f"Descender {descender_id!r} is not participating")
        if participant.status != ParticipationStatus.ACTIVE:
            raise MultiStratumProgressionError("only an active Descender can change Sector")
        if participant.current_floor != descent.current_floor:
            raise MultiStratumProgressionError("Descender is not in the current Stratum")
        stratum = descent.floors[descent.current_floor]
        if sector_id not in stratum.locations:
            raise MultiStratumProgressionError("target Sector does not exist in the current Stratum")
        origin = participant.current_location_id
        if origin is None or origin not in stratum.locations:
            raise MultiStratumProgressionError("Descender has no valid source Sector")
        if sector_id != origin and sector_id not in stratum.locations[origin].adjacency:
            raise MultiStratumProgressionError("canonical Sector position must follow an adjacent edge")
        if sector_id == origin:
            return descent
        participant.current_location_id = sector_id
        self.lifecycle.record_event(
            descent,
            "DESCENDER_POSITION_CHANGED",
            f"Descender {descender_id} changed canonical Sector position.",
            actor_ids=[descender_id],
            location_id=sector_id,
            data={
                "from_sector_id": origin,
                "to_sector_id": sector_id,
                "state_changes": {"stratum_index": descent.current_floor - 1, "sector_id": sector_id},
            },
        )
        validate_multi_stratum_descent(descent)
        return descent

    def eliminate(
        self,
        descent: Descent,
        descender_id: str,
        *,
        dead: bool = False,
        summary: str | None = None,
    ) -> Descent:
        validate_multi_stratum_descent(descent)
        self.lifecycle.eliminate(descent, descender_id, dead=dead, summary=summary)
        validate_multi_stratum_descent(descent)
        return descent

    def advance(self, descent: Descent, *, advance_ticks: int = 1) -> Descent:
        """Complete the current Stratum and move active survivors one Stratum forward."""
        validate_multi_stratum_descent(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise MultiStratumProgressionError("only an active Descent can advance")
        if descent.current_floor >= len(descent.floors):
            raise MultiStratumProgressionError("final Stratum must use complete()")
        if advance_ticks < 0:
            raise MultiStratumProgressionError("advance_ticks cannot be negative")
        from_number = descent.current_floor
        from_stratum = descent.floors[from_number]
        survivors = sorted(
            descender_id
            for descender_id, participant in descent.participants.items()
            if participant.status == ParticipationStatus.ACTIVE and participant.current_floor == from_number
        )
        if not survivors:
            raise MultiStratumProgressionError("at least one active survivor is required to advance")
        if any(descent.participants[item].current_location_id not in from_stratum.exit_location_ids for item in survivors):
            raise MultiStratumProgressionError("all active survivors must reach an exit before Stratum advancement")

        from_digest = _stratum_digest(descent, from_number)
        tick_before = descent.current_tick
        self.lifecycle.complete_current_floor(descent, advance_ticks=advance_ticks, activate_next=True)
        to_number = descent.current_floor
        if to_number != from_number + 1:
            raise MultiStratumProgressionError("canonical lifecycle did not advance exactly one Stratum")
        to_stratum = descent.floors[to_number]
        entrance = to_stratum.entrance_location_id
        for descender_id in survivors:
            participant = descent.participants[descender_id]
            if participant.status != ParticipationStatus.ACTIVE:
                raise MultiStratumProgressionError("survivor did not return to active status after advancement")
            if participant.current_floor != to_number or participant.current_location_id != entrance:
                raise MultiStratumProgressionError("survivor did not arrive at next Stratum entrance")

        record = {
            "transition_index": len(_metadata(descent)["transitions"]),
            "from_stratum_index": from_number - 1,
            "from_stratum_number": from_number,
            "to_stratum_index": to_number - 1,
            "to_stratum_number": to_number,
            "tick_before": tick_before,
            "tick_after": descent.current_tick,
            "advance_ticks": int(advance_ticks),
            "survivor_descender_ids": survivors,
            "survivor_roster_digest": payload_digest(survivors),
            "survivor_count": len(survivors),
            "eliminated_descender_count": descent.eliminated_crawler_count,
            "from_stratum_state_digest": from_digest,
            "completed_from_stratum_state_digest": _stratum_digest(descent, from_number),
            "to_stratum_state_digest": _stratum_digest(descent, to_number),
            "arrival_sector_id": entrance,
        }
        record["digest"] = payload_digest(record)
        _metadata(descent)["transitions"].append(record)
        event = self.lifecycle.record_event(
            descent,
            "STRATUM_ADVANCED",
            f"Surviving Descenders advanced from Stratum {from_number} to {to_number}.",
            floor_number=to_number,
            actor_ids=survivors,
            location_id=entrance,
            data={
                "transition_digest": record["digest"],
                "from_stratum_number": from_number,
                "to_stratum_number": to_number,
                "survivor_count": len(survivors),
                "survivor_roster_digest": record["survivor_roster_digest"],
                "state_changes": {"current_stratum_index": to_number - 1, "current_stratum_number": to_number},
            },
        )
        record["ledger_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_multi_stratum_descent(descent)
        return descent

    def complete(self, descent: Descent, *, advance_ticks: int = 0) -> Descent:
        """Complete the final Stratum after all active survivors reach an exit."""
        validate_multi_stratum_descent(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise MultiStratumProgressionError("only an active Descent can complete")
        if descent.current_floor != len(descent.floors):
            raise MultiStratumProgressionError("Descent cannot complete before the final Stratum")
        if advance_ticks < 0:
            raise MultiStratumProgressionError("advance_ticks cannot be negative")
        stratum = descent.floors[descent.current_floor]
        survivors = sorted(
            descender_id
            for descender_id, participant in descent.participants.items()
            if participant.status == ParticipationStatus.ACTIVE and participant.current_floor == descent.current_floor
        )
        if not survivors:
            raise MultiStratumProgressionError("at least one active survivor is required to complete the Descent")
        if any(descent.participants[item].current_location_id not in stratum.exit_location_ids for item in survivors):
            raise MultiStratumProgressionError("all active survivors must reach an exit before final completion")
        final_number = descent.current_floor
        self.lifecycle.complete_current_floor(descent, advance_ticks=advance_ticks)
        self.lifecycle.record_event(
            descent,
            "MULTI_STRATUM_DESCENT_COMPLETED",
            "Final Stratum completed; canonical multi-Stratum Descent resolved.",
            floor_number=final_number,
            actor_ids=survivors,
            data={
                "configured_stratum_count": len(descent.floors),
                "survivor_count": len(survivors),
                "survivor_roster_digest": payload_digest(survivors),
                "transition_history_digest": payload_digest(_metadata(descent)["transitions"]),
                "state_changes": {"descent_status": CrawlStatus.COMPLETED.value},
            },
        )
        validate_multi_stratum_descent(descent)
        return descent

    def snapshot(self, descent: Descent) -> dict[str, Any]:
        return build_multi_stratum_snapshot(descent)

    def serialize(self, descent: Descent) -> str:
        return serialize_multi_stratum_descent(descent)

    def restore(self, value: str | dict[str, Any]) -> Descent:
        return restore_multi_stratum_descent(value)
