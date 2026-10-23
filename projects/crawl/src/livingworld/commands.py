from __future__ import annotations

import re
import uuid
from typing import Any

from .domain import BorderPolicy, CommandEnvelope, CommandRecord, CommandStatus, RefugeePolicy
from .persistence import Persistence
from .simulation import WorldEngine


class CommandError(ValueError):
    pass


class CommandGateway:
    def __init__(self, engine: WorldEngine, persistence: Persistence) -> None:
        self.engine = engine
        self.persistence = persistence

    def execute(self, command: CommandEnvelope) -> CommandRecord:
        record = CommandRecord(
            id=f"command_{uuid.uuid4().hex}",
            command=command,
            status=CommandStatus.QUEUED,
            created_at=self.engine.world.date.model_copy(deep=True),
        )
        self.persistence.save_command(record)
        try:
            record.status = CommandStatus.ACCEPTED
            self.persistence.save_command(record)
            record.status = CommandStatus.EXECUTING
            self.persistence.save_command(record)
            result = self._dispatch(command)
            record.result = result
            record.status = CommandStatus.COMPLETED
            record.completed_at = self.engine.world.date.model_copy(deep=True)
            self.engine.emit(
                "ADMIN_COMMAND",
                f"External command {command.type} completed for {command.target_id or 'world'}.",
                [command.target_id] if command.target_id else [],
                data={"command_id": record.id, "command": command.model_dump(mode="json"), "result": result},
                source=command.issuer,
                importance=0.12,
            )
            self.persistence.save_world(self.engine.world)
        except (CommandError, ValueError, KeyError) as exc:
            record.status = CommandStatus.REJECTED
            record.error = str(exc)
            record.completed_at = self.engine.world.date.model_copy(deep=True)
        except Exception as exc:
            record.status = CommandStatus.FAILED
            record.error = str(exc)
            record.completed_at = self.engine.world.date.model_copy(deep=True)
        finally:
            self.persistence.save_command(record)
        return record

    def _dispatch(self, command: CommandEnvelope) -> dict[str, Any]:
        world = self.engine.world
        kind = command.type.lower().strip()
        p = command.parameters

        if kind == "world.pause":
            world.paused = True
            return {"paused": True}
        if kind == "world.resume":
            world.paused = False
            return {"paused": False}
        if kind == "world.set_speed":
            speed = float(p.get("speed", 1.0))
            if speed < 0 or speed > 10_000:
                raise CommandError("speed must be between 0 and 10000")
            world.speed_multiplier = speed
            return {"speed_multiplier": speed}
        if kind == "world.advance":
            amount = int(p.get("amount", 1))
            unit = str(p.get("unit", "day")).lower().rstrip("s")
            if amount < 0:
                raise CommandError("amount must be non-negative")
            if unit == "hour":
                self.engine.advance_hours(amount, ignore_pause=True)
            elif unit == "day":
                self.engine.advance_days(amount, ignore_pause=True)
            elif unit == "month":
                self.engine.advance_months(amount, ignore_pause=True)
            elif unit == "year":
                self.engine.advance_years(amount, ignore_pause=True)
            else:
                raise CommandError("unit must be hour, day, month, or year")
            return {"date": world.date.model_dump(), "advanced": amount, "unit": unit}
        if kind == "world.disaster":
            disaster = str(p.get("disaster", "famine"))
            severity = max(0.0, min(1.0, float(p.get("severity", 0.5))))
            settlement_ids = list(world.settlements)
            if command.target_id:
                if command.target_id in world.settlements:
                    settlement_ids = [command.target_id]
                elif command.target_id in world.kingdoms:
                    settlement_ids = list(world.kingdoms[command.target_id].settlement_ids)
                else:
                    raise CommandError("disaster target must be a settlement, kingdom, or omitted for the world")
            for sid in settlement_ids:
                settlement = world.settlements[sid]
                if disaster == "famine":
                    grain = settlement.resources.get("grain")
                    if grain:
                        grain.quantity *= max(0.0, 1 - severity * 0.8)
                    settlement.food_security *= max(0.0, 1 - severity * 0.6)
                elif disaster == "plague":
                    settlement.health *= max(0.1, 1 - severity * 0.5)
                    settlement.population = max(0, int(settlement.population * (1 - severity * 0.04)))
                elif disaster == "earthquake":
                    settlement.infrastructure = {k: max(0, v - severity * 0.25) for k, v in settlement.infrastructure.items()}
                    settlement.housing_capacity = max(settlement.population // 2, int(settlement.housing_capacity * (1 - severity * 0.15)))
                else:
                    raise CommandError("supported disasters: famine, plague, earthquake")
            self.engine.emit("DISASTER", f"An externally triggered {disaster} affected {len(settlement_ids)} settlements.", settlement_ids[:20], data={"severity": severity}, source=command.issuer, importance=0.85)
            return {"disaster": disaster, "severity": severity, "settlements_affected": len(settlement_ids)}

        if kind.startswith("kingdom."):
            kingdom = world.kingdoms.get(command.target_id or "")
            if not kingdom:
                raise CommandError("unknown kingdom target")
            if kind == "kingdom.set_priority":
                priority = str(p["priority"])
                weight = max(0.0, min(1.0, float(p.get("weight", 1.0))))
                kingdom.goals[priority] = weight
                return {"priority": priority, "weight": weight}
            if kind == "kingdom.set_tax":
                rate = float(p["rate"])
                if not 0 <= rate <= 0.75:
                    raise CommandError("tax rate must be between 0 and 0.75")
                kingdom.tax_rate = rate
                return {"tax_rate": rate}
            if kind == "kingdom.set_border_policy":
                try:
                    policy = BorderPolicy(str(p["policy"]).lower())
                except ValueError as exc:
                    raise CommandError("border policy must be open, controlled, or closed") from exc
                kingdom.border_policy = policy
                self.engine.emit(
                    "BORDER_POLICY_CHANGED",
                    f"{kingdom.name} changed its border policy to {policy.value}.",
                    [kingdom.id], kingdom.capital_settlement_id,
                    data={"border_policy": policy.value}, source=command.issuer, importance=0.42,
                )
                return {"border_policy": policy.value}
            if kind == "kingdom.set_refugee_policy":
                try:
                    policy = RefugeePolicy(str(p["policy"]).lower())
                except ValueError as exc:
                    raise CommandError("refugee policy must be welcome, limited, or reject") from exc
                kingdom.refugee_policy = policy
                self.engine.emit(
                    "REFUGEE_POLICY_CHANGED",
                    f"{kingdom.name} changed its refugee policy to {policy.value}.",
                    [kingdom.id], kingdom.capital_settlement_id,
                    data={"refugee_policy": policy.value}, source=command.issuer, importance=0.42,
                )
                return {"refugee_policy": policy.value}
            if kind == "kingdom.declare_war":
                defender = str(p["target_kingdom_id"])
                war = self.engine.declare_war(kingdom.id, defender, str(p.get("goal", "admin-directed conflict")), source=command.issuer)
                return {"war_id": war.id}
            if kind == "kingdom.change_ruler":
                npc_id = str(p["npc_id"])
                npc = world.npcs.get(npc_id)
                if not npc or not npc.alive or npc.kingdom_id != kingdom.id:
                    raise CommandError("ruler must be a living NPC in the kingdom")
                old = world.npcs.get(kingdom.ruler_npc_id or "")
                if old:
                    old.title = None
                    old.social_status = "elite"
                npc.title = "Sovereign"
                npc.occupation = "ruler"
                npc.social_status = "ruler"
                kingdom.ruler_npc_id = npc.id
                self.engine.emit("RULER_CHANGED", f"{npc.name} was installed as ruler of {kingdom.name} by external decree.", [npc.id, kingdom.id], kingdom.capital_settlement_id, source=command.issuer, importance=0.95)
                return {"ruler_npc_id": npc.id}
            if kind == "kingdom.mobilize":
                target = str(p.get("destination_settlement_id", kingdom.capital_settlement_id))
                if target not in world.settlements:
                    raise CommandError("unknown destination settlement")
                for aid in kingdom.army_ids:
                    army = world.armies.get(aid)
                    if army and army.active:
                        army.destination_settlement_id = target
                        army.readiness = min(1.0, army.readiness + 0.1)
                return {"destination_settlement_id": target, "armies": kingdom.army_ids}

        if kind.startswith("settlement."):
            settlement = world.settlements.get(command.target_id or "")
            if not settlement:
                raise CommandError("unknown settlement target")
            if kind == "settlement.add_resource":
                resource = str(p["resource"])
                amount = float(p["amount"])
                stock = settlement.resources.get(resource)
                if not stock:
                    raise CommandError(f"settlement has no {resource} stock")
                stock.quantity += amount
                stock.clamp()
                return {"resource": resource, "quantity": stock.quantity}
            if kind == "settlement.set_stability":
                settlement.stability = max(0.0, min(1.0, float(p["stability"])))
                return {"stability": settlement.stability}
            if kind == "settlement.build":
                building = str(p["building"])
                count = max(1, int(p.get("count", 1)))
                settlement.buildings[building] = settlement.buildings.get(building, 0) + count
                settlement.wealth = max(0.0, settlement.wealth - 10 * count)
                return {"building": building, "count": settlement.buildings[building]}
            if kind == "settlement.change_kingdom":
                new_id = str(p["kingdom_id"])
                new_kingdom = world.kingdoms.get(new_id)
                old_kingdom = world.kingdoms.get(settlement.kingdom_id)
                if not new_kingdom:
                    raise CommandError("unknown destination kingdom")
                if old_kingdom and settlement.id in old_kingdom.settlement_ids:
                    if old_kingdom.capital_settlement_id == settlement.id:
                        raise CommandError("cannot transfer a capital with this command")
                    old_kingdom.settlement_ids.remove(settlement.id)
                if settlement.id not in new_kingdom.settlement_ids:
                    new_kingdom.settlement_ids.append(settlement.id)
                settlement.kingdom_id = new_id
                return {"kingdom_id": new_id}

        if kind.startswith("npc."):
            npc = world.npcs.get(command.target_id or "")
            if not npc:
                raise CommandError("unknown NPC target")
            if kind == "npc.travel":
                destination = str(p["settlement_id"])
                if destination not in world.settlements:
                    raise CommandError("unknown settlement destination")
                old = npc.settlement_id
                npc.settlement_id = destination
                npc.kingdom_id = world.settlements[destination].kingdom_id
                self.engine.emit("NPC_TRAVELED", f"{npc.name} traveled from {world.settlements[old].name} to {world.settlements[destination].name}.", [npc.id], destination, source=command.issuer, importance=0.25)
                return {"settlement_id": destination}
            if kind == "npc.kill":
                self.engine.kill_npc(npc.id, str(p.get("cause", "external decree")), source=command.issuer)
                return {"alive": npc.alive}
            if kind == "npc.set_goal":
                goal = str(p["goal"])
                if goal not in npc.goals:
                    npc.goals.append(goal)
                    npc.goal_progress[goal] = 0.0
                return {"goals": npc.goals}
            if kind == "npc.set_occupation":
                npc.occupation = str(p["occupation"])
                return {"occupation": npc.occupation}

        if kind == "war.end":
            war = world.wars.get(command.target_id or "")
            if not war or war.state.value != "active":
                raise CommandError("unknown or inactive war")
            winner = p.get("winner_kingdom_id")
            if winner is not None and winner not in {war.attacker_kingdom_id, war.defender_kingdom_id}:
                raise CommandError("winner must participate in the war")
            self.engine._end_war(war, winner, str(p.get("reason", "external peace settlement")))
            return {"state": war.state.value}

        raise CommandError(f"unsupported command type: {command.type}")


def parse_basic_command(text: str, issuer: str = "admin-console") -> CommandEnvelope | None:
    """Parse a deliberately small deterministic command language.

    Complex natural language belongs to the optional AI command parser. Basic admin
    operations remain available offline and without an LLM.
    """

    clean = " ".join(text.strip().split())
    lower = clean.lower()
    if lower == "pause world":
        return CommandEnvelope(type="world.pause", issuer=issuer)
    if lower == "resume world":
        return CommandEnvelope(type="world.resume", issuer=issuer)

    match = re.fullmatch(r"advance (\d+) (hours?|days?|months?|years?)", lower)
    if match:
        return CommandEnvelope(type="world.advance", parameters={"amount": int(match.group(1)), "unit": match.group(2)}, issuer=issuer)

    match = re.fullmatch(r"kill (npc_\d+)(?: (.+))?", lower)
    if match:
        return CommandEnvelope(type="npc.kill", target_id=match.group(1), parameters={"cause": match.group(2) or "external decree"}, issuer=issuer)

    match = re.fullmatch(r"tell (npc_\d+) travel (settlement_\d+)", lower)
    if match:
        return CommandEnvelope(type="npc.travel", target_id=match.group(1), parameters={"settlement_id": match.group(2)}, issuer=issuer)

    match = re.fullmatch(r"tell (kingdom_\d+) declare-war (kingdom_\d+)(?: (.+))?", lower)
    if match:
        return CommandEnvelope(type="kingdom.declare_war", target_id=match.group(1), parameters={"target_kingdom_id": match.group(2), "goal": match.group(3) or "external directive"}, issuer=issuer)

    match = re.fullmatch(r"give (settlement_\d+) ([0-9.]+) ([a-z_]+)", lower)
    if match:
        return CommandEnvelope(type="settlement.add_resource", target_id=match.group(1), parameters={"amount": float(match.group(2)), "resource": match.group(3)}, issuer=issuer)

    match = re.fullmatch(r"set (kingdom_\d+) priority ([a-z_]+) ([0-9.]+)", lower)
    if match:
        return CommandEnvelope(type="kingdom.set_priority", target_id=match.group(1), parameters={"priority": match.group(2), "weight": float(match.group(3))}, issuer=issuer)

    match = re.fullmatch(r"set (kingdom_\d+) border (open|controlled|closed)", lower)
    if match:
        return CommandEnvelope(type="kingdom.set_border_policy", target_id=match.group(1), parameters={"policy": match.group(2)}, issuer=issuer)

    match = re.fullmatch(r"set (kingdom_\d+) refugees (welcome|limited|reject)", lower)
    if match:
        return CommandEnvelope(type="kingdom.set_refugee_policy", target_id=match.group(1), parameters={"policy": match.group(2)}, issuer=issuer)

    return None
