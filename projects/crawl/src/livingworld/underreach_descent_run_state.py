"""Canonical Underreach Descent run-state foundation for Slice 30A.1.

The established ``Crawl`` model remains the one mutable authoritative state
object (exposed as ``underreach_domain.Descent``).  This module adds an
Underreach-facing lifecycle facade and deterministic snapshot/serialization
contract without creating a second gameplay truth tree.

30A.1 initializes exactly one Stratum.  Creating/advancing additional Strata is
reserved for 30A.2.
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


PROTOCOL = "underreach.descent-run-state.v1"
IMPLEMENTATION_VERSION = "30a1.1"
SERIALIZATION_PROTOCOL = "underreach.descent-run-serialization.v1"
RUN_METADATA_KEY = "_descent_run_state"
DEFAULT_RULESET_ID = "underreach.descent"
DEFAULT_RULESET_VERSION = IMPLEMENTATION_VERSION


class DescentRunStateError(ValueError):
    """Raised when an operation would violate the 30A.1 canonical run contract."""


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _ordered_ids(descender_ids: Iterable[str]) -> tuple[str, ...]:
    supplied = tuple(str(value) for value in descender_ids)
    if not supplied:
        raise DescentRunStateError("30A.1 requires at least one Descender")
    if any(not value for value in supplied):
        raise DescentRunStateError("Descender IDs must be non-empty")
    if len(supplied) != len(set(supplied)):
        raise DescentRunStateError("Descender IDs must be unique")
    return tuple(sorted(supplied))


def _run_metadata(descent: Descent) -> dict[str, Any]:
    metadata = descent.modifiers.get(RUN_METADATA_KEY)
    if not isinstance(metadata, dict):
        raise DescentRunStateError("Descent is missing 30A.1 run metadata")
    if metadata.get("protocol") != PROTOCOL:
        raise DescentRunStateError("Descent run metadata protocol mismatch")
    if metadata.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise DescentRunStateError("Descent run metadata version mismatch")
    if metadata.get("authoritative") is not True:
        raise DescentRunStateError("Descent run state must remain authoritative")
    if metadata.get("presentation_feedback_allowed") is not False:
        raise DescentRunStateError("presentation feedback cannot mutate canonical run state")

    ids = sorted(descent.participants)
    if metadata.get("ordered_descender_ids") != ids:
        raise DescentRunStateError("Descent run roster metadata diverged")
    if metadata.get("roster_digest") != payload_digest(ids):
        raise DescentRunStateError("Descent run roster digest mismatch")

    multi = metadata.get("multi_stratum_progression_enabled")
    if multi is not False:
        raise DescentRunStateError("30A.1 cannot enable multi-Stratum progression")
    if len(descent.floors) != 1 or descent.current_floor != 1:
        raise DescentRunStateError("30A.1 owns exactly the initial Stratum")
    return metadata


def validate_descent_run(descent: Descent) -> bool:
    """Validate the canonical Descent plus the additional 30A.1 invariants."""
    descent = Descent.model_validate(descent.model_dump(mode="python"))
    metadata = _run_metadata(descent)

    if descent.ruleset_id != metadata.get("ruleset_id"):
        raise DescentRunStateError("ruleset ID diverged from run metadata")
    if descent.ruleset_version != metadata.get("ruleset_version"):
        raise DescentRunStateError("ruleset version diverged from run metadata")

    stratum = descent.floors[1]
    if descent.status == CrawlStatus.PLANNED:
        if descent.started_at_tick is not None or stratum.status != FloorStatus.PENDING:
            raise DescentRunStateError("planned Descent has active lifecycle state")
    elif descent.status == CrawlStatus.RUNNING:
        if descent.started_at_tick is None or stratum.status != FloorStatus.ACTIVE:
            raise DescentRunStateError("active Descent must have one active initial Stratum")
    elif descent.status == CrawlStatus.COMPLETED:
        if stratum.status != FloorStatus.COMPLETED:
            raise DescentRunStateError("completed Descent must have a completed initial Stratum")
    elif descent.status == CrawlStatus.ARCHIVED:
        if stratum.status != FloorStatus.COMPLETED:
            raise DescentRunStateError("archived Descent must preserve completed Stratum state")

    for descender_id, participant in descent.participants.items():
        if participant.current_floor != 1:
            raise DescentRunStateError("30A.1 participant left the initial Stratum")
        if participant.current_location_id not in stratum.locations:
            raise DescentRunStateError(
                f"Descender {descender_id} has no valid canonical Sector position"
            )

    if len(descent.history_event_ids) != len(set(descent.history_event_ids)):
        raise DescentRunStateError("canonical Ledger event IDs must be unique")
    return True


def _snapshot_body(descent: Descent) -> dict[str, Any]:
    validate_descent_run(descent)
    metadata = _run_metadata(descent)
    stratum = descent.floors[descent.current_floor]
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
    status_counts = Counter(item["participation_status"] for item in positions)
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
        "current_stratum_index": descent.current_floor - 1,
        "current_stratum_number": descent.current_floor,
        "current_stratum_seed": stratum.seed,
        "current_stratum_theme": stratum.theme,
        "current_stratum_status": stratum.status.value,
        "current_stratum_state_digest": payload_digest(stratum.model_dump(mode="json")),
        "initial_stratum_only": True,
        "multi_stratum_progression_enabled": False,
        "multi_stratum_owner_slice": "30A.2",
        "ordered_descender_ids": list(metadata["ordered_descender_ids"]),
        "roster_digest": metadata["roster_digest"],
        "starting_descender_count": descent.starting_crawler_count,
        "surviving_descender_count": descent.surviving_crawler_count,
        "eliminated_descender_count": descent.eliminated_crawler_count,
        "participation_status_counts": dict(sorted(status_counts.items())),
        "participant_positions": positions,
        "history_event_ids": list(descent.history_event_ids),
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
    }


def build_descent_run_snapshot(descent: Descent) -> dict[str, Any]:
    body = _snapshot_body(descent)
    return {**body, "digest": payload_digest(body)}


def validate_descent_run_snapshot(snapshot: dict[str, Any], descent: Descent) -> bool:
    expected = build_descent_run_snapshot(descent)
    supplied = dict(snapshot)
    if supplied.get("digest") != payload_digest(
        {key: value for key, value in supplied.items() if key != "digest"}
    ):
        raise DescentRunStateError("Descent run snapshot digest mismatch")
    if supplied != expected:
        raise DescentRunStateError("Descent run snapshot does not match canonical state")
    return True


def serialize_descent_run(descent: Descent) -> str:
    """Return a canonical portable payload for exact deterministic state restore.

    Durable unattended-runtime checkpoints still use ``AlphaCheckpointStore`` so
    they can prove the exact Ledger prefix.  This portable envelope deliberately
    reuses the same canonical JSON and SHA-256 helpers.
    """
    snapshot = build_descent_run_snapshot(descent)
    body = {
        "protocol": SERIALIZATION_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_state": descent.model_dump(mode="json"),
        "canonical_descent_fingerprint": descent.fingerprint(),
        "run_state_digest": snapshot["digest"],
        "history_event_ids_digest": snapshot["history_event_ids_digest"],
    }
    return canonical_json({**body, "digest": payload_digest(body)})


def restore_descent_run(value: str | dict[str, Any]) -> Descent:
    try:
        payload = json.loads(value) if isinstance(value, str) else dict(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise DescentRunStateError("invalid Descent run serialization") from exc
    if payload.get("protocol") != SERIALIZATION_PROTOCOL:
        raise DescentRunStateError("unsupported Descent run serialization protocol")
    supplied = payload.get("digest")
    body = {key: item for key, item in payload.items() if key != "digest"}
    if supplied != payload_digest(body):
        raise DescentRunStateError("Descent run serialization digest mismatch")
    try:
        descent = Descent.model_validate(payload.get("canonical_state"))
    except Exception as exc:
        raise DescentRunStateError("serialized canonical Descent state is invalid") from exc
    validate_descent_run(descent)
    if descent.fingerprint() != payload.get("canonical_descent_fingerprint"):
        raise DescentRunStateError("serialized Descent fingerprint mismatch")
    snapshot = build_descent_run_snapshot(descent)
    if snapshot["digest"] != payload.get("run_state_digest"):
        raise DescentRunStateError("serialized run-state digest mismatch")
    if snapshot["history_event_ids_digest"] != payload.get("history_event_ids_digest"):
        raise DescentRunStateError("serialized Ledger ID digest mismatch")
    return descent


class DescentRunStateService:
    """Authoritative lifecycle facade for the initial 30A.1 Descent Stratum."""

    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence
        self.lifecycle = CrawlLifecycleService(persistence)

    def create(
        self,
        *,
        seed: str,
        descender_ids: Iterable[str],
        ruleset_id: str = DEFAULT_RULESET_ID,
        ruleset_version: str = DEFAULT_RULESET_VERSION,
        descent_id: str | None = None,
    ) -> Descent:
        ids = _ordered_ids(descender_ids)
        roster_digest = payload_digest(list(ids))
        actual_id = descent_id or _stable_id(
            "descent", seed, ruleset_id, ruleset_version, roster_digest
        )
        descent = self.lifecycle.create_seeded_crawl(
            seed=str(seed),
            crawler_ids=ids,
            floor_count=1,
            ruleset_id=ruleset_id,
            ruleset_version=ruleset_version,
            crawl_id=actual_id,
        )
        descent.modifiers[RUN_METADATA_KEY] = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "presentation_feedback_allowed": False,
            "ruleset_id": ruleset_id,
            "ruleset_version": ruleset_version,
            "ordered_descender_ids": list(ids),
            "roster_digest": roster_digest,
            "initial_stratum_count": 1,
            "multi_stratum_progression_enabled": False,
            "multi_stratum_owner_slice": "30A.2",
        }
        self.lifecycle.record_event(
            descent,
            "DESCENT_RUN_STATE_INITIALIZED",
            "Canonical Underreach Descent run state initialized.",
            data={
                "protocol": PROTOCOL,
                "roster_digest": roster_digest,
                "state_changes": {
                    "descent_status": descent.status.value,
                    "current_stratum_index": 0,
                },
            },
        )
        validate_descent_run(descent)
        return descent

    def start(self, descent: Descent, *, tick: int = 0) -> Descent:
        validate_descent_run(descent)
        self.lifecycle.start(descent, tick=tick)
        validate_descent_run(descent)
        return descent

    def set_tick(self, descent: Descent, tick: int) -> Descent:
        validate_descent_run(descent)
        self.lifecycle.set_tick(descent, tick)
        validate_descent_run(descent)
        return descent

    def commit_descender_position(
        self,
        descent: Descent,
        descender_id: str,
        sector_id: str,
    ) -> Descent:
        """Commit a valid adjacent Sector position chosen by an authoritative system.

        This method does not choose destinations, spend movement resources, or
        decide traversal outcomes.  It only validates and records the canonical
        position transition.
        """
        validate_descent_run(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise DescentRunStateError("position changes require an active Descent")
        participant = descent.participants.get(descender_id)
        if participant is None:
            raise KeyError(f"Descender {descender_id!r} is not participating")
        if participant.status != ParticipationStatus.ACTIVE:
            raise DescentRunStateError("only an active Descender can change Sector")
        if participant.current_floor != descent.current_floor:
            raise DescentRunStateError("Descender is not in the current Stratum")

        stratum = descent.floors[descent.current_floor]
        if sector_id not in stratum.locations:
            raise DescentRunStateError("target Sector does not exist in the current Stratum")
        origin = participant.current_location_id
        if origin is None or origin not in stratum.locations:
            raise DescentRunStateError("Descender has no valid source Sector")
        if sector_id != origin and sector_id not in stratum.locations[origin].adjacency:
            raise DescentRunStateError("canonical Sector position must follow an adjacent edge")
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
                "state_changes": {
                    "stratum_index": descent.current_floor - 1,
                    "sector_id": sector_id,
                },
            },
        )
        validate_descent_run(descent)
        return descent

    def eliminate(
        self,
        descent: Descent,
        descender_id: str,
        *,
        dead: bool = False,
        summary: str | None = None,
    ) -> Descent:
        validate_descent_run(descent)
        self.lifecycle.eliminate(descent, descender_id, dead=dead, summary=summary)
        validate_descent_run(descent)
        return descent

    def complete(self, descent: Descent) -> Descent:
        """Complete the single-Stratum 30A.1 run once all active Descenders exit."""
        validate_descent_run(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise DescentRunStateError("only an active Descent can complete")
        stratum = descent.floors[descent.current_floor]
        active = [
            participant
            for participant in descent.participants.values()
            if participant.status == ParticipationStatus.ACTIVE
        ]
        if active and any(
            participant.current_location_id not in stratum.exit_location_ids
            for participant in active
        ):
            raise DescentRunStateError(
                "all active Descenders must reach an exit before Descent completion"
            )
        self.lifecycle.complete_current_floor(descent, advance_ticks=0)
        validate_descent_run(descent)
        return descent

    def snapshot(self, descent: Descent) -> dict[str, Any]:
        return build_descent_run_snapshot(descent)

    def serialize(self, descent: Descent) -> str:
        return serialize_descent_run(descent)

    def restore(self, value: str | dict[str, Any]) -> Descent:
        return restore_descent_run(value)
