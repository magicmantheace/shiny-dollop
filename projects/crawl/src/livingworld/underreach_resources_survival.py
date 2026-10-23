"""Canonical resources and survival pressure for Underreach Slice 30A.4.

30A.3 owns loot/cache/relic truth and 30A.2 owns sequential Stratum
progression.  This slice layers deterministic hydration/nutrition pressure and
canonical survival supplies onto the same mutable ``Descent`` object.

There is deliberately no duplicate stamina pool: ``participant.gameplay.stamina``
remains authoritative.  Unreal and all presentation systems remain downstream
consumers only.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterable

from .crawl_domain import CrawlStatus, ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .gameplay_domain import CrawlItem, ItemCategory, ItemRarity
from .item_system import transfer_item_to_crawler
from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_domain import Descent
from .underreach_loot_cache_relic import (
    LootCacheRelicService,
    build_loot_cache_relic_snapshot,
    validate_loot_cache_relic,
)


PROTOCOL = "underreach.resources-survival.v1"
IMPLEMENTATION_VERSION = "30a4.1"
SERIALIZATION_PROTOCOL = "underreach.resources-survival-serialization.v1"
METADATA_KEY = "_resources_survival"
HYDRATION_DRAIN_PER_TICK = 0.018
NUTRITION_DRAIN_PER_TICK = 0.010
WARNING_THRESHOLD = 0.45
CRITICAL_THRESHOLD = 0.18
STABLE_THRESHOLD = 0.70
STAMINA_WARNING_DRAIN_PER_TICK = 0.012
STAMINA_CRITICAL_DRAIN_PER_TICK = 0.018
STAMINA_STABLE_RECOVERY_PER_TICK = 0.006
HYDRATION_CRITICAL_HEALTH_DAMAGE_PER_TICK = 0.007
NUTRITION_CRITICAL_HEALTH_DAMAGE_PER_TICK = 0.004
MIN_SURVIVAL_HEALTH = 0.05
SAFE_REST_STAMINA_RECOVERY = 0.25
SUPPLIES_PER_CACHE = 2


class ResourcesSurvivalError(ValueError):
    """Raised when an operation violates the canonical 30A.4 survival contract."""


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _unit(*parts: object) -> float:
    digest = sha256(":".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64 - 1)


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise ResourcesSurvivalError("Descent is missing 30A.4 survival metadata")
    if value.get("protocol") != PROTOCOL or value.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise ResourcesSurvivalError("resources/survival protocol or version mismatch")
    if value.get("authoritative") is not True:
        raise ResourcesSurvivalError("resources/survival state must remain authoritative")
    if value.get("presentation_feedback_allowed") is not False:
        raise ResourcesSurvivalError("presentation feedback cannot mutate survival truth")
    if not isinstance(value.get("descenders"), dict) or not isinstance(value.get("supply_caches"), list):
        raise ResourcesSurvivalError("resources/survival metadata structure is invalid")
    return value


def _risk_band(hydration: float, nutrition: float) -> str:
    minimum = min(float(hydration), float(nutrition))
    if minimum <= CRITICAL_THRESHOLD:
        return "critical"
    if minimum <= WARNING_THRESHOLD:
        return "warning"
    return "stable"


def _initial_state(seed: str, descender_id: str) -> dict[str, Any]:
    hydration = round(0.84 + _unit(seed, descender_id, "hydration") * 0.14, 6)
    nutrition = round(0.82 + _unit(seed, descender_id, "nutrition") * 0.16, 6)
    return {
        "hydration": hydration,
        "nutrition": nutrition,
        "risk_band": _risk_band(hydration, nutrition),
        "warning_event_ids": [],
        "critical_event_ids": [],
        "consumption_event_ids": [],
        "recovery_event_ids": [],
        "total_health_damage": 0.0,
        "total_ticks_processed": 0,
    }


def _supply_blueprint(descent: Descent, source_cache: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind not in {"hydration", "nutrition"}:
        raise ResourcesSurvivalError("unknown survival supply kind")
    item_id = _stable_id("supply", descent.id, source_cache["cache_id"], kind)
    base = 0.46 if kind == "hydration" else 0.40
    spread = 0.10 if kind == "hydration" else 0.12
    amount = round(base + _unit(descent.seed, source_cache["cache_id"], kind) * spread, 6)
    blueprint = {
        "id": item_id,
        "name": "Sealed Water Flask" if kind == "hydration" else "Dense Field Ration",
        "resource_kind": kind,
        "category": ItemCategory.RESOURCE.value,
        "rarity": ItemRarity.COMMON.value,
        "effects": {kind: amount},
        "important": False,
    }
    blueprint["blueprint_digest"] = payload_digest({k: v for k, v in blueprint.items() if k != "blueprint_digest"})
    return blueprint


def _supply_generation_projection(caches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "source_cache_id": cache["source_cache_id"],
            "stratum_number": cache["stratum_number"],
            "sector_id": cache["sector_id"],
            "blueprints": cache["blueprints"],
        }
        for cache in caches
    ]


def _supply_cache_for_source(descent: Descent, source_cache_id: str) -> dict[str, Any]:
    for cache in _metadata(descent)["supply_caches"]:
        if cache["source_cache_id"] == source_cache_id:
            return cache
    raise KeyError(f"No 30A.4 survival supplies are bound to cache {source_cache_id!r}")


def _supply_cache_for_item(descent: Descent, item_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for cache in _metadata(descent)["supply_caches"]:
        for blueprint in cache["blueprints"]:
            if blueprint["id"] == item_id:
                return cache, blueprint
    raise KeyError(f"Supply item {item_id!r} is not managed by 30A.4")


def _loot_cache_map(descent: Descent) -> dict[str, dict[str, Any]]:
    loot = descent.modifiers.get("_loot_cache_relic", {})
    caches = loot.get("caches", []) if isinstance(loot, dict) else []
    return {cache["cache_id"]: cache for cache in caches}


def _materialize_supply(blueprint: dict[str, Any], location_id: str) -> CrawlItem:
    return CrawlItem(
        id=blueprint["id"],
        name=blueprint["name"],
        category=ItemCategory.RESOURCE,
        rarity=ItemRarity.COMMON,
        effects=dict(blueprint["effects"]),
        location_id=location_id,
        important=False,
    )


def _supply_matches_blueprint(item: CrawlItem, blueprint: dict[str, Any]) -> bool:
    return (
        item.id == blueprint["id"]
        and item.name == blueprint["name"]
        and item.category == ItemCategory.RESOURCE
        and item.rarity == ItemRarity.COMMON
        and item.slot is None
        and item.effects == blueprint["effects"]
        and item.important is False
    )


def validate_resources_survival(descent: Descent) -> bool:
    """Validate survival pools, supply holders, cache binding, and event history."""
    validate_loot_cache_relic(descent)
    Descent.model_validate(descent.model_dump(mode="python"))
    metadata = _metadata(descent)
    descender_states = metadata["descenders"]
    expected_ids = sorted(descent.participants)
    if sorted(descender_states) != expected_ids:
        raise ResourcesSurvivalError("survival Descender roster diverged from canonical participants")
    if metadata.get("roster_digest") != payload_digest(expected_ids):
        raise ResourcesSurvivalError("survival roster digest mismatch")
    if int(metadata.get("last_processed_tick", -1)) != descent.current_tick:
        raise ResourcesSurvivalError("survival clock is not synchronized to canonical tick")

    for descender_id in expected_ids:
        state = descender_states[descender_id]
        for field in ("hydration", "nutrition"):
            value = float(state.get(field, -1.0))
            if not 0.0 <= value <= 1.0:
                raise ResourcesSurvivalError(f"{descender_id} has invalid {field}")
        expected_band = _risk_band(state["hydration"], state["nutrition"])
        if state.get("risk_band") != expected_band:
            raise ResourcesSurvivalError("survival risk band diverged from canonical resource pools")
        if float(state.get("total_health_damage", -1.0)) < 0.0 or int(state.get("total_ticks_processed", -1)) < 0:
            raise ResourcesSurvivalError("survival accumulated counters are invalid")
        for key in ("warning_event_ids", "critical_event_ids", "consumption_event_ids", "recovery_event_ids"):
            values = state.get(key)
            if not isinstance(values, list) or values != list(dict.fromkeys(values)):
                raise ResourcesSurvivalError("survival event history is invalid")
            if set(values) - set(descent.history_event_ids):
                raise ResourcesSurvivalError("survival event history references a foreign Ledger event")

    supply_caches = metadata["supply_caches"]
    loot_caches = _loot_cache_map(descent)
    if len(supply_caches) != len(loot_caches):
        raise ResourcesSurvivalError("survival supply cache count must mirror 30A.3 caches")
    if metadata.get("supply_generation_digest") != payload_digest(_supply_generation_projection(supply_caches)):
        raise ResourcesSurvivalError("deterministic survival supply generation digest mismatch")

    supply_ids: set[str] = set()
    for supply_cache in supply_caches:
        source_id = supply_cache.get("source_cache_id")
        source = loot_caches.get(source_id)
        if source is None:
            raise ResourcesSurvivalError("survival supplies reference an unknown 30A.3 cache")
        if supply_cache.get("stratum_number") != source.get("stratum_number") or supply_cache.get("sector_id") != source.get("sector_id"):
            raise ResourcesSurvivalError("survival supply origin diverged from its source cache")
        blueprints = supply_cache.get("blueprints")
        if not isinstance(blueprints, list) or len(blueprints) != SUPPLIES_PER_CACHE:
            raise ResourcesSurvivalError("survival cache supply count changed")
        kinds = sorted(blueprint.get("resource_kind") for blueprint in blueprints)
        if kinds != ["hydration", "nutrition"]:
            raise ResourcesSurvivalError("each survival cache must contain hydration and nutrition supplies")
        local_ids: list[str] = []
        for blueprint in blueprints:
            body = {k: v for k, v in blueprint.items() if k != "blueprint_digest"}
            if blueprint.get("blueprint_digest") != payload_digest(body):
                raise ResourcesSurvivalError("survival supply blueprint digest mismatch")
            item_id = blueprint.get("id")
            if not isinstance(item_id, str) or item_id in supply_ids:
                raise ResourcesSurvivalError("survival supply IDs must be globally unique")
            supply_ids.add(item_id)
            local_ids.append(item_id)
            if blueprint.get("category") != ItemCategory.RESOURCE.value or blueprint.get("rarity") != ItemRarity.COMMON.value:
                raise ResourcesSurvivalError("survival supply item identity changed")
            amount = float((blueprint.get("effects") or {}).get(blueprint["resource_kind"], 0.0))
            if not 0.0 < amount <= 1.0:
                raise ResourcesSurvivalError("survival supply replenishment amount is invalid")

        materialized = supply_cache.get("materialized_item_ids")
        claimed = supply_cache.get("claimed_item_ids")
        consumed = supply_cache.get("consumed_item_ids")
        if any(not isinstance(values, list) for values in (materialized, claimed, consumed)):
            raise ResourcesSurvivalError("survival supply tracking structure is invalid")
        for values in (materialized, claimed, consumed):
            if values != sorted(values) or len(values) != len(set(values)):
                raise ResourcesSurvivalError("survival supply tracking must be sorted and unique")
        if not set(claimed).issubset(materialized) or not set(consumed).issubset(claimed):
            raise ResourcesSurvivalError("survival supply lifecycle references invalid items")

        source_open = source.get("status") in {"opened", "depleted"}
        if not source_open:
            if supply_cache.get("status") != "sealed" or materialized or claimed or consumed:
                raise ResourcesSurvivalError("sealed loot cache cannot expose survival supplies")
        else:
            if supply_cache.get("status") not in {"opened", "depleted"}:
                raise ResourcesSurvivalError("opened loot cache must expose its survival supplies")
            if set(materialized) != set(local_ids):
                raise ResourcesSurvivalError("opened survival supply cache must materialize every blueprint")
            event_id = supply_cache.get("revealed_event_id")
            if event_id not in descent.history_event_ids:
                raise ResourcesSurvivalError("survival supply reveal lacks canonical Ledger provenance")
            expected_status = "depleted" if set(consumed) == set(materialized) else "opened"
            if supply_cache.get("status") != expected_status:
                raise ResourcesSurvivalError("survival supply cache status disagrees with consumption state")

        for item_id in materialized:
            if item_id in consumed:
                if item_id in descent.items:
                    raise ResourcesSurvivalError("consumed survival supply still exists as a CrawlItem")
                continue
            item = descent.items.get(item_id)
            if item is None:
                raise ResourcesSurvivalError("materialized survival supply disappeared without consumption")
            blueprint = next(value for value in blueprints if value["id"] == item_id)
            if not _supply_matches_blueprint(item, blueprint):
                raise ResourcesSurvivalError("materialized survival supply diverged from blueprint")
            if item.location_id is not None:
                origin_stratum = int(supply_cache["stratum_number"])
                matching_strata = sorted(
                    number
                    for number, floor in descent.floors.items()
                    if item.location_id in floor.locations
                )
                if not matching_strata:
                    raise ResourcesSurvivalError("ground survival supply has invalid canonical Sector")
                if all(number < origin_stratum for number in matching_strata):
                    raise ResourcesSurvivalError("ground survival supply cannot precede its origin Stratum")
            if item.owner_npc_id is not None:
                if item.owner_npc_id not in descent.participants:
                    raise ResourcesSurvivalError("survival supply owner is not a participating Descender")
                if item_id not in descent.participants[item.owner_npc_id].gameplay.inventory_item_ids:
                    raise ResourcesSurvivalError("owned survival supply is missing from canonical inventory")

        for key in ("acquisition_event_ids", "consumption_event_ids"):
            mapping = supply_cache.get(key)
            if not isinstance(mapping, dict):
                raise ResourcesSurvivalError("survival supply provenance mapping is invalid")
            for item_id, event_ids in mapping.items():
                if item_id not in local_ids or not isinstance(event_ids, list) or set(event_ids) - set(descent.history_event_ids):
                    raise ResourcesSurvivalError("survival supply provenance references invalid data")

    if metadata.get("initialized_event_id") not in descent.history_event_ids:
        raise ResourcesSurvivalError("survival initialization is not bound to the canonical Ledger")
    return True


def build_resources_survival_snapshot(descent: Descent) -> dict[str, Any]:
    validate_resources_survival(descent)
    metadata = _metadata(descent)
    states = json.loads(canonical_json(metadata["descenders"]))
    supply_caches = json.loads(canonical_json(metadata["supply_caches"]))
    managed_ids = sorted({bp["id"] for cache in supply_caches for bp in cache["blueprints"]})
    live_items = [descent.items[item_id].model_dump(mode="json") for item_id in managed_ids if item_id in descent.items]
    bands = {"stable": 0, "warning": 0, "critical": 0}
    for state in states.values():
        bands[state["risk_band"]] += 1
    body = {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "presentation_feedback_allowed": False,
        "descent_id": descent.id,
        "seed": descent.seed,
        "status": descent.status.value,
        "current_tick": descent.current_tick,
        "current_stratum_index": descent.current_floor - 1,
        "source_loot_snapshot_digest": build_loot_cache_relic_snapshot(descent)["digest"],
        "roster_digest": metadata["roster_digest"],
        "supply_generation_digest": metadata["supply_generation_digest"],
        "descender_states": states,
        "survival_state_digest": payload_digest(states),
        "risk_band_counts": bands,
        "supply_caches": supply_caches,
        "supply_cache_count": len(supply_caches),
        "revealed_supply_cache_count": sum(cache["status"] != "sealed" for cache in supply_caches),
        "depleted_supply_cache_count": sum(cache["status"] == "depleted" for cache in supply_caches),
        "materialized_supply_count": sum(len(cache["materialized_item_ids"]) for cache in supply_caches),
        "claimed_supply_count": sum(len(cache["claimed_item_ids"]) for cache in supply_caches),
        "consumed_supply_count": sum(len(cache["consumed_item_ids"]) for cache in supply_caches),
        "live_supply_items": live_items,
        "live_supply_items_digest": payload_digest(live_items),
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
    }
    return {**body, "digest": payload_digest(body)}


def serialize_resources_survival(descent: Descent) -> str:
    snapshot = build_resources_survival_snapshot(descent)
    body = {
        "protocol": SERIALIZATION_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_state": descent.model_dump(mode="json"),
        "canonical_descent_fingerprint": descent.fingerprint(),
        "survival_snapshot_digest": snapshot["digest"],
        "survival_state_digest": snapshot["survival_state_digest"],
        "history_event_ids_digest": snapshot["history_event_ids_digest"],
    }
    return canonical_json({**body, "digest": payload_digest(body)})


def restore_resources_survival(value: str | dict[str, Any]) -> Descent:
    try:
        payload = json.loads(value) if isinstance(value, str) else dict(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ResourcesSurvivalError("invalid resources/survival serialization") from exc
    if payload.get("protocol") != SERIALIZATION_PROTOCOL:
        raise ResourcesSurvivalError("unsupported resources/survival serialization protocol")
    body = {key: item for key, item in payload.items() if key != "digest"}
    if payload.get("digest") != payload_digest(body):
        raise ResourcesSurvivalError("resources/survival serialization digest mismatch")
    try:
        descent = Descent.model_validate(payload.get("canonical_state"))
    except Exception as exc:
        raise ResourcesSurvivalError("serialized canonical Descent state is invalid") from exc
    validate_resources_survival(descent)
    snapshot = build_resources_survival_snapshot(descent)
    if descent.fingerprint() != payload.get("canonical_descent_fingerprint"):
        raise ResourcesSurvivalError("serialized Descent fingerprint mismatch")
    if snapshot["digest"] != payload.get("survival_snapshot_digest"):
        raise ResourcesSurvivalError("serialized survival snapshot digest mismatch")
    if snapshot["survival_state_digest"] != payload.get("survival_state_digest"):
        raise ResourcesSurvivalError("serialized survival state digest mismatch")
    if snapshot["history_event_ids_digest"] != payload.get("history_event_ids_digest"):
        raise ResourcesSurvivalError("serialized survival Ledger digest mismatch")
    return descent


class ResourcesSurvivalService:
    """Authoritative 30A.4 facade layered on accepted 30A.3 loot/progression."""

    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence
        self.loot = LootCacheRelicService(persistence)
        self.lifecycle = self.loot.lifecycle

    def create(
        self,
        *,
        seed: str,
        descender_ids: Iterable[str],
        stratum_count: int = 4,
        descent_id: str | None = None,
    ) -> Descent:
        descent = self.loot.create(
            seed=seed,
            descender_ids=descender_ids,
            stratum_count=stratum_count,
            descent_id=descent_id,
        )
        loot_caches = sorted(_loot_cache_map(descent).values(), key=lambda value: value["cache_id"])
        supply_caches: list[dict[str, Any]] = []
        for source in loot_caches:
            blueprints = sorted(
                [_supply_blueprint(descent, source, "hydration"), _supply_blueprint(descent, source, "nutrition")],
                key=lambda value: value["id"],
            )
            supply_caches.append({
                "source_cache_id": source["cache_id"],
                "stratum_number": source["stratum_number"],
                "sector_id": source["sector_id"],
                "status": "sealed",
                "blueprints": blueprints,
                "revealed_event_id": None,
                "materialized_item_ids": [],
                "claimed_item_ids": [],
                "consumed_item_ids": [],
                "acquisition_event_ids": {},
                "consumption_event_ids": {},
            })
        supply_caches.sort(key=lambda value: value["source_cache_id"])
        states = {descender_id: _initial_state(descent.seed, descender_id) for descender_id in sorted(descent.participants)}
        metadata = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "presentation_feedback_allowed": False,
            "extends_slice": "30A.3",
            "full_autonomous_owner_slice": "30A.5",
            "roster_digest": payload_digest(sorted(descent.participants)),
            "drain_rates": {
                "hydration_per_tick": HYDRATION_DRAIN_PER_TICK,
                "nutrition_per_tick": NUTRITION_DRAIN_PER_TICK,
            },
            "thresholds": {
                "warning": WARNING_THRESHOLD,
                "critical": CRITICAL_THRESHOLD,
                "stable": STABLE_THRESHOLD,
            },
            "last_processed_tick": descent.current_tick,
            "descenders": states,
            "supply_caches": supply_caches,
            "supply_generation_digest": payload_digest(_supply_generation_projection(supply_caches)),
        }
        descent.modifiers[METADATA_KEY] = metadata
        event = self.lifecycle.record_event(
            descent,
            "RESOURCES_SURVIVAL_INITIALIZED",
            "Canonical hydration, nutrition, stamina coupling, and survival supplies initialized.",
            data={
                "protocol": PROTOCOL,
                "supply_cache_count": len(supply_caches),
                "supply_generation_digest": metadata["supply_generation_digest"],
                "state_changes": {"resources_survival_initialized": True},
            },
        )
        metadata["initialized_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_resources_survival(descent)
        return descent

    def start(self, descent: Descent, *, tick: int = 0) -> Descent:
        validate_resources_survival(descent)
        self.loot.start(descent, tick=tick)
        _metadata(descent)["last_processed_tick"] = descent.current_tick
        self.lifecycle.save(descent)
        validate_resources_survival(descent)
        return descent

    def commit_descender_position(self, descent: Descent, descender_id: str, sector_id: str) -> Descent:
        validate_resources_survival(descent)
        self.loot.commit_descender_position(descent, descender_id, sector_id)
        validate_resources_survival(descent)
        return descent

    def open_cache(self, descent: Descent, cache_id: str, descender_id: str) -> list[str]:
        validate_resources_survival(descent)
        loot_item_ids = self.loot.open_cache(descent, cache_id, descender_id)
        supply_cache = _supply_cache_for_source(descent, cache_id)
        if supply_cache["status"] == "sealed":
            materialized: list[str] = []
            for blueprint in supply_cache["blueprints"]:
                if blueprint["id"] in descent.items:
                    raise ResourcesSurvivalError("survival supply attempted to reuse an existing item ID")
                descent.items[blueprint["id"]] = _materialize_supply(blueprint, supply_cache["sector_id"])
                materialized.append(blueprint["id"])
            materialized.sort()
            supply_cache["materialized_item_ids"] = materialized
            supply_cache["status"] = "opened"
            event = self.lifecycle.record_event(
                descent,
                "SURVIVAL_SUPPLIES_REVEALED",
                f"Cache {cache_id} exposed deterministic survival supplies.",
                actor_ids=[descender_id],
                location_id=supply_cache["sector_id"],
                data={
                    "source_cache_id": cache_id,
                    "item_ids": materialized,
                    "state_changes": {"survival_supply_cache_status": "opened"},
                },
            )
            supply_cache["revealed_event_id"] = event.id
            for item_id in materialized:
                descent.items[item_id].provenance_event_ids.append(event.id)
            self.lifecycle.save(descent)
        validate_resources_survival(descent)
        return loot_item_ids

    def supply_item_ids_for_cache(self, descent: Descent, cache_id: str) -> list[str]:
        validate_resources_survival(descent)
        return list(_supply_cache_for_source(descent, cache_id)["materialized_item_ids"])

    def claim_supply_item(self, descent: Descent, item_id: str, descender_id: str) -> CrawlItem:
        validate_resources_survival(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise ResourcesSurvivalError("survival supply acquisition requires an active Descent")
        supply_cache, blueprint = _supply_cache_for_item(descent, item_id)
        if supply_cache["status"] == "sealed" or item_id not in supply_cache["materialized_item_ids"]:
            raise ResourcesSurvivalError("survival supply has not been revealed")
        if item_id in supply_cache["consumed_item_ids"]:
            raise ResourcesSurvivalError("survival supply was already consumed")
        item = descent.items.get(item_id)
        if item is None or item.location_id is None or item.owner_npc_id is not None:
            raise ResourcesSurvivalError("survival supply is not available as ground loot")
        participant = descent.participants.get(descender_id)
        if participant is None:
            raise KeyError(f"Descender {descender_id!r} is not participating")
        if participant.status != ParticipationStatus.ACTIVE or participant.current_floor != descent.current_floor:
            raise ResourcesSurvivalError("only an active current-Stratum Descender can acquire survival supplies")
        if participant.current_location_id != item.location_id:
            raise ResourcesSurvivalError("Descender must occupy the supply Sector to acquire it")
        transfer_item_to_crawler(descent, item_id, descender_id)
        event = self.lifecycle.record_event(
            descent,
            "SURVIVAL_SUPPLY_ACQUIRED",
            f"Descender {descender_id} acquired {item.name}.",
            actor_ids=[descender_id],
            location_id=participant.current_location_id,
            data={
                "item_id": item_id,
                "resource_kind": blueprint["resource_kind"],
                "source_cache_id": supply_cache["source_cache_id"],
                "state_changes": {"item_owner_descender_id": descender_id},
            },
        )
        item.provenance_event_ids.append(event.id)
        if item_id not in supply_cache["claimed_item_ids"]:
            supply_cache["claimed_item_ids"].append(item_id)
            supply_cache["claimed_item_ids"].sort()
        supply_cache["acquisition_event_ids"].setdefault(item_id, []).append(event.id)
        self.lifecycle.save(descent)
        validate_resources_survival(descent)
        return item

    def consume_supply_item(self, descent: Descent, item_id: str, descender_id: str) -> dict[str, Any]:
        validate_resources_survival(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise ResourcesSurvivalError("survival supply consumption requires an active Descent")
        supply_cache, blueprint = _supply_cache_for_item(descent, item_id)
        item = descent.items.get(item_id)
        if item is None or item.owner_npc_id != descender_id:
            raise ResourcesSurvivalError("Descender does not own the requested survival supply")
        participant = descent.participants.get(descender_id)
        if participant is None or participant.status != ParticipationStatus.ACTIVE:
            raise ResourcesSurvivalError("only an active Descender can consume survival supplies")
        state = _metadata(descent)["descenders"][descender_id]
        kind = blueprint["resource_kind"]
        amount = float(blueprint["effects"][kind])
        before = float(state[kind])
        after = min(1.0, before + amount)
        state[kind] = round(after, 6)
        previous_band = state["risk_band"]
        state["risk_band"] = _risk_band(state["hydration"], state["nutrition"])
        participant.gameplay.inventory_item_ids.remove(item_id)
        participant.gameplay.equipment = {slot: value for slot, value in participant.gameplay.equipment.items() if value != item_id}
        del descent.items[item_id]
        if item_id not in supply_cache["consumed_item_ids"]:
            supply_cache["consumed_item_ids"].append(item_id)
            supply_cache["consumed_item_ids"].sort()
        if set(supply_cache["consumed_item_ids"]) == set(supply_cache["materialized_item_ids"]):
            supply_cache["status"] = "depleted"
        event = self.lifecycle.record_event(
            descent,
            "SURVIVAL_RESOURCE_CONSUMED",
            f"Descender {descender_id} consumed {blueprint['name']}.",
            actor_ids=[descender_id],
            location_id=participant.current_location_id,
            data={
                "item_id": item_id,
                "resource_kind": kind,
                "resource_before": round(before, 6),
                "resource_after": round(after, 6),
                "resource_amount": amount,
                "risk_band_before": previous_band,
                "risk_band_after": state["risk_band"],
                "source_cache_id": supply_cache["source_cache_id"],
                "state_changes": {kind: round(after, 6), "risk_band": state["risk_band"]},
            },
        )
        state["consumption_event_ids"].append(event.id)
        supply_cache["consumption_event_ids"].setdefault(item_id, []).append(event.id)
        self.lifecycle.save(descent)
        validate_resources_survival(descent)
        return {
            "item_id": item_id,
            "resource_kind": kind,
            "before": round(before, 6),
            "after": round(after, 6),
            "event_id": event.id,
        }

    def advance_time(self, descent: Descent, to_tick: int) -> Descent:
        """Apply deterministic survival pressure for every elapsed canonical tick."""
        validate_resources_survival(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise ResourcesSurvivalError("survival time can advance only during an active Descent")
        target = int(to_tick)
        if target < descent.current_tick:
            raise ResourcesSurvivalError("survival time cannot move backwards")
        delta = target - descent.current_tick
        if delta == 0:
            return descent
        metadata = _metadata(descent)
        states = metadata["descenders"]
        floor = descent.floors[descent.current_floor]
        hydration_rate = HYDRATION_DRAIN_PER_TICK * (1.0 + float(floor.danger_level) * 0.35)
        nutrition_rate = NUTRITION_DRAIN_PER_TICK * (1.0 + float(floor.danger_level) * 0.15)
        previous_bands = {descender_id: states[descender_id]["risk_band"] for descender_id in states}
        health_damaged: set[str] = set()
        active_ids = sorted(
            descender_id
            for descender_id, participant in descent.participants.items()
            if participant.status == ParticipationStatus.ACTIVE and participant.current_floor == descent.current_floor
        )
        for _ in range(delta):
            for descender_id in active_ids:
                participant = descent.participants[descender_id]
                state = states[descender_id]
                state["hydration"] = round(max(0.0, float(state["hydration"]) - hydration_rate), 6)
                state["nutrition"] = round(max(0.0, float(state["nutrition"]) - nutrition_rate), 6)
                band = _risk_band(state["hydration"], state["nutrition"])
                if band == "critical":
                    stamina_drain = STAMINA_CRITICAL_DRAIN_PER_TICK
                elif band == "warning":
                    stamina_drain = STAMINA_WARNING_DRAIN_PER_TICK
                else:
                    stamina_drain = -STAMINA_STABLE_RECOVERY_PER_TICK if min(state["hydration"], state["nutrition"]) >= STABLE_THRESHOLD else 0.0
                participant.gameplay.stamina = round(max(0.0, min(1.0, participant.gameplay.stamina - stamina_drain)), 6)
                damage = 0.0
                if state["hydration"] <= CRITICAL_THRESHOLD:
                    damage += HYDRATION_CRITICAL_HEALTH_DAMAGE_PER_TICK
                if state["nutrition"] <= CRITICAL_THRESHOLD:
                    damage += NUTRITION_CRITICAL_HEALTH_DAMAGE_PER_TICK
                if damage > 0.0:
                    before_health = participant.health
                    participant.health = round(max(MIN_SURVIVAL_HEALTH, participant.health - damage), 6)
                    actual = max(0.0, before_health - participant.health)
                    state["total_health_damage"] = round(float(state["total_health_damage"]) + actual, 6)
                    if actual > 0.0:
                        health_damaged.add(descender_id)
                state["risk_band"] = band
                state["total_ticks_processed"] = int(state["total_ticks_processed"]) + 1

        self.loot.set_tick(descent, target)
        metadata["last_processed_tick"] = descent.current_tick
        warning_ids = sorted(descender_id for descender_id in active_ids if states[descender_id]["risk_band"] == "warning")
        critical_ids = sorted(descender_id for descender_id in active_ids if states[descender_id]["risk_band"] == "critical")
        aggregate = self.lifecycle.record_event(
            descent,
            "SURVIVAL_TIME_APPLIED",
            f"Applied {delta} deterministic survival tick(s) on Stratum {descent.current_floor}.",
            actor_ids=active_ids,
            data={
                "delta_ticks": delta,
                "stratum_number": descent.current_floor,
                "hydration_drain_per_tick": round(hydration_rate, 8),
                "nutrition_drain_per_tick": round(nutrition_rate, 8),
                "warning_descender_ids": warning_ids,
                "critical_descender_ids": critical_ids,
                "health_damaged_descender_ids": sorted(health_damaged),
                "state_changes": {"current_tick": descent.current_tick},
            },
        )
        for descender_id in active_ids:
            before = previous_bands[descender_id]
            after = states[descender_id]["risk_band"]
            if before != after and after in {"warning", "critical"}:
                event = self.lifecycle.record_event(
                    descent,
                    "SURVIVAL_THRESHOLD_REACHED",
                    f"Descender {descender_id} entered {after} survival pressure.",
                    actor_ids=[descender_id],
                    location_id=descent.participants[descender_id].current_location_id,
                    data={
                        "from_band": before,
                        "to_band": after,
                        "hydration": states[descender_id]["hydration"],
                        "nutrition": states[descender_id]["nutrition"],
                        "source_survival_tick_event_id": aggregate.id,
                    },
                )
                states[descender_id]["warning_event_ids" if after == "warning" else "critical_event_ids"].append(event.id)
        self.lifecycle.save(descent)
        validate_resources_survival(descent)
        return descent

    def recover_at_safe_area(self, descent: Descent, descender_id: str) -> dict[str, Any]:
        validate_resources_survival(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise ResourcesSurvivalError("safe recovery requires an active Descent")
        participant = descent.participants.get(descender_id)
        if participant is None or participant.status != ParticipationStatus.ACTIVE or participant.current_floor != descent.current_floor:
            raise ResourcesSurvivalError("safe recovery requires an active current-Stratum Descender")
        floor = descent.floors[descent.current_floor]
        if participant.current_location_id not in floor.safe_area_ids:
            raise ResourcesSurvivalError("Descender must occupy a canonical safe area to recover")
        before = participant.gameplay.stamina
        participant.gameplay.stamina = round(min(1.0, before + SAFE_REST_STAMINA_RECOVERY), 6)
        event = self.lifecycle.record_event(
            descent,
            "SURVIVAL_SAFE_RECOVERY",
            f"Descender {descender_id} recovered stamina in a safe area.",
            actor_ids=[descender_id],
            location_id=participant.current_location_id,
            data={
                "stamina_before": before,
                "stamina_after": participant.gameplay.stamina,
                "state_changes": {"stamina": participant.gameplay.stamina},
            },
        )
        _metadata(descent)["descenders"][descender_id]["recovery_event_ids"].append(event.id)
        self.lifecycle.save(descent)
        validate_resources_survival(descent)
        return {"before": before, "after": participant.gameplay.stamina, "event_id": event.id}

    def claim_ground_item(self, descent: Descent, item_id: str, descender_id: str) -> CrawlItem:
        validate_resources_survival(descent)
        item = self.loot.claim_ground_item(descent, item_id, descender_id)
        validate_resources_survival(descent)
        return item

    def drop_owned_item(self, descent: Descent, item_id: str, descender_id: str) -> CrawlItem:
        validate_resources_survival(descent)
        item = self.loot.drop_owned_item(descent, item_id, descender_id)
        validate_resources_survival(descent)
        return item

    def advance(self, descent: Descent, *, advance_ticks: int = 1) -> Descent:
        validate_resources_survival(descent)
        if advance_ticks < 0:
            raise ResourcesSurvivalError("advance_ticks cannot be negative")
        if advance_ticks:
            self.advance_time(descent, descent.current_tick + int(advance_ticks))
        self.loot.advance(descent, advance_ticks=0)
        _metadata(descent)["last_processed_tick"] = descent.current_tick
        self.lifecycle.record_event(
            descent,
            "SURVIVAL_STRATUM_CARRIED_FORWARD",
            "Canonical survival state carried unchanged into the next Stratum.",
            actor_ids=sorted(
                descender_id
                for descender_id, participant in descent.participants.items()
                if participant.status == ParticipationStatus.ACTIVE and participant.current_floor == descent.current_floor
            ),
            data={"stratum_number": descent.current_floor, "state_changes": {"current_stratum_index": descent.current_floor - 1}},
        )
        self.lifecycle.save(descent)
        validate_resources_survival(descent)
        return descent

    def complete(self, descent: Descent, *, advance_ticks: int = 0) -> Descent:
        validate_resources_survival(descent)
        if advance_ticks < 0:
            raise ResourcesSurvivalError("advance_ticks cannot be negative")
        if advance_ticks:
            self.advance_time(descent, descent.current_tick + int(advance_ticks))
        self.loot.complete(descent, advance_ticks=0)
        _metadata(descent)["last_processed_tick"] = descent.current_tick
        self.lifecycle.save(descent)
        validate_resources_survival(descent)
        return descent

    def snapshot(self, descent: Descent) -> dict[str, Any]:
        return build_resources_survival_snapshot(descent)

    def serialize(self, descent: Descent) -> str:
        return serialize_resources_survival(descent)

    def restore(self, value: str | dict[str, Any]) -> Descent:
        return restore_resources_survival(value)
