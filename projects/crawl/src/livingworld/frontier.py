from __future__ import annotations

import math
from collections import defaultdict
from typing import TYPE_CHECKING

from .domain import Ancestry, CampStatus, Position, ResourceStock, Settlement, SettlementType, TradeRoute
from .generation import RESOURCES, SETTLEMENT_PREFIX, SETTLEMENT_SUFFIX

if TYPE_CHECKING:
    from .simulation import WorldEngine


FRONTIER_TYPES = {SettlementType.HAMLET, SettlementType.FORT, SettlementType.TRADE_POST}


def _distance_xy(ax: float, ay: float, bx: float, by: float) -> float:
    return math.hypot(ax - bx, ay - by)


def _distance(a: Settlement, b: Settlement) -> float:
    return _distance_xy(a.position.x, a.position.y, b.position.x, b.position.y)


def _allocate_counts(counts: dict[Ancestry, int], amount: int, total: int) -> dict[Ancestry, int]:
    if amount <= 0 or total <= 0:
        return {}
    allocations: dict[Ancestry, int] = {}
    fractions: list[tuple[float, str, Ancestry]] = []
    moved = 0
    for ancestry, count in counts.items():
        raw = amount * count / total
        take = min(count, int(raw))
        allocations[ancestry] = take
        moved += take
        fractions.append((raw - take, ancestry.value, ancestry))
    remaining = amount - moved
    for _, _, ancestry in sorted(fractions, reverse=True):
        if remaining <= 0:
            break
        available = counts.get(ancestry, 0) - allocations.get(ancestry, 0)
        if available <= 0:
            continue
        allocations[ancestry] = allocations.get(ancestry, 0) + 1
        remaining -= 1
    return {ancestry: count for ancestry, count in allocations.items() if count > 0}


def _subtract_counts(counts: dict[Ancestry, int], allocations: dict[Ancestry, int]) -> None:
    for ancestry, amount in allocations.items():
        counts[ancestry] = max(0, counts.get(ancestry, 0) - amount)


def _add_counts(counts: dict[Ancestry, int], allocations: dict[Ancestry, int]) -> None:
    for ancestry, amount in allocations.items():
        counts[ancestry] = counts.get(ancestry, 0) + amount


def _frontier_name(engine: WorldEngine) -> str:
    used = {settlement.name for settlement in engine.world.settlements.values()}
    rng = engine._rng(f"frontier-name:{len(used)}")
    for _ in range(100):
        name = f"{rng.choice(SETTLEMENT_PREFIX)}{rng.choice(SETTLEMENT_SUFFIX)}"
        if name not in used:
            return name
    return f"Frontier {len(used) + 1}"


def colonization_pressure(engine: WorldEngine, kingdom_id: str) -> float:
    world = engine.world
    kingdom = world.kingdoms[kingdom_id]
    culture = world.cultures.get(kingdom.culture_id)
    active = [
        world.settlements[sid]
        for sid in kingdom.settlement_ids
        if sid in world.settlements and world.settlements[sid].population > 0 and world.settlements[sid].type != SettlementType.RUIN
    ]
    if not active:
        return 0.0
    overcrowding = sum(
        max(0.0, settlement.population / max(1, settlement.housing_capacity) - 0.88)
        for settlement in active
    ) / len(active)
    prosperity = sum(settlement.food_security * settlement.stability for settlement in active) / len(active)
    expansionism = culture.expansionism if culture else 0.5
    goal = float(kingdom.goals.get("expansion", 0.4))
    treasury = min(1.0, kingdom.treasury / 18_000.0)
    war_penalty = 0.18 if any(
        kingdom.id in {war.attacker_kingdom_id, war.defender_kingdom_id}
        for war in world.active_wars()
    ) else 0.0
    return max(0.0, min(1.0,
        expansionism * 0.28
        + goal * 0.22
        + kingdom.stability * 0.12
        + prosperity * 0.12
        + treasury * 0.10
        + min(1.0, overcrowding * 4.0) * 0.16
        - war_penalty
    ))


def _candidate_regions(engine: WorldEngine, kingdom_id: str, preferred_region_id: str | None) -> list[str]:
    world = engine.world
    if preferred_region_id:
        if preferred_region_id not in world.regions:
            raise ValueError("unknown frontier region")
        return [preferred_region_id]
    owned_region_ids = {
        settlement.region_id
        for settlement in world.settlements.values()
        if settlement.kingdom_id == kingdom_id and settlement.population > 0 and settlement.type != SettlementType.RUIN
    }
    if not owned_region_ids:
        return []
    # Include immediately neighboring region rectangles when an existing settlement is
    # close enough to reach them. This lets frontiers cross regional seams without
    # granting arbitrary long-distance colonies.
    result = set(owned_region_ids)
    own_settlements = [s for s in world.settlements.values() if s.kingdom_id == kingdom_id and s.population > 0]
    for region_id, region in world.regions.items():
        if region_id in result:
            continue
        min_x = region.bounds.get("min_x", 0.0)
        max_x = region.bounds.get("max_x", 0.0)
        min_y = region.bounds.get("min_y", 0.0)
        max_y = region.bounds.get("max_y", 0.0)
        for settlement in own_settlements:
            dx = max(min_x - settlement.position.x, 0.0, settlement.position.x - max_x)
            dy = max(min_y - settlement.position.y, 0.0, settlement.position.y - max_y)
            if math.hypot(dx, dy) <= 38.0:
                result.add(region_id)
                break
    return sorted(result)


def _find_frontier_site(
    engine: WorldEngine,
    kingdom_id: str,
    preferred_region_id: str | None = None,
) -> tuple[str, Position, float, list[str], Settlement] | None:
    world = engine.world
    regions = _candidate_regions(engine, kingdom_id, preferred_region_id)
    if not regions:
        return None
    own = [
        settlement for settlement in world.settlements.values()
        if settlement.kingdom_id == kingdom_id and settlement.population >= 80 and settlement.type != SettlementType.RUIN
    ]
    active = [settlement for settlement in world.settlements.values() if settlement.population > 0 and settlement.type != SettlementType.RUIN]
    if not own:
        return None

    rng = engine._rng(f"frontier-site:{kingdom_id}:{preferred_region_id or 'auto'}")
    best: tuple[float, str, Position, float, list[str], Settlement] | None = None
    for region_id in regions:
        region = world.regions[region_id]
        min_x = region.bounds.get("min_x", 0.0) + 4.0
        max_x = region.bounds.get("max_x", 100.0) - 4.0
        min_y = region.bounds.get("min_y", 0.0) + 4.0
        max_y = region.bounds.get("max_y", 100.0) - 4.0
        if min_x >= max_x or min_y >= max_y:
            continue
        for _ in range(28):
            x = rng.uniform(min_x, max_x)
            y = rng.uniform(min_y, max_y)
            nearest_any = min(_distance_xy(x, y, s.position.x, s.position.y) for s in active)
            if nearest_any < 7.5:
                continue
            source = min(own, key=lambda s: _distance_xy(x, y, s.position.x, s.position.y))
            own_distance = _distance_xy(x, y, source.position.x, source.position.y)
            if own_distance > 58.0:
                continue
            other_distances = [
                (_distance_xy(x, y, s.position.x, s.position.y), s.kingdom_id)
                for s in active if s.kingdom_id != kingdom_id
            ]
            nearest_other = min((item[0] for item in other_distances), default=999.0)
            contested_by = sorted({kid for distance, kid in other_distances if distance <= 24.0})
            elevation = rng.uniform(40.0, 780.0)
            defensibility = max(0.1, min(1.0,
                elevation / 900.0 * 0.55
                + min(1.0, nearest_any / 24.0) * 0.25
                + (0.20 if contested_by else 0.05)
            ))
            link_quality = max(0.0, 1.0 - abs(own_distance - 24.0) / 38.0)
            sparsity = min(1.0, nearest_any / 22.0)
            border_value = 0.25 if 16.0 <= nearest_other <= 42.0 else 0.0
            score = sparsity * 0.40 + link_quality * 0.30 + defensibility * 0.20 + border_value * 0.10
            candidate = (score, region_id, Position(x=x, y=y, elevation=elevation), defensibility, contested_by, source)
            if best is None or candidate[0] > best[0]:
                best = candidate
    if best is None:
        return None
    _, region_id, position, defensibility, contested_by, source = best
    return region_id, position, defensibility, contested_by, source


def _frontier_type(
    preferred_type: SettlementType | None,
    defensibility: float,
    contested_by: list[str],
    source_distance: float,
) -> SettlementType:
    if preferred_type:
        if preferred_type not in FRONTIER_TYPES:
            raise ValueError("frontier settlement type must be hamlet, fort, or trade_post")
        return preferred_type
    if contested_by or defensibility >= 0.72:
        return SettlementType.FORT
    if source_distance >= 32.0:
        return SettlementType.TRADE_POST
    return SettlementType.HAMLET


def _frontier_resources(engine: WorldEngine, population: int, settlement_type: SettlementType, biome: str) -> dict[str, ResourceStock]:
    rng = engine._rng(f"frontier-resources:{population}:{settlement_type.value}:{biome}")
    resources: dict[str, ResourceStock] = {}
    type_bonus = 1.15 if settlement_type == SettlementType.TRADE_POST else 0.95 if settlement_type == SettlementType.FORT else 1.0
    for resource, (base_capacity, base_price) in RESOURCES.items():
        suitability = rng.uniform(0.45, 1.15)
        if resource == "timber" and "forest" in biome:
            suitability *= 1.35
        if resource in {"stone", "iron"} and biome == "highland":
            suitability *= 1.45
        if resource == "grain" and biome in {"grassland", "river_valley"}:
            suitability *= 1.4
        scale = max(0.35, population / 180.0) * type_bonus
        capacity = base_capacity * suitability * scale
        production = capacity * rng.uniform(0.012, 0.028)
        consumption = max(0.04, population / 100.0) * (0.9 if resource == "grain" else 0.15)
        resources[resource] = ResourceStock(
            resource=resource,
            quantity=capacity * rng.uniform(0.28, 0.58),
            capacity=capacity,
            base_price=base_price,
            price=base_price,
            production_per_day=production,
            consumption_per_day=consumption,
        )
    return resources


def _move_named_colonists(engine: WorldEngine, source: Settlement, destination: Settlement, amount: int, source_before: int) -> list[str]:
    world = engine.world
    commander_ids = {army.commander_npc_id for army in world.armies.values() if army.active and army.commander_npc_id}
    ruler_ids = {kingdom.ruler_npc_id for kingdom in world.kingdoms.values() if kingdom.ruler_npc_id}
    residents = [
        npc for npc in world.npcs.values()
        if npc.alive and npc.settlement_id == source.id and npc.id not in commander_ids and npc.id not in ruler_ids and npc.social_status != "ruler"
    ]
    if not residents:
        return []
    target = min(4, max(1, round(len(residents) * amount / max(1, source_before))))
    rng = engine._rng(f"frontier-npcs:{source.id}:{destination.id}")
    selected = rng.sample(residents, k=min(target, len(residents)))
    moved_ids = []
    for npc in selected:
        npc.settlement_id = destination.id
        npc.kingdom_id = destination.kingdom_id
        moved_ids.append(npc.id)
    return moved_ids


def _take_from_camp(engine: WorldEngine, kingdom_id: str, amount: int) -> tuple[int, dict[Ancestry, int], str | None]:
    camps = [
        camp for camp in engine.world.refugee_camps.values()
        if camp.host_kingdom_id == kingdom_id and camp.status != CampStatus.CLOSED and camp.people >= 15
    ]
    if not camps or amount <= 0:
        return 0, {}, None
    camp = max(camps, key=lambda item: (item.people, item.id))
    take = min(amount, camp.people, 45)
    allocations = _allocate_counts(camp.ancestry_population, take, camp.people)
    _subtract_counts(camp.ancestry_population, allocations)
    camp.people -= take
    if camp.people <= 0:
        camp.people = 0
        camp.status = CampStatus.CLOSED
    else:
        camp.status = CampStatus.RESETTLING
    return take, allocations, camp.id


def found_frontier_settlement(
    engine: WorldEngine,
    kingdom_id: str,
    *,
    region_id: str | None = None,
    preferred_type: SettlementType | str | None = None,
    force: bool = False,
) -> Settlement:
    world = engine.world
    kingdom = world.kingdoms.get(kingdom_id)
    if not kingdom:
        raise ValueError("unknown kingdom")
    if isinstance(preferred_type, str):
        preferred_type = SettlementType(preferred_type)
    active_frontiers = [
        s for s in world.settlements.values()
        if s.kingdom_id == kingdom_id and s.frontier and s.population > 0 and s.type != SettlementType.RUIN
    ]
    if len(active_frontiers) >= 6 and not force:
        raise ValueError("kingdom already has the maximum active frontier settlements")
    pressure = colonization_pressure(engine, kingdom_id)
    if pressure < 0.54 and not force:
        raise ValueError("colonization pressure is too low")

    site = _find_frontier_site(engine, kingdom_id, region_id)
    if site is None:
        raise ValueError("no viable frontier site found")
    site_region_id, position, defensibility, contested_by, source = site
    source_distance = _distance_xy(position.x, position.y, source.position.x, source.position.y)
    settlement_type = _frontier_type(preferred_type, defensibility, contested_by, source_distance)

    source_before = source.population
    available_source = max(0, source.population - 60)
    desired = min(110, max(42, int(source.population * 0.035)))
    camp_take, camp_ancestry, camp_id = _take_from_camp(engine, kingdom_id, desired // 3)
    source_take = min(max(0, desired - camp_take), available_source)
    if source_take + camp_take < 30:
        # Return any tentatively selected camp population before failing.
        if camp_take and camp_id:
            camp = world.refugee_camps[camp_id]
            camp.people += camp_take
            _add_counts(camp.ancestry_population, camp_ancestry)
            if camp.status == CampStatus.CLOSED:
                camp.status = CampStatus.ACTIVE
        raise ValueError("not enough population is available to found a frontier settlement")

    source_ancestry = _allocate_counts(source.ancestry_population, source_take, source.population)
    _subtract_counts(source.ancestry_population, source_ancestry)
    source.population -= source_take
    ancestry: dict[Ancestry, int] = defaultdict(int)
    for key, value in source_ancestry.items():
        ancestry[key] += value
    for key, value in camp_ancestry.items():
        ancestry[key] += value
    population = source_take + camp_take

    rng = engine._rng(f"frontier-settlement:{kingdom_id}:{site_region_id}:{len(world.settlements)}")
    region = world.regions[site_region_id]
    biome = max(region.biome_mix, key=region.biome_mix.get) if region.biome_mix else rng.choice(["grassland", "temperate_forest", "highland"])
    settlement_id = world.new_entity_id("settlement")
    defenses = max(0.30, defensibility if settlement_type == SettlementType.FORT else defensibility * 0.65)
    buildings = {
        "homes": max(6, population // 5),
        "farms": max(2, population // 35),
        "workshops": max(1, population // 55),
        "market": 1 if settlement_type == SettlementType.TRADE_POST else 0,
        "temple": 0,
        "watchtower": 2 if settlement_type == SettlementType.FORT else 1,
    }
    settlement = Settlement(
        id=settlement_id,
        name=_frontier_name(engine),
        type=settlement_type,
        kingdom_id=kingdom_id,
        region_id=site_region_id,
        position=position,
        biome=biome,
        population=population,
        ancestry_population=dict(ancestry),
        food_security=0.68 if camp_take == 0 else 0.60,
        wealth=population * (4.0 if settlement_type == SettlementType.TRADE_POST else 2.8),
        housing_capacity=max(population + 30, int(population * 1.35)),
        stability=0.64 if contested_by else 0.72,
        crime=0.09,
        health=0.76,
        magic_intensity=max(0.0, min(1.0, region.magic_intensity + rng.uniform(-0.12, 0.12))),
        infrastructure={"roads": 0.22, "sanitation": 0.28, "defenses": defenses},
        resources=_frontier_resources(engine, population, settlement_type, biome),
        buildings=buildings,
        founded_year=world.date.year,
        frontier=True,
        origin_settlement_id=source.id,
    )
    world.settlements[settlement.id] = settlement
    kingdom.settlement_ids.append(settlement.id)
    if settlement.id not in region.settlement_ids:
        region.settlement_ids.append(settlement.id)
    if kingdom_id not in region.kingdom_ids:
        region.kingdom_ids.append(kingdom_id)

    moved_npcs = _move_named_colonists(engine, source, settlement, source_take, source_before)
    route_id = world.new_entity_id("route")
    world.trade_routes[route_id] = TradeRoute(
        id=route_id,
        origin_settlement_id=source.id,
        destination_settlement_id=settlement.id,
        distance=source_distance,
        safety=0.76 if contested_by else 0.88,
        capacity=55.0 if settlement_type == SettlementType.TRADE_POST else 35.0,
        commodities=["grain", "timber", "stone", "iron"],
    )

    claim_id = world.new_entity_id("claim")
    radius = 14.0 if settlement_type == SettlementType.FORT else 12.0 if settlement_type == SettlementType.TRADE_POST else 9.0
    strength = max(0.35, min(1.0, 0.35 + defenses * 0.35 + settlement.stability * 0.20 + min(0.10, population / 1000.0)))
    status = "contested" if contested_by else "active"
    world.territory_claims[claim_id] = {
        "id": claim_id,
        "kingdom_id": kingdom_id,
        "region_id": site_region_id,
        "settlement_id": settlement.id,
        "position": position.model_dump(mode="json"),
        "control_radius": radius,
        "strength": strength,
        "defensibility": defensibility,
        "status": status,
        "contested_by_kingdom_ids": contested_by,
        "created_at": world.date.model_dump(mode="json"),
    }
    kingdom.claims.append(claim_id)

    engine.emit(
        "SETTLEMENT_FOUNDED",
        f"{kingdom.name} founded {settlement.name}, a frontier {settlement.type.value.replace('_', ' ')} in {region.name}.",
        [kingdom.id, settlement.id, claim_id, source.id, *moved_npcs],
        settlement.id,
        data={
            "kingdom_id": kingdom.id,
            "settlement_id": settlement.id,
            "claim_id": claim_id,
            "region_id": site_region_id,
            "origin_settlement_id": source.id,
            "settlers": population,
            "source_settlers": source_take,
            "refugee_settlers": camp_take,
            "refugee_camp_id": camp_id,
            "settlement_type": settlement.type.value,
            "defensibility": defensibility,
            "contested_by_kingdom_ids": contested_by,
        },
        importance=0.82,
    )
    if contested_by:
        engine.emit(
            "FRONTIER_CLAIM_CONTESTED",
            f"The new claim around {settlement.name} overlaps the interests of {len(contested_by)} neighboring kingdom(s).",
            [claim_id, settlement.id, kingdom.id, *contested_by],
            settlement.id,
            data={"claim_id": claim_id, "contested_by_kingdom_ids": contested_by},
            importance=0.62,
        )
    return settlement


def _claim_for_settlement(engine: WorldEngine, settlement_id: str) -> tuple[str, dict] | None:
    for claim_id, claim in engine.world.territory_claims.items():
        if claim.get("settlement_id") == settlement_id and claim.get("status") != "abandoned":
            return claim_id, claim
    return None


def _update_claim_contest(engine: WorldEngine, settlement: Settlement) -> None:
    found = _claim_for_settlement(engine, settlement.id)
    if not found:
        return
    claim_id, claim = found
    radius = float(claim.get("control_radius", 9.0))
    contested_by = sorted({
        other.kingdom_id
        for other in engine.world.settlements.values()
        if other.population > 0
        and other.type != SettlementType.RUIN
        and other.kingdom_id != settlement.kingdom_id
        and _distance(settlement, other) <= radius + 15.0
    })
    previous = set(claim.get("contested_by_kingdom_ids", []))
    claim["contested_by_kingdom_ids"] = contested_by
    claim["status"] = "contested" if contested_by else "active"
    defenses = settlement.infrastructure.get("defenses", 0.3)
    claim["strength"] = max(0.05, min(1.0,
        0.25 + settlement.stability * 0.25 + defenses * 0.35 + min(0.15, settlement.population / 800.0)
    ))
    if contested_by and set(contested_by) != previous:
        engine.emit(
            "FRONTIER_CLAIM_CONTESTED",
            f"Territorial pressure increased around {settlement.name}.",
            [claim_id, settlement.id, settlement.kingdom_id, *contested_by],
            settlement.id,
            data={"claim_id": claim_id, "contested_by_kingdom_ids": contested_by},
            importance=0.58,
        )


def _fortify_if_needed(engine: WorldEngine, settlement: Settlement) -> None:
    found = _claim_for_settlement(engine, settlement.id)
    if not found:
        return
    _, claim = found
    if claim.get("status") != "contested":
        return
    kingdom = engine.world.kingdoms.get(settlement.kingdom_id)
    if not kingdom or kingdom.treasury < 180:
        return
    defenses = settlement.infrastructure.get("defenses", 0.3)
    if defenses < 0.82:
        investment = min(220.0, kingdom.treasury * 0.01)
        kingdom.treasury -= investment
        settlement.infrastructure["defenses"] = min(1.0, defenses + 0.045)
        settlement.wealth += investment * 0.25
    if settlement.type != SettlementType.FORT and settlement.infrastructure.get("defenses", 0.0) >= 0.74:
        settlement.type = SettlementType.FORT
        settlement.buildings["watchtower"] = max(2, settlement.buildings.get("watchtower", 0))
        engine.emit(
            "FRONTIER_FORTIFIED",
            f"{settlement.name} was fortified to secure a contested frontier.",
            [settlement.id, settlement.kingdom_id],
            settlement.id,
            importance=0.64,
        )


def abandon_frontier_settlement(engine: WorldEngine, settlement_id: str, reason: str = "frontier collapse") -> bool:
    world = engine.world
    settlement = world.settlements.get(settlement_id)
    if not settlement or not settlement.frontier or settlement.type == SettlementType.RUIN:
        return False
    destinations = [
        other for other in world.settlements.values()
        if other.id != settlement.id
        and other.kingdom_id == settlement.kingdom_id
        and other.population > 0
        and other.type != SettlementType.RUIN
    ]
    if not destinations:
        return False
    destination = min(destinations, key=lambda other: _distance(settlement, other))
    moved = settlement.population
    _add_counts(destination.ancestry_population, settlement.ancestry_population)
    destination.population += moved
    destination.housing_capacity = max(destination.housing_capacity, destination.population + 20)
    for ancestry in list(settlement.ancestry_population):
        settlement.ancestry_population[ancestry] = 0
    settlement.population = 0
    settlement.type = SettlementType.RUIN
    settlement.frontier = False
    settlement.abandoned_year = world.date.year
    settlement.frontier_stress_months = 0
    settlement.wealth = 0.0
    settlement.housing_capacity = 0
    settlement.food_security = 0.0
    settlement.stability = 0.0
    for stock in settlement.resources.values():
        stock.quantity = 0.0
        stock.production_per_day = 0.0
        stock.consumption_per_day = 0.0
    moved_npcs = []
    for npc in world.npcs.values():
        if npc.alive and npc.settlement_id == settlement.id:
            npc.settlement_id = destination.id
            npc.kingdom_id = destination.kingdom_id
            moved_npcs.append(npc.id)
    kingdom = world.kingdoms.get(settlement.kingdom_id)
    if kingdom and settlement.id in kingdom.settlement_ids:
        kingdom.settlement_ids.remove(settlement.id)
    for route in world.trade_routes.values():
        if settlement.id in {route.origin_settlement_id, route.destination_settlement_id}:
            route.active = False
    found = _claim_for_settlement(engine, settlement.id)
    claim_id = None
    if found:
        claim_id, claim = found
        claim["status"] = "abandoned"
        claim["strength"] = 0.0
        claim["contested_by_kingdom_ids"] = []
    engine.emit(
        "SETTLEMENT_ABANDONED",
        f"{settlement.name} was abandoned after {reason}; {moved:,} survivors relocated to {destination.name}.",
        [settlement.id, destination.id, *( [claim_id] if claim_id else []), *moved_npcs],
        settlement.id,
        data={
            "settlement_id": settlement.id,
            "destination_settlement_id": destination.id,
            "people_relocated": moved,
            "reason": reason,
            "claim_id": claim_id,
        },
        importance=0.76,
    )
    return True


def update_frontiers(engine: WorldEngine) -> None:
    world = engine.world
    frontier_settlements = [
        settlement for settlement in list(world.settlements.values())
        if settlement.frontier and settlement.population > 0 and settlement.type != SettlementType.RUIN
    ]
    for settlement in frontier_settlements:
        _update_claim_contest(engine, settlement)
        _fortify_if_needed(engine, settlement)
        stressed = (
            settlement.population < 15
            or settlement.food_security < 0.18
            or settlement.stability < 0.22
            or settlement.health < 0.28
        )
        if stressed:
            settlement.frontier_stress_months += 1
        else:
            settlement.frontier_stress_months = max(0, settlement.frontier_stress_months - 1)
        if settlement.frontier_stress_months >= 3:
            abandon_frontier_settlement(engine, settlement.id, "three months of severe frontier stress")


def run_colonization_cycle(engine: WorldEngine) -> Settlement | None:
    world = engine.world
    candidates = []
    for kingdom in world.kingdoms.values():
        active_frontiers = sum(
            1 for settlement in world.settlements.values()
            if settlement.kingdom_id == kingdom.id and settlement.frontier and settlement.population > 0
        )
        if active_frontiers >= 6:
            continue
        pressure = colonization_pressure(engine, kingdom.id)
        candidates.append((pressure, kingdom.id))
    if not candidates:
        return None
    pressure, kingdom_id = max(candidates, key=lambda item: (item[0], item[1]))
    if pressure < 0.54:
        return None
    rng = engine._rng(f"colonization-cycle:{kingdom_id}")
    if rng.random() > min(0.85, 0.20 + pressure * 0.65):
        return None
    try:
        return found_frontier_settlement(engine, kingdom_id)
    except ValueError:
        return None


def run_frontier_cycle(engine: WorldEngine) -> None:
    """Update frontier claims monthly and attempt one new colony at the start of each year."""
    update_frontiers(engine)
    if engine.world.date.month == 1:
        run_colonization_cycle(engine)
    refresh_frontier_metrics(engine.world)


def refresh_frontier_metrics(world) -> None:
    active_claims = [claim for claim in world.territory_claims.values() if claim.get("status") in {"active", "contested"}]
    frontier_settlements = [s for s in world.settlements.values() if s.frontier and s.population > 0]
    ruins = [s for s in world.settlements.values() if s.type == SettlementType.RUIN and s.abandoned_year is not None]
    forts = [s for s in frontier_settlements if s.type == SettlementType.FORT]
    world.metrics["active_frontier_claims"] = float(len(active_claims))
    world.metrics["frontier_settlements"] = float(len(frontier_settlements))
    world.metrics["frontier_forts"] = float(len(forts))
    world.metrics["frontier_ruins"] = float(len(ruins))
    world.metrics["contested_frontier_claims"] = float(sum(1 for claim in active_claims if claim.get("status") == "contested"))


def territory_summary(world) -> list[dict]:
    claims_by_kingdom: dict[str, list[dict]] = defaultdict(list)
    for claim in world.territory_claims.values():
        claims_by_kingdom[str(claim.get("kingdom_id", ""))].append(claim)
    payload = []
    for kingdom in world.kingdoms.values():
        core = [
            world.settlements[sid]
            for sid in kingdom.settlement_ids
            if sid in world.settlements and world.settlements[sid].population > 0 and world.settlements[sid].type != SettlementType.RUIN
        ]
        claims = claims_by_kingdom.get(kingdom.id, [])
        active_claims = [claim for claim in claims if claim.get("status") in {"active", "contested"}]
        claim_area = sum(
            math.pi * float(claim.get("control_radius", 0.0)) ** 2 * float(claim.get("strength", 0.0))
            for claim in active_claims
        )
        # Core control is an influence estimate, not a polygon union. It exists so
        # clients can compare kingdoms without pretending we have terrain polygons yet.
        core_area = len(core) * math.pi * 6.0 ** 2
        payload.append({
            "kingdom_id": kingdom.id,
            "kingdom_name": kingdom.name,
            "core_settlements": len(core),
            "frontier_settlements": sum(1 for settlement in core if settlement.frontier),
            "frontier_forts": sum(1 for settlement in core if settlement.frontier and settlement.type == SettlementType.FORT),
            "active_claims": len(active_claims),
            "contested_claims": sum(1 for claim in active_claims if claim.get("status") == "contested"),
            "estimated_control_area": round(core_area + claim_area, 2),
        })
    return payload
