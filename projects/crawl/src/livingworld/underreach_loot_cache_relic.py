"""Canonical loot, cache, and relic foundation for Underreach Slice 30A.3.

30A.2 owns sequential multi-Stratum progression.  This slice extends the same
mutable authoritative ``Descent`` object with deterministic sealed caches,
materialized CrawlItems, unique relic identity, and item provenance.

Sealed cache contents exist as deterministic blueprints, not loose CrawlItems.
That prevents existing ground-loot collection code from bypassing the cache-open
contract.  Opening a cache materializes its contents at the cache Sector; all
subsequent ownership/location changes use the established CrawlItem invariant of
exactly one owner, world location, or encounter holder.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Iterable

from .crawl_domain import CrawlStatus, ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .gameplay_domain import CrawlItem, EquipmentSlot, ItemCategory, ItemRarity
from .item_system import choose_and_equip, drop_item, generate_item, transfer_item_to_crawler
from .runtime_checkpoint import canonical_json, payload_digest
from .underreach_domain import Descent
from .underreach_multi_stratum_progression import (
    MultiStratumProgressionService,
    build_multi_stratum_snapshot,
    validate_multi_stratum_descent,
)


PROTOCOL = "underreach.loot-cache-relic.v1"
IMPLEMENTATION_VERSION = "30a3.1"
METADATA_KEY = "_loot_cache_relic"
CACHE_COUNT_PER_STRATUM = 1
ORDINARY_ITEMS_PER_CACHE = 2
RELIC_ITEMS_PER_CACHE = 1


class LootCacheRelicError(ValueError):
    """Raised when an operation violates the canonical 30A.3 loot contract."""


def _stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def _unit(*parts: object) -> float:
    digest = sha256(":".join(str(part) for part in parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64 - 1)


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise LootCacheRelicError("Descent is missing 30A.3 loot metadata")
    if value.get("protocol") != PROTOCOL:
        raise LootCacheRelicError("loot/cache/relic protocol mismatch")
    if value.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise LootCacheRelicError("loot/cache/relic implementation version mismatch")
    if value.get("authoritative") is not True:
        raise LootCacheRelicError("loot/cache/relic state must remain authoritative")
    if value.get("presentation_feedback_allowed") is not False:
        raise LootCacheRelicError("presentation feedback cannot mutate canonical loot")
    caches = value.get("caches")
    relics = value.get("relics")
    if not isinstance(caches, list) or not isinstance(relics, dict):
        raise LootCacheRelicError("loot/cache/relic metadata structure is invalid")
    return value


def _blueprint_body(blueprint: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in blueprint.items() if key != "blueprint_digest"}


def _blueprint_digest(blueprint: dict[str, Any]) -> str:
    return payload_digest(_blueprint_body(blueprint))


def _ordinary_blueprint(descent: Descent, cache_id: str, stratum_number: int, index: int) -> dict[str, Any]:
    preview = generate_item(
        descent.seed,
        source_id=cache_id,
        index=index,
        floor_number=stratum_number,
        holder=cache_id,
    )
    value = preview.model_dump(mode="json")
    value.pop("owner_npc_id", None)
    value.pop("location_id", None)
    value.pop("encounter_id", None)
    value.pop("provenance_event_ids", None)
    blueprint = {
        "kind": "ordinary",
        **value,
    }
    blueprint["blueprint_digest"] = _blueprint_digest(blueprint)
    return blueprint


def _relic_blueprint(descent: Descent, cache_id: str, stratum_number: int) -> dict[str, Any]:
    adjectives = ("Ashen", "Hollow", "Veiled", "Iron", "Gloam", "Runed")
    nouns = ("Compass", "Seal", "Keystone", "Lens", "Ember", "Talisman")
    adjective = adjectives[min(len(adjectives) - 1, int(_unit(descent.seed, cache_id, "relic-adj") * len(adjectives)))]
    noun = nouns[min(len(nouns) - 1, int(_unit(descent.seed, cache_id, "relic-noun") * len(nouns)))]
    item_id = _stable_id("relic", descent.seed, cache_id, stratum_number)
    scale = 1.0 + stratum_number * 0.035
    blueprint = {
        "kind": "relic",
        "relic_key": f"underreach.relic.{sha256(item_id.encode('utf-8')).hexdigest()[:16]}",
        "id": item_id,
        "name": f"{adjective} {noun}",
        "category": ItemCategory.TRINKET.value,
        "rarity": ItemRarity.EPIC.value,
        "slot": EquipmentSlot.TRINKET.value,
        "stats": {
            "defense": round((0.025 + _unit(descent.seed, cache_id, "defense") * 0.025) * scale, 4),
            "evasion": round((0.018 + _unit(descent.seed, cache_id, "evasion") * 0.020) * scale, 4),
            "stamina": round((0.035 + _unit(descent.seed, cache_id, "stamina") * 0.035) * scale, 4),
        },
        "effects": {},
        "durability": 1.0,
        "requirements": {},
        "important": True,
    }
    blueprint["blueprint_digest"] = _blueprint_digest(blueprint)
    return blueprint


def _cache_candidates(descent: Descent, stratum_number: int) -> list[tuple[str, str]]:
    stratum = descent.floors[stratum_number]
    result: list[tuple[str, str]] = []
    for sector_id, sector in sorted(stratum.locations.items()):
        if sector_id == stratum.entrance_location_id or sector_id in stratum.exit_location_ids:
            continue
        for node in sorted(sector.loot_resource_nodes):
            result.append((sector_id, node))
    if not result:
        raise LootCacheRelicError(f"Stratum {stratum_number} has no eligible cache Sector")
    return result


def _build_cache(descent: Descent, stratum_number: int, cache_index: int) -> dict[str, Any]:
    candidates = _cache_candidates(descent, stratum_number)
    ranked = sorted(
        candidates,
        key=lambda value: (
            sha256(f"{descent.seed}:{stratum_number}:{cache_index}:{value[0]}:{value[1]}".encode("utf-8")).hexdigest(),
            value,
        ),
    )
    sector_id, source_node = ranked[cache_index % len(ranked)]
    cache_id = _stable_id("cache", descent.id, stratum_number, sector_id, cache_index)
    blueprints = [
        _ordinary_blueprint(descent, cache_id, stratum_number, index)
        for index in range(ORDINARY_ITEMS_PER_CACHE)
    ]
    blueprints.extend(_relic_blueprint(descent, cache_id, stratum_number) for _ in range(RELIC_ITEMS_PER_CACHE))
    blueprints.sort(key=lambda value: value["id"])
    return {
        "cache_id": cache_id,
        "stratum_index": stratum_number - 1,
        "stratum_number": stratum_number,
        "sector_id": sector_id,
        "source_node": source_node,
        "status": "sealed",
        "blueprints": blueprints,
        "opener_descender_id": None,
        "opened_tick": None,
        "opened_event_id": None,
        "materialized_item_ids": [],
        "claimed_item_ids": [],
    }


def _generation_projection(caches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "cache_id": cache["cache_id"],
            "stratum_index": cache["stratum_index"],
            "stratum_number": cache["stratum_number"],
            "sector_id": cache["sector_id"],
            "source_node": cache["source_node"],
            "blueprints": cache["blueprints"],
        }
        for cache in caches
    ]


def _cache_by_id(descent: Descent, cache_id: str) -> dict[str, Any]:
    for cache in _metadata(descent)["caches"]:
        if cache.get("cache_id") == cache_id:
            return cache
    raise KeyError(f"Cache {cache_id!r} does not exist")


def _cache_for_item(descent: Descent, item_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    for cache in _metadata(descent)["caches"]:
        for blueprint in cache["blueprints"]:
            if blueprint["id"] == item_id:
                return cache, blueprint
    raise KeyError(f"Item {item_id!r} is not managed by 30A.3")


def _materialize_blueprint(blueprint: dict[str, Any], location_id: str) -> CrawlItem:
    return CrawlItem(
        id=blueprint["id"],
        name=blueprint["name"],
        category=blueprint["category"],
        rarity=blueprint["rarity"],
        slot=blueprint.get("slot"),
        stats=dict(blueprint.get("stats") or {}),
        effects=dict(blueprint.get("effects") or {}),
        durability=float(blueprint.get("durability", 1.0)),
        requirements=dict(blueprint.get("requirements") or {}),
        location_id=location_id,
        provenance_event_ids=[],
        important=bool(blueprint.get("important", False)),
    )


def _item_matches_blueprint(item: CrawlItem, blueprint: dict[str, Any]) -> bool:
    expected = {
        "id": blueprint["id"],
        "name": blueprint["name"],
        "category": blueprint["category"],
        "rarity": blueprint["rarity"],
        "slot": blueprint.get("slot"),
        "stats": blueprint.get("stats") or {},
        "effects": blueprint.get("effects") or {},
        "durability": float(blueprint.get("durability", 1.0)),
        "requirements": blueprint.get("requirements") or {},
        "important": bool(blueprint.get("important", False)),
    }
    actual = item.model_dump(mode="json")
    actual = {key: actual[key] for key in expected}
    return canonical_json(actual) == canonical_json(expected)


def validate_loot_cache_relic(descent: Descent) -> bool:
    """Validate cache generation, materialized item holders, and relic provenance."""
    validate_multi_stratum_descent(descent)
    Descent.model_validate(descent.model_dump(mode="python"))
    metadata = _metadata(descent)
    caches = metadata["caches"]
    if len(caches) != len(descent.floors) * CACHE_COUNT_PER_STRATUM:
        raise LootCacheRelicError("cache count does not match configured Strata")
    if metadata.get("cache_generation_digest") != payload_digest(_generation_projection(caches)):
        raise LootCacheRelicError("deterministic cache generation digest mismatch")

    cache_ids: set[str] = set()
    blueprint_ids: set[str] = set()
    relic_blueprint_ids: set[str] = set()
    history_ids = set(descent.history_event_ids)

    for cache in caches:
        cache_id = cache.get("cache_id")
        if not isinstance(cache_id, str) or not cache_id or cache_id in cache_ids:
            raise LootCacheRelicError("cache IDs must be unique and non-empty")
        cache_ids.add(cache_id)
        number = int(cache.get("stratum_number", 0))
        if number not in descent.floors or cache.get("stratum_index") != number - 1:
            raise LootCacheRelicError("cache Stratum identity is invalid")
        if cache.get("sector_id") not in descent.floors[number].locations:
            raise LootCacheRelicError("cache Sector does not exist")
        if cache.get("status") not in {"sealed", "opened", "depleted"}:
            raise LootCacheRelicError("cache status is invalid")
        blueprints = cache.get("blueprints")
        if not isinstance(blueprints, list) or len(blueprints) != ORDINARY_ITEMS_PER_CACHE + RELIC_ITEMS_PER_CACHE:
            raise LootCacheRelicError("cache blueprint count changed")
        local_ids: list[str] = []
        for blueprint in blueprints:
            if blueprint.get("blueprint_digest") != _blueprint_digest(blueprint):
                raise LootCacheRelicError("cache item blueprint digest mismatch")
            item_id = blueprint.get("id")
            if not isinstance(item_id, str) or item_id in blueprint_ids:
                raise LootCacheRelicError("cache blueprint item IDs must be globally unique")
            blueprint_ids.add(item_id)
            local_ids.append(item_id)
            if blueprint.get("kind") == "relic":
                relic_blueprint_ids.add(item_id)
                if blueprint.get("category") != ItemCategory.TRINKET.value:
                    raise LootCacheRelicError("relic foundation requires trinket relics")
                if blueprint.get("rarity") != ItemRarity.EPIC.value or blueprint.get("important") is not True:
                    raise LootCacheRelicError("relic identity must remain epic and important")
                if not blueprint.get("relic_key"):
                    raise LootCacheRelicError("relic blueprint is missing stable relic identity")
            elif blueprint.get("kind") != "ordinary":
                raise LootCacheRelicError("unknown cache blueprint kind")

        materialized = cache.get("materialized_item_ids")
        claimed = cache.get("claimed_item_ids")
        if not isinstance(materialized, list) or not isinstance(claimed, list):
            raise LootCacheRelicError("cache materialized/claimed item tracking is invalid")
        if materialized != sorted(materialized) or claimed != sorted(claimed):
            raise LootCacheRelicError("cache item tracking must use canonical sorted order")
        if len(materialized) != len(set(materialized)) or len(claimed) != len(set(claimed)):
            raise LootCacheRelicError("cache item tracking cannot contain duplicates")
        if not set(materialized).issubset(local_ids) or not set(claimed).issubset(materialized):
            raise LootCacheRelicError("cache item tracking references foreign items")

        if cache["status"] == "sealed":
            if materialized or claimed or cache.get("opened_event_id") is not None or cache.get("opener_descender_id") is not None:
                raise LootCacheRelicError("sealed cache contains opened-state data")
        else:
            if set(materialized) != set(local_ids):
                raise LootCacheRelicError("opened cache must materialize every blueprint exactly once")
            if cache.get("opened_event_id") not in history_ids:
                raise LootCacheRelicError("opened cache is missing its canonical Ledger event")
            if cache.get("opener_descender_id") not in descent.participants or cache.get("opened_tick") is None:
                raise LootCacheRelicError("opened cache opener/tick is invalid")
            expected_status = "depleted" if set(claimed) == set(materialized) else "opened"
            if cache["status"] != expected_status:
                raise LootCacheRelicError("cache status disagrees with initial-claim completion")

        for item_id in materialized:
            item = descent.items.get(item_id)
            if item is None:
                raise LootCacheRelicError("materialized cache item disappeared from canonical state")
            blueprint = next(value for value in blueprints if value["id"] == item_id)
            if not _item_matches_blueprint(item, blueprint):
                raise LootCacheRelicError("materialized item definition diverged from its cache blueprint")
            if len(item.provenance_event_ids) != len(set(item.provenance_event_ids)):
                raise LootCacheRelicError("item provenance cannot contain duplicate Ledger events")
            if set(item.provenance_event_ids) - history_ids:
                raise LootCacheRelicError("item provenance references missing Ledger events")

    relics = metadata["relics"]
    if set(relics) != relic_blueprint_ids:
        raise LootCacheRelicError("relic registry does not exactly cover relic blueprints")
    for item_id, record in relics.items():
        cache, blueprint = _cache_for_item(descent, item_id)
        if record.get("relic_key") != blueprint.get("relic_key"):
            raise LootCacheRelicError("relic registry identity diverged from blueprint")
        if record.get("origin_cache_id") != cache["cache_id"] or record.get("origin_sector_id") != cache["sector_id"]:
            raise LootCacheRelicError("relic origin provenance diverged")
        if record.get("origin_stratum_number") != cache["stratum_number"]:
            raise LootCacheRelicError("relic origin Stratum diverged")
        discovery = record.get("discovery_event_id")
        if discovery is not None and discovery not in history_ids:
            raise LootCacheRelicError("relic discovery event is missing from Ledger")
        acquisitions = record.get("acquisition_event_ids")
        if not isinstance(acquisitions, list) or acquisitions != list(dict.fromkeys(acquisitions)):
            raise LootCacheRelicError("relic acquisition provenance is invalid")
        if set(acquisitions) - history_ids:
            raise LootCacheRelicError("relic acquisition provenance references missing Ledger events")

    managed_materialized = {item_id for cache in caches for item_id in cache["materialized_item_ids"]}
    if managed_materialized - set(descent.items):
        raise LootCacheRelicError("managed materialized items are missing")
    return True


def build_loot_cache_relic_snapshot(descent: Descent) -> dict[str, Any]:
    validate_loot_cache_relic(descent)
    metadata = _metadata(descent)
    caches = json.loads(canonical_json(metadata["caches"]))
    relics = json.loads(canonical_json(metadata["relics"]))
    managed_ids = sorted({blueprint["id"] for cache in caches for blueprint in cache["blueprints"]})
    materialized_ids = sorted(item_id for item_id in managed_ids if item_id in descent.items)
    item_states = [
        descent.items[item_id].model_dump(mode="json")
        for item_id in materialized_ids
    ]
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
        "source_progression_snapshot_digest": build_multi_stratum_snapshot(descent)["digest"],
        "cache_generation_digest": metadata["cache_generation_digest"],
        "cache_count": len(caches),
        "sealed_cache_count": sum(cache["status"] == "sealed" for cache in caches),
        "opened_cache_count": sum(cache["status"] == "opened" for cache in caches),
        "depleted_cache_count": sum(cache["status"] == "depleted" for cache in caches),
        "blueprint_item_count": len(managed_ids),
        "materialized_item_count": len(materialized_ids),
        "owned_item_count": sum(descent.items[item_id].owner_npc_id is not None for item_id in materialized_ids),
        "ground_item_count": sum(descent.items[item_id].location_id is not None for item_id in materialized_ids),
        "relic_blueprint_count": len(relics),
        "materialized_relic_count": sum(item_id in descent.items for item_id in relics),
        "owned_relic_count": sum(item_id in descent.items and descent.items[item_id].owner_npc_id is not None for item_id in relics),
        "caches": caches,
        "relics": relics,
        "materialized_items": item_states,
        "materialized_items_digest": payload_digest(item_states),
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
    }
    return {**body, "digest": payload_digest(body)}


class LootCacheRelicService:
    """Authoritative 30A.3 facade layered on accepted multi-Stratum progression."""

    def __init__(self, persistence: CrawlPersistence | None = None) -> None:
        self.persistence = persistence
        self.progression = MultiStratumProgressionService(persistence)
        self.lifecycle = self.progression.lifecycle

    def create(
        self,
        *,
        seed: str,
        descender_ids: Iterable[str],
        stratum_count: int = 4,
        descent_id: str | None = None,
    ) -> Descent:
        descent = self.progression.create(
            seed=seed,
            descender_ids=descender_ids,
            stratum_count=stratum_count,
            descent_id=descent_id,
        )
        caches = [
            _build_cache(descent, number, cache_index)
            for number in range(1, len(descent.floors) + 1)
            for cache_index in range(CACHE_COUNT_PER_STRATUM)
        ]
        caches.sort(key=lambda value: value["cache_id"])
        relics: dict[str, dict[str, Any]] = {}
        for cache in caches:
            for blueprint in cache["blueprints"]:
                if blueprint["kind"] == "relic":
                    relics[blueprint["id"]] = {
                        "item_id": blueprint["id"],
                        "relic_key": blueprint["relic_key"],
                        "origin_cache_id": cache["cache_id"],
                        "origin_stratum_index": cache["stratum_index"],
                        "origin_stratum_number": cache["stratum_number"],
                        "origin_sector_id": cache["sector_id"],
                        "discovery_event_id": None,
                        "acquisition_event_ids": [],
                    }
        metadata = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "presentation_feedback_allowed": False,
            "extends_slice": "30A.2",
            "resource_survival_owner_slice": "30A.4",
            "cache_count_per_stratum": CACHE_COUNT_PER_STRATUM,
            "ordinary_items_per_cache": ORDINARY_ITEMS_PER_CACHE,
            "relic_items_per_cache": RELIC_ITEMS_PER_CACHE,
            "caches": caches,
            "relics": dict(sorted(relics.items())),
            "cache_generation_digest": payload_digest(_generation_projection(caches)),
        }
        descent.modifiers[METADATA_KEY] = metadata
        event = self.lifecycle.record_event(
            descent,
            "LOOT_CACHE_RELIC_INITIALIZED",
            "Canonical deterministic cache and relic foundation initialized.",
            data={
                "protocol": PROTOCOL,
                "cache_count": len(caches),
                "relic_count": len(relics),
                "cache_generation_digest": metadata["cache_generation_digest"],
                "state_changes": {"loot_cache_relic_initialized": True},
            },
        )
        metadata["initialized_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_loot_cache_relic(descent)
        return descent

    def start(self, descent: Descent, *, tick: int = 0) -> Descent:
        validate_loot_cache_relic(descent)
        self.progression.start(descent, tick=tick)
        validate_loot_cache_relic(descent)
        return descent

    def set_tick(self, descent: Descent, tick: int) -> Descent:
        validate_loot_cache_relic(descent)
        self.progression.set_tick(descent, tick)
        validate_loot_cache_relic(descent)
        return descent

    def commit_descender_position(self, descent: Descent, descender_id: str, sector_id: str) -> Descent:
        validate_loot_cache_relic(descent)
        self.progression.commit_descender_position(descent, descender_id, sector_id)
        validate_loot_cache_relic(descent)
        return descent

    def cache_ids_for_stratum(self, descent: Descent, stratum_number: int) -> list[str]:
        validate_loot_cache_relic(descent)
        return sorted(
            cache["cache_id"]
            for cache in _metadata(descent)["caches"]
            if cache["stratum_number"] == stratum_number
        )

    def open_cache(self, descent: Descent, cache_id: str, descender_id: str) -> list[str]:
        validate_loot_cache_relic(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise LootCacheRelicError("cache opening requires an active Descent")
        cache = _cache_by_id(descent, cache_id)
        if cache["stratum_number"] != descent.current_floor:
            raise LootCacheRelicError("only a cache in the current Stratum can be opened")
        participant = descent.participants.get(descender_id)
        if participant is None:
            raise KeyError(f"Descender {descender_id!r} is not participating")
        if participant.status != ParticipationStatus.ACTIVE or participant.current_floor != descent.current_floor:
            raise LootCacheRelicError("only an active current-Stratum Descender can open a cache")
        if participant.current_location_id != cache["sector_id"]:
            raise LootCacheRelicError("Descender must occupy the cache Sector to open it")
        if cache["status"] != "sealed":
            return list(cache["materialized_item_ids"])

        materialized: list[str] = []
        for blueprint in cache["blueprints"]:
            item_id = blueprint["id"]
            if item_id in descent.items:
                raise LootCacheRelicError("cache attempted to materialize an existing item ID")
            descent.items[item_id] = _materialize_blueprint(blueprint, cache["sector_id"])
            materialized.append(item_id)
        materialized.sort()
        cache["status"] = "opened"
        cache["opener_descender_id"] = descender_id
        cache["opened_tick"] = descent.current_tick
        cache["materialized_item_ids"] = materialized
        event = self.lifecycle.record_event(
            descent,
            "CACHE_OPENED",
            f"Descender {descender_id} opened cache {cache_id}.",
            actor_ids=[descender_id],
            location_id=cache["sector_id"],
            data={
                "cache_id": cache_id,
                "stratum_number": cache["stratum_number"],
                "item_ids": materialized,
                "state_changes": {"cache_status": "opened"},
            },
        )
        cache["opened_event_id"] = event.id
        relics = _metadata(descent)["relics"]
        for item_id in materialized:
            descent.items[item_id].provenance_event_ids.append(event.id)
            if item_id in relics:
                relics[item_id]["discovery_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_loot_cache_relic(descent)
        return materialized

    def claim_ground_item(self, descent: Descent, item_id: str, descender_id: str) -> CrawlItem:
        validate_loot_cache_relic(descent)
        if descent.status != CrawlStatus.RUNNING:
            raise LootCacheRelicError("item acquisition requires an active Descent")
        cache, blueprint = _cache_for_item(descent, item_id)
        if item_id not in cache["materialized_item_ids"] or cache["status"] == "sealed":
            raise LootCacheRelicError("cache item has not been materialized")
        item = descent.items.get(item_id)
        if item is None or item.location_id is None or item.owner_npc_id is not None or item.encounter_id is not None:
            raise LootCacheRelicError("item is not currently available as ground loot")
        participant = descent.participants.get(descender_id)
        if participant is None:
            raise KeyError(f"Descender {descender_id!r} is not participating")
        if participant.status != ParticipationStatus.ACTIVE or participant.current_floor != descent.current_floor:
            raise LootCacheRelicError("only an active current-Stratum Descender can acquire loot")
        if participant.current_location_id != item.location_id:
            raise LootCacheRelicError("Descender must occupy the item's Sector to acquire it")

        first_claim = item_id not in cache["claimed_item_ids"]
        transfer_item_to_crawler(descent, item_id, descender_id)
        choose_and_equip(descent, descender_id)
        event = self.lifecycle.record_event(
            descent,
            "ITEM_ACQUIRED",
            f"Descender {descender_id} acquired {item.name}.",
            actor_ids=[descender_id],
            location_id=participant.current_location_id,
            data={
                "item_id": item_id,
                "item_kind": blueprint["kind"],
                "source_cache_id": cache["cache_id"],
                "origin_stratum_number": cache["stratum_number"],
                "first_cache_claim": first_claim,
                "rarity": item.rarity.value,
                "state_changes": {"item_owner_descender_id": descender_id},
            },
        )
        item.provenance_event_ids.append(event.id)
        if first_claim:
            cache["claimed_item_ids"].append(item_id)
            cache["claimed_item_ids"].sort()
        if set(cache["claimed_item_ids"]) == set(cache["materialized_item_ids"]):
            cache["status"] = "depleted"
        if blueprint["kind"] == "relic":
            relic = _metadata(descent)["relics"][item_id]
            relic["acquisition_event_ids"].append(event.id)
        self.lifecycle.save(descent)
        validate_loot_cache_relic(descent)
        return item

    def drop_owned_item(self, descent: Descent, item_id: str, descender_id: str) -> CrawlItem:
        validate_loot_cache_relic(descent)
        _cache_for_item(descent, item_id)
        item = descent.items.get(item_id)
        if item is None or item.owner_npc_id != descender_id:
            raise LootCacheRelicError("Descender does not own the requested managed item")
        participant = descent.participants.get(descender_id)
        if participant is None or participant.current_location_id is None:
            raise LootCacheRelicError("item owner has no valid canonical Sector")
        location_id = participant.current_location_id
        drop_item(descent, item_id, location_id)
        event = self.lifecycle.record_event(
            descent,
            "ITEM_DROPPED",
            f"Descender {descender_id} dropped {item.name}.",
            actor_ids=[descender_id],
            location_id=location_id,
            data={
                "item_id": item_id,
                "state_changes": {"item_owner_descender_id": None, "item_location_id": location_id},
            },
        )
        item.provenance_event_ids.append(event.id)
        self.lifecycle.save(descent)
        validate_loot_cache_relic(descent)
        return item

    def advance(self, descent: Descent, *, advance_ticks: int = 1) -> Descent:
        validate_loot_cache_relic(descent)
        self.progression.advance(descent, advance_ticks=advance_ticks)
        validate_loot_cache_relic(descent)
        return descent

    def complete(self, descent: Descent, *, advance_ticks: int = 0) -> Descent:
        validate_loot_cache_relic(descent)
        self.progression.complete(descent, advance_ticks=advance_ticks)
        validate_loot_cache_relic(descent)
        return descent

    def snapshot(self, descent: Descent) -> dict[str, Any]:
        return build_loot_cache_relic_snapshot(descent)
