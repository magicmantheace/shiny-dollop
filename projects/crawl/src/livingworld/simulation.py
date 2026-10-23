from __future__ import annotations

import math
import random
from collections.abc import Callable

from .domain import (
    Ancestry,
    HistoricalEvent,
    Kingdom,
    NPC,
    StrategicDecision,
    War,
    WarState,
    WorldState,
)
from .generation import _refresh_metrics


EventSink = Callable[[HistoricalEvent], None]


class WorldEngine:
    """Authoritative deterministic simulation over a WorldState.

    The engine never delegates state mutation to an LLM. Randomness is seeded from
    the world seed and current world hour so a persisted world resumes predictably.
    """

    def __init__(self, world: WorldState, event_sink: EventSink | None = None) -> None:
        self.world = world
        self.event_sink = event_sink

    def _rng(self, salt: str = "") -> random.Random:
        return random.Random(f"{self.world.seed}:{self.world.date.ordinal_hour()}:{salt}")

    def emit(
        self,
        event_type: str,
        summary: str,
        subject_ids: list[str] | None = None,
        location_id: str | None = None,
        data: dict | None = None,
        source: str = "simulation",
        importance: float = 0.5,
    ) -> HistoricalEvent:
        event = HistoricalEvent(
            id=self.world.new_event_id(),
            type=event_type,
            occurred_at=self.world.date.model_copy(deep=True),
            summary=summary,
            subject_ids=subject_ids or [],
            location_id=location_id,
            data=data or {},
            source=source,
            importance=importance,
        )
        self.world.recent_events.append(event)
        if len(self.world.recent_events) > 500:
            self.world.recent_events = self.world.recent_events[-500:]
        if self.event_sink:
            self.event_sink(event)
        self._apply_memories(event)
        return event

    def advance_hours(self, hours: int, *, ignore_pause: bool = False) -> WorldState:
        if hours < 0:
            raise ValueError("hours must be non-negative")
        if self.world.paused and not ignore_pause:
            return self.world

        for _ in range(hours):
            previous = self.world.date
            self.world.date = previous.plus_hours(1)
            self._hourly()
            if self.world.date.hour == 0:
                self._daily()
                if self.world.date.day == 1:
                    self._monthly()
                    if self.world.date.month in {1, 4, 7, 10}:
                        self._seasonal()
                    if self.world.date.month == 1:
                        self._yearly()
        _refresh_metrics(self.world)
        return self.world

    def advance_days(self, days: int, *, ignore_pause: bool = False) -> WorldState:
        return self.advance_hours(days * 24, ignore_pause=ignore_pause)

    def advance_months(self, months: int, *, ignore_pause: bool = False) -> WorldState:
        return self.advance_days(months * 30, ignore_pause=ignore_pause)

    def advance_years(self, years: int, *, ignore_pause: bool = False) -> WorldState:
        return self.advance_days(years * 360, ignore_pause=ignore_pause)

    # ------------------------------------------------------------------
    # Cadence systems
    # ------------------------------------------------------------------

    def _hourly(self) -> None:
        self._move_armies()

    def _daily(self) -> None:
        self._produce_and_consume()
        self._run_trade()
        self._npc_daily_lives()
        self._update_army_supplies()

    def _monthly(self) -> None:
        self._collect_taxes()
        self._demography()
        self._persistent_mortality()
        self._settlement_change()
        self._diplomacy()
        self._resolve_wars()
        self._succession_checks()
        self._update_kingdom_pressure()

    def _seasonal(self) -> None:
        self._seasonal_harvest()
        for kingdom in list(self.world.kingdoms.values()):
            if kingdom.settlement_ids:
                self._kingdom_decision(kingdom)

    def _yearly(self) -> None:
        self._age_npcs()
        self._cultural_drift()
        self._decay_memories()
        self.emit(
            "YEAR_BEGAN",
            f"Year {self.world.date.year} began with {self.world.total_population:,} inhabitants across {len(self.world.kingdoms)} kingdoms.",
            data=dict(self.world.metrics),
            importance=0.25,
        )

    # ------------------------------------------------------------------
    # Economy and trade
    # ------------------------------------------------------------------

    def _produce_and_consume(self) -> None:
        for settlement in self.world.settlements.values():
            if settlement.population <= 0:
                continue
            for stock in settlement.resources.values():
                productivity = 0.55 + 0.45 * settlement.health
                infrastructure = 0.75 + 0.25 * settlement.infrastructure.get("roads", 0.5)
                production = stock.production_per_day * productivity * infrastructure
                consumption = stock.consumption_per_day * max(0.1, settlement.population / max(1, settlement.housing_capacity * 0.8))
                stock.quantity += production - consumption
                stock.clamp()
                fill = stock.quantity / max(1.0, stock.capacity)
                scarcity = max(0.3, min(4.0, 1.4 - fill * 1.2))
                stock.price = max(0.05, stock.base_price * scarcity)

            grain = settlement.resources.get("grain")
            livestock = settlement.resources.get("livestock")
            if grain:
                days_grain = grain.quantity / max(0.01, grain.consumption_per_day)
                meat_support = 0.0 if not livestock else min(0.2, livestock.quantity / max(1.0, livestock.capacity) * 0.2)
                settlement.food_security = max(0.0, min(1.0, days_grain / 90.0 + meat_support))
            settlement.health = max(0.15, min(1.0, settlement.health + (settlement.food_security - 0.55) * 0.001 - settlement.crime * 0.0002))

    def _run_trade(self) -> None:
        for route in self.world.trade_routes.values():
            route.volume_last_day = 0.0
            if not route.active:
                continue
            a = self.world.settlements.get(route.origin_settlement_id)
            b = self.world.settlements.get(route.destination_settlement_id)
            if not a or not b or a.population <= 0 or b.population <= 0:
                continue
            remaining = route.capacity * route.safety
            for commodity in route.commodities:
                if remaining <= 0:
                    break
                sa, sb = a.resources.get(commodity), b.resources.get(commodity)
                if not sa or not sb:
                    continue
                fill_a = sa.quantity / max(1.0, sa.capacity)
                fill_b = sb.quantity / max(1.0, sb.capacity)
                if abs(fill_a - fill_b) < 0.12:
                    continue
                source_settlement, source, target_settlement, target = (a, sa, b, sb) if fill_a > fill_b else (b, sb, a, sa)
                transferable = min(remaining, source.quantity * 0.08, target.capacity - target.quantity)
                if transferable <= 0:
                    continue
                value = transferable * ((source.price + target.price) / 2)
                affordable = min(transferable, target_settlement.wealth / max(0.01, (source.price + target.price) / 2))
                if affordable <= 0:
                    continue
                source.quantity -= affordable
                target.quantity += affordable
                target_settlement.wealth -= affordable * target.price
                source_settlement.wealth += affordable * source.price
                route.volume_last_day += affordable
                remaining -= affordable

    def _collect_taxes(self) -> None:
        for kingdom in self.world.kingdoms.values():
            revenue = 0.0
            for sid in kingdom.settlement_ids:
                settlement = self.world.settlements.get(sid)
                if not settlement:
                    continue
                taxable = max(0.0, settlement.wealth * kingdom.tax_rate * 0.025)
                settlement.wealth -= taxable
                revenue += taxable
            kingdom.treasury += revenue

    def _seasonal_harvest(self) -> None:
        rng = self._rng("harvest")
        season = self.world.date.month
        for settlement in self.world.settlements.values():
            grain = settlement.resources.get("grain")
            if not grain:
                continue
            modifier = 1.0
            if season == 7:  # summer harvest pulse
                modifier = rng.uniform(1.4, 2.2)
            elif season == 1:  # winter
                modifier = rng.uniform(0.45, 0.7)
            grain.quantity += grain.production_per_day * 25 * modifier
            grain.clamp()

    # ------------------------------------------------------------------
    # Population and NPC lives
    # ------------------------------------------------------------------

    def _demography(self) -> None:
        rng = self._rng("demography")
        for settlement in self.world.settlements.values():
            if settlement.population <= 0:
                continue
            # Monthly statistical demography. Rates are intentionally modest.
            birth_rate = 0.0011 * settlement.health * (0.65 + settlement.food_security * 0.7)
            death_rate = 0.0007 * (1.35 - settlement.health) * (1.5 - settlement.food_security * 0.5)
            births = sum(1 for _ in range(settlement.population) if rng.random() < birth_rate)
            deaths = sum(1 for _ in range(settlement.population) if rng.random() < death_rate)
            net = births - deaths
            if net:
                dominant = max(settlement.ancestry_population, key=settlement.ancestry_population.get)
                if net > 0:
                    settlement.ancestry_population[dominant] = settlement.ancestry_population.get(dominant, 0) + net
                else:
                    remaining = -net
                    for ancestry in sorted(settlement.ancestry_population, key=settlement.ancestry_population.get, reverse=True):
                        remove = min(remaining, settlement.ancestry_population[ancestry])
                        settlement.ancestry_population[ancestry] -= remove
                        remaining -= remove
                        if remaining <= 0:
                            break
                settlement.population = max(0, settlement.population + net)

    def _persistent_mortality(self) -> None:
        rng = self._rng("npc-mortality")
        for npc in list(self.world.npcs.values()):
            if not npc.alive:
                continue
            age_risk = 0.00005 if npc.age < 50 else 0.00025 if npc.age < 70 else 0.0012 if npc.age < 90 else 0.004
            health_risk = max(0.0, 0.0008 * (0.55 - npc.health))
            settlement = self.world.settlements.get(npc.settlement_id)
            scarcity_risk = 0.0 if not settlement else max(0.0, 0.001 * (0.35 - settlement.food_security))
            if rng.random() < age_risk + health_risk + scarcity_risk:
                self.kill_npc(npc.id, cause="natural causes", source="simulation")

    def _npc_daily_lives(self) -> None:
        rng = self._rng("npc-life")
        for npc in self.world.npcs.values():
            if not npc.alive:
                continue
            settlement = self.world.settlements.get(npc.settlement_id)
            if not settlement:
                continue
            income = {
                "farmer": 0.10, "smith": 0.18, "merchant": 0.24, "guard": 0.13, "miner": 0.15,
                "ruler": 1.2, "soldier": 0.14, "priest": 0.1, "healer": 0.16,
            }.get(npc.occupation, 0.11)
            npc.wealth += income * (0.65 + settlement.wealth / max(1.0, settlement.population * 10))
            npc.wealth = max(0.0, npc.wealth - 0.07)
            npc.health = max(0.05, min(1.0, npc.health + (settlement.health - 0.6) * 0.0005))
            for goal in list(npc.goals):
                drive = 0.0008 + npc.traits.get("ambition", 0.5) * 0.0012
                npc.goal_progress[goal] = min(1.0, npc.goal_progress.get(goal, 0.0) + drive)
                if npc.goal_progress[goal] >= 1.0:
                    self._complete_npc_goal(npc, goal)
                    npc.goal_progress[goal] = 0.0
            if rng.random() < 0.0008 and npc.relationships:
                relation = rng.choice(list(npc.relationships.values()))
                relation.affinity = max(-1.0, min(1.0, relation.affinity + rng.uniform(-0.03, 0.04)))
                relation.trust = max(-1.0, min(1.0, relation.trust + rng.uniform(-0.02, 0.03)))

    def _complete_npc_goal(self, npc: NPC, goal: str) -> None:
        if goal == "become_wealthy":
            npc.wealth += 25
        elif goal == "gain_status":
            order = ["commoner", "respected", "notable", "elite"]
            if npc.social_status in order:
                npc.social_status = order[min(order.index(npc.social_status) + 1, len(order) - 1)]
        elif goal == "master_craft":
            npc.reputation[npc.settlement_id] = min(1.0, npc.reputation.get(npc.settlement_id, 0.0) + 0.15)
        elif goal == "own_land":
            npc.wealth = max(0, npc.wealth - 10)
        elif goal == "learn_magic":
            npc.values["magic"] = min(1.0, npc.values.get("magic", 0.0) + 0.2)
        self.emit(
            "NPC_GOAL_COMPLETED",
            f"{npc.name} made meaningful progress toward {goal.replace('_', ' ')}.",
            [npc.id], npc.settlement_id, {"goal": goal}, importance=0.18,
        )

    def _age_npcs(self) -> None:
        for npc in self.world.npcs.values():
            if npc.alive:
                npc.age += 1

    def _decay_memories(self) -> None:
        for npc in self.world.npcs.values():
            retained = []
            for memory in npc.memories:
                memory.confidence = max(0.0, memory.confidence - memory.decay_per_year)
                if memory.importance >= 0.8 or memory.confidence >= 0.15:
                    retained.append(memory)
            npc.memories = retained[-100:]

    def _apply_memories(self, event: HistoricalEvent) -> None:
        # Avoid recursive import overhead at module level.
        from .domain import Memory

        if event.importance < 0.45:
            return
        witnesses: list[NPC] = []
        subject_set = set(event.subject_ids)
        for npc in self.world.npcs.values():
            if not npc.alive:
                continue
            if npc.id in subject_set or (event.location_id and npc.settlement_id == event.location_id):
                witnesses.append(npc)
        for npc in witnesses[:40]:
            npc.memories.append(Memory(
                event_id=event.id, summary=event.summary, subject_id=event.subject_ids[0] if event.subject_ids else None,
                emotion="fear" if event.type in {"WAR_DECLARED", "BATTLE", "NPC_DIED", "FAMINE"} else "significant",
                importance=event.importance, confidence=1.0, decay_per_year=max(0.0, 0.12 - event.importance * 0.1),
                created_at=event.occurred_at.model_copy(deep=True),
            ))
            npc.memories = npc.memories[-100:]

    # ------------------------------------------------------------------
    # Settlement dynamics
    # ------------------------------------------------------------------

    def _settlement_change(self) -> None:
        for settlement in self.world.settlements.values():
            if settlement.population <= 0:
                continue
            prosperity = settlement.food_security * 0.35 + settlement.health * 0.25 + settlement.stability * 0.25 + (1 - settlement.crime) * 0.15
            if settlement.population > settlement.housing_capacity:
                prosperity -= 0.15
            settlement.stability = max(0.05, min(1.0, settlement.stability + (prosperity - 0.55) * 0.006))
            settlement.crime = max(0.01, min(0.8, settlement.crime + (0.55 - prosperity) * 0.004))
            if prosperity > 0.72 and settlement.population > settlement.housing_capacity * 0.9:
                settlement.housing_capacity += max(2, settlement.population // 150)
                settlement.buildings["homes"] = settlement.buildings.get("homes", 0) + max(1, settlement.population // 500)
            if settlement.food_security < 0.18:
                self.emit("FAMINE", f"Severe food scarcity struck {settlement.name}.", [settlement.id], settlement.id, importance=0.72)

    # ------------------------------------------------------------------
    # Kingdom AI and diplomacy
    # ------------------------------------------------------------------

    def _update_kingdom_pressure(self) -> None:
        for kingdom in self.world.kingdoms.values():
            settlements = [self.world.settlements[s] for s in kingdom.settlement_ids if s in self.world.settlements]
            if not settlements:
                kingdom.stability = 0
                continue
            kingdom.food_reserve = sum(s.food_security * s.population for s in settlements) / max(1, sum(s.population for s in settlements))
            kingdom.stability = max(0.0, min(1.0, sum(s.stability for s in settlements) / len(settlements) * 0.75 + kingdom.legitimacy * 0.25))
            army_strength = sum(self.world.armies[a].readiness for a in kingdom.army_ids if a in self.world.armies)
            kingdom.military_readiness = max(0.0, min(1.0, army_strength / max(1, len(kingdom.army_ids))))

    def _kingdom_decision(self, kingdom: Kingdom) -> StrategicDecision:
        rng = self._rng(f"decision:{kingdom.id}")
        population = sum(self.world.settlements[s].population for s in kingdom.settlement_ids if s in self.world.settlements)
        avg_food = kingdom.food_reserve
        active_war = self._war_for_kingdom(kingdom.id)
        treasury_per_capita = kingdom.treasury / max(1, population)
        reasons_by_action: dict[str, dict[str, float]] = {
            "improve_food": {
                "food_pressure": (0.62 - avg_food) * 90,
                "goal_weight": kingdom.goals.get("food", 0.5) * 25,
                "treasury": min(15, treasury_per_capita * 2),
            },
            "build_infrastructure": {
                "wealth_goal": kingdom.goals.get("wealth", 0.5) * 24,
                "treasury": min(30, treasury_per_capita * 3),
                "stability": kingdom.stability * 12,
            },
            "strengthen_military": {
                "security_goal": kingdom.goals.get("security", 0.5) * 30,
                "readiness_gap": (1 - kingdom.military_readiness) * 30,
                "war": 25 if active_war else 0,
            },
            "seek_trade": {
                "food_pressure": (0.65 - avg_food) * 45,
                "wealth_goal": kingdom.goals.get("wealth", 0.5) * 22,
                "peace": 15 if not active_war else -5,
            },
            "pressure_neighbor": {
                "expansion_goal": kingdom.goals.get("expansion", 0.5) * 38,
                "military": kingdom.military_readiness * 26,
                "stability": kingdom.stability * 18,
                "war_penalty": -80 if active_war else 0,
            },
        }
        scored = []
        for action, reasons in reasons_by_action.items():
            score = sum(reasons.values()) + rng.uniform(-5, 5)
            scored.append((score, action, reasons))
        score, action, reasons = max(scored, key=lambda item: item[0])
        target_id = None
        other = next((k for k in self.world.kingdoms.values() if k.id != kingdom.id), None)
        if action in {"seek_trade", "pressure_neighbor"} and other:
            target_id = other.id
        decision = StrategicDecision(action=action, score=score, reasons=reasons, target_id=target_id, created_at=self.world.date.model_copy(deep=True))
        kingdom.last_decision = decision
        self._execute_kingdom_decision(kingdom, decision)
        return decision

    def _execute_kingdom_decision(self, kingdom: Kingdom, decision: StrategicDecision) -> None:
        if decision.action == "improve_food":
            cost = min(kingdom.treasury, 500.0)
            if cost <= 0:
                return
            kingdom.treasury -= cost
            for sid in kingdom.settlement_ids:
                settlement = self.world.settlements.get(sid)
                if settlement and "grain" in settlement.resources:
                    settlement.resources["grain"].production_per_day *= 1.015
            self.emit("KINGDOM_POLICY", f"{kingdom.name} invested in food security.", [kingdom.id], data={"decision": decision.model_dump(mode="json")}, importance=0.32)
        elif decision.action == "build_infrastructure":
            candidates = [self.world.settlements[s] for s in kingdom.settlement_ids if s in self.world.settlements]
            if candidates and kingdom.treasury >= 350:
                target = min(candidates, key=lambda s: s.infrastructure.get("roads", 0.0))
                kingdom.treasury -= 350
                target.infrastructure["roads"] = min(1.0, target.infrastructure.get("roads", 0) + 0.08)
                self.emit("INFRASTRUCTURE_BUILT", f"{kingdom.name} improved the roads around {target.name}.", [kingdom.id, target.id], target.id, importance=0.3)
        elif decision.action == "strengthen_military":
            if kingdom.treasury >= 400:
                kingdom.treasury -= 400
                for aid in kingdom.army_ids:
                    army = self.world.armies.get(aid)
                    if army:
                        army.readiness = min(1.0, army.readiness + 0.08)
                        army.supply_days += 8
        elif decision.action == "seek_trade" and decision.target_id:
            relation = kingdom.relations.get(decision.target_id)
            if relation:
                relation.opinion = min(1.0, relation.opinion + 0.08)
                relation.trade_access = True
                self.emit("TRADE_NEGOTIATION", f"{kingdom.name} sought stronger trade with {self.world.kingdoms[decision.target_id].name}.", [kingdom.id, decision.target_id], importance=0.3)
        elif decision.action == "pressure_neighbor" and decision.target_id:
            relation = kingdom.relations.get(decision.target_id)
            if relation:
                relation.opinion = max(-1.0, relation.opinion - 0.08)
                relation.grievances.append(f"Border pressure in year {self.world.date.year}")
                if decision.score >= 67 and relation.opinion <= -0.35 and not self._war_between(kingdom.id, decision.target_id):
                    self.declare_war(kingdom.id, decision.target_id, "territorial expansion", source="kingdom_ai")

    def _diplomacy(self) -> None:
        for kingdom in self.world.kingdoms.values():
            for relation in kingdom.relations.values():
                if self._war_between(kingdom.id, relation.target_kingdom_id):
                    relation.opinion = max(-1.0, relation.opinion - 0.02)
                else:
                    # Mild regression toward neutral with persistent grievance drag.
                    relation.opinion *= 0.995
                    relation.opinion -= min(0.005, len(relation.grievances) * 0.0003)

    # ------------------------------------------------------------------
    # Warfare
    # ------------------------------------------------------------------

    def declare_war(self, attacker_id: str, defender_id: str, goal: str, source: str = "admin") -> War:
        if attacker_id == defender_id:
            raise ValueError("a kingdom cannot declare war on itself")
        if attacker_id not in self.world.kingdoms or defender_id not in self.world.kingdoms:
            raise KeyError("unknown kingdom")
        existing = self._war_between(attacker_id, defender_id)
        if existing:
            return existing
        war_id = self.world.new_entity_id("war")
        war = War(
            id=war_id,
            attacker_kingdom_id=attacker_id,
            defender_kingdom_id=defender_id,
            goal=goal,
            started_at=self.world.date.model_copy(deep=True),
            casualties={attacker_id: 0, defender_id: 0},
        )
        self.world.wars[war.id] = war
        attacker = self.world.kingdoms[attacker_id]
        defender = self.world.kingdoms[defender_id]
        for aid in attacker.army_ids:
            army = self.world.armies.get(aid)
            if army:
                army.destination_settlement_id = defender.capital_settlement_id
        for aid in defender.army_ids:
            army = self.world.armies.get(aid)
            if army:
                army.destination_settlement_id = defender.capital_settlement_id
        self.emit("WAR_DECLARED", f"{attacker.name} declared war on {defender.name} over {goal}.", [attacker_id, defender_id, war.id], data={"goal": goal}, source=source, importance=0.95)
        return war

    def _war_between(self, a: str, b: str) -> War | None:
        for war in self.world.active_wars():
            if {war.attacker_kingdom_id, war.defender_kingdom_id} == {a, b}:
                return war
        return None

    def _war_for_kingdom(self, kingdom_id: str) -> War | None:
        return next((w for w in self.world.active_wars() if kingdom_id in {w.attacker_kingdom_id, w.defender_kingdom_id}), None)

    def _move_armies(self) -> None:
        for army in self.world.armies.values():
            if not army.active or not army.destination_settlement_id or army.supply_days <= 0:
                continue
            origin = self.world.settlements.get(army.location_settlement_id)
            destination = self.world.settlements.get(army.destination_settlement_id)
            if not origin or not destination:
                army.destination_settlement_id = None
                continue
            distance = math.hypot(destination.position.x - origin.position.x, destination.position.y - origin.position.y)
            # Strategic movement is abstract: one hour has a small chance to complete a journey based on route distance.
            probability = min(1.0, 1.0 / max(4.0, distance * 1.8))
            if self._rng(f"move:{army.id}").random() < probability:
                army.location_settlement_id = destination.id
                army.destination_settlement_id = None
                self.emit("ARMY_ARRIVED", f"{army.name} arrived at {destination.name}.", [army.id, army.kingdom_id, destination.id], destination.id, importance=0.38)

    def _update_army_supplies(self) -> None:
        for army in self.world.armies.values():
            if not army.active:
                continue
            consumption = max(0.1, army.troop_count / 500.0)
            army.supply_days = max(0.0, army.supply_days - consumption / 24.0)
            if army.supply_days <= 0:
                army.morale = max(0.1, army.morale - 0.005)
                army.readiness = max(0.1, army.readiness - 0.003)

    def _resolve_wars(self) -> None:
        rng = self._rng("war-resolution")
        for war in list(self.world.active_wars()):
            attacker = self.world.kingdoms.get(war.attacker_kingdom_id)
            defender = self.world.kingdoms.get(war.defender_kingdom_id)
            if not attacker or not defender:
                war.state = WarState.ENDED
                continue
            a_armies = [self.world.armies[a] for a in attacker.army_ids if a in self.world.armies and self.world.armies[a].active]
            d_armies = [self.world.armies[a] for a in defender.army_ids if a in self.world.armies and self.world.armies[a].active]
            if not a_armies or not d_armies:
                self._end_war(war, defender.id if not a_armies else attacker.id, "military collapse")
                continue

            a_power = sum(a.troop_count * a.readiness * a.morale for a in a_armies) * rng.uniform(0.85, 1.15)
            d_power = sum(a.troop_count * a.readiness * a.morale for a in d_armies) * rng.uniform(0.9, 1.2)
            total = max(1.0, a_power + d_power)
            intensity = rng.uniform(0.015, 0.055)
            a_loss = int(sum(a.troop_count for a in a_armies) * intensity * d_power / total)
            d_loss = int(sum(a.troop_count for a in d_armies) * intensity * a_power / total)
            self._apply_army_losses(a_armies, a_loss)
            self._apply_army_losses(d_armies, d_loss)
            war.casualties[attacker.id] = war.casualties.get(attacker.id, 0) + a_loss
            war.casualties[defender.id] = war.casualties.get(defender.id, 0) + d_loss
            delta = (d_loss - a_loss) / max(1, a_loss + d_loss) * 12
            war.attacker_score += delta
            war.defender_score -= delta
            self.emit(
                "BATTLE",
                f"Forces of {attacker.name} and {defender.name} clashed; {a_loss + d_loss:,} soldiers were lost.",
                [war.id, attacker.id, defender.id],
                data={"attacker_losses": a_loss, "defender_losses": d_loss, "attacker_score": war.attacker_score},
                importance=0.72,
            )

            duration_years = (self.world.date.ordinal_hour() - war.started_at.ordinal_hour()) / (360 * 24)
            if war.attacker_score >= 40:
                self._end_war(war, attacker.id, "decisive battlefield advantage")
            elif war.attacker_score <= -40:
                self._end_war(war, defender.id, "decisive battlefield advantage")
            elif duration_years >= 4 and abs(war.attacker_score) < 20:
                self._end_war(war, None, "war exhaustion")

    def _apply_army_losses(self, armies: list, total_loss: int) -> None:
        remaining = total_loss
        for army in sorted(armies, key=lambda a: a.troop_count, reverse=True):
            if remaining <= 0:
                break
            loss = min(army.troop_count, max(1, int(total_loss * army.troop_count / max(1, sum(a.troop_count for a in armies)))))
            army.troop_count -= loss
            remaining -= loss
            army.morale = max(0.1, army.morale - loss / max(1, army.troop_count + loss) * 0.2)
            if army.troop_count <= 0:
                army.active = False

    def _end_war(self, war: War, winner_id: str | None, reason: str) -> None:
        war.state = WarState.ENDED
        war.ended_at = self.world.date.model_copy(deep=True)
        attacker = self.world.kingdoms[war.attacker_kingdom_id]
        defender = self.world.kingdoms[war.defender_kingdom_id]
        if winner_id:
            loser_id = defender.id if winner_id == attacker.id else attacker.id
            winner = self.world.kingdoms[winner_id]
            loser = self.world.kingdoms[loser_id]
            transferable = [sid for sid in loser.settlement_ids if sid != loser.capital_settlement_id]
            if transferable:
                # Transfer the settlement nearest the winner's capital.
                cap = self.world.settlements[winner.capital_settlement_id]
                sid = min(transferable, key=lambda s: math.hypot(self.world.settlements[s].position.x - cap.position.x, self.world.settlements[s].position.y - cap.position.y))
                loser.settlement_ids.remove(sid)
                winner.settlement_ids.append(sid)
                self.world.settlements[sid].kingdom_id = winner.id
                war.occupied_settlement_ids.append(sid)
                self.emit("SETTLEMENT_TRANSFERRED", f"{self.world.settlements[sid].name} passed from {loser.name} to {winner.name} after the war.", [sid, loser.id, winner.id, war.id], sid, importance=0.82)
            summary = f"{winner.name} won the war between {attacker.name} and {defender.name} through {reason}."
        else:
            summary = f"The war between {attacker.name} and {defender.name} ended without a clear victor due to {reason}."
        for kingdom in (attacker, defender):
            relation = kingdom.relations.get(defender.id if kingdom.id == attacker.id else attacker.id)
            if relation:
                relation.truce_until_year = self.world.date.year + 3
                relation.opinion = min(relation.opinion, -0.45)
            for aid in kingdom.army_ids:
                army = self.world.armies.get(aid)
                if army:
                    army.destination_settlement_id = kingdom.capital_settlement_id
        self.emit("WAR_ENDED", summary, [war.id, attacker.id, defender.id], data={"winner_id": winner_id, "reason": reason}, importance=0.92)

    # ------------------------------------------------------------------
    # Succession and culture
    # ------------------------------------------------------------------

    def kill_npc(self, npc_id: str, cause: str, source: str = "admin") -> NPC:
        npc = self.world.npcs.get(npc_id)
        if not npc:
            raise KeyError("unknown NPC")
        if not npc.alive:
            return npc
        npc.alive = False
        npc.health = 0.0
        self.emit("NPC_DIED", f"{npc.name} died from {cause} at age {npc.age}.", [npc.id, npc.kingdom_id], npc.settlement_id, {"cause": cause}, source=source, importance=0.62 if npc.title else 0.35)
        return npc

    def _succession_checks(self) -> None:
        for kingdom in list(self.world.kingdoms.values()):
            ruler = self.world.npcs.get(kingdom.ruler_npc_id or "")
            if ruler and ruler.alive:
                continue
            candidates = [n for n in self.world.npcs.values() if n.kingdom_id == kingdom.id and n.alive and n.age >= 18]
            if not candidates:
                kingdom.ruler_npc_id = None
                kingdom.legitimacy = max(0.0, kingdom.legitimacy - 0.08)
                continue
            children = [self.world.npcs[c] for c in (ruler.child_ids if ruler else []) if c in self.world.npcs and self.world.npcs[c].alive]
            pool = children or candidates
            successor = max(pool, key=lambda n: n.social_status == "elite" or n.traits.get("ambition", 0) + n.values.get("status", 0))
            old_name = ruler.name if ruler else "the previous ruler"
            successor.title = "Sovereign"
            successor.occupation = "ruler"
            successor.social_status = "ruler"
            kingdom.ruler_npc_id = successor.id
            kingdom.legitimacy = max(0.2, min(1.0, kingdom.legitimacy + (0.04 if children else -0.12)))
            self.emit("RULER_SUCCEEDED", f"{successor.name} succeeded {old_name} as ruler of {kingdom.name}.", [successor.id, kingdom.id], kingdom.capital_settlement_id, importance=0.9)

    def _cultural_drift(self) -> None:
        rng = self._rng("culture")
        for culture in self.world.cultures.values():
            delta = lambda: rng.uniform(-0.015, 0.015)
            culture.honor = max(0, min(1, culture.honor + delta()))
            culture.collectivism = max(0, min(1, culture.collectivism + delta()))
            culture.trade_orientation = max(0, min(1, culture.trade_orientation + delta()))
            culture.magic_acceptance = max(0, min(1, culture.magic_acceptance + delta()))
            culture.tradition = max(0, min(1, culture.tradition + delta()))
            associated = [k for k in self.world.kingdoms.values() if k.culture_id == culture.id]
            if any(self._war_for_kingdom(k.id) for k in associated):
                culture.militarism = min(1.0, culture.militarism + 0.01)
            else:
                culture.militarism = max(0.0, min(1.0, culture.militarism + delta()))
