from __future__ import annotations

import math
import random
from collections import Counter

from .domain import (
    Ancestry,
    Army,
    Culture,
    DiplomaticRelation,
    GovernmentType,
    Kingdom,
    Landmark,
    NPC,
    Position,
    Region,
    Relationship,
    Religion,
    ResourceStock,
    Settlement,
    SettlementType,
    TradeRoute,
    WorldDate,
    WorldState,
)


FIRST_NAMES = {
    Ancestry.HUMAN: ["Aldric", "Mara", "Elara", "Rowan", "Cedric", "Lyra", "Bran", "Tessa"],
    Ancestry.ELF: ["Aelwen", "Sylvar", "Lethiel", "Caeren", "Ilyra", "Theren", "Vaelis", "Nym"],
    Ancestry.DWARF: ["Thorin", "Bera", "Dorrin", "Helga", "Kelda", "Brom", "Orik", "Sigrun"],
    Ancestry.GNOME: ["Pip", "Nissa", "Tovin", "Merri", "Boddyn", "Fenna", "Wizzle", "Lumi"],
    Ancestry.HALFLING: ["Milo", "Pella", "Tobyn", "Rosie", "Finn", "Mara", "Jory", "Linnet"],
    Ancestry.ORC: ["Gorak", "Shara", "Durg", "Vesha", "Korga", "Ruk", "Thara", "Mog"],
    Ancestry.GOBLIN: ["Nib", "Skrit", "Vikka", "Taz", "Grimble", "Zikka", "Ratch", "Mib"],
}

SURNAMES = [
    "Ironwood", "Riverrun", "Stonehand", "Ashvale", "Goldleaf", "Deepdelve", "Brightgear",
    "Thornfield", "Blackwater", "Redforge", "Moonbrook", "Stormward", "Oakenshield", "Duskfall",
]

SETTLEMENT_PREFIX = [
    "Red", "Stone", "Silver", "Oak", "Moon", "Iron", "Green", "High", "Deep", "Bright", "West", "East",
    "North", "South", "Dawn", "Dusk", "River", "Ash", "Gold", "Frost", "Ember", "Thorn", "Star", "Wolf",
]
SETTLEMENT_SUFFIX = ["haven", "ford", "wall", "watch", "brook", "vale", "stead", "fall", "reach", "gate", "mere", "hold"]
KINGDOM_NAMES = ["Aranor", "Velis", "Kharad", "Sylvara", "Bramholt", "Orrakai", "Luneth", "Dornfell"]
CULTURE_STEMS = ["Arani", "Velari", "Khazren", "Sylven", "Bramish", "Orakai", "Lunari", "Dornic"]
DEITIES = ["Aurelia", "Moradin", "Elyndra", "Tharos", "Nimara", "Velor", "Khuld", "Serath"]
DOMAINS = ["light", "forge", "wilds", "war", "knowledge", "trade", "death", "harvest", "storms", "magic"]
OCCUPATIONS = [
    "farmer", "smith", "carpenter", "merchant", "guard", "miner", "herbalist", "miller", "weaver", "hunter",
    "priest", "scribe", "mason", "brewer", "teamster", "fisher", "healer", "teacher", "soldier", "innkeeper",
]
GOALS = [
    "protect_family", "become_wealthy", "master_craft", "gain_status", "serve_community", "explore_world",
    "own_land", "learn_magic", "join_government", "build_legacy", "strengthen_faith", "avenge_grievance",
]
BIOMES = ["temperate_forest", "grassland", "highland", "river_valley", "marsh", "pine_forest"]
RESOURCES = {
    "grain": (1200.0, 1.0),
    "livestock": (700.0, 2.2),
    "timber": (900.0, 1.6),
    "stone": (800.0, 1.4),
    "iron": (500.0, 4.0),
    "herbs": (350.0, 3.0),
    "mana_crystal": (120.0, 12.0),
}


def _normalized(values: list[float], total: int) -> list[int]:
    raw = [v / sum(values) * total for v in values]
    result = [int(v) for v in raw]
    for index in sorted(range(len(raw)), key=lambda i: raw[i] - result[i], reverse=True)[: total - sum(result)]:
        result[index] += 1
    return result


def _name(rng: random.Random, ancestry: Ancestry) -> str:
    return f"{rng.choice(FIRST_NAMES[ancestry])} {rng.choice(SURNAMES)}"


def _settlement_name(rng: random.Random, used: set[str]) -> str:
    while True:
        name = f"{rng.choice(SETTLEMENT_PREFIX)}{rng.choice(SETTLEMENT_SUFFIX)}"
        if name not in used:
            used.add(name)
            return name


def _weighted_ancestry(rng: random.Random, dominant: Ancestry) -> Ancestry:
    ancestries = list(Ancestry)
    weights = [0.58 if a == dominant else 0.42 / (len(ancestries) - 1) for a in ancestries]
    return rng.choices(ancestries, weights=weights, k=1)[0]


def _culture(rng: random.Random, idx: int, ancestry: Ancestry) -> Culture:
    center = lambda spread=0.25: max(0.05, min(0.95, 0.5 + rng.uniform(-spread, spread)))
    return Culture(
        id=f"culture_{idx + 1:04d}",
        name=f"{CULTURE_STEMS[idx % len(CULTURE_STEMS)]} Tradition",
        dominant_ancestry=ancestry,
        honor=center(), collectivism=center(), militarism=center(), devotion=center(),
        trade_orientation=center(), expansionism=center(), tolerance=center(),
        magic_acceptance=center(), tradition=center(),
    )


def _religion(rng: random.Random, idx: int) -> Religion:
    deity = DEITIES[idx % len(DEITIES)]
    domains = rng.sample(DOMAINS, k=3)
    return Religion(
        id=f"religion_{idx + 1:04d}",
        name=f"Path of {deity}",
        deity=deity,
        domains=domains,
        doctrine=[f"Honor the domain of {domains[0]}", f"Protect those who uphold {domains[1]}", f"Seek balance through {domains[2]}"],
    )


def generate_world(
    seed: str,
    name: str,
    target_population: int = 10_000,
    persistent_npcs: int = 100,
    towns: int = 5,
    villages: int = 20,
) -> WorldState:
    rng = random.Random(seed)
    if towns < 2:
        raise ValueError("at least two towns are required for two kingdom capitals")
    if persistent_npcs < 2:
        raise ValueError("at least two persistent NPCs are required for rulers")

    kingdom_ancestries = rng.sample(list(Ancestry), k=2)
    cultures = {culture.id: culture for culture in (_culture(rng, i, kingdom_ancestries[i]) for i in range(2))}
    religions = {religion.id: religion for religion in (_religion(rng, i) for i in range(2))}
    culture_list = list(cultures.values())
    religion_list = list(religions.values())

    kingdoms: dict[str, Kingdom] = {}
    for idx in range(2):
        kid = f"kingdom_{idx + 1:04d}"
        kingdoms[kid] = Kingdom(
            id=kid,
            name=f"Kingdom of {KINGDOM_NAMES[idx]}",
            capital_settlement_id="",
            government=rng.choice(list(GovernmentType)),
            dominant_ancestry=kingdom_ancestries[idx],
            culture_id=culture_list[idx].id,
            religion_id=religion_list[idx].id,
            treasury=rng.uniform(10_000, 18_000),
            tax_rate=rng.uniform(0.08, 0.16),
            stability=rng.uniform(0.62, 0.86),
            legitimacy=rng.uniform(0.62, 0.9),
            military_readiness=rng.uniform(0.4, 0.7),
            goals={"food": 0.7, "wealth": 0.6, "security": 0.75, "expansion": rng.uniform(0.25, 0.7), "stability": 0.8},
        )
    k_ids = list(kingdoms)
    kingdoms[k_ids[0]].relations[k_ids[1]] = DiplomaticRelation(target_kingdom_id=k_ids[1], opinion=rng.uniform(-0.15, 0.2))
    kingdoms[k_ids[1]].relations[k_ids[0]] = DiplomaticRelation(target_kingdom_id=k_ids[0], opinion=rng.uniform(-0.15, 0.2))

    total_settlements = towns + villages
    town_weights = [rng.uniform(5.0, 8.0) for _ in range(towns)]
    village_weights = [rng.uniform(0.8, 2.0) for _ in range(villages)]
    populations = _normalized(town_weights + village_weights, target_population)
    used_names: set[str] = set()
    settlements: dict[str, Settlement] = {}

    for idx in range(total_settlements):
        sid = f"settlement_{idx + 1:05d}"
        stype = SettlementType.TOWN if idx < towns else SettlementType.VILLAGE
        # Capitals are deliberately split; subsequent settlements loosely cluster by x-coordinate.
        if idx == 0:
            kingdom_idx = 0
            x = rng.uniform(12, 30)
        elif idx == 1:
            kingdom_idx = 1
            x = rng.uniform(70, 88)
        else:
            x = rng.uniform(5, 95)
            kingdom_idx = 0 if x < 50 else 1
        y = rng.uniform(8, 92)
        kingdom = kingdoms[k_ids[kingdom_idx]]
        pop = populations[idx]
        ancestry_counts = Counter()
        for _ in range(pop):
            ancestry_counts[_weighted_ancestry(rng, kingdom.dominant_ancestry)] += 1
        biome = rng.choice(BIOMES)
        magic = max(0.0, min(1.0, rng.betavariate(2, 5) + (0.12 if biome == "highland" else 0)))
        stocks: dict[str, ResourceStock] = {}
        for resource, (base_capacity, base_price) in RESOURCES.items():
            suitability = rng.uniform(0.4, 1.4)
            if resource == "timber" and "forest" in biome:
                suitability *= 1.45
            if resource in {"stone", "iron"} and biome == "highland":
                suitability *= 1.6
            if resource == "grain" and biome in {"grassland", "river_valley"}:
                suitability *= 1.5
            if resource == "mana_crystal":
                suitability *= 0.4 + magic
            capacity = base_capacity * suitability * max(0.5, pop / 250)
            production = capacity * rng.uniform(0.015, 0.035)
            consumption = max(0.05, pop / 100) * (0.9 if resource == "grain" else 0.15)
            stocks[resource] = ResourceStock(
                resource=resource,
                quantity=capacity * rng.uniform(0.35, 0.8),
                capacity=capacity,
                base_price=base_price,
                price=base_price,
                production_per_day=production,
                consumption_per_day=consumption,
            )
        settlement = Settlement(
            id=sid,
            name=_settlement_name(rng, used_names),
            type=stype,
            kingdom_id=kingdom.id,
            region_id="region_0001",
            position=Position(x=x, y=y, elevation=rng.uniform(20, 900 if biome == "highland" else 350)),
            biome=biome,
            population=pop,
            ancestry_population=dict(ancestry_counts),
            food_security=rng.uniform(0.62, 0.9),
            wealth=pop * rng.uniform(2.5, 7.0),
            stability=rng.uniform(0.62, 0.88),
            crime=rng.uniform(0.04, 0.2),
            health=rng.uniform(0.68, 0.9),
            magic_intensity=magic,
            infrastructure={"roads": rng.uniform(0.25, 0.75), "sanitation": rng.uniform(0.2, 0.7), "defenses": rng.uniform(0.15, 0.75)},
            resources=stocks,
            buildings={
                "homes": max(4, pop // 5),
                "farms": max(2, pop // 80),
                "workshops": max(1, pop // 150),
                "market": 1 if stype == SettlementType.TOWN else int(rng.random() < 0.35),
                "temple": 1 if pop > 180 else int(rng.random() < 0.25),
            },
        )
        settlements[sid] = settlement
        kingdom.settlement_ids.append(sid)
        if idx in (0, 1):
            kingdom.capital_settlement_id = sid

    # Persistent NPCs are distributed in proportion to settlement population.
    npc_counts = _normalized([s.population for s in settlements.values()], persistent_npcs)
    npcs: dict[str, NPC] = {}
    npc_index = 1
    for settlement, count in zip(settlements.values(), npc_counts, strict=True):
        kingdom = kingdoms[settlement.kingdom_id]
        culture = cultures[kingdom.culture_id]
        for _ in range(count):
            ancestry = _weighted_ancestry(rng, kingdom.dominant_ancestry)
            nid = f"npc_{npc_index:07d}"
            npc_index += 1
            goals = rng.sample(GOALS, k=rng.randint(1, 3))
            npcs[nid] = NPC(
                id=nid,
                name=_name(rng, ancestry),
                ancestry=ancestry,
                culture_id=culture.id,
                religion_id=kingdom.religion_id if rng.random() < 0.8 else None,
                settlement_id=settlement.id,
                kingdom_id=kingdom.id,
                age=rng.randint(16, 72),
                sex=rng.choice(["female", "male"]),
                health=rng.uniform(0.58, 1.0),
                wealth=rng.lognormvariate(3.0, 0.7),
                occupation=rng.choice(OCCUPATIONS),
                traits={
                    "ambition": rng.random(), "courage": rng.random(), "empathy": rng.random(),
                    "greed": rng.random(), "curiosity": rng.random(), "loyalty": rng.random(),
                },
                values={"family": rng.random(), "wealth": rng.random(), "faith": rng.random(), "status": rng.random(), "freedom": rng.random()},
                goals=goals,
                goal_progress={goal: rng.uniform(0.0, 0.25) for goal in goals},
            )

    # Build a small persistent social graph and family structure inside settlements.
    by_settlement: dict[str, list[NPC]] = {}
    for npc in npcs.values():
        by_settlement.setdefault(npc.settlement_id, []).append(npc)
    for group in by_settlement.values():
        for npc in group:
            candidates = [other for other in group if other.id != npc.id]
            for other in rng.sample(candidates, k=min(len(candidates), rng.randint(1, 4))):
                npc.relationships[other.id] = Relationship(
                    target_id=other.id,
                    affinity=rng.uniform(-0.5, 0.8),
                    trust=rng.uniform(-0.3, 0.8),
                    fear=rng.uniform(0.0, 0.25),
                    tags=[rng.choice(["neighbor", "friend", "coworker", "rival", "customer"])],
                )
        adults = [n for n in group if 20 <= n.age <= 60 and n.spouse_id is None]
        rng.shuffle(adults)
        for a, b in zip(adults[::2], adults[1::2]):
            if a.sex != b.sex and rng.random() < 0.35:
                a.spouse_id, b.spouse_id = b.id, a.id
                a.relationships[b.id] = Relationship(target_id=b.id, affinity=0.75, trust=0.8, tags=["spouse"])
                b.relationships[a.id] = Relationship(target_id=a.id, affinity=0.75, trust=0.8, tags=["spouse"])

    # Install rulers from capital residents and commanders from military-oriented adults.
    for kingdom in kingdoms.values():
        capital_candidates = [n for n in npcs.values() if n.settlement_id == kingdom.capital_settlement_id and n.alive]
        if not capital_candidates:
            capital_candidates = [n for n in npcs.values() if n.kingdom_id == kingdom.id]
        ruler = max(capital_candidates, key=lambda n: n.traits.get("ambition", 0.0) + n.values.get("status", 0.0))
        ruler.title = "Sovereign"
        ruler.social_status = "ruler"
        ruler.occupation = "ruler"
        ruler.wealth += 2_500
        kingdom.ruler_npc_id = ruler.id

    armies: dict[str, Army] = {}
    for idx, kingdom in enumerate(kingdoms.values(), start=1):
        candidates = [n for n in npcs.values() if n.kingdom_id == kingdom.id and n.alive and n.id != kingdom.ruler_npc_id]
        commander = max(candidates, key=lambda n: n.traits.get("courage", 0.0) + n.traits.get("loyalty", 0.0))
        commander.title = "Captain"
        commander.occupation = "soldier"
        army = Army(
            id=f"army_{idx:04d}", kingdom_id=kingdom.id, name=f"{kingdom.name.replace('Kingdom of ', '')} Host",
            troop_count=max(80, sum(settlements[s].population for s in kingdom.settlement_ids) // 18),
            location_settlement_id=kingdom.capital_settlement_id,
            morale=rng.uniform(0.62, 0.88), supply_days=rng.uniform(24, 50), readiness=rng.uniform(0.5, 0.75),
            commander_npc_id=commander.id,
        )
        armies[army.id] = army
        kingdom.army_ids.append(army.id)

    # Link each settlement to its three nearest neighbors; duplicates collapse to one route.
    routes: dict[str, TradeRoute] = {}
    seen_pairs: set[tuple[str, str]] = set()
    settlement_list = list(settlements.values())
    route_index = 1
    for origin in settlement_list:
        neighbors = sorted(
            (other for other in settlement_list if other.id != origin.id),
            key=lambda other: math.hypot(other.position.x - origin.position.x, other.position.y - origin.position.y),
        )[:3]
        for destination in neighbors:
            pair = tuple(sorted((origin.id, destination.id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            distance = math.hypot(destination.position.x - origin.position.x, destination.position.y - origin.position.y)
            route = TradeRoute(
                id=f"trade_{route_index:05d}", origin_settlement_id=origin.id, destination_settlement_id=destination.id,
                distance=distance, safety=rng.uniform(0.55, 0.95), capacity=max(30, min(origin.population, destination.population) * 0.18),
                commodities=rng.sample(list(RESOURCES), k=3),
            )
            routes[route.id] = route
            route_index += 1

    landmarks = [
        Landmark(id="landmark_0001", name="The Shattered Peaks", kind="mountain_range", position=Position(x=48, y=75, elevation=1600), description="Jagged mineral-rich peaks that divide the northern watershed.", magic_intensity=0.32),
        Landmark(id="landmark_0002", name="River Aster", kind="river", position=Position(x=50, y=45, elevation=90), description="The region's primary navigable river and trade artery.", magic_intensity=0.12),
        Landmark(id="landmark_0003", name="Starfall Hollow", kind="magical_site", position=Position(x=64, y=24, elevation=180), description="A luminous crater where mana crystals grow near the surface.", magic_intensity=0.92),
    ]
    region = Region(
        id="region_0001", name="The Aster Marches", seed=seed, climate="temperate",
        biome_mix={"temperate_forest": 0.28, "grassland": 0.30, "highland": 0.15, "river_valley": 0.15, "marsh": 0.05, "pine_forest": 0.07},
        magic_intensity=0.28, bounds={"min_x": 0, "max_x": 100, "min_y": 0, "max_y": 100},
        settlement_ids=list(settlements), kingdom_ids=list(kingdoms), landmarks=landmarks,
        resource_distribution={resource: rng.uniform(0.35, 0.95) for resource in RESOURCES},
    )

    world = WorldState(
        name=name, seed=seed, date=WorldDate(), region=region, cultures=cultures, religions=religions,
        kingdoms=kingdoms, settlements=settlements, npcs=npcs, trade_routes=routes, armies=armies,
    )
    _refresh_metrics(world)
    return world


def _refresh_metrics(world: WorldState) -> None:
    living = world.alive_npcs()
    world.metrics = {
        "population": float(world.total_population),
        "persistent_npcs": float(len(living)),
        "kingdoms": float(len(world.kingdoms)),
        "settlements": float(len(world.settlements)),
        "active_wars": float(len(world.active_wars())),
        "trade_routes": float(sum(1 for route in world.trade_routes.values() if route.active)),
        "average_stability": sum(k.stability for k in world.kingdoms.values()) / max(1, len(world.kingdoms)),
        "average_food_security": sum(s.food_security for s in world.settlements.values()) / max(1, len(world.settlements)),
    }
