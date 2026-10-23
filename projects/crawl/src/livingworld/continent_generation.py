from __future__ import annotations

import math
import random

from .domain import (
    Continent,
    DiplomaticRelation,
    Landmark,
    Position,
    Region,
    Relationship,
    TradeRoute,
    WorldDate,
    WorldState,
)
from .generation import generate_world


REGION_NAMES = [
    "Frostmere Reach",
    "The Verdant Crown",
    "Aster Lowlands",
    "Ironspine March",
    "Sunward Basin",
    "Ember Coast",
]
REGION_CLIMATES = [
    "cool_temperate",
    "cool_temperate",
    "temperate",
    "temperate",
    "warm_temperate",
    "warm_temperate",
]
CONTINENT_KINGDOM_NAMES = [
    "Avarra",
    "Thornwatch",
    "Kharad-Dun",
    "Veloria",
    "Sundermere",
    "Emberfall",
]


def _partition(total: int, parts: int) -> list[int]:
    base, remainder = divmod(total, parts)
    return [base + (1 if index < remainder else 0) for index in range(parts)]


def _distance(a: Position, b: Position) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def generate_continent_world(
    seed: str,
    name: str,
    *,
    target_population: int = 100_000,
    persistent_npcs: int = 500,
    kingdoms: int = 6,
    towns: int = 30,
    villages: int = 120,
) -> WorldState:
    """Generate the v0.2 continent target while preserving the v0.1 simulation contract.

    v0.1's well-tested two-kingdom generator is used as a deterministic building block.
    Three generated strips are remapped into one continent containing six political
    regions. All IDs and references are rewritten so the resulting WorldState is a
    normal authoritative world that the existing simulation engine can advance.
    """
    if kingdoms != 6:
        raise ValueError("v0.2 continent generation currently requires exactly 6 kingdoms")
    if towns < kingdoms:
        raise ValueError("at least one town per kingdom is required")
    if persistent_npcs < kingdoms * 2:
        raise ValueError("at least two persistent NPCs per kingdom are required")

    rng = random.Random(f"continent:{seed}")
    pair_count = kingdoms // 2
    population_parts = _partition(target_population, pair_count)
    npc_parts = _partition(persistent_npcs, pair_count)
    town_parts = _partition(towns, pair_count)
    village_parts = _partition(villages, pair_count)

    cultures = {}
    religions = {}
    merged_kingdoms = {}
    settlements = {}
    npcs = {}
    trade_routes = {}
    armies = {}
    wars = {}
    regions: dict[str, Region] = {}
    used_settlement_names: set[str] = set()

    next_culture = 1
    next_religion = 1
    next_kingdom = 1
    next_settlement = 1
    next_npc = 1
    next_army = 1
    next_trade = 1
    next_landmark = 1

    for strip_index in range(pair_count):
        chunk = generate_world(
            seed=f"{seed}:strip:{strip_index}",
            name=f"{name} Strip {strip_index + 1}",
            target_population=population_parts[strip_index],
            persistent_npcs=npc_parts[strip_index],
            towns=town_parts[strip_index],
            villages=village_parts[strip_index],
        )

        culture_map: dict[str, str] = {}
        for old_id in sorted(chunk.cultures):
            new_id = f"culture_{next_culture:04d}"
            culture_map[old_id] = new_id
            culture = chunk.cultures[old_id].model_copy(deep=True)
            culture.id = new_id
            culture.name = f"{culture.name} of {REGION_NAMES[next_culture - 1]}"
            cultures[new_id] = culture
            next_culture += 1

        religion_map: dict[str, str] = {}
        for old_id in sorted(chunk.religions):
            new_id = f"religion_{next_religion:04d}"
            religion_map[old_id] = new_id
            religion = chunk.religions[old_id].model_copy(deep=True)
            religion.id = new_id
            religion.name = f"{religion.name} of {REGION_NAMES[next_religion - 1]}"
            religions[new_id] = religion
            next_religion += 1

        kingdom_map: dict[str, str] = {}
        region_by_old_kingdom: dict[str, str] = {}
        for local_index, old_id in enumerate(sorted(chunk.kingdoms)):
            new_id = f"kingdom_{next_kingdom:04d}"
            region_id = f"region_{next_kingdom:04d}"
            kingdom_map[old_id] = new_id
            region_by_old_kingdom[old_id] = region_id
            next_kingdom += 1

            region_index = len(regions)
            side = local_index
            min_x = side * 100.0
            max_x = min_x + 100.0
            min_y = strip_index * 100.0
            max_y = min_y + 100.0
            regions[region_id] = Region(
                id=region_id,
                name=REGION_NAMES[region_index],
                seed=f"{seed}:region:{region_index}",
                climate=REGION_CLIMATES[region_index],
                biome_mix=dict(chunk.region.biome_mix),
                magic_intensity=max(0.05, min(0.95, chunk.region.magic_intensity + rng.uniform(-0.08, 0.08))),
                bounds={"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y},
                resource_distribution={
                    resource: max(0.05, min(1.0, abundance + rng.uniform(-0.15, 0.15)))
                    for resource, abundance in chunk.region.resource_distribution.items()
                },
            )

        settlement_map: dict[str, str] = {}
        for old_id in sorted(chunk.settlements):
            settlement_map[old_id] = f"settlement_{next_settlement:05d}"
            next_settlement += 1

        npc_map: dict[str, str] = {}
        for old_id in sorted(chunk.npcs):
            npc_map[old_id] = f"npc_{next_npc:07d}"
            next_npc += 1

        army_map: dict[str, str] = {}
        for old_id in sorted(chunk.armies):
            army_map[old_id] = f"army_{next_army:04d}"
            next_army += 1

        for old_id in sorted(chunk.kingdoms):
            old = chunk.kingdoms[old_id]
            item = old.model_copy(deep=True)
            item.id = kingdom_map[old_id]
            kingdom_index = int(item.id.split("_")[1]) - 1
            item.name = f"Kingdom of {CONTINENT_KINGDOM_NAMES[kingdom_index]}"
            item.culture_id = culture_map[old.culture_id]
            item.religion_id = religion_map.get(old.religion_id or "")
            item.capital_settlement_id = settlement_map[old.capital_settlement_id]
            item.ruler_npc_id = npc_map.get(old.ruler_npc_id or "")
            item.settlement_ids = [settlement_map[sid] for sid in old.settlement_ids]
            item.army_ids = [army_map[aid] for aid in old.army_ids]
            item.relations = {
                kingdom_map[target]: relation.model_copy(
                    deep=True,
                    update={"target_kingdom_id": kingdom_map[target]},
                )
                for target, relation in old.relations.items()
                if target in kingdom_map
            }
            merged_kingdoms[item.id] = item
            regions[region_by_old_kingdom[old_id]].kingdom_ids.append(item.id)

        for old_id in sorted(chunk.settlements):
            old = chunk.settlements[old_id]
            item = old.model_copy(deep=True)
            old_kingdom = old.kingdom_id
            item.id = settlement_map[old_id]
            item.kingdom_id = kingdom_map[old_kingdom]
            item.region_id = region_by_old_kingdom[old_kingdom]
            item.position = Position(
                x=old.position.x * 2.0,
                y=old.position.y + strip_index * 100.0,
                elevation=old.position.elevation,
            )
            if item.name in used_settlement_names:
                item.name = f"{item.name} {regions[item.region_id].name.split()[0]}"
            suffix = 2
            base_name = item.name
            while item.name in used_settlement_names:
                item.name = f"{base_name} {suffix}"
                suffix += 1
            used_settlement_names.add(item.name)
            settlements[item.id] = item
            regions[item.region_id].settlement_ids.append(item.id)

        for old_id in sorted(chunk.npcs):
            old = chunk.npcs[old_id]
            item = old.model_copy(deep=True)
            item.id = npc_map[old_id]
            item.culture_id = culture_map[old.culture_id]
            item.religion_id = religion_map.get(old.religion_id or "")
            item.settlement_id = settlement_map[old.settlement_id]
            item.kingdom_id = kingdom_map[old.kingdom_id]
            item.spouse_id = npc_map.get(old.spouse_id or "")
            item.parent_ids = [npc_map[nid] for nid in old.parent_ids if nid in npc_map]
            item.child_ids = [npc_map[nid] for nid in old.child_ids if nid in npc_map]
            item.relationships = {
                npc_map[target]: Relationship(
                    **relation.model_dump(exclude={"target_id"}),
                    target_id=npc_map[target],
                )
                for target, relation in old.relationships.items()
                if target in npc_map
            }
            npcs[item.id] = item

        for old_id in sorted(chunk.armies):
            old = chunk.armies[old_id]
            item = old.model_copy(deep=True)
            item.id = army_map[old_id]
            item.kingdom_id = kingdom_map[old.kingdom_id]
            item.location_settlement_id = settlement_map[old.location_settlement_id]
            item.destination_settlement_id = settlement_map.get(old.destination_settlement_id or "")
            item.commander_npc_id = npc_map.get(old.commander_npc_id or "")
            armies[item.id] = item

        for old_id in sorted(chunk.trade_routes):
            old = chunk.trade_routes[old_id]
            item = old.model_copy(deep=True)
            item.id = f"trade_{next_trade:05d}"
            next_trade += 1
            item.origin_settlement_id = settlement_map[old.origin_settlement_id]
            item.destination_settlement_id = settlement_map[old.destination_settlement_id]
            origin = settlements[item.origin_settlement_id]
            destination = settlements[item.destination_settlement_id]
            item.distance = _distance(origin.position, destination.position)
            trade_routes[item.id] = item

        for landmark in chunk.region.landmarks:
            transformed = landmark.model_copy(deep=True)
            transformed.id = f"landmark_{next_landmark:04d}"
            next_landmark += 1
            transformed.position = Position(
                x=landmark.position.x * 2.0,
                y=landmark.position.y + strip_index * 100.0,
                elevation=landmark.position.elevation,
            )
            region_index = 0 if transformed.position.x < 100.0 else 1
            region_id = region_by_old_kingdom[sorted(chunk.kingdoms)[region_index]]
            regions[region_id].landmarks.append(transformed)

    kingdom_ids = sorted(merged_kingdoms)
    for index, left_id in enumerate(kingdom_ids):
        left = merged_kingdoms[left_id]
        for right_id in kingdom_ids[index + 1 :]:
            right = merged_kingdoms[right_id]
            if right_id not in left.relations:
                opinion = rng.uniform(-0.18, 0.22)
                left.relations[right_id] = DiplomaticRelation(target_kingdom_id=right_id, opinion=opinion)
                right.relations[left_id] = DiplomaticRelation(target_kingdom_id=left_id, opinion=opinion + rng.uniform(-0.05, 0.05))

    region_ids = sorted(regions)
    for upper_index, lower_index in ((0, 2), (1, 3), (2, 4), (3, 5)):
        upper = regions[region_ids[upper_index]]
        lower = regions[region_ids[lower_index]]
        candidates = [
            (a, b, _distance(settlements[a].position, settlements[b].position))
            for a in upper.settlement_ids
            for b in lower.settlement_ids
        ]
        origin_id, destination_id, distance = min(candidates, key=lambda item: item[2])
        route = TradeRoute(
            id=f"trade_{next_trade:05d}",
            origin_settlement_id=origin_id,
            destination_settlement_id=destination_id,
            distance=distance,
            safety=rng.uniform(0.55, 0.85),
            capacity=max(60.0, min(settlements[origin_id].population, settlements[destination_id].population) * 0.15),
            commodities=["grain", "timber", "iron"],
        )
        next_trade += 1
        trade_routes[route.id] = route

    all_landmarks: list[Landmark] = []
    for region in regions.values():
        all_landmarks.extend(region.landmarks)

    continent = Continent(
        id="continent_0001",
        name=f"Continent of {name}",
        seed=seed,
        bounds={"min_x": 0.0, "max_x": 200.0, "min_y": 0.0, "max_y": 300.0},
        region_ids=sorted(regions),
        climate_bands=["cool_temperate", "temperate", "warm_temperate"],
        ocean_fraction=0.31,
    )
    aggregate_region = Region(
        id="region_continent",
        name=continent.name,
        seed=seed,
        climate="continental",
        biome_mix={
            "temperate_forest": 0.24,
            "grassland": 0.26,
            "highland": 0.16,
            "river_valley": 0.14,
            "marsh": 0.06,
            "pine_forest": 0.14,
        },
        magic_intensity=sum(region.magic_intensity for region in regions.values()) / len(regions),
        bounds=dict(continent.bounds),
        settlement_ids=sorted(settlements),
        kingdom_ids=sorted(merged_kingdoms),
        landmarks=all_landmarks,
        resource_distribution={
            resource: sum(region.resource_distribution.get(resource, 0.0) for region in regions.values()) / len(regions)
            for resource in next(iter(regions.values())).resource_distribution
        },
    )

    world = WorldState(
        name=name,
        seed=seed,
        date=WorldDate(),
        region=aggregate_region,
        continent=continent,
        regions=regions,
        cultures=cultures,
        religions=religions,
        kingdoms=merged_kingdoms,
        settlements=settlements,
        npcs=npcs,
        trade_routes=trade_routes,
        armies=armies,
        wars=wars,
        next_entity_sequence=20_000,
    )
    world.metrics = {
        "population": float(world.total_population),
        "persistent_npcs": float(len(world.alive_npcs())),
        "kingdoms": float(len(world.kingdoms)),
        "regions": float(len(world.regions)),
        "settlements": float(len(world.settlements)),
        "active_wars": 0.0,
        "trade_routes": float(len(world.trade_routes)),
        "average_stability": sum(k.stability for k in world.kingdoms.values()) / len(world.kingdoms),
        "average_food_security": sum(s.food_security for s in world.settlements.values()) / len(world.settlements),
    }
    return world
