from __future__ import annotations

from contextlib import nullcontext
from threading import RLock

from .commands import CommandGateway
from .domain import Ancestry, CommandEnvelope


class ValidatedCommandGateway(CommandGateway):
    """Command gateway extensions that preserve cross-entity invariants."""

    def __init__(self, engine, persistence, mutation_lock: RLock | None = None) -> None:
        super().__init__(engine, persistence)
        self.mutation_lock = mutation_lock

    def execute(self, command: CommandEnvelope):
        context = self.mutation_lock if self.mutation_lock is not None else nullcontext()
        with context:
            return super().execute(command)

    def _dispatch(self, command: CommandEnvelope) -> dict:
        result = super()._dispatch(command)
        kind = command.type.lower().strip()
        world = self.engine.world

        if kind == "settlement.change_kingdom" and command.target_id:
            settlement = world.settlements.get(command.target_id)
            if settlement:
                for npc in world.npcs.values():
                    if npc.alive and npc.settlement_id == settlement.id:
                        npc.kingdom_id = settlement.kingdom_id

        if kind == "world.disaster" and str(command.parameters.get("disaster", "famine")) == "plague":
            settlement_ids = list(world.settlements)
            if command.target_id:
                if command.target_id in world.settlements:
                    settlement_ids = [command.target_id]
                elif command.target_id in world.kingdoms:
                    settlement_ids = list(world.kingdoms[command.target_id].settlement_ids)
            for settlement_id in settlement_ids:
                settlement = world.settlements.get(settlement_id)
                if settlement:
                    self._reconcile_ancestry_population(settlement)

        return result

    @staticmethod
    def _reconcile_ancestry_population(settlement) -> None:
        """Keep ancestry totals equal to the settlement's statistical population."""
        target = max(0, settlement.population)
        current = sum(settlement.ancestry_population.values())
        if current == target:
            return
        if target == 0:
            settlement.ancestry_population = {ancestry: 0 for ancestry in settlement.ancestry_population}
            return
        if current <= 0:
            settlement.ancestry_population = {Ancestry.HUMAN: target}
            return

        scaled = {
            ancestry: int(count * target / current)
            for ancestry, count in settlement.ancestry_population.items()
        }
        remainder = target - sum(scaled.values())
        if remainder:
            dominant = max(
                settlement.ancestry_population,
                key=settlement.ancestry_population.get,
            )
            scaled[dominant] = scaled.get(dominant, 0) + remainder
        settlement.ancestry_population = scaled
