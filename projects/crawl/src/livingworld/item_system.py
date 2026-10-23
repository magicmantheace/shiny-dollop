from __future__ import annotations

from hashlib import sha256
from random import Random

from .crawl_domain import Crawl, CrawlerParticipation
from .gameplay_domain import CrawlItem, EquipmentSlot, ItemCategory, ItemRarity


RARITY_MULTIPLIER = {
    ItemRarity.COMMON: 1.0,
    ItemRarity.UNCOMMON: 1.25,
    ItemRarity.RARE: 1.6,
    ItemRarity.EPIC: 2.1,
}


def _stable_id(prefix: str, *parts: object) -> str:
    digest = sha256(":".join(str(part) for part in parts).encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def generate_item(seed: str, *, source_id: str, index: int, floor_number: int, holder: str) -> CrawlItem:
    digest = sha256(f"{seed}:{source_id}:{index}:item".encode("utf-8")).hexdigest()
    rng = Random(int(digest[:16], 16))
    rarity_roll = rng.random() + min(0.25, floor_number * 0.015)
    if rarity_roll > 1.08:
        rarity = ItemRarity.EPIC
    elif rarity_roll > 0.86:
        rarity = ItemRarity.RARE
    elif rarity_roll > 0.58:
        rarity = ItemRarity.UNCOMMON
    else:
        rarity = ItemRarity.COMMON

    categories = (ItemCategory.WEAPON, ItemCategory.ARMOR, ItemCategory.CONSUMABLE, ItemCategory.TRINKET)
    category = categories[rng.randrange(len(categories))]
    multiplier = RARITY_MULTIPLIER[rarity] * (1.0 + floor_number * 0.04)
    item_id = _stable_id("item", seed, source_id, index, floor_number)

    if category == ItemCategory.WEAPON:
        return CrawlItem(
            id=item_id,
            name=f"{rarity.value.title()} Edge",
            category=category,
            rarity=rarity,
            slot=EquipmentSlot.MAIN_HAND,
            stats={"attack": round((0.08 + rng.random() * 0.12) * multiplier, 4), "accuracy": round(0.02 * multiplier, 4)},
            encounter_id=holder,
            important=rarity in {ItemRarity.RARE, ItemRarity.EPIC},
        )
    if category == ItemCategory.ARMOR:
        return CrawlItem(
            id=item_id,
            name=f"{rarity.value.title()} Guard",
            category=category,
            rarity=rarity,
            slot=EquipmentSlot.ARMOR,
            stats={"armor": round((0.06 + rng.random() * 0.10) * multiplier, 4), "defense": round(0.025 * multiplier, 4)},
            encounter_id=holder,
            important=rarity in {ItemRarity.RARE, ItemRarity.EPIC},
        )
    if category == ItemCategory.TRINKET:
        return CrawlItem(
            id=item_id,
            name=f"{rarity.value.title()} Sigil",
            category=category,
            rarity=rarity,
            slot=EquipmentSlot.TRINKET,
            stats={"evasion": round(0.018 * multiplier, 4), "stamina": round(0.04 * multiplier, 4)},
            encounter_id=holder,
            important=rarity in {ItemRarity.RARE, ItemRarity.EPIC},
        )
    return CrawlItem(
        id=item_id,
        name=f"{rarity.value.title()} Recovery Draught",
        category=category,
        rarity=rarity,
        effects={"heal": round((0.16 + rng.random() * 0.16) * multiplier, 4), "stamina": round(0.12 * multiplier, 4)},
        encounter_id=holder,
    )


def item_score(item: CrawlItem, participant: CrawlerParticipation) -> float:
    agent = participant.agent
    if agent is None:
        return 0.0
    score = 0.0
    score += item.stats.get("attack", 0.0) * (0.6 + agent.skills.melee)
    score += item.stats.get("accuracy", 0.0) * (0.6 + agent.skills.ranged)
    score += item.stats.get("armor", 0.0) * (0.8 + agent.skills.defense)
    score += item.stats.get("defense", 0.0) * (0.8 + agent.skills.defense)
    score += item.stats.get("evasion", 0.0) * (0.5 + agent.traits.caution)
    score += item.stats.get("stamina", 0.0) * (0.5 + (1.0 - participant.gameplay.stamina))
    score += item.effects.get("heal", 0.0) * (1.0 + (1.0 - participant.health))
    score *= 0.85 + agent.traits.greed * 0.3
    return score


def transfer_item_to_crawler(crawl: Crawl, item_id: str, npc_id: str) -> CrawlItem:
    item = crawl.items[item_id]
    participant = crawl.participants[npc_id]
    if item.owner_npc_id is not None:
        old_owner = crawl.participants[item.owner_npc_id]
        if item_id in old_owner.gameplay.inventory_item_ids:
            old_owner.gameplay.inventory_item_ids.remove(item_id)
        for slot, equipped_id in list(old_owner.gameplay.equipment.items()):
            if equipped_id == item_id:
                del old_owner.gameplay.equipment[slot]
    item.owner_npc_id = npc_id
    item.location_id = None
    item.encounter_id = None
    if item_id not in participant.gameplay.inventory_item_ids:
        participant.gameplay.inventory_item_ids.append(item_id)
    return item


def drop_item(crawl: Crawl, item_id: str, location_id: str) -> CrawlItem:
    item = crawl.items[item_id]
    if item.owner_npc_id is not None:
        participant = crawl.participants[item.owner_npc_id]
        if item_id in participant.gameplay.inventory_item_ids:
            participant.gameplay.inventory_item_ids.remove(item_id)
        for slot, equipped_id in list(participant.gameplay.equipment.items()):
            if equipped_id == item_id:
                del participant.gameplay.equipment[slot]
    item.owner_npc_id = None
    item.encounter_id = None
    item.location_id = location_id
    return item


def choose_and_equip(crawl: Crawl, npc_id: str) -> list[str]:
    participant = crawl.participants[npc_id]
    equipped: list[str] = []
    candidates = [crawl.items[item_id] for item_id in participant.gameplay.inventory_item_ids]
    for slot in EquipmentSlot:
        matching = [item for item in candidates if item.slot == slot]
        if not matching:
            continue
        best = max(matching, key=lambda item: (item_score(item, participant), item.id))
        participant.gameplay.equipment[slot.value] = best.id
        equipped.append(best.id)
    if participant.agent is not None:
        quality = sum(item_score(crawl.items[item_id], participant) for item_id in equipped)
        participant.agent.needs.equipment_readiness = max(0.0, min(1.0, 0.35 + quality))
    return equipped


def consume_best_healing_item(crawl: Crawl, npc_id: str) -> str | None:
    participant = crawl.participants[npc_id]
    candidates = [
        crawl.items[item_id]
        for item_id in participant.gameplay.inventory_item_ids
        if crawl.items[item_id].category == ItemCategory.CONSUMABLE and crawl.items[item_id].effects.get("heal", 0.0) > 0
    ]
    if not candidates:
        return None
    item = max(candidates, key=lambda value: (value.effects.get("heal", 0.0), value.id))
    participant.health = min(1.0, participant.health + item.effects.get("heal", 0.0))
    participant.gameplay.stamina = min(1.0, participant.gameplay.stamina + item.effects.get("stamina", 0.0))
    participant.gameplay.inventory_item_ids.remove(item.id)
    participant.gameplay.equipment = {slot: iid for slot, iid in participant.gameplay.equipment.items() if iid != item.id}
    for encounter in crawl.encounters.values():
        if item.id in encounter.reward_item_ids:
            encounter.reward_item_ids.remove(item.id)
    del crawl.items[item.id]
    return item.id


def drop_all_on_death(crawl: Crawl, npc_id: str) -> list[str]:
    participant = crawl.participants[npc_id]
    if participant.current_location_id is None:
        return []
    dropped = list(participant.gameplay.inventory_item_ids)
    for item_id in dropped:
        drop_item(crawl, item_id, participant.current_location_id)
    return dropped
