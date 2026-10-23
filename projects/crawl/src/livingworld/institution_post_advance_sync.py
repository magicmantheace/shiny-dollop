from __future__ import annotations

from .advanced_simulation import LivingWorldEngine
from .institutions import ensure_institutional_society


_ORIGINAL_ADVANCE_HOURS = LivingWorldEngine.advance_hours
_INSTALLED = False


def _advance_hours_with_post_world_institution_sync(
    self: LivingWorldEngine,
    hours: int,
    *,
    ignore_pause: bool = False,
):
    """Resynchronize institutions after all subclass monthly systems finish.

    FinalWorldEngine continues with migration/frontier systems after the Slice 2
    institution cycle runs inside LivingWorldEngine._monthly. Those later systems
    can found or transfer settlements. Refreshing here, after the complete public
    advance returns, guarantees policy_compliance and effective_policies describe
    the authoritative kingdom settlement lists visible to callers.
    """
    world = _ORIGINAL_ADVANCE_HOURS(self, hours, ignore_pause=ignore_pause)
    ensure_institutional_society(self)
    return world


def install_post_advance_institution_sync() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    LivingWorldEngine.advance_hours = _advance_hours_with_post_world_institution_sync
    _INSTALLED = True
