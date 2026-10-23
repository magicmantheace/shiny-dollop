"""Deterministic, presentation-only attack and reaction selection.

Canonical Crawl events decide that a hit occurred. This module only selects a
validated animation silhouette and matching reaction intensity for that hit.
"""

from hashlib import sha256


ATTACK_TIERS = {
    "light": (
        "humanoid.combat.attack.default",
        "humanoid.combat.attack.02",
        "humanoid.combat.attack.03",
    ),
    "heavy": (
        "humanoid.combat.attack.charged",
        "humanoid.combat.attack.03",
        "humanoid.combat.attack.default",
    ),
}

REACTION_BY_ATTACK_SUFFIX = {
    ".default": "light",
    ".02": "light",
    ".03": "medium",
    ".charged": "heavy",
}

VALIDATION_ATTACK_ORDER = (
    "humanoid.combat.attack.default",
    "humanoid.combat.attack.02",
    # The third encounter window contains a foreground bystander. Keep the
    # already-proven default there and reserve new long-silhouette profiles for
    # the two unobstructed final pair windows.
    "humanoid.combat.attack.default",
    "humanoid.combat.attack.charged",
    "humanoid.combat.attack.03",
)


def _prefix(actor_kind: str) -> str:
    return "humanoid" if actor_kind == "crawler" else "enemy.biped"


def _stable_index(token: str, count: int) -> int:
    if count <= 0:
        raise ValueError("selection pool cannot be empty")
    digest = sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % count


def attack_tier(event_type: str, event_data: dict | None = None) -> str:
    """Map existing metadata to style without inventing canonical damage."""
    del event_type
    data = event_data or {}
    severity = str(data.get("severity", data.get("hit_severity", ""))).lower()
    if severity in {"heavy", "critical", "major", "charged"}:
        return "heavy"
    return "light"


def choose_attack_slot(
    event_id: str,
    event_type: str,
    validated_slots,
    event_data: dict | None = None,
    actor_kind: str = "crawler",
    *,
    performer_id: str = "",
    target_id: str = "",
    presentation_seed: str = "",
) -> str:
    """Choose only from validated profiles, with Attack_01 as safe baseline."""
    prefix = _prefix(actor_kind)
    tier = attack_tier(event_type, event_data)
    validated = set(validated_slots)
    candidates = []
    for humanoid_slot in ATTACK_TIERS[tier]:
        slot = humanoid_slot.replace("humanoid", prefix, 1)
        if slot in validated:
            candidates.append(slot)
    fallback = f"{prefix}.combat.attack.default"
    if fallback in validated and fallback not in candidates:
        candidates.append(fallback)
    if not candidates:
        # Attack_01 is the already-proven compatibility baseline. Optional
        # profiles can disappear without breaking presentation generation.
        return fallback
    token = ":".join(
        (presentation_seed, str(event_id), tier, prefix, performer_id, target_id)
    )
    return candidates[_stable_index(token, len(candidates))]


def validation_cycle_attack_slot(index: int, actor_kind: str, validated_slots) -> str:
    """Diagnostic-only deterministic cycle that proves every active profile."""
    prefix = _prefix(actor_kind)
    validated = set(validated_slots)
    candidates = [
        slot.replace("humanoid", prefix, 1)
        for slot in VALIDATION_ATTACK_ORDER
        if slot.replace("humanoid", prefix, 1) in validated
    ]
    if not candidates:
        return f"{prefix}.combat.attack.default"
    return candidates[int(index) % len(candidates)]


def reaction_tier(event_data: dict | None = None, attack_slot: str = "") -> str:
    data = event_data or {}
    severity = str(data.get("severity", data.get("hit_severity", ""))).lower()
    if severity in {"heavy", "critical", "major", "charged"}:
        return "heavy"
    if severity in {"medium", "moderate"}:
        return "medium"
    for suffix, tier in REACTION_BY_ATTACK_SUFFIX.items():
        if attack_slot.endswith(suffix):
            return tier
    return "light"


def choose_reaction_slot(
    actor_kind: str,
    event_data: dict | None = None,
    attack_slot: str = "",
    validated_slots=None,
) -> str:
    prefix = _prefix(actor_kind)
    desired = f"{prefix}.reaction.hit.{reaction_tier(event_data, attack_slot)}"
    if validated_slots is None or desired in set(validated_slots):
        return desired
    fallback = f"{prefix}.reaction.hit.default"
    return fallback
