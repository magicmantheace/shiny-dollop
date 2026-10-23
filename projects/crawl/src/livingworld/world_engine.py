from __future__ import annotations

import math

from .advanced_simulation import LivingWorldEngine
from .domain import CampStatus, NPC, Relationship, War
from .frontier import refresh_frontier_metrics, run_frontier_cycle
from .generation import FIRST_NAMES, GOALS, OCCUPATIONS
from .migration import run_migration_cycle, update_refugee_camps
from .warfare import end_war, refresh_warfare_metrics, run_warfare_cycle


class FinalWorldEngine(LivingWorldEngine):
    """Complete deterministic living-world simulation engine."""

    def advance_hours(self, hours: int, *, ignore_pause: bool = False):
        world = super().advance_hours(hours, ignore_pause=ignore_pause)
        self._restore_migration_metrics()
        refresh_frontier_metrics(self.world)
        refresh_warfare_metrics(self.world)
        return world

    def _monthly(self) -> None:
        super()._monthly()
        self._migration_dynamics()
        self._refugee_camp_dynamics()
        self._frontier_dynamics()
        self._religious_dynamics()
        self._political_escalation()

    def _yearly(self) -> None:
        super()._yearly()
        self._replenish_persistent_cast()

    def _resolve_wars(self) -> None:
        active_before = list(self.world.active_wars())
        run_warfare_cycle(self)
        for war in active_before:
            if war.ended_at is not None:
                self._apply_postwar_recovery(war)

    # ------------------------------------------------------------------
    # Long-run population balance
    # ------------------------------------------------------------------

    @staticmethod
    def _sample_binomial_approx(rng, population: int, probability: float) -> int:
        """Fast deterministic approximation for large statistical populations.

        The original implementation performed one RNG draw per inhabitant for births
        and deaths every month. That becomes prohibitively expensive at MMO-scale
        populations. A normal approximation preserves expected value and variance
        while making demographic cost independent of settlement population.
        """
        population = max(0, int(population))
        probability = max(0.0, min(1.0, float(probability)))
        if population == 0 or probability == 0:
            return 0
        mean = population * probability
        variance = population * probability * (1.0 - probability)
        if variance <= 0:
            return min(population, int(round(mean)))
        sample = int(round(rng.gauss(mean, math.sqrt(variance))))
        return max(0, min(population, sample))

    @staticmethod
    def _allocate_demographic_change(counts, amount: int, total: int) -> dict:
        if amount <= 0 or total <= 0:
            return {}
        allocations = {}
        fractions = []
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
        return {ancestry: value for ancestry, value in allocations.items() if value > 0}

    def _demography(self) -> None:
        rng = self._rng("demography-balanced")
        for settlement in self.world.settlements.values():
            if settlement.population <= 0:
                continue

            density = settlement.population / max(1, settlement.housing_capacity)
            housing_factor = max(0.05, min(1.10, (1.10 - density) / 0.28))
            health = max(0.05, min(1.0, settlement.health))
            food = max(0.0, min(1.0, settlement.food_security))

            birth_rate = 0.00105 * health * (0.70 + food * 0.60) * housing_factor
            death_rate = 0.00065 * (1.40 - health) * (1.45 - food * 0.45)
            death_rate += max(0.0, density - 0.90) * 0.0015

            if settlement.besieged_by_kingdom_id:
                birth_rate *= 0.55
                death_rate += 0.00040
            if settlement.occupied_by_kingdom_id:
                birth_rate *= 0.75
                death_rate += 0.00022
            if self._war_for_kingdom(settlement.kingdom_id):
                birth_rate *= 0.92
                death_rate += 0.00008
            if food < 0.30:
                birth_rate *= max(0.20, food / 0.30)
                death_rate += (0.30 - food) * 0.0018

            before_population = settlement.population
            births = self._sample_binomial_approx(rng, before_population, birth_rate)
            deaths = self._sample_binomial_approx(rng, before_population, death_rate)
            deaths = min(deaths, before_population + births)

            if births:
                birth_allocations = self._allocate_demographic_change(
                    settlement.ancestry_population, births, before_population
                )
                allocated = sum(birth_allocations.values())
                if allocated < births:
                    dominant = max(settlement.ancestry_population, key=settlement.ancestry_population.get)
                    birth_allocations[dominant] = birth_allocations.get(dominant, 0) + births - allocated
                for ancestry, amount in birth_allocations.items():
                    settlement.ancestry_population[ancestry] = settlement.ancestry_population.get(ancestry, 0) + amount

            population_after_births = before_population + births
            if deaths:
                death_allocations = self._allocate_demographic_change(
                    settlement.ancestry_population, deaths, population_after_births
                )
                for ancestry, amount in death_allocations.items():
                    settlement.ancestry_population[ancestry] = max(
                        0, settlement.ancestry_population.get(ancestry, 0) - amount
                    )

            settlement.population = max(0, population_after_births - deaths)

    def _settlement_change(self) -> None:
        for settlement in self.world.settlements.values():
            if settlement.population <= 0:
                continue
            prosperity = (
                settlement.food_security * 0.35
                + settlement.health * 0.25
                + settlement.stability * 0.25
                + (1 - settlement.crime) * 0.15
            )
            density = settlement.population / max(1, settlement.housing_capacity)
            if density > 1.0:
                prosperity -= min(0.30, (density - 1.0) * 0.60 + 0.12)
            elif density > 0.92:
                prosperity -= (density - 0.92) * 0.35

            settlement.stability = max(
                0.05, min(1.0, settlement.stability + (prosperity - 0.55) * 0.006)
            )
            settlement.crime = max(
                0.01, min(0.8, settlement.crime + (0.55 - prosperity) * 0.004)
            )

            # Housing expands deliberately rather than automatically outrunning
            # population forever. Prosperous settlements can grow, but construction
            # consumes wealth and only occurs quarterly near capacity.
            if (
                prosperity > 0.72
                and density > 0.94
                and self.world.date.month in {1, 4, 7, 10}
            ):
                homes = max(1, settlement.population // 1_800)
                housing_gain = homes * 4
                construction_cost = housing_gain * 3.0
                if settlement.wealth >= construction_cost:
                    settlement.wealth -= construction_cost
                    settlement.housing_capacity += housing_gain
                    settlement.buildings["homes"] = settlement.buildings.get("homes", 0) + homes

            if settlement.food_security < 0.18:
                self.emit(
                    "FAMINE",
                    f"Severe food scarcity struck {settlement.name}.",
                    [settlement.id],
                    settlement.id,
                    importance=0.72,
                )

    # ------------------------------------------------------------------
    # Persistent named population
    # ------------------------------------------------------------------

    def _form_marriages(self) -> None:
        # A dead or missing spouse must not permanently remove the survivor from the
        # marriage pool. Preserve the historical relationship, but reopen spouse_id.
        for npc in self.world.npcs.values():
            if not npc.alive or not npc.spouse_id:
                continue
            spouse = self.world.npcs.get(npc.spouse_id)
            if not spouse or not spouse.alive:
                npc.spouse_id = None
        super()._form_marriages()

    def _persistent_target(self) -> int:
        # Preserve the smaller legacy-world cast while scaling the 100k continent
        # to roughly 500 named actors and capping very large worlds at 700.
        return max(110, min(700, self.world.total_population // 200))

    def _persistent_births(self) -> None:
        """Maintain multi-generational named families without unbounded cast growth."""
        rng = self._rng("persistent-births")
        living_count = len(self.world.alive_npcs())
        target_living = self._persistent_target()
        pressure = max(
            0.001,
            min(0.045, 0.003 + max(0, target_living - living_count) / 12_000),
        )
        mothers = [
            npc
            for npc in self.world.npcs.values()
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
                key: max(
                    0.0,
                    min(
                        1.0,
                        (mother.traits.get(key, 0.5) + father.traits.get(key, 0.5)) / 2
                        + rng.uniform(-0.12, 0.12),
                    ),
                )
                for key in {**mother.traits, **father.traits}
            }
            values = {
                key: max(
                    0.0,
                    min(
                        1.0,
                        (mother.values.get(key, 0.5) + father.values.get(key, 0.5)) / 2
                        + rng.uniform(-0.08, 0.08),
                    ),
                )
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
                health=max(
                    0.55,
                    min(
                        1.0,
                        (mother.health + father.health) / 2 + rng.uniform(-0.08, 0.08),
                    ),
                ),
                wealth=0.0,
                occupation="child",
                social_status="child",
                traits=traits,
                values=values,
                goals=[],
                parent_ids=[mother.id, father.id],
                relationships={
                    mother.id: Relationship(
                        target_id=mother.id, affinity=0.8, trust=0.9, tags=["parent"]
                    ),
                    father.id: Relationship(
                        target_id=father.id, affinity=0.8, trust=0.9, tags=["parent"]
                    ),
                },
            )
            mother.child_ids.append(child.id)
            father.child_ids.append(child.id)
            mother.relationships[child.id] = Relationship(
                target_id=child.id, affinity=0.9, trust=0.9, tags=["child"]
            )
            father.relationships[child.id] = Relationship(
                target_id=child.id, affinity=0.9, trust=0.9, tags=["child"]
            )
            self.world.npcs[child.id] = child
            self.emit(
                "NPC_BORN",
                f"{child.name} was born in {self.world.settlements[child.settlement_id].name} to {mother.name} and {father.name}.",
                [child.id, mother.id, father.id],
                child.settlement_id,
                importance=0.28,
            )

    def _replenish_persistent_cast(self) -> None:
        """Promote statistical inhabitants into the named cast if genealogy collapses.

        Persistent NPCs are representative named individuals inside the statistical
        population, not additional population. Promotion therefore does not alter
        settlement population totals; it only restores enough named actors for rulers,
        families, commanders, merchants, and local stories to keep existing.
        """
        target = self._persistent_target()
        living = self.world.alive_npcs()
        floor = max(75, int(target * 0.70))
        if len(living) >= floor:
            return

        active_settlements = [
            settlement
            for settlement in self.world.settlements.values()
            if settlement.population > 0 and settlement.kingdom_id in self.world.kingdoms
        ]
        if not active_settlements:
            return

        rng = self._rng("persistent-replenishment")
        additions = min(30, target - len(living))
        weights = [max(1, settlement.population) for settlement in active_settlements]
        for _ in range(max(0, additions)):
            settlement = rng.choices(active_settlements, weights=weights, k=1)[0]
            kingdom = self.world.kingdoms[settlement.kingdom_id]
            ancestries = [a for a, count in settlement.ancestry_population.items() if count > 0]
            ancestry_weights = [settlement.ancestry_population[a] for a in ancestries]
            if not ancestries:
                continue
            ancestry = rng.choices(ancestries, weights=ancestry_weights, k=1)[0]
            first = rng.choice(FIRST_NAMES[ancestry])
            prior_residents = [
                npc
                for npc in self.world.npcs.values()
                if npc.settlement_id == settlement.id and npc.name
            ]
            if prior_residents:
                surname = rng.choice(prior_residents).name.split()[-1]
            else:
                surname = settlement.name.replace(" ", "")[:18] or "Wayfarer"
            goals = rng.sample(GOALS, k=min(2, len(GOALS)))
            npc = NPC(
                id=self.world.new_entity_id("npc"),
                name=f"{first} {surname}",
                ancestry=ancestry,
                culture_id=kingdom.culture_id,
                religion_id=kingdom.religion_id,
                settlement_id=settlement.id,
                kingdom_id=kingdom.id,
                age=rng.randint(18, 35),
                sex=rng.choice(["female", "male"]),
                health=max(0.55, min(1.0, settlement.health + rng.uniform(-0.12, 0.12))),
                wealth=rng.uniform(8.0, 45.0),
                occupation=rng.choice(OCCUPATIONS),
                social_status="commoner",
                traits={
                    "ambition": rng.uniform(0.2, 0.9),
                    "courage": rng.uniform(0.2, 0.9),
                    "sociability": rng.uniform(0.2, 0.9),
                },
                values={
                    "family": rng.uniform(0.2, 0.9),
                    "status": rng.uniform(0.2, 0.9),
                    "wealth": rng.uniform(0.2, 0.9),
                },
                goals=goals,
                goal_progress={goal: 0.0 for goal in goals},
            )
            self.world.npcs[npc.id] = npc
            self.emit(
                "NPC_ENTERED_RECORD",
                f"{npc.name}, a {npc.occupation}, became a notable resident of {settlement.name}.",
                [npc.id, settlement.id, kingdom.id],
                settlement.id,
                importance=0.22,
            )

    # ------------------------------------------------------------------
    # Migration, frontier, religion, and political escalation
    # ------------------------------------------------------------------

    def _migration_dynamics(self) -> None:
        run_migration_cycle(self)

    def _refugee_camp_dynamics(self) -> None:
        update_refugee_camps(self)

    def _frontier_dynamics(self) -> None:
        run_frontier_cycle(self)

    def _restore_migration_metrics(self) -> None:
        relevant = [
            event
            for event in self.world.recent_events
            if event.type in {"MIGRATION", "REFUGEE_MOVEMENT"}
            and event.occurred_at.year == self.world.date.year
            and event.occurred_at.month == self.world.date.month
        ]
        refugee_events = [event for event in relevant if event.type == "REFUGEE_MOVEMENT"]
        self.world.metrics["migration_last_month"] = float(
            sum(int(event.data.get("people", 0)) for event in relevant)
        )
        self.world.metrics["refugees_last_month"] = float(
            sum(int(event.data.get("people", 0)) for event in refugee_events)
        )
        self.world.metrics["refugees_accepted_last_month"] = float(
            sum(
                int(event.data.get("accepted_people", event.data.get("people", 0)))
                for event in refugee_events
            )
        )
        self.world.metrics["refugees_rejected_last_month"] = float(
            sum(int(event.data.get("camped_people", 0)) for event in refugee_events)
        )
        self.world.metrics["migration_flows_last_month"] = float(len(relevant))
        active_camps = [
            camp for camp in self.world.refugee_camps.values() if camp.status != CampStatus.CLOSED
        ]
        self.world.metrics["active_refugee_camps"] = float(len(active_camps))
        self.world.metrics["refugee_camp_population"] = float(
            sum(camp.people for camp in active_camps)
        )
        self.world.metrics.setdefault("refugees_resettled_last_month", 0.0)

    def _seasonal(self) -> None:
        super()._seasonal()
        self._magic_dynamics()

    def _apply_postwar_recovery(self, war: War) -> None:
        """Give former belligerents time to recover before the same rivalry reignites."""
        recovery_until = self.world.date.year + 8
        pairs = (
            (war.attacker_kingdom_id, war.defender_kingdom_id),
            (war.defender_kingdom_id, war.attacker_kingdom_id),
        )
        for kingdom_id, other_id in pairs:
            kingdom = self.world.kingdoms.get(kingdom_id)
            if not kingdom:
                continue
            relation = kingdom.relations.get(other_id)
            if not relation:
                continue
            relation.truce_until_year = max(relation.truce_until_year or 0, recovery_until)
            relation.opinion = max(relation.opinion, -0.30)

    def _political_escalation(self) -> None:
        """Connect frontier/religious tension to organic war declarations."""
        pair_claims: dict[tuple[str, str], list[str]] = {}
        for claim_id, claim in self.world.territory_claims.items():
            if claim.get("status") == "abandoned":
                continue
            owner_id = claim.get("kingdom_id")
            if owner_id not in self.world.kingdoms:
                continue
            for rival_id in claim.get("contested_by_kingdom_ids", []):
                if rival_id not in self.world.kingdoms or rival_id == owner_id:
                    continue
                pair = tuple(sorted((owner_id, rival_id)))
                pair_claims.setdefault(pair, []).append(claim_id)

        candidate_pairs = set(pair_claims)
        for kingdom in self.world.kingdoms.values():
            for target_id, relation in kingdom.relations.items():
                if target_id not in self.world.kingdoms or target_id == kingdom.id:
                    continue
                religious = any("Religious dispute" in grievance for grievance in relation.grievances)
                if relation.opinion <= -0.65 or religious:
                    candidate_pairs.add(tuple(sorted((kingdom.id, target_id))))

        for left_id, right_id in sorted(candidate_pairs):
            left = self.world.kingdoms.get(left_id)
            right = self.world.kingdoms.get(right_id)
            if not left or not right:
                continue
            if left.overlord_kingdom_id == right.id or right.overlord_kingdom_id == left.id:
                continue
            if left.overlord_kingdom_id and left.overlord_kingdom_id == right.overlord_kingdom_id:
                continue
            if self._war_between(left.id, right.id):
                continue
            if self._war_for_kingdom(left.id) or self._war_for_kingdom(right.id):
                continue

            left_relation = left.relations.get(right.id)
            right_relation = right.relations.get(left.id)
            if not left_relation or not right_relation:
                continue
            truce_year = max(
                left_relation.truce_until_year or 0,
                right_relation.truce_until_year or 0,
            )
            if truce_year >= self.world.date.year:
                continue

            claims = pair_claims.get((left_id, right_id), [])
            for claim_id in claims:
                grievance = f"Contested frontier claim {claim_id}"
                if grievance not in left_relation.grievances:
                    left_relation.grievances.append(grievance)
                if grievance not in right_relation.grievances:
                    right_relation.grievances.append(grievance)
            if claims:
                pressure = min(0.004, 0.001 * len(claims))
                left_relation.opinion = max(-1.0, left_relation.opinion - pressure)
                right_relation.opinion = max(-1.0, right_relation.opinion - pressure)

            hostility = max(0.0, -(left_relation.opinion + right_relation.opinion) / 2)
            claim_pressure = min(1.0, len(claims) / 3.0)
            left_culture = self.world.cultures.get(left.culture_id)
            right_culture = self.world.cultures.get(right.culture_id)
            militarism = (
                (left_culture.militarism if left_culture else 0.5)
                + (right_culture.militarism if right_culture else 0.5)
            ) / 2
            expansion = (
                left.goals.get("expansion", 0.5) + right.goals.get("expansion", 0.5)
            ) / 2
            readiness = (left.military_readiness + right.military_readiness) / 2
            aggression = militarism * 0.35 + expansion * 0.35 + readiness * 0.30
            religious = any(
                "Religious dispute" in grievance
                for grievance in [*left_relation.grievances, *right_relation.grievances]
            )
            tension = (
                hostility * 0.45
                + claim_pressure * 0.32
                + aggression * 0.23
                + (0.05 if religious else 0.0)
            )

            # Tension continues changing every month, but kingdoms only make the
            # irreversible decision to declare war twice per year. This preserves
            # diplomatic crises while preventing a hostile pair from getting twelve
            # independent declaration opportunities every year.
            if self.world.date.month not in {1, 7}:
                if tension >= 0.68 and self.world.date.month in {4, 10}:
                    self.emit(
                        "DIPLOMATIC_CRISIS",
                        f"Tensions remained high between {left.name} and {right.name}.",
                        [left.id, right.id, *claims[:3]],
                        data={"tension": tension, "contested_claims": claims},
                        importance=0.48,
                    )
                continue

            rng = self._rng(f"political-escalation:{left_id}:{right_id}")
            stochastic_threshold = max(0.0, (tension - 0.58) * 0.05)
            should_escalate = tension >= 0.82 or (
                tension >= 0.62 and rng.random() < stochastic_threshold
            )
            if not should_escalate:
                if tension >= 0.62:
                    self.emit(
                        "DIPLOMATIC_CRISIS",
                        f"Tensions rose between {left.name} and {right.name}.",
                        [left.id, right.id, *claims[:3]],
                        data={"tension": tension, "contested_claims": claims},
                        importance=0.52,
                    )
                continue

            def aggression_score(kingdom, culture) -> float:
                return (
                    kingdom.goals.get("expansion", 0.5) * 0.40
                    + kingdom.military_readiness * 0.35
                    + (culture.militarism if culture else 0.5) * 0.25
                )

            left_score = aggression_score(left, left_culture)
            right_score = aggression_score(right, right_culture)
            attacker, defender = (
                (left, right) if (left_score, left.id) >= (right_score, right.id) else (right, left)
            )
            goal = "contested frontier claim" if claims else "political and religious rivalry"
            self.declare_war(attacker.id, defender.id, goal, source="political_escalation")

    def _end_war(self, war: War, winner_id: str | None, reason: str) -> None:
        end_war(self, war, winner_id, reason)
        self._apply_postwar_recovery(war)

    def _religious_dynamics(self) -> None:
        rng = self._rng("religion")
        for kingdom in self.world.kingdoms.values():
            culture = self.world.cultures.get(kingdom.culture_id)
            if not culture:
                continue
            for sid in kingdom.settlement_ids:
                settlement = self.world.settlements.get(sid)
                if not settlement:
                    continue
                temples = settlement.buildings.get("temple", 0)
                if temples:
                    settlement.stability = min(
                        1.0, settlement.stability + culture.devotion * 0.0008 * temples
                    )

            for target_id, relation in kingdom.relations.items():
                other = self.world.kingdoms.get(target_id)
                if not other:
                    continue
                same_faith = bool(
                    kingdom.religion_id and kingdom.religion_id == other.religion_id
                )
                if same_faith:
                    relation.opinion = min(
                        1.0, relation.opinion + culture.devotion * 0.0015
                    )
                else:
                    tension = culture.devotion * (1.0 - culture.tolerance) * 0.0012
                    relation.opinion = max(-1.0, relation.opinion - tension)
                    if (
                        relation.opinion < -0.55
                        and tension > 0.00035
                        and rng.random() < 0.015
                    ):
                        grievance = f"Religious dispute in year {self.world.date.year}"
                        if grievance not in relation.grievances:
                            relation.grievances.append(grievance)
                        self.emit(
                            "RELIGIOUS_TENSION",
                            f"Religious tensions worsened relations between {kingdom.name} and {other.name}.",
                            [kingdom.id, other.id],
                            data={
                                "religion_id": kingdom.religion_id,
                                "other_religion_id": other.religion_id,
                            },
                            importance=0.42,
                        )

    def _magic_dynamics(self) -> None:
        rng = self._rng("magic")
        for settlement in self.world.settlements.values():
            mana = settlement.resources.get("mana_crystal")
            if not mana or settlement.magic_intensity < 0.55:
                continue
            chance = (settlement.magic_intensity - 0.5) * 0.08
            if rng.random() < chance:
                amount = mana.capacity * rng.uniform(0.04, 0.12)
                mana.quantity += amount
                mana.clamp()
                settlement.health = max(
                    0.1,
                    min(1.0, settlement.health + rng.uniform(-0.015, 0.02)),
                )
                self.emit(
                    "ARCANE_SURGE",
                    f"An arcane surge altered the mana crystal fields near {settlement.name}.",
                    [settlement.id],
                    settlement.id,
                    data={
                        "mana_change": amount,
                        "magic_intensity": settlement.magic_intensity,
                    },
                    importance=0.48,
                )