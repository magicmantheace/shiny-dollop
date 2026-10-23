"""Full autonomous Underreach Descent orchestration for Slice 30A.5.

30A.1-30A.4 established canonical run state, multi-Stratum progression,
loot/cache/relic ownership, and resources/survival pressure.  This slice does
not replace any of those authorities.  It coordinates them into a deterministic
headless run that can advance from a planned Descent to a completed Descent
without presentation input.

The orchestration policy is intentionally bounded and deterministic.  It uses
existing crawler personality/navigation, encounter/combat, canonical cache and
supply services, and the accepted resource clock.  Unreal and all presentation
systems remain downstream consumers only.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable

from .crawl_domain import CrawlStatus, LocationKind, ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .crawler_decision import CrawlerDecision, choose_action
from .crawler_domain import LocationKnowledge
from .crawler_navigation import choose_destination, perceive
from .encounter_system import encounter_at, resolve_encounter, seed_floor_encounters
from .gameplay_domain import ItemCategory
from .item_system import choose_and_equip, item_score, transfer_item_to_crawler
from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_domain import Descent
from .underreach_resources_survival import (
    CRITICAL_THRESHOLD,
    METADATA_KEY as SURVIVAL_METADATA_KEY,
    WARNING_THRESHOLD,
    ResourcesSurvivalService,
    build_resources_survival_snapshot,
    validate_resources_survival,
)


PROTOCOL = "underreach.full-autonomous-descent.v1"
IMPLEMENTATION_VERSION = "30a5.1"
METADATA_KEY = "_full_autonomous_descent"
AUTO_CONSUME_THRESHOLD = 0.54
SAFE_RECOVERY_STAMINA_THRESHOLD = 0.42
CACHE_SEARCH_BUDGET_STEPS = 14
HIDDEN_SEARCH_BASE_CHANCE = 0.22
HIDDEN_SEARCH_ATTEMPT_BONUS = 0.18
MAX_HIDDEN_SEARCH_CHANCE = 0.96


class FullAutonomousDescentError(ValueError):
    """Raised when autonomous orchestration would violate canonical truth."""


@dataclass(frozen=True)
class AutonomousRunResult:
    outcome: str
    steps_executed: int
    current_tick: int
    current_stratum_number: int
    surviving_descenders: int
    eliminated_descenders: int
    completed: bool
    extinguished: bool
    step_limit_reached: bool


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise FullAutonomousDescentError("Descent is missing 30A.5 autonomous metadata")
    if value.get("protocol") != PROTOCOL or value.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise FullAutonomousDescentError("full autonomous Descent protocol or version mismatch")
    if value.get("authoritative") is not True:
        raise FullAutonomousDescentError("autonomous orchestration must remain authoritative")
    if value.get("presentation_feedback_allowed") is not False:
        raise FullAutonomousDescentError("presentation feedback cannot steer canonical autonomy")
    if not isinstance(value.get("step_records"), list):
        raise FullAutonomousDescentError("autonomous step record structure is invalid")
    return value


def _record_body(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"digest", "ledger_event_id"}}


def _active_ids(descent: Descent) -> list[str]:
    return sorted(
        descender_id
        for descender_id, participant in descent.participants.items()
        if participant.status == ParticipationStatus.ACTIVE
        and participant.current_floor == descent.current_floor
    )


def _loot_cache_metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get("_loot_cache_relic")
    if not isinstance(value, dict):
        raise FullAutonomousDescentError("30A.5 requires accepted 30A.3 loot metadata")
    return value


def _survival_metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(SURVIVAL_METADATA_KEY)
    if not isinstance(value, dict):
        raise FullAutonomousDescentError("30A.5 requires accepted 30A.4 survival metadata")
    return value


def _managed_loot_ids(descent: Descent) -> set[str]:
    return {
        blueprint["id"]
        for cache in _loot_cache_metadata(descent).get("caches", [])
        for blueprint in cache.get("blueprints", [])
    }


def _managed_supply_ids(descent: Descent) -> set[str]:
    return {
        blueprint["id"]
        for cache in _survival_metadata(descent).get("supply_caches", [])
        for blueprint in cache.get("blueprints", [])
    }


def _supply_kind(descent: Descent, item_id: str) -> str | None:
    for cache in _survival_metadata(descent)["supply_caches"]:
        for blueprint in cache["blueprints"]:
            if blueprint["id"] == item_id:
                return str(blueprint["resource_kind"])
    return None


def _cache_for_current_stratum(descent: Descent) -> dict[str, Any] | None:
    candidates = [
        cache
        for cache in _loot_cache_metadata(descent).get("caches", [])
        if int(cache.get("stratum_number", 0)) == descent.current_floor
    ]
    return min(candidates, key=lambda value: value["cache_id"]) if candidates else None


def _known_safe_area_exists(descent: Descent, descender_id: str) -> bool:
    participant = descent.participants[descender_id]
    if participant.agent is None:
        return False
    floor = descent.floors[descent.current_floor]
    return any(
        knowledge.location_id in floor.locations and knowledge.believed_safe
        for knowledge in participant.agent.knowledge.values()
    )


def _decision_override(
    descent: Descent,
    descender_id: str,
    raw: CrawlerDecision,
) -> CrawlerDecision:
    participant = descent.participants[descender_id]
    state = _survival_metadata(descent)["descenders"][descender_id]
    minimum_resource = min(float(state["hydration"]), float(state["nutrition"]))
    cache = _cache_for_current_stratum(descent)
    floor_steps = int(_metadata(descent)["stratum_step_counts"].get(str(descent.current_floor), 0))
    cache_search_active = (
        cache is not None
        and cache.get("status") == "sealed"
        and floor_steps < CACHE_SEARCH_BUDGET_STEPS
    )

    # Once a Descender reaches an exit it stays there.  Before the bounded
    # search budget expires other Descenders may still search for a cache; after
    # the budget every non-exited Descender enters a deterministic exit phase.
    if participant.current_location_id in descent.floors[descent.current_floor].exit_location_ids:
        return CrawlerDecision("wait", 10.0, {"already_at_exit": 1.0})

    if floor_steps >= CACHE_SEARCH_BUDGET_STEPS:
        return CrawlerDecision("seek_exit", 10.0, {"bounded_search_complete": 1.0})

    if participant.gameplay.stamina <= SAFE_RECOVERY_STAMINA_THRESHOLD and _known_safe_area_exists(descent, descender_id):
        return CrawlerDecision("seek_safety", 9.0, {"canonical_stamina_pressure": 1.0})

    if minimum_resource <= CRITICAL_THRESHOLD:
        if cache_search_active:
            return CrawlerDecision("explore", 8.0, {"critical_survival_cache_search": 1.0})
        return CrawlerDecision("seek_exit", 8.0, {"critical_survival_exit_pressure": 1.0})

    if minimum_resource <= WARNING_THRESHOLD and cache_search_active:
        return CrawlerDecision("explore", 7.0, {"warning_survival_cache_search": 1.0})

    if cache_search_active and raw.action == "seek_exit":
        return CrawlerDecision("explore", raw.score + 1.0, {**raw.reasons, "bounded_cache_search": 1.0})

    if raw.action == "recover" and participant.current_location_id not in descent.floors[descent.current_floor].safe_area_ids:
        return CrawlerDecision(
            "seek_safety" if _known_safe_area_exists(descent, descender_id) else "explore",
            raw.score,
            {**raw.reasons, "recovery_requires_safe_area": 1.0},
        )
    return raw


def _deterministic_unit(*parts: object) -> float:
    digest = sha256(":".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64 - 1)


def _deliberate_search(descent: Descent, descender_id: str) -> str | None:
    """Give a stalled crawler a bounded deterministic chance to reveal one hidden edge."""
    participant = descent.participants[descender_id]
    agent = participant.agent
    current_id = participant.current_location_id
    if agent is None or current_id is None:
        return None
    floor = descent.floors[descent.current_floor]
    current = floor.locations[current_id]
    knowledge = agent.knowledge.get(current_id)
    known = set(knowledge.known_neighbors) if knowledge is not None else set()
    hidden = sorted(set(current.adjacency) - known)
    if not hidden:
        return None

    key = f"{descender_id}:{descent.current_floor}:{current_id}"
    attempts = _metadata(descent)["search_attempts"]
    attempt = int(attempts.get(key, 0)) + 1
    attempts[key] = attempt
    chance = min(
        MAX_HIDDEN_SEARCH_CHANCE,
        HIDDEN_SEARCH_BASE_CHANCE
        + attempt * HIDDEN_SEARCH_ATTEMPT_BONUS
        + agent.skills.perception * 0.20
        + agent.skills.navigation * 0.16,
    )
    ranked = sorted(
        hidden,
        key=lambda neighbor: (
            sha256(f"{descent.seed}:{descender_id}:{current_id}:{neighbor}:{attempt}".encode("utf-8")).hexdigest(),
            neighbor,
        ),
    )
    candidate = ranked[0]
    roll = _deterministic_unit(descent.seed, descender_id, current_id, candidate, attempt, "deliberate-search")
    if roll > chance:
        return None

    if knowledge is None:
        knowledge = LocationKnowledge(
            location_id=current_id,
            last_observed_tick=descent.current_tick,
            confidence=1.0,
            known_neighbors={},
            tags=list(current.environmental_tags),
            hazard_tags=list(current.hazards),
            believed_safe=current.kind in {LocationKind.ENTRANCE, LocationKind.SAFE_AREA},
            believed_exit=current.kind == LocationKind.EXIT,
            visits=1,
        )
        agent.knowledge[current_id] = knowledge
    knowledge.known_neighbors[candidate] = current.adjacency[candidate]
    neighbor = floor.locations[candidate]
    if candidate not in agent.knowledge:
        agent.knowledge[candidate] = LocationKnowledge(
            location_id=candidate,
            last_observed_tick=descent.current_tick,
            confidence=0.5,
            known_neighbors={},
            tags=[tag for tag in neighbor.environmental_tags if not tag.startswith("hidden_path:")],
            hazard_tags=[],
            believed_safe=neighbor.kind == LocationKind.SAFE_AREA,
            believed_exit=neighbor.kind == LocationKind.EXIT,
            visits=0,
        )
    return candidate


def _movement_cost(descent: Descent, descender_id: str, origin: str, destination: str) -> float:
    participant = descent.participants[descender_id]
    floor = descent.floors[participant.current_floor]
    cost = float(floor.locations[origin].adjacency[destination])
    participant.floor_statistics["moves"] = participant.floor_statistics.get("moves", 0.0) + 1.0
    participant.floor_statistics["distance_cost"] = participant.floor_statistics.get("distance_cost", 0.0) + cost
    stamina_cost = min(0.08, cost * 0.018)
    participant.gameplay.stamina = round(max(0.0, participant.gameplay.stamina - stamina_cost), 6)
    if participant.agent is not None:
        participant.agent.needs.stamina = participant.gameplay.stamina
        participant.agent.needs.hunger = min(1.0, participant.agent.needs.hunger + min(0.015, cost * 0.0025))
        destination_state = floor.locations[destination]
        participant.agent.needs.stress = min(
            1.0,
            participant.agent.needs.stress
            + floor.danger_level * 0.008
            + len(destination_state.hazards) * 0.012,
        )
    return round(cost, 6)


def validate_full_autonomous_descent(descent: Descent) -> bool:
    """Validate the orchestration trace without weakening any accepted source invariant."""
    validate_resources_survival(descent)
    metadata = _metadata(descent)
    if metadata.get("extends_slice") != "30A.4":
        raise FullAutonomousDescentError("30A.5 source-slice boundary changed")
    if metadata.get("decision_policy") != "deterministic-bounded-v1":
        raise FullAutonomousDescentError("autonomous decision policy changed")
    if int(metadata.get("step_count", -1)) != len(metadata["step_records"]):
        raise FullAutonomousDescentError("autonomous step count diverged from trace")
    if not isinstance(metadata.get("search_attempts"), dict) or not isinstance(metadata.get("stratum_step_counts"), dict):
        raise FullAutonomousDescentError("autonomous search/Stratum counters are invalid")

    history_ids = set(descent.history_event_ids)
    previous_tick = -1
    previous_index = -1
    for record in metadata["step_records"]:
        if not isinstance(record, dict):
            raise FullAutonomousDescentError("autonomous step record is invalid")
        index = int(record.get("step_index", -1))
        if index != previous_index + 1:
            raise FullAutonomousDescentError("autonomous step indices are not contiguous")
        if int(record.get("tick", -1)) < previous_tick:
            raise FullAutonomousDescentError("autonomous step ticks moved backwards")
        if record.get("digest") != payload_digest(_record_body(record)):
            raise FullAutonomousDescentError("autonomous step digest mismatch")
        event_id = record.get("ledger_event_id")
        if event_id not in history_ids:
            raise FullAutonomousDescentError("autonomous step is not bound to its Ledger event")
        actions = record.get("actions")
        if not isinstance(actions, list):
            raise FullAutonomousDescentError("autonomous action trace is invalid")
        for action in actions:
            if action.get("action") not in {"explore", "seek_exit", "seek_safety", "recover", "wait"}:
                raise FullAutonomousDescentError("autonomous action escaped the bounded policy")
        previous_tick = int(record["tick"])
        previous_index = index

    metrics = metadata.get("metrics")
    if not isinstance(metrics, dict):
        raise FullAutonomousDescentError("autonomous metrics are invalid")
    for key, value in metrics.items():
        if int(value) < 0:
            raise FullAutonomousDescentError(f"autonomous metric {key} cannot be negative")

    outcome = metadata.get("run_outcome")
    if outcome not in {"planned", "running", "completed", "extinguished"}:
        raise FullAutonomousDescentError("autonomous run outcome is invalid")
    if outcome == "planned" and descent.status != CrawlStatus.PLANNED:
        raise FullAutonomousDescentError("planned autonomous outcome disagrees with canonical Descent")
    if outcome == "running" and descent.status != CrawlStatus.RUNNING:
        raise FullAutonomousDescentError("running autonomous outcome disagrees with canonical Descent")
    if outcome == "completed" and descent.status != CrawlStatus.COMPLETED:
        raise FullAutonomousDescentError("completed autonomous outcome disagrees with canonical Descent")
    if outcome == "extinguished":
        if descent.status != CrawlStatus.RUNNING or _active_ids(descent):
            raise FullAutonomousDescentError("extinguished autonomous outcome must preserve a valid no-survivor source state")

    for event_key in ("initialized_event_id", "started_event_id", "terminal_event_id"):
        value = metadata.get(event_key)
        if value is not None and value not in history_ids:
            raise FullAutonomousDescentError("autonomous lifecycle event is missing from the Ledger")
    return True


def build_full_autonomous_snapshot(descent: Descent) -> dict[str, Any]:
    validate_full_autonomous_descent(descent)
    metadata = _metadata(descent)
    records = json.loads(canonical_json(metadata["step_records"]))
    body = {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "presentation_feedback_allowed": False,
        "descent_id": descent.id,
        "seed": descent.seed,
        "status": descent.status.value,
        "run_outcome": metadata["run_outcome"],
        "current_tick": descent.current_tick,
        "current_stratum_index": descent.current_floor - 1,
        "configured_stratum_count": len(descent.floors),
        "source_survival_snapshot_digest": build_resources_survival_snapshot(descent)["digest"],
        "step_count": metadata["step_count"],
        "step_records": records,
        "step_trace_digest": payload_digest(records),
        "metrics": dict(sorted(metadata["metrics"].items())),
        "stratum_step_counts": dict(sorted(metadata["stratum_step_counts"].items())),
        "surviving_descender_count": descent.surviving_crawler_count,
        "eliminated_descender_count": descent.eliminated_crawler_count,
        "active_current_stratum_count": len(_active_ids(descent)),
        "encounter_count": len(descent.encounters),
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
    }
    return {**body, "digest": payload_digest(body)}


class FullAutonomousDescentService:
    """Deterministic headless runner coordinating accepted 30A.1-30A.4 truth."""

    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence
        self.survival = ResourcesSurvivalService(persistence)
        self.lifecycle = self.survival.lifecycle

    def create(
        self,
        *,
        seed: str,
        descender_ids: Iterable[str],
        stratum_count: int = 4,
        descent_id: str | None = None,
    ) -> Descent:
        descent = self.survival.create(
            seed=seed,
            descender_ids=descender_ids,
            stratum_count=stratum_count,
            descent_id=descent_id,
        )
        encounter_ids: list[str] = []
        for number in sorted(descent.floors):
            encounter_ids.extend(seed_floor_encounters(descent, number))
        metadata = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "presentation_feedback_allowed": False,
            "extends_slice": "30A.4",
            "decision_policy": "deterministic-bounded-v1",
            "run_outcome": "planned",
            "step_count": 0,
            "step_records": [],
            "stratum_step_counts": {str(number): 0 for number in sorted(descent.floors)},
            "search_attempts": {},
            "seeded_encounter_ids": sorted(encounter_ids),
            "seeded_encounter_digest": payload_digest(sorted(encounter_ids)),
            "metrics": {
                "moves": 0,
                "waits": 0,
                "safe_recoveries": 0,
                "cache_opens": 0,
                "loot_claims": 0,
                "supply_claims": 0,
                "supply_consumptions": 0,
                "encounters_resolved": 0,
                "strata_advanced": 0,
                "hidden_paths_discovered": 0,
            },
            "initialized_event_id": None,
            "started_event_id": None,
            "terminal_event_id": None,
        }
        descent.modifiers[METADATA_KEY] = metadata
        event = self.lifecycle.record_event(
            descent,
            "FULL_AUTONOMOUS_DESCENT_INITIALIZED",
            "Deterministic full autonomous Descent orchestration initialized.",
            data={
                "protocol": PROTOCOL,
                "encounter_count": len(encounter_ids),
                "encounter_digest": metadata["seeded_encounter_digest"],
                "state_changes": {"autonomous_run_outcome": "planned"},
            },
        )
        metadata["initialized_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_full_autonomous_descent(descent)
        return descent

    def start(self, descent: Descent, *, tick: int = 0) -> Descent:
        validate_full_autonomous_descent(descent)
        if _metadata(descent)["run_outcome"] != "planned":
            raise FullAutonomousDescentError("only a planned autonomous Descent can start")
        self.survival.start(descent, tick=tick)
        metadata = _metadata(descent)
        metadata["run_outcome"] = "running"
        event = self.lifecycle.record_event(
            descent,
            "FULL_AUTONOMOUS_DESCENT_STARTED",
            "Autonomous Descent execution started.",
            actor_ids=_active_ids(descent),
            data={"state_changes": {"autonomous_run_outcome": "running"}},
        )
        metadata["started_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_full_autonomous_descent(descent)
        return descent

    def _consume_needed_supply(self, descent: Descent, descender_id: str) -> list[str]:
        participant = descent.participants[descender_id]
        state = _survival_metadata(descent)["descenders"][descender_id]
        consumed: list[str] = []
        needs = sorted(("hydration", "nutrition"), key=lambda kind: (float(state[kind]), kind))
        for kind in needs:
            if float(state[kind]) > AUTO_CONSUME_THRESHOLD:
                continue
            candidates = [
                item_id
                for item_id in participant.gameplay.inventory_item_ids
                if item_id in descent.items and _supply_kind(descent, item_id) == kind
            ]
            if not candidates:
                continue
            best = max(
                candidates,
                key=lambda item_id: (float(descent.items[item_id].effects.get(kind, 0.0)), item_id),
            )
            self.survival.consume_supply_item(descent, best, descender_id)
            consumed.append(best)
            _metadata(descent)["metrics"]["supply_consumptions"] += 1
        return consumed

    def _choose_and_move(self, descent: Descent, descender_id: str) -> dict[str, Any]:
        participant = descent.participants[descender_id]
        floor = descent.floors[descent.current_floor]
        if participant.agent is None:
            raise FullAutonomousDescentError("full autonomous Descent requires deterministic crawler agents")
        participant.agent.needs.stamina = participant.gameplay.stamina
        perceive(participant, floor, descent.current_tick)

        if (
            participant.current_location_id in floor.safe_area_ids
            and participant.gameplay.stamina <= SAFE_RECOVERY_STAMINA_THRESHOLD
        ):
            result = self.survival.recover_at_safe_area(descent, descender_id)
            participant.agent.needs.stamina = participant.gameplay.stamina
            _metadata(descent)["metrics"]["safe_recoveries"] += 1
            return {
                "descender_id": descender_id,
                "action": "recover",
                "origin_sector_id": participant.current_location_id,
                "destination_sector_id": participant.current_location_id,
                "edge_cost": 0.0,
                "recovered_stamina": round(float(result["after"]) - float(result["before"]), 6),
            }

        raw = choose_action(participant.agent, health=participant.health, seed=floor.seed)
        decision = _decision_override(descent, descender_id, raw)
        origin = participant.current_location_id
        destination = choose_destination(participant, floor, decision)
        hidden_discovery = None
        if destination == origin and decision.action in {"explore", "seek_safety", "seek_exit"}:
            hidden_discovery = _deliberate_search(descent, descender_id)
            if hidden_discovery is not None:
                _metadata(descent)["metrics"]["hidden_paths_discovered"] += 1
                self.lifecycle.record_event(
                    descent,
                    "AUTONOMOUS_HIDDEN_PATH_DISCOVERED",
                    f"Descender {descender_id} discovered a hidden traversal option.",
                    actor_ids=[descender_id],
                    location_id=origin,
                    data={
                        "discovered_sector_id": hidden_discovery,
                        "state_changes": {"navigation_knowledge_updated": True},
                    },
                )
                destination = choose_destination(participant, floor, decision)

        if destination is None or destination == origin:
            _metadata(descent)["metrics"]["waits"] += 1
            return {
                "descender_id": descender_id,
                "action": decision.action,
                "origin_sector_id": origin,
                "destination_sector_id": origin,
                "edge_cost": 0.0,
                "hidden_path_discovered": hidden_discovery,
            }

        if origin is None or destination not in floor.locations[origin].adjacency:
            raise FullAutonomousDescentError("autonomous navigation produced a non-adjacent destination")
        self.survival.commit_descender_position(descent, descender_id, destination)
        cost = _movement_cost(descent, descender_id, origin, destination)
        _metadata(descent)["metrics"]["moves"] += 1
        self.lifecycle.save(descent)
        return {
            "descender_id": descender_id,
            "action": decision.action,
            "origin_sector_id": origin,
            "destination_sector_id": destination,
            "edge_cost": cost,
            "hidden_path_discovered": hidden_discovery,
        }

    def _resolve_occupied_encounters(self, descent: Descent) -> list[str]:
        resolved: list[str] = []
        occupied = sorted(
            {
                descent.participants[descender_id].current_location_id
                for descender_id in _active_ids(descent)
                if descent.participants[descender_id].current_location_id is not None
            }
        )
        for location_id in occupied:
            if location_id in descent.floors[descent.current_floor].exit_location_ids:
                continue
            encounter = encounter_at(descent, descent.current_floor, location_id)
            if encounter is None:
                continue
            result = resolve_encounter(descent, encounter, self.lifecycle)
            if result.get("already_resolved"):
                continue
            resolved.append(encounter.id)
            _metadata(descent)["metrics"]["encounters_resolved"] += 1
            self.lifecycle.save(descent)
            validate_resources_survival(descent)
        return resolved

    def _open_reached_caches(self, descent: Descent) -> list[str]:
        opened: list[str] = []
        current = [
            cache
            for cache in _loot_cache_metadata(descent).get("caches", [])
            if cache.get("stratum_number") == descent.current_floor and cache.get("status") == "sealed"
        ]
        for cache in sorted(current, key=lambda value: value["cache_id"]):
            eligible = [
                descender_id
                for descender_id in _active_ids(descent)
                if descent.participants[descender_id].current_location_id == cache["sector_id"]
            ]
            if not eligible:
                continue
            opener = eligible[0]
            self.survival.open_cache(descent, cache["cache_id"], opener)
            opened.append(cache["cache_id"])
            _metadata(descent)["metrics"]["cache_opens"] += 1
        return opened

    def _collect_ground_items(self, descent: Descent) -> tuple[int, int, list[str]]:
        loot_ids = _managed_loot_ids(descent)
        supply_ids = _managed_supply_ids(descent)
        loot_claims = 0
        supply_claims = 0
        consumed: list[str] = []
        ground = sorted(
            (item for item in descent.items.values() if item.location_id is not None),
            key=lambda item: item.id,
        )
        for item in ground:
            location_id = item.location_id
            candidates = [
                descender_id
                for descender_id in _active_ids(descent)
                if descent.participants[descender_id].current_location_id == location_id
            ]
            if not candidates:
                continue
            if item.id in supply_ids:
                kind = _supply_kind(descent, item.id)
                if kind is None:
                    raise FullAutonomousDescentError("managed supply lost its resource kind")
                winner = min(
                    candidates,
                    key=lambda descender_id: (
                        float(_survival_metadata(descent)["descenders"][descender_id][kind]),
                        descender_id,
                    ),
                )
                self.survival.claim_supply_item(descent, item.id, winner)
                supply_claims += 1
                _metadata(descent)["metrics"]["supply_claims"] += 1
                consumed.extend(self._consume_needed_supply(descent, winner))
                continue
            if item.id in loot_ids:
                winner = max(
                    candidates,
                    key=lambda descender_id: (item_score(item, descent.participants[descender_id]), descender_id),
                )
                self.survival.claim_ground_item(descent, item.id, winner)
                loot_claims += 1
                _metadata(descent)["metrics"]["loot_claims"] += 1
                continue

            winner = max(
                candidates,
                key=lambda descender_id: (item_score(item, descent.participants[descender_id]), descender_id),
            )
            transfer_item_to_crawler(descent, item.id, winner)
            choose_and_equip(descent, winner)
            event = self.lifecycle.record_event(
                descent,
                "AUTONOMOUS_GROUND_LOOT_ACQUIRED",
                f"Descender {winner} autonomously acquired available ground loot.",
                actor_ids=[winner],
                location_id=location_id,
                data={"item_id": item.id, "state_changes": {"item_owner_descender_id": winner}},
            )
            item.provenance_event_ids.append(event.id)
            loot_claims += 1
            _metadata(descent)["metrics"]["loot_claims"] += 1
        self.lifecycle.save(descent)
        validate_resources_survival(descent)
        return loot_claims, supply_claims, consumed

    def step(self, descent: Descent) -> dict[str, Any]:
        validate_full_autonomous_descent(descent)
        metadata = _metadata(descent)
        if metadata["run_outcome"] != "running" or descent.status != CrawlStatus.RUNNING:
            raise FullAutonomousDescentError("autonomous step requires a running Descent")
        if not _active_ids(descent):
            metadata["run_outcome"] = "extinguished"
            event = self.lifecycle.record_event(
                descent,
                "FULL_AUTONOMOUS_DESCENT_EXTINGUISHED",
                "No active Descenders remain; autonomous execution terminated.",
                data={"state_changes": {"autonomous_run_outcome": "extinguished"}},
            )
            metadata["terminal_event_id"] = event.id
            self.lifecycle.save(descent)
            validate_full_autonomous_descent(descent)
            return {"outcome": "extinguished", "step_index": metadata["step_count"]}

        step_index = int(metadata["step_count"])
        stratum_before = descent.current_floor
        metadata["stratum_step_counts"][str(stratum_before)] = int(
            metadata["stratum_step_counts"].get(str(stratum_before), 0)
        ) + 1

        self.survival.advance_time(descent, descent.current_tick + 1)
        consumed_before_move: list[str] = []
        for descender_id in _active_ids(descent):
            consumed_before_move.extend(self._consume_needed_supply(descent, descender_id))

        actions: list[dict[str, Any]] = []
        for descender_id in list(_active_ids(descent)):
            if descent.participants[descender_id].status == ParticipationStatus.ACTIVE:
                actions.append(self._choose_and_move(descent, descender_id))

        encounters = self._resolve_occupied_encounters(descent)
        opened_caches = self._open_reached_caches(descent)
        loot_claims, supply_claims, consumed_after_move = self._collect_ground_items(descent)

        for descender_id in list(_active_ids(descent)):
            self._consume_needed_supply(descent, descender_id)
            participant = descent.participants[descender_id]
            if (
                participant.current_location_id in descent.floors[descent.current_floor].safe_area_ids
                and participant.gameplay.stamina <= SAFE_RECOVERY_STAMINA_THRESHOLD
            ):
                self.survival.recover_at_safe_area(descent, descender_id)
                _metadata(descent)["metrics"]["safe_recoveries"] += 1

        advanced = False
        completed = False
        if not _active_ids(descent):
            metadata["run_outcome"] = "extinguished"
            terminal = self.lifecycle.record_event(
                descent,
                "FULL_AUTONOMOUS_DESCENT_EXTINGUISHED",
                "All Descenders were eliminated during autonomous execution.",
                data={"state_changes": {"autonomous_run_outcome": "extinguished"}},
            )
            metadata["terminal_event_id"] = terminal.id
        else:
            floor = descent.floors[descent.current_floor]
            if all(
                descent.participants[descender_id].current_location_id in floor.exit_location_ids
                for descender_id in _active_ids(descent)
            ):
                if descent.current_floor == max(descent.floors):
                    self.survival.complete(descent, advance_ticks=0)
                    metadata["run_outcome"] = "completed"
                    completed = True
                    terminal = self.lifecycle.record_event(
                        descent,
                        "FULL_AUTONOMOUS_DESCENT_COMPLETED",
                        "Autonomous execution completed the final Stratum.",
                        actor_ids=sorted(
                            descender_id
                            for descender_id, participant in descent.participants.items()
                            if participant.status == ParticipationStatus.ADVANCED
                        ),
                        data={"state_changes": {"autonomous_run_outcome": "completed"}},
                    )
                    metadata["terminal_event_id"] = terminal.id
                else:
                    self.survival.advance(descent, advance_ticks=0)
                    metadata["metrics"]["strata_advanced"] += 1
                    advanced = True

        record = {
            "step_index": step_index,
            "tick": descent.current_tick,
            "stratum_before": stratum_before,
            "stratum_after": descent.current_floor,
            "actions": sorted(actions, key=lambda value: value["descender_id"]),
            "encounter_ids": sorted(encounters),
            "opened_cache_ids": sorted(opened_caches),
            "loot_claim_count": loot_claims,
            "supply_claim_count": supply_claims,
            "supply_consumption_count": len(consumed_before_move) + len(consumed_after_move),
            "advanced": advanced,
            "completed": completed,
            "run_outcome": metadata["run_outcome"],
            "surviving_descender_count": descent.surviving_crawler_count,
            "eliminated_descender_count": descent.eliminated_crawler_count,
        }
        record["digest"] = payload_digest(_record_body(record))
        step_event = self.lifecycle.record_event(
            descent,
            "AUTONOMOUS_STEP_RESOLVED",
            f"Autonomous Descent step {step_index} resolved deterministically.",
            actor_ids=_active_ids(descent),
            data={
                "step_index": step_index,
                "step_digest": record["digest"],
                "stratum_before": stratum_before,
                "stratum_after": descent.current_floor,
                "run_outcome": metadata["run_outcome"],
            },
        )
        record["ledger_event_id"] = step_event.id
        metadata["step_records"].append(record)
        metadata["step_count"] = step_index + 1
        self.lifecycle.save(descent)
        validate_full_autonomous_descent(descent)
        return record

    def run(
        self,
        descent: Descent,
        *,
        max_steps: int = 2_000,
        start_if_planned: bool = True,
    ) -> AutonomousRunResult:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        validate_full_autonomous_descent(descent)
        if _metadata(descent)["run_outcome"] == "planned":
            if not start_if_planned:
                raise FullAutonomousDescentError("planned autonomous Descent requires start_if_planned")
            self.start(descent, tick=descent.current_tick)

        executed = 0
        while executed < max_steps and _metadata(descent)["run_outcome"] == "running":
            self.step(descent)
            executed += 1

        outcome = str(_metadata(descent)["run_outcome"])
        return AutonomousRunResult(
            outcome=outcome,
            steps_executed=executed,
            current_tick=descent.current_tick,
            current_stratum_number=descent.current_floor,
            surviving_descenders=descent.surviving_crawler_count,
            eliminated_descenders=descent.eliminated_crawler_count,
            completed=outcome == "completed",
            extinguished=outcome == "extinguished",
            step_limit_reached=executed >= max_steps and outcome == "running",
        )

    def snapshot(self, descent: Descent) -> dict[str, Any]:
        return build_full_autonomous_snapshot(descent)
