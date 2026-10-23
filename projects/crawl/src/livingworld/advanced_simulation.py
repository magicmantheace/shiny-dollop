from __future__ import annotations

import random

from .domain import (
    Ancestry,
    Army,
    Culture,
    DiplomaticRelation,
    GovernmentType,
    Kingdom,
    NPC,
    Relationship,
    War,
)
from .generation import FIRST_NAMES, GOALS, OCCUPATIONS, _refresh_metrics
from .politics import (
    ensure_political_society,
    initialize_kingdom_politics,
    rebellion_candidate,
    refresh_political_metrics,
    run_political_cycle,
    succession_check,
)
from .simulation import WorldEngine


class LivingWorldEngine(WorldEngine):
    """WorldEngine extensions that let people and political entities outlive founders."""

    def __init__(self, world, event_sink=None) -> None:
        super().__init__(world, event_sink)
        # Political institutions are deterministic bootstrap state, not a historical
        # event that occurred before WORLD_GENERATED. The current politics initializer
        # emits an institutional-formation event, so suppress persistence and remove
        # both that event and any memory derived from it before normal history begins.
        prior_sink = self.event_sink
        prior_event_count = len(self.world.recent_events)
        prior_event_sequence = self.world.next_event_sequence
        self.event_sink = None
        ensure_political_society(self)
        bootstrap_events = self.world.recent_events[prior_event_count:]
        bootstrap_event_ids = {event.id for event in bootstrap_events}
        if bootstrap_event_ids:
            for npc in self.world.npcs.values():
                npc.memories = [
                    memory for memory in npc.memories
                    if memory.event_id not in bootstrap_event_ids
                ]
        self.world.recent_events = self.world.recent_events[:prior_event_count]
        self.world.next_event_sequence = prior_event_sequence
        self.event_sink = prior_sink

    def advance_hours(self, hours: int, *, ignore_pause: bool = False):
        world = super().advance_hours(hours, ignore_pause=ignore_pause)
        # generation._refresh_metrics intentionally replaces the metrics dictionary.
        # Restore politics observability after every public simulation advance.
        refresh_political_metrics(self)
        return world

    def _monthly(self) -> None:
        super()._monthly()
        self._persistent_births()
        run_political_cycle(self)
        self._political_fragility()
        _refresh_metrics(self.world)

    def _yearly(self) -> None:
        super()._yearly()
        self._mature_npcs()
        self._form_marriages()

    def _succession_checks(self) -> None:
        succession_check(self)

    def _persistent_births(self) -> None:
        rng = self._rng("persistent-births")
        living_count = len(self.world.alive_npcs())
        target_living = 110
        pressure = max(0.001, min(0.012, 0.004 + (target_living - living_count) / 20_000))
        mothers = [
            npc for npc in self.world.npcs.values()
            if npc.alive and npc.sex == "female" and 19 <= npc.age <= 42 and npc.spouse_id
        ]
        for mother in mothers:
            father = self.world.npcs.get(mother.spouse_id or "")
            if not father or not father.alive or father.settlement_id != mother.settlement_id:
                continue
            if rng.random() >= pressure:
                continue
            ancestry = rng.choice([mother.ancestry, father.ancestry])
            first = rng.choice(FIRST_NAMES[ancestry])
            surname = father.name.split()[-1] if father.name else mother.name.split()[-1]
            nid = self.world.new_entity_id("npc")
            traits = {
                key: max(0.0, min(1.0, (mother.traits.get(key, 0.5) + father.traits.get(key, 0.5)) / 2 + rng.uniform(-0.12, 0.12)))
                for key in {**mother.traits, **father.traits}
            }
            values = {
                key: max(0.0, min(1.0, (mother.values.get(key, 0.5) + father.values.get(key, 0.5)) / 2 + rng.uniform(-0.08, 0.08)))
                for key in {**mother.values, **father.values}
            }
            child = NPC(
                id=nid,
                name=f"{first} {surname}",
                ancestry=ancestry,
                culture_id=mother.culture_id,
                religion_id=mother.religion_id,
                settlement_id=mother.settlement_id,
                kingdom_id=mother.kingdom_id,
                age=0,
                sex=rng.choice(["female", "male"]),
                health=max(0.55, min(1.0, (mother.health + father.health) / 2 + rng.uniform(-0.08, 0.08))),
                wealth=0.0,
                occupation="child",
                social_status="child",
                traits=traits,
                values=values,
                goals=[],
                parent_ids=[mother.id, father.id],
                relationships={
                    mother.id: Relationship(target_id=mother.id, affinity=0.8, trust=0.9, tags=["parent"]),
                    father.id: Relationship(target_id=father.id, affinity=0.8, trust=0.9, tags=["parent"]),
                },
            )
            mother.child_ids.append(child.id)
            father.child_ids.append(child.id)
            mother.relationships[child.id] = Relationship(target_id=child.id, affinity=0.9, trust=0.9, tags=["child"])
            father.relationships[child.id] = Relationship(target_id=child.id, affinity=0.9, trust=0.9, tags=["child"])
            self.world.npcs[child.id] = child
            self.emit(
                "NPC_BORN",
                f"{child.name} was born in {self.world.settlements[child.settlement_id].name} to {mother.name} and {father.name}.",
                [child.id, mother.id, father.id],
                child.settlement_id,
                importance=0.28,
            )

    def _mature_npcs(self) -> None:
        rng = self._rng("maturity")
        for npc in self.world.npcs.values():
            if not npc.alive:
                continue
            if npc.age == 16 and npc.occupation == "child":
                npc.occupation = rng.choice(OCCUPATIONS)
                npc.social_status = "commoner"
                npc.goals = rng.sample(GOALS, k=2)
                npc.goal_progress = {goal: 0.0 for goal in npc.goals}
                self.emit(
                    "NPC_CAME_OF_AGE",
                    f"{npc.name} came of age and began work as a {npc.occupation}.",
                    [npc.id], npc.settlement_id, importance=0.22,
                )

    def _form_marriages(self) -> None:
        rng = self._rng("marriage")
        by_settlement: dict[str, list[NPC]] = {}
        for npc in self.world.npcs.values():
            if npc.alive and 18 <= npc.age <= 48 and npc.spouse_id is None:
                by_settlement.setdefault(npc.settlement_id, []).append(npc)
        for residents in by_settlement.values():
            rng.shuffle(residents)
            women = [n for n in residents if n.sex == "female"]
            men = [n for n in residents if n.sex == "male"]
            rng.shuffle(women)
            rng.shuffle(men)
            for woman, man in zip(women, men):
                if woman.spouse_id or man.spouse_id or rng.random() > 0.28:
                    continue
                affinity = 0.62 + rng.uniform(0, 0.28)
                woman.spouse_id = man.id
                man.spouse_id = woman.id
                woman.relationships[man.id] = Relationship(target_id=man.id, affinity=affinity, trust=0.72, tags=["spouse"])
                man.relationships[woman.id] = Relationship(target_id=woman.id, affinity=affinity, trust=0.72, tags=["spouse"])
                self.emit(
                    "NPC_MARRIED",
                    f"{woman.name} and {man.name} married in {self.world.settlements[woman.settlement_id].name}.",
                    [woman.id, man.id], woman.settlement_id, importance=0.3,
                )

    def _political_fragility(self) -> None:
        for kingdom in list(self.world.kingdoms.values()):
            proposal = rebellion_candidate(self, kingdom)
            if not proposal:
                continue
            faction, settlement_id = proposal
            new = self._found_breakaway_kingdom(
                kingdom,
                settlement_id,
                self._rng(f"breakaway:{kingdom.id}:{faction.id}"),
            )
            self._reconcile_parent_factions_after_secession(kingdom, settlement_id)
            initialize_kingdom_politics(self, new)
            self.emit(
                "FACTION_REBELLION",
                f"The {faction.name} turned its grievances into open rebellion against {kingdom.name}.",
                [kingdom.id, new.id, faction.id, settlement_id],
                settlement_id,
                data={
                    "faction_id": faction.id,
                    "parent_kingdom_id": kingdom.id,
                    "new_kingdom_id": new.id,
                    "grievances": list(faction.grievances),
                },
                importance=0.94,
            )

    def _reconcile_parent_factions_after_secession(self, parent: Kingdom, lost_settlement_id: str) -> None:
        """Remove faction references that crossed into a newly independent kingdom."""
        for faction_id in parent.faction_ids:
            faction = self.world.political_factions.get(faction_id)
            if not faction or not faction.active:
                continue
            faction.member_npc_ids = [
                npc_id
                for npc_id in faction.member_npc_ids
                if npc_id in self.world.npcs
                and self.world.npcs[npc_id].alive
                and self.world.npcs[npc_id].kingdom_id == parent.id
            ]
            leader = self.world.npcs.get(faction.leader_npc_id or "")
            if not leader or not leader.alive or leader.kingdom_id != parent.id:
                faction.leader_npc_id = faction.member_npc_ids[0] if faction.member_npc_ids else None
            if faction.regional_base_settlement_id == lost_settlement_id:
                faction.regional_base_settlement_id = None

    def _found_breakaway_kingdom(self, parent: Kingdom, settlement_id: str, rng: random.Random) -> Kingdom:
        settlement = self.world.settlements[settlement_id]
        ancestry = max(settlement.ancestry_population, key=settlement.ancestry_population.get)
        parent_culture = self.world.cultures[parent.culture_id]
        culture_id = self.world.new_entity_id("culture")
        culture = Culture(
            id=culture_id,
            name=f"{settlement.name} Free Tradition",
            dominant_ancestry=ancestry,
            honor=max(0, min(1, parent_culture.honor + rng.uniform(-0.08, 0.08))),
            collectivism=max(0, min(1, parent_culture.collectivism + rng.uniform(-0.08, 0.08))),
            militarism=min(1, parent_culture.militarism + 0.12),
            devotion=parent_culture.devotion,
            trade_orientation=parent_culture.trade_orientation,
            expansionism=max(0.2, parent_culture.expansionism - 0.1),
            tolerance=parent_culture.tolerance,
            magic_acceptance=parent_culture.magic_acceptance,
            tradition=max(0, min(1, parent_culture.tradition + rng.uniform(-0.1, 0.1))),
        )
        self.world.cultures[culture.id] = culture

        new_id = self.world.new_entity_id("kingdom")
        treasury = min(parent.treasury * 0.16, settlement.wealth * 0.4)
        parent.treasury = max(0, parent.treasury - treasury)
        new = Kingdom(
            id=new_id,
            name=f"Free Realm of {settlement.name}",
            capital_settlement_id=settlement.id,
            government=rng.choice([GovernmentType.COUNCIL, GovernmentType.ELECTIVE_MONARCHY, GovernmentType.CLAN_CONFEDERACY]),
            dominant_ancestry=ancestry,
            culture_id=culture.id,
            religion_id=parent.religion_id,
            treasury=treasury,
            tax_rate=max(0.05, parent.tax_rate + rng.uniform(-0.03, 0.03)),
            stability=0.52,
            legitimacy=0.42,
            military_readiness=0.38,
            food_reserve=settlement.food_security,
            goals={"food": 0.8, "wealth": 0.5, "security": 1.0, "expansion": 0.3, "stability": 1.0},
            settlement_ids=[settlement.id],
        )
        if settlement.id in parent.settlement_ids:
            parent.settlement_ids.remove(settlement.id)
        settlement.kingdom_id = new.id

        residents = [npc for npc in self.world.npcs.values() if npc.settlement_id == settlement.id and npc.alive]
        for npc in residents:
            npc.kingdom_id = new.id
            npc.culture_id = culture.id
        if residents:
            ruler = max(residents, key=lambda n: n.traits.get("ambition", 0.5) + n.values.get("status", 0.5))
            ruler.title = "Sovereign"
            ruler.occupation = "ruler"
            ruler.social_status = "ruler"
            new.ruler_npc_id = ruler.id

        parent.relations[new.id] = DiplomaticRelation(target_kingdom_id=new.id, opinion=-0.85, trade_access=False, grievances=["Secession"])
        new.relations[parent.id] = DiplomaticRelation(target_kingdom_id=parent.id, opinion=-0.85, trade_access=False, grievances=["War of independence"])
        for other in self.world.kingdoms.values():
            if other.id == parent.id:
                continue
            new.relations[other.id] = DiplomaticRelation(target_kingdom_id=other.id, opinion=0.0)
            other.relations[new.id] = DiplomaticRelation(target_kingdom_id=new.id, opinion=0.0)

        army_id = self.world.new_entity_id("army")
        army = Army(
            id=army_id,
            kingdom_id=new.id,
            name=f"{settlement.name} Free Host",
            troop_count=max(30, settlement.population // 22),
            location_settlement_id=settlement.id,
            morale=0.78,
            supply_days=24,
            readiness=0.55,
            commander_npc_id=next((n.id for n in residents if n.id != new.ruler_npc_id), new.ruler_npc_id),
        )
        self.world.armies[army.id] = army
        new.army_ids.append(army.id)
        self.world.kingdoms[new.id] = new
        parent.stability = max(0.05, parent.stability - 0.08)
        parent.legitimacy = max(0.05, parent.legitimacy - 0.1)

        self.emit(
            "REBELLION",
            f"{settlement.name} rebelled against {parent.name} and proclaimed the {new.name}.",
            [parent.id, new.id, settlement.id],
            settlement.id,
            data={"new_kingdom_id": new.id, "parent_kingdom_id": parent.id},
            importance=0.94,
        )
        self.emit(
            "KINGDOM_FOUNDED",
            f"The {new.name} entered history with {settlement.name} as its capital.",
            [new.id, settlement.id], settlement.id, importance=0.92,
        )
        return new

    def _end_war(self, war: War, winner_id: str | None, reason: str) -> None:
        attacker_id = war.attacker_kingdom_id
        defender_id = war.defender_kingdom_id
        super()._end_war(war, winner_id, reason)
        if not winner_id:
            return
        loser_id = defender_id if winner_id == attacker_id else attacker_id
        winner = self.world.kingdoms.get(winner_id)
        loser = self.world.kingdoms.get(loser_id)
        if not winner or not loser or len(loser.settlement_ids) != 1:
            return

        capital_id = loser.settlement_ids[0]
        capital = self.world.settlements[capital_id]
        loser.settlement_ids.clear()
        if capital_id not in winner.settlement_ids:
            winner.settlement_ids.append(capital_id)
        capital.kingdom_id = winner.id
        for npc in self.world.npcs.values():
            if npc.kingdom_id == loser.id:
                npc.kingdom_id = winner.id
                if npc.id == loser.ruler_npc_id:
                    npc.title = "Former Sovereign"
                    npc.social_status = "elite"
        for aid in loser.army_ids:
            army = self.world.armies.get(aid)
            if army:
                army.active = False
        for faction_id in loser.faction_ids:
            faction = self.world.political_factions.get(faction_id)
            if faction:
                faction.active = False
        for kingdom in self.world.kingdoms.values():
            kingdom.relations.pop(loser.id, None)
        del self.world.kingdoms[loser.id]
        self.emit(
            "KINGDOM_DESTROYED",
            f"{loser.name} ceased to exist after its final capital, {capital.name}, fell to {winner.name}.",
            [loser.id, winner.id, capital.id, war.id], capital.id,
            data={"absorbed_by": winner.id}, importance=1.0,
        )
        _refresh_metrics(self.world)
