from __future__ import annotations

from . import politics, warfare
from .advanced_simulation import LivingWorldEngine
from .domain import Kingdom


_INSTALLED = False


def _ruler_is_valid(engine: LivingWorldEngine, kingdom: Kingdom) -> bool:
    if not kingdom.ruler_npc_id:
        return False
    ruler = engine.world.npcs.get(kingdom.ruler_npc_id)
    return bool(ruler and ruler.alive and ruler.kingdom_id == kingdom.id)


def _reconcile_kingdom_politics(engine: LivingWorldEngine, kingdom: Kingdom) -> None:
    """Repair political references after people or settlements change kingdoms.

    Warfare transfers every living resident of a ceded settlement to the winner.
    A ruler, office holder, faction member, or faction regional base can therefore
    become foreign to the kingdom that still references it. Political invariants
    require those references to be reconciled immediately rather than waiting for a
    later monthly refresh.
    """

    # Regional bases must remain inside the faction's kingdom. Membership refresh
    # below rebuilds members/leaders from currently valid adults in the kingdom.
    for faction_id in kingdom.faction_ids:
        faction = engine.world.political_factions.get(faction_id)
        if not faction or not faction.active:
            continue
        if faction.regional_base_settlement_id:
            base = engine.world.settlements.get(faction.regional_base_settlement_id)
            if not base or base.kingdom_id != kingdom.id:
                faction.regional_base_settlement_id = None

    politics._refresh_faction_membership(engine, kingdom)

    # An alive ruler is not valid if territorial transfer moved that NPC into a
    # different kingdom. Install a legitimate remaining successor when possible.
    if kingdom.ruler_npc_id and not _ruler_is_valid(engine, kingdom):
        prior_ruler = engine.world.npcs.get(kingdom.ruler_npc_id)
        successor = politics.select_successor(engine, kingdom, prior_ruler)
        if successor:
            politics.install_ruler(
                engine,
                kingdom,
                successor,
                prior_ruler,
                method="postwar political succession",
                succession=True,
            )
        else:
            kingdom.ruler_npc_id = None
            kingdom.legitimacy = max(0.0, kingdom.legitimacy - 0.08)

    # refresh_offices replaces any surviving office holder who now belongs to the
    # other kingdom and keeps the ruler office synchronized with ruler_npc_id.
    politics.refresh_offices(engine, kingdom, emit_changes=False)


def reconcile_transfer_politics(
    engine: LivingWorldEngine,
    winner_id: str,
    loser_id: str,
) -> None:
    for kingdom_id in (loser_id, winner_id):
        kingdom = engine.world.kingdoms.get(kingdom_id)
        if kingdom:
            _reconcile_kingdom_politics(engine, kingdom)
    politics.refresh_political_metrics(engine)


def install_warfare_political_reconciliation() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    original_transfer = warfare._transfer_settlement
    original_succession_checks = LivingWorldEngine._succession_checks

    def transfer_with_political_reconciliation(
        engine: LivingWorldEngine,
        settlement_id: str,
        winner_id: str,
        loser_id: str,
        war,
    ) -> None:
        original_transfer(engine, settlement_id, winner_id, loser_id, war)
        reconcile_transfer_politics(engine, winner_id, loser_id)

    def succession_checks_with_kingdom_guard(self: LivingWorldEngine) -> None:
        # Defense in depth: any future subsystem that changes an NPC's kingdom must
        # not leave an alive foreign ruler immune to succession merely because the
        # NPC is still alive.
        for kingdom in list(self.world.kingdoms.values()):
            if kingdom.ruler_npc_id and not _ruler_is_valid(self, kingdom):
                _reconcile_kingdom_politics(self, kingdom)
        original_succession_checks(self)
        for kingdom in list(self.world.kingdoms.values()):
            politics.refresh_offices(self, kingdom, emit_changes=False)
        politics.refresh_political_metrics(self)

    warfare._transfer_settlement = transfer_with_political_reconciliation
    LivingWorldEngine._succession_checks = succession_checks_with_kingdom_guard
    _INSTALLED = True
