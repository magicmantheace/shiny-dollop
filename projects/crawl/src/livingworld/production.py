from __future__ import annotations

import math
from collections import defaultdict

from .advanced_simulation import LivingWorldEngine
from .domain import (
    Kingdom,
    LaborCategory,
    ProductionSite,
    ResourceStock,
    Settlement,
    SettlementType,
    WorldState,
)


PRODUCTION_VERSION = 1

# Slice 3 keeps the existing ResourceStock inventory container but makes every
# material change flow through either a documented extraction/production site,
# consumption/spoilage, trade, or an explicit reserve transfer.
_RESOURCE_PRICES: dict[str, float] = {
    "grain": 1.0,
    "flour": 1.4,
    "food": 1.8,
    "livestock": 2.2,
    "meat": 2.8,
    "leather": 3.2,
    "logs": 1.3,
    "lumber": 2.0,
    "stone": 1.4,
    "masonry": 2.2,
    "fortification_materials": 3.0,
    "iron_ore": 2.6,
    "iron": 4.0,
    "tools": 6.0,
    "weapons": 9.0,
    "fiber": 1.2,
    "cloth": 2.5,
    "clothing": 4.0,
    "mana_crystal": 12.0,
    "refined_mana": 20.0,
    "magical_goods": 36.0,
    "herbs": 3.0,
}

_LEGACY_COMMODITY_MAP = {
    "timber": "logs",
    "iron": "iron_ore",
}

_SPOILAGE = {
    "grain": 0.0005,
    "flour": 0.0010,
    "food": 0.0040,
    "meat": 0.0060,
    "livestock": 0.0001,
    "fiber": 0.0002,
    "herbs": 0.0015,
}

_INSTALLED = False


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _stock(
    settlement: Settlement,
    resource: str,
    *,
    capacity: float,
    quantity: float = 0.0,
) -> ResourceStock:
    existing = settlement.resources.get(resource)
    if existing:
        existing.capacity = max(existing.capacity, capacity)
        existing.quantity = _clamp(existing.quantity, 0.0, existing.capacity)
        existing.base_price = _RESOURCE_PRICES.get(resource, existing.base_price)
        existing.price = max(0.05, existing.price)
        existing.production_per_day = 0.0
        existing.consumption_per_day = 0.0
        return existing
    created = ResourceStock(
        resource=resource,
        quantity=max(0.0, min(quantity, capacity)),
        capacity=max(1.0, capacity),
        base_price=_RESOURCE_PRICES.get(resource, 1.0),
        price=_RESOURCE_PRICES.get(resource, 1.0),
    )
    settlement.resources[resource] = created
    return created


def _reserve_stock(
    kingdom: Kingdom,
    resource: str,
    *,
    capacity: float,
    quantity: float = 0.0,
) -> ResourceStock:
    existing = kingdom.resource_reserves.get(resource)
    if existing:
        existing.capacity = max(existing.capacity, capacity)
        existing.quantity = _clamp(existing.quantity, 0.0, existing.capacity)
        return existing
    created = ResourceStock(
        resource=resource,
        quantity=max(0.0, min(quantity, capacity)),
        capacity=max(1.0, capacity),
        base_price=_RESOURCE_PRICES.get(resource, 1.0),
        price=_RESOURCE_PRICES.get(resource, 1.0),
    )
    kingdom.resource_reserves[resource] = created
    return created


def _move_legacy_stock(settlement: Settlement, legacy: str, replacement: str) -> float:
    old = settlement.resources.get(legacy)
    if not old:
        return 0.0
    legacy_rate = max(0.0, old.production_per_day)
    replacement_stock = settlement.resources.get(replacement)
    if replacement_stock is None:
        replacement_stock = ResourceStock(
            resource=replacement,
            quantity=old.quantity,
            capacity=max(1.0, old.capacity),
            base_price=_RESOURCE_PRICES[replacement],
            price=_RESOURCE_PRICES[replacement],
        )
        settlement.resources[replacement] = replacement_stock
    elif replacement != legacy:
        room = max(0.0, replacement_stock.capacity - replacement_stock.quantity)
        moved = min(room, old.quantity)
        replacement_stock.quantity += moved
        old.quantity -= moved
    old.quantity = 0.0 if replacement != legacy else old.quantity
    old.production_per_day = 0.0
    old.consumption_per_day = 0.0
    return legacy_rate


def _site(
    settlement: Settlement,
    kind: str,
    labor: LaborCategory,
    worker_capacity: int,
    inputs: dict[str, float],
    outputs: dict[str, float],
    throughput: float,
    *,
    efficiency: float = 1.0,
) -> None:
    site_id = f"production:{settlement.id}:{kind}"
    settlement.production_sites[site_id] = ProductionSite(
        id=site_id,
        settlement_id=settlement.id,
        kind=kind,
        labor_category=labor,
        worker_capacity=max(1, worker_capacity),
        inputs=inputs,
        outputs=outputs,
        base_throughput=max(0.01, throughput),
        efficiency=max(0.1, efficiency),
    )


def initialize_settlement_production(engine: LivingWorldEngine, settlement: Settlement) -> None:
    if settlement.production_initialized:
        return
    if settlement.population <= 0 or settlement.type == SettlementType.RUIN:
        settlement.production_initialized = True
        settlement.labor_allocation = {LaborCategory.DEPENDENT.value: max(0, settlement.population)}
        return

    population = max(1, settlement.population)

    # Capture the old generated suitability before retiring the legacy independent
    # production rates. Those generated rates become the capacity input for explicit
    # extraction sites rather than continuing to mint every stock independently.
    grain_rate = max(0.0, settlement.resources.get("grain", ResourceStock(resource="grain")).production_per_day)
    livestock_rate = max(0.0, settlement.resources.get("livestock", ResourceStock(resource="livestock")).production_per_day)
    timber_rate = _move_legacy_stock(settlement, "timber", "logs")
    stone_rate = max(0.0, settlement.resources.get("stone", ResourceStock(resource="stone")).production_per_day)
    iron_rate = _move_legacy_stock(settlement, "iron", "iron_ore")
    mana_rate = max(0.0, settlement.resources.get("mana_crystal", ResourceStock(resource="mana_crystal")).production_per_day)

    # Retain existing raw inventories while disabling the old direct daily rates.
    for name in ("grain", "livestock", "stone", "mana_crystal", "herbs"):
        existing = settlement.resources.get(name)
        if existing:
            existing.production_per_day = 0.0
            existing.consumption_per_day = 0.0

    # Explicit raw and processed inventories. Finished-goods bootstrap amounts are
    # small working stocks so a newly migrated world does not starve during the first
    # few production days; after initialization all flow is material-accounted.
    _stock(settlement, "grain", capacity=max(120.0, population * 1.20))
    _stock(settlement, "livestock", capacity=max(70.0, population * 0.55))
    _stock(settlement, "logs", capacity=max(90.0, population * 0.80))
    _stock(settlement, "stone", capacity=max(80.0, population * 0.65))
    _stock(settlement, "iron_ore", capacity=max(45.0, population * 0.35))
    _stock(settlement, "mana_crystal", capacity=max(12.0, population * 0.08))
    _stock(settlement, "fiber", capacity=max(50.0, population * 0.40), quantity=population * 0.05)

    _stock(settlement, "flour", capacity=max(50.0, population * 0.45), quantity=population * 0.02)
    _stock(settlement, "food", capacity=max(70.0, population * 0.80), quantity=population * 0.12)
    _stock(settlement, "meat", capacity=max(35.0, population * 0.25), quantity=population * 0.015)
    _stock(settlement, "leather", capacity=max(25.0, population * 0.18))
    _stock(settlement, "lumber", capacity=max(50.0, population * 0.38))
    _stock(settlement, "iron", capacity=max(28.0, population * 0.20))
    _stock(settlement, "tools", capacity=max(20.0, population * 0.12), quantity=population * 0.015)
    _stock(settlement, "weapons", capacity=max(15.0, population * 0.08), quantity=population * 0.004)
    _stock(settlement, "masonry", capacity=max(45.0, population * 0.32))
    _stock(settlement, "fortification_materials", capacity=max(25.0, population * 0.18))
    _stock(settlement, "cloth", capacity=max(35.0, population * 0.28))
    _stock(settlement, "clothing", capacity=max(35.0, population * 0.25), quantity=population * 0.02)
    _stock(settlement, "refined_mana", capacity=max(8.0, population * 0.04))
    _stock(settlement, "magical_goods", capacity=max(5.0, population * 0.02))

    workshops = max(1, settlement.buildings.get("workshops", 1))
    workshop_factor = _clamp(0.70 + math.log1p(workshops) * 0.12, 0.7, 1.35)

    _site(settlement, "grain_farms", LaborCategory.AGRICULTURE, math.ceil(population * 0.050), {}, {"grain": 1.0}, max(grain_rate * 0.18, population * 0.012))
    _site(settlement, "ranches", LaborCategory.AGRICULTURE, math.ceil(population * 0.025), {}, {"livestock": 1.0}, max(livestock_rate * 0.12, population * 0.0035))
    _site(settlement, "fiber_farms", LaborCategory.AGRICULTURE, math.ceil(population * 0.020), {}, {"fiber": 1.0}, population * 0.003)
    _site(settlement, "logging_camps", LaborCategory.EXTRACTION, math.ceil(population * 0.025), {}, {"logs": 1.0}, max(timber_rate * 0.12, population * 0.005))
    _site(settlement, "quarries", LaborCategory.EXTRACTION, math.ceil(population * 0.020), {}, {"stone": 1.0}, max(stone_rate * 0.10, population * 0.003))
    _site(settlement, "iron_mines", LaborCategory.EXTRACTION, math.ceil(population * 0.015), {}, {"iron_ore": 1.0}, max(iron_rate * 0.08, population * 0.0014))
    _site(settlement, "mana_sites", LaborCategory.EXTRACTION, math.ceil(population * 0.008), {}, {"mana_crystal": 1.0}, max(mana_rate * 0.06, population * 0.00018), efficiency=0.65 + settlement.magic_intensity * 0.7)

    _site(settlement, "mills", LaborCategory.CRAFTS, math.ceil(population * 0.015), {"grain": 1.0}, {"flour": 0.90}, population * 0.010, efficiency=workshop_factor)
    _site(settlement, "foodworks", LaborCategory.CRAFTS, math.ceil(population * 0.020), {"flour": 0.75}, {"food": 1.0}, population * 0.009, efficiency=workshop_factor)
    _site(settlement, "butchers", LaborCategory.CRAFTS, math.ceil(population * 0.012), {"livestock": 0.80}, {"meat": 0.55, "leather": 0.25}, population * 0.0025, efficiency=workshop_factor)
    _site(settlement, "sawmills", LaborCategory.CRAFTS, math.ceil(population * 0.012), {"logs": 1.0}, {"lumber": 0.75}, population * 0.004, efficiency=workshop_factor)
    _site(settlement, "smelters", LaborCategory.CRAFTS, math.ceil(population * 0.010), {"iron_ore": 1.0}, {"iron": 0.65}, population * 0.0012, efficiency=workshop_factor)
    _site(settlement, "toolsmiths", LaborCategory.CRAFTS, math.ceil(population * 0.008), {"iron": 0.60, "lumber": 0.25}, {"tools": 0.50}, population * 0.0008, efficiency=workshop_factor)
    _site(settlement, "weaponsmiths", LaborCategory.CRAFTS, math.ceil(population * 0.006), {"iron": 0.80, "lumber": 0.20}, {"weapons": 0.45}, population * 0.00025, efficiency=workshop_factor)
    _site(settlement, "masons", LaborCategory.CRAFTS, math.ceil(population * 0.008), {"stone": 1.0}, {"masonry": 0.75}, population * 0.0025, efficiency=workshop_factor)
    _site(settlement, "fortification_works", LaborCategory.CRAFTS, math.ceil(population * 0.006), {"masonry": 1.0}, {"fortification_materials": 0.80}, population * 0.0010, efficiency=workshop_factor)
    _site(settlement, "looms", LaborCategory.CRAFTS, math.ceil(population * 0.010), {"fiber": 1.0}, {"cloth": 0.80}, population * 0.0024, efficiency=workshop_factor)
    _site(settlement, "tailors", LaborCategory.CRAFTS, math.ceil(population * 0.010), {"cloth": 0.80}, {"clothing": 0.70}, population * 0.0016, efficiency=workshop_factor)
    _site(settlement, "mana_refineries", LaborCategory.CRAFTS, math.ceil(population * 0.005), {"mana_crystal": 0.50}, {"refined_mana": 0.35}, population * 0.00015, efficiency=workshop_factor)
    _site(settlement, "enchanters", LaborCategory.CRAFTS, math.ceil(population * 0.004), {"refined_mana": 0.25, "tools": 0.05}, {"magical_goods": 0.12}, population * 0.00004, efficiency=workshop_factor * (0.55 + settlement.magic_intensity))

    settlement.production_initialized = True
    allocate_labor(engine, settlement)


def _kingdom_population(engine: LivingWorldEngine, kingdom: Kingdom) -> int:
    return sum(
        max(0, engine.world.settlements[sid].population)
        for sid in kingdom.settlement_ids
        if sid in engine.world.settlements
    )


def initialize_kingdom_reserves(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
    population = max(1, _kingdom_population(engine, kingdom))
    food_capacity = max(100.0, population * 0.45)
    existing_food = kingdom.resource_reserves.get("food")
    if existing_food is None:
        # Convert the pre-Slice-3 abstract food-reserve ratio into explicit starting
        # material once. This preserves the prior world's state instead of inventing
        # a second reserve on top of it.
        _reserve_stock(
            kingdom,
            "food",
            capacity=food_capacity,
            quantity=food_capacity * _clamp(kingdom.food_reserve),
        )
    else:
        _reserve_stock(kingdom, "food", capacity=food_capacity)
    _reserve_stock(kingdom, "tools", capacity=max(25.0, population * 0.04))
    _reserve_stock(kingdom, "weapons", capacity=max(20.0, population * 0.03))
    _reserve_stock(kingdom, "masonry", capacity=max(30.0, population * 0.05))


def _migrate_trade_commodities(engine: LivingWorldEngine) -> None:
    for route in engine.world.trade_routes.values():
        migrated: list[str] = []
        for commodity in route.commodities:
            replacement = _LEGACY_COMMODITY_MAP.get(commodity, commodity)
            if replacement not in migrated:
                migrated.append(replacement)
        route.commodities = migrated


def ensure_production_society(engine: LivingWorldEngine) -> None:
    for settlement in engine.world.settlements.values():
        if not settlement.production_initialized:
            initialize_settlement_production(engine, settlement)
        elif sum(settlement.labor_allocation.values()) != max(0, settlement.population):
            allocate_labor(engine, settlement)
    for kingdom in engine.world.kingdoms.values():
        initialize_kingdom_reserves(engine, kingdom)
    _migrate_trade_commodities(engine)
    refresh_production_metrics(engine)


def _split_workers(total: int, sites: list[ProductionSite]) -> dict[str, int]:
    if total <= 0 or not sites:
        return {site.id: 0 for site in sites}
    demand = sum(max(1, site.worker_capacity) for site in sites)
    if demand <= 0:
        return {site.id: 0 for site in sites}
    raw = {site.id: total * max(1, site.worker_capacity) / demand for site in sites}
    assigned = {site.id: min(site.worker_capacity, int(raw[site.id])) for site in sites}
    remaining = total - sum(assigned.values())
    order = sorted(
        sites,
        key=lambda site: (raw[site.id] - int(raw[site.id]), site.id),
        reverse=True,
    )
    while remaining > 0:
        progressed = False
        for site in order:
            if remaining <= 0:
                break
            if assigned[site.id] >= site.worker_capacity:
                continue
            assigned[site.id] += 1
            remaining -= 1
            progressed = True
        if not progressed:
            break
    return assigned


def allocate_labor(engine: LivingWorldEngine, settlement: Settlement) -> None:
    population = max(0, settlement.population)
    if population <= 0:
        settlement.labor_allocation = {LaborCategory.DEPENDENT.value: 0}
        for site in settlement.production_sites.values():
            site.assigned_workers = 0
        return

    workforce = max(0, min(population, int(population * 0.58)))
    kingdom = engine.world.kingdoms.get(settlement.kingdom_id)
    conscription = 0.35
    admin_reach = 0.55
    if kingdom:
        conscription = kingdom.effective_policies.get("conscription", kingdom.laws.conscription)
        admin_reach = kingdom.institutions.administrative_reach

    fixed = {
        LaborCategory.ADMINISTRATION.value: int(workforce * (0.045 + admin_reach * 0.025)),
        LaborCategory.RELIGION.value: int(workforce * 0.040),
        LaborCategory.MILITARY.value: int(workforce * (0.070 + _clamp(conscription) * 0.080)),
        LaborCategory.TRADE.value: int(workforce * 0.100),
        LaborCategory.SERVICES.value: int(workforce * 0.180),
    }
    fixed_total = min(workforce, sum(fixed.values()))
    if sum(fixed.values()) > workforce and fixed_total > 0:
        scale = workforce / sum(fixed.values())
        fixed = {key: int(value * scale) for key, value in fixed.items()}
        fixed_total = sum(fixed.values())

    production_pool = max(0, workforce - fixed_total)
    by_category: dict[LaborCategory, list[ProductionSite]] = defaultdict(list)
    for site in settlement.production_sites.values():
        if site.active:
            by_category[site.labor_category].append(site)

    productive_categories = [LaborCategory.AGRICULTURE, LaborCategory.EXTRACTION, LaborCategory.CRAFTS]
    demand_by_category = {
        category: sum(site.worker_capacity for site in by_category.get(category, []))
        for category in productive_categories
    }
    total_demand = sum(demand_by_category.values())
    category_workers: dict[LaborCategory, int] = {category: 0 for category in productive_categories}
    if total_demand > 0 and production_pool > 0:
        raw = {
            category: production_pool * demand_by_category[category] / total_demand
            for category in productive_categories
        }
        category_workers = {
            category: min(demand_by_category[category], int(raw[category]))
            for category in productive_categories
        }
        remaining = production_pool - sum(category_workers.values())
        for category in sorted(
            productive_categories,
            key=lambda item: (raw[item] - int(raw[item]), item.value),
            reverse=True,
        ):
            if remaining <= 0:
                break
            room = demand_by_category[category] - category_workers[category]
            take = min(room, remaining)
            category_workers[category] += take
            remaining -= take

    for category in productive_categories:
        assignment = _split_workers(category_workers[category], by_category.get(category, []))
        for site in by_category.get(category, []):
            site.assigned_workers = assignment.get(site.id, 0)

    used_workforce = sum(fixed.values()) + sum(category_workers.values())
    dependent = max(0, population - used_workforce)
    settlement.labor_allocation = {
        LaborCategory.AGRICULTURE.value: category_workers[LaborCategory.AGRICULTURE],
        LaborCategory.EXTRACTION.value: category_workers[LaborCategory.EXTRACTION],
        LaborCategory.CRAFTS.value: category_workers[LaborCategory.CRAFTS],
        **fixed,
        LaborCategory.DEPENDENT.value: dependent,
    }


def _season_factor(month: int, category: LaborCategory) -> float:
    if category != LaborCategory.AGRICULTURE:
        return 1.0
    return {
        1: 0.55,
        2: 0.65,
        3: 0.80,
        4: 0.95,
        5: 1.05,
        6: 1.15,
        7: 1.30,
        8: 1.25,
        9: 1.15,
        10: 1.00,
        11: 0.80,
        12: 0.65,
    }.get(month, 1.0)


def _record_shortage(settlement: Settlement, key: str, severity: float) -> None:
    settlement.production_shortages[key] = max(
        settlement.production_shortages.get(key, 0.0),
        _clamp(severity),
    )


def _run_site(engine: LivingWorldEngine, settlement: Settlement, site: ProductionSite) -> float:
    if not site.active or site.assigned_workers <= 0 or site.worker_capacity <= 0:
        return 0.0

    labor_factor = _clamp(site.assigned_workers / max(1, site.worker_capacity))
    if labor_factor < 0.75:
        _record_shortage(settlement, f"labor:{site.labor_category.value}", 1.0 - labor_factor)

    health_factor = 0.65 + _clamp(settlement.health) * 0.35
    roads = _clamp(settlement.infrastructure.get("roads", 0.5))
    infrastructure_factor = 0.72 + roads * 0.28
    security_factor = _clamp(1.0 - settlement.crime * 0.55, 0.35, 1.0)
    if settlement.besieged_by_kingdom_id:
        security_factor *= 0.55
    elif settlement.occupied_by_kingdom_id and settlement.occupied_by_kingdom_id != settlement.kingdom_id:
        security_factor *= 0.75

    tools = settlement.resources.get("tools")
    tool_fill = 0.0 if not tools else tools.quantity / max(1.0, settlement.population * 0.015)
    tool_factor = 0.65 + min(1.0, tool_fill) * 0.35
    if site.labor_category == LaborCategory.AGRICULTURE:
        tool_factor = 0.78 + min(1.0, tool_fill) * 0.22

    desired = (
        site.base_throughput
        * site.efficiency
        * labor_factor
        * health_factor
        * infrastructure_factor
        * security_factor
        * tool_factor
        * _season_factor(engine.world.date.month, site.labor_category)
    )
    if desired <= 0:
        return 0.0

    input_limit = math.inf
    for resource, per_unit in site.inputs.items():
        if per_unit <= 0:
            continue
        stock = settlement.resources.get(resource)
        available_units = 0.0 if stock is None else stock.quantity / per_unit
        input_limit = min(input_limit, available_units)
        if available_units < desired:
            _record_shortage(settlement, resource, 1.0 - available_units / max(0.001, desired))

    output_limit = math.inf
    for resource, per_unit in site.outputs.items():
        if per_unit <= 0:
            continue
        stock = settlement.resources.get(resource)
        if stock is None:
            continue
        output_limit = min(output_limit, max(0.0, stock.capacity - stock.quantity) / per_unit)

    units = min(desired, input_limit, output_limit)
    if not math.isfinite(units):
        units = desired
    units = max(0.0, units)
    if units <= 0:
        return 0.0

    for resource, per_unit in site.inputs.items():
        stock = settlement.resources[resource]
        amount = min(stock.quantity, units * per_unit)
        stock.quantity -= amount
        settlement.consumption_last_day[resource] = settlement.consumption_last_day.get(resource, 0.0) + amount

    produced_total = 0.0
    for resource, per_unit in site.outputs.items():
        stock = settlement.resources[resource]
        amount = units * per_unit
        stock.quantity = min(stock.capacity, stock.quantity + amount)
        settlement.production_last_day[resource] = settlement.production_last_day.get(resource, 0.0) + amount
        produced_total += amount
    return produced_total


def _consume(settlement: Settlement, resource: str, amount: float) -> float:
    if amount <= 0:
        return 0.0
    stock = settlement.resources.get(resource)
    if stock is None or stock.quantity <= 0:
        return 0.0
    used = min(stock.quantity, amount)
    stock.quantity -= used
    settlement.consumption_last_day[resource] = settlement.consumption_last_day.get(resource, 0.0) + used
    return used


def _consume_households(settlement: Settlement) -> None:
    population = max(0, settlement.population)
    if population <= 0:
        return

    demand = max(0.01, population * 0.010)
    remaining = demand
    nutrition = 0.0
    for resource, value in (("food", 1.0), ("meat", 0.95), ("flour", 0.82), ("grain", 0.72)):
        if remaining <= 0:
            break
        needed_material = remaining / value
        used = _consume(settlement, resource, needed_material)
        supplied = used * value
        nutrition += supplied
        remaining -= supplied

    reserve_nutrition = 0.0
    for resource, value in (("food", 1.0), ("meat", 0.95), ("flour", 0.82), ("grain", 0.72)):
        stock = settlement.resources.get(resource)
        if stock:
            reserve_nutrition += stock.quantity * value
    reserve_days = reserve_nutrition / max(0.01, demand)
    fulfillment = _clamp(nutrition / max(0.01, demand))
    target_food_security = _clamp(fulfillment * 0.68 + min(1.0, reserve_days / 45.0) * 0.32)
    settlement.food_security = _clamp(settlement.food_security + (target_food_security - settlement.food_security) * 0.10)

    production_workers = sum(
        settlement.labor_allocation.get(category.value, 0)
        for category in (LaborCategory.AGRICULTURE, LaborCategory.EXTRACTION, LaborCategory.CRAFTS)
    )
    _consume(settlement, "tools", production_workers * 0.00005)
    _consume(settlement, "clothing", population * 0.00008)

    settlement.health = _clamp(
        settlement.health + (settlement.food_security - 0.55) * 0.001 - settlement.crime * 0.0002,
        0.15,
        1.0,
    )


def _apply_spoilage(settlement: Settlement) -> None:
    for resource, rate in _SPOILAGE.items():
        stock = settlement.resources.get(resource)
        if not stock or stock.quantity <= 0:
            continue
        spoiled = min(stock.quantity, stock.quantity * rate)
        stock.quantity -= spoiled
        settlement.consumption_last_day[resource] = settlement.consumption_last_day.get(resource, 0.0) + spoiled


def _update_compatibility_prices(settlement: Settlement) -> None:
    # Slice 4 will replace this with actual markets. For now preserve the old API's
    # simple scarcity signal so existing trade code continues to function.
    for stock in settlement.resources.values():
        fill = stock.quantity / max(1.0, stock.capacity)
        scarcity = max(0.35, min(3.5, 1.35 - fill * 1.05))
        stock.price = max(0.05, stock.base_price * scarcity)


def _manage_kingdom_food_reserve(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
    initialize_kingdom_reserves(engine, kingdom)
    reserve = kingdom.resource_reserves["food"]
    population = max(1, _kingdom_population(engine, kingdom))
    policy = _clamp(kingdom.laws.grain_reserve)
    target = reserve.capacity * (0.25 + policy * 0.50)

    settlements = [
        engine.world.settlements[sid]
        for sid in kingdom.settlement_ids
        if sid in engine.world.settlements and engine.world.settlements[sid].population > 0
    ]
    if reserve.quantity < target:
        needed = target - reserve.quantity
        for settlement in sorted(settlements, key=lambda item: item.id):
            stock = settlement.resources.get("food")
            if not stock:
                continue
            protected = stock.capacity * 0.55
            surplus = max(0.0, stock.quantity - protected)
            compliance = kingdom.policy_compliance.get(settlement.id, 0.5)
            take = min(needed, surplus * policy * compliance * 0.08)
            if take <= 0:
                continue
            stock.quantity -= take
            reserve.quantity += take
            needed -= take
            if needed <= 0:
                break

    # Material relief now moves real reserve inventory. It does not create food.
    for settlement in sorted(settlements, key=lambda item: item.id):
        if reserve.quantity <= 0 or settlement.food_security >= 0.45:
            continue
        stock = settlement.resources.get("food")
        if not stock:
            continue
        compliance = kingdom.policy_compliance.get(settlement.id, 0.5)
        desired = settlement.population * 0.04 * policy * compliance
        moved = min(desired, reserve.quantity, max(0.0, stock.capacity - stock.quantity))
        if moved <= 0:
            continue
        reserve.quantity -= moved
        stock.quantity += moved

    kingdom.food_reserve = _clamp(reserve.quantity / max(1.0, reserve.capacity))


def run_production_day(engine: LivingWorldEngine) -> None:
    for settlement in engine.world.settlements.values():
        if not settlement.production_initialized:
            initialize_settlement_production(engine, settlement)
        if settlement.population <= 0 or settlement.type == SettlementType.RUIN:
            continue
        if engine.world.date.day == 1:
            allocate_labor(engine, settlement)

        settlement.production_shortages = {}
        settlement.production_last_day = {}
        settlement.consumption_last_day = {}

        for site in sorted(settlement.production_sites.values(), key=lambda item: item.id):
            _run_site(engine, settlement, site)
        _consume_households(settlement)
        _apply_spoilage(settlement)
        _update_compatibility_prices(settlement)

    if engine.world.date.day == 1:
        for kingdom in engine.world.kingdoms.values():
            _manage_kingdom_food_reserve(engine, kingdom)


def refresh_production_metrics(engine: LivingWorldEngine) -> None:
    active = [
        settlement
        for settlement in engine.world.settlements.values()
        if settlement.population > 0 and settlement.type != SettlementType.RUIN
    ]
    sites = [site for settlement in active for site in settlement.production_sites.values() if site.active]
    worker_capacity = sum(site.worker_capacity for site in sites)
    assigned_workers = sum(site.assigned_workers for site in sites)
    engine.world.metrics["production_sites"] = float(len(sites))
    engine.world.metrics["average_labor_utilization"] = (
        assigned_workers / max(1, worker_capacity)
    )
    engine.world.metrics["labor_shortage_settlements"] = float(
        sum(
            1
            for settlement in active
            if any(key.startswith("labor:") for key in settlement.production_shortages)
        )
    )
    engine.world.metrics["material_shortage_settlements"] = float(
        sum(1 for settlement in active if settlement.production_shortages)
    )
    engine.world.metrics["production_throughput_last_day"] = sum(
        sum(settlement.production_last_day.values()) for settlement in active
    )
    engine.world.metrics["total_food_inventory"] = sum(
        settlement.resources.get("food", ResourceStock(resource="food")).quantity
        for settlement in active
    )
    engine.world.metrics["total_tools_inventory"] = sum(
        settlement.resources.get("tools", ResourceStock(resource="tools")).quantity
        for settlement in active
    )
    engine.world.metrics["kingdom_food_reserves"] = sum(
        kingdom.resource_reserves.get("food", ResourceStock(resource="food")).quantity
        for kingdom in engine.world.kingdoms.values()
    )


def validate_production(world: WorldState) -> list[str]:
    errors: list[str] = []
    for settlement in world.settlements.values():
        if settlement.population > 0 and settlement.type != SettlementType.RUIN and not settlement.production_initialized:
            errors.append(f"{settlement.id}: production not initialized")
        if settlement.production_initialized:
            labor_total = sum(settlement.labor_allocation.values())
            if labor_total != max(0, settlement.population):
                errors.append(
                    f"{settlement.id}: labor allocation totals {labor_total}, population is {settlement.population}"
                )
        for resource, stock in settlement.resources.items():
            if not math.isfinite(stock.quantity) or stock.quantity < -1e-9:
                errors.append(f"{settlement.id}:{resource}: negative/non-finite inventory")
            if not math.isfinite(stock.capacity) or stock.capacity <= 0:
                errors.append(f"{settlement.id}:{resource}: invalid capacity")
            if stock.quantity > stock.capacity + 1e-6:
                errors.append(f"{settlement.id}:{resource}: inventory exceeds capacity")
        for site in settlement.production_sites.values():
            if site.settlement_id != settlement.id:
                errors.append(f"{site.id}: production site belongs to {site.settlement_id}, expected {settlement.id}")
            if site.worker_capacity <= 0:
                errors.append(f"{site.id}: worker capacity must be positive")
            if not 0 <= site.assigned_workers <= site.worker_capacity:
                errors.append(f"{site.id}: assigned workers out of range")
            for resource in [*site.inputs, *site.outputs]:
                if resource not in settlement.resources:
                    errors.append(f"{site.id}: references missing inventory {resource}")

    for kingdom in world.kingdoms.values():
        if "food" not in kingdom.resource_reserves:
            errors.append(f"{kingdom.id}: missing explicit food reserve")
        for resource, stock in kingdom.resource_reserves.items():
            if not math.isfinite(stock.quantity) or stock.quantity < -1e-9:
                errors.append(f"{kingdom.id}:{resource}: negative/non-finite reserve")
            if stock.quantity > stock.capacity + 1e-6:
                errors.append(f"{kingdom.id}:{resource}: reserve exceeds capacity")
    return errors


def _production_noop_harvest(self: LivingWorldEngine) -> None:
    # Agriculture is already seasonal inside explicit farm sites. Retaining the old
    # seasonal pulse would create grain outside the material-flow ledger.
    return None


def _production_day(self: LivingWorldEngine) -> None:
    run_production_day(self)


def install_production_model() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    # Capture wrappers at installation time, after Slice 2 has installed its own
    # initialization and post-advance synchronization layers.
    original_init = LivingWorldEngine.__init__
    original_advance_hours = LivingWorldEngine.advance_hours

    def init_with_production(self, world, event_sink=None) -> None:
        original_init(self, world, event_sink)
        ensure_production_society(self)

    def advance_with_production_sync(self, hours: int, *, ignore_pause: bool = False):
        world = original_advance_hours(self, hours, ignore_pause=ignore_pause)
        ensure_production_society(self)
        return world

    LivingWorldEngine.__init__ = init_with_production
    LivingWorldEngine.advance_hours = advance_with_production_sync
    LivingWorldEngine._produce_and_consume = _production_day
    LivingWorldEngine._seasonal_harvest = _production_noop_harvest
    _INSTALLED = True
