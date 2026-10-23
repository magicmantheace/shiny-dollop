from __future__ import annotations

from hashlib import sha256
from random import Random

from .crawl_domain import CrawlFloor, CrawlLocation, LocationKind


THEMES = (
    "ashen_foundry",
    "flooded_catacombs",
    "glasswood",
    "storm_gallery",
    "verdant_ruins",
    "frostbound_halls",
)


def stable_id(prefix: str, *parts: object) -> str:
    payload = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(payload.encode('utf-8')).hexdigest()[:20]}"


def floor_seed(crawl_seed: str, floor_number: int) -> str:
    return sha256(f"{crawl_seed}:floor:v2:{floor_number}".encode("utf-8")).hexdigest()


def _link(locations: dict[str, CrawlLocation], left: str, right: str, cost: float) -> None:
    locations[left].adjacency[right] = cost
    locations[right].adjacency[left] = cost
    if right not in locations[left].exits:
        locations[left].exits.append(right)
    if left not in locations[right].exits:
        locations[right].exits.append(left)


def _mark_hidden(locations: dict[str, CrawlLocation], left: str, right: str) -> None:
    left_tag = f"hidden_path:{right}"
    right_tag = f"hidden_path:{left}"
    if left_tag not in locations[left].environmental_tags:
        locations[left].environmental_tags.append(left_tag)
    if right_tag not in locations[right].environmental_tags:
        locations[right].environmental_tags.append(right_tag)


def generate_floor(crawl_seed: str, floor_number: int) -> CrawlFloor:
    """Generate a deterministic connected floor graph with branches and strategic variation."""

    seed = floor_seed(crawl_seed, floor_number)
    rng = Random(int(seed[:16], 16))
    theme = THEMES[rng.randrange(len(THEMES))]
    danger = min(0.95, 0.16 + floor_number * 0.055 + rng.random() * 0.09)
    room_count = 8 + min(8, floor_number) + rng.randrange(0, 4)

    locations: dict[str, CrawlLocation] = {}
    ids = [stable_id("loc", crawl_seed, floor_number, index) for index in range(room_count)]
    entrance_id = ids[0]
    exit_id = ids[-1]

    safe_indices = {max(2, room_count // 3)}
    if room_count >= 12:
        safe_indices.add(max(3, (room_count * 2) // 3))

    for index, location_id in enumerate(ids):
        if index == 0:
            kind = LocationKind.ENTRANCE
            name = "Arrival Gate"
        elif index == room_count - 1:
            kind = LocationKind.EXIT
            name = "Advancement Gate"
        elif index in safe_indices:
            kind = LocationKind.SAFE_AREA
            name = f"Refuge {index}"
        elif index % 4 == 0:
            kind = LocationKind.ZONE
            name = f"Crossroads {index}"
        else:
            kind = LocationKind.ROOM
            name = f"Chamber {index}"

        local_danger = min(1.0, max(0.0, danger + rng.uniform(-0.16, 0.18)))
        safe = kind in {LocationKind.ENTRANCE, LocationKind.SAFE_AREA}
        hazards = [] if safe else (["environmental_pressure"] if local_danger >= 0.38 else [])
        if not safe and local_danger >= 0.64 and rng.random() < 0.55:
            hazards.append("severe_hazard")

        locations[location_id] = CrawlLocation(
            id=location_id,
            floor_number=floor_number,
            name=name,
            kind=kind,
            adjacency={},
            visibility=max(0.2, min(1.0, 0.94 - local_danger * 0.34)),
            hazards=hazards,
            exits=[],
            encounter_slots=0 if safe or kind == LocationKind.EXIT else 1 + int(local_danger > 0.62),
            loot_resource_nodes=[] if kind == LocationKind.ENTRANCE else (["recovery_cache"] if safe else ["search_node"]),
            environmental_tags=[theme, f"danger:{local_danger:.2f}", *( ["safe"] if safe else [] )],
            capacity=96 if kind == LocationKind.SAFE_AREA else None,
        )

    # Backbone guarantees an entrance-to-exit path.
    for index in range(room_count - 1):
        cost = round(0.85 + rng.random() * 0.8 + danger * 0.35, 3)
        _link(locations, ids[index], ids[index + 1], cost)

    # Add loops and shortcuts. Some shortcuts are tagged hidden/conditional for perception rules.
    extra_edges = max(2, room_count // 3)
    for edge_index in range(extra_edges):
        left_index = rng.randrange(0, room_count - 3)
        right_index = min(room_count - 1, left_index + rng.randrange(2, min(6, room_count - left_index)))
        left = ids[left_index]
        right = ids[right_index]
        if right in locations[left].adjacency:
            continue
        cost = round(0.95 + rng.random() * 1.15, 3)
        _link(locations, left, right, cost)
        if edge_index % 2 == 0:
            _mark_hidden(locations, left, right)

    # Every floor exposes at least one discoverable hidden shortcut so perception
    # differences are testable even when random extra-edge attempts collide.
    if not any(tag.startswith("hidden_path:") for loc in locations.values() for tag in loc.environmental_tags):
        left, right = ids[0], ids[2]
        if right not in locations[left].adjacency:
            _link(locations, left, right, round(1.15 + danger * 0.25, 3))
        _mark_hidden(locations, left, right)

    safe_ids = [ids[index] for index in sorted(safe_indices)]
    return CrawlFloor(
        number=floor_number,
        seed=seed,
        theme=theme,
        completion_rules={
            "type": "reach_exit",
            "minimum_survivors": 1,
            "floor_duration_ticks": 2_000 + floor_number * 400,
        },
        advancement_rules={"type": "surviving_crawlers_at_exit"},
        locations=locations,
        entrance_location_id=entrance_id,
        exit_location_ids=[exit_id],
        safe_area_ids=safe_ids,
        danger_level=danger,
        director_budget=100.0 + floor_number * 25.0,
        encounter_budget=75.0 + floor_number * 30.0,
    )
