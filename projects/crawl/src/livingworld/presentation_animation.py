from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from .attack_variety import (
    choose_attack_slot,
    choose_reaction_slot,
    validation_cycle_attack_slot,
)
from .presentation_staging import PresentationBeat, PresentationStagingManifest, StagedActor

ANIMATION_PROTOCOL = "crawl.presentation-animation.v1"

VALIDATED_ATTACK_SLOTS = frozenset(
    f"{prefix}.combat.attack{suffix}"
    for prefix in ("humanoid", "enemy.biped")
    for suffix in (".default", ".02", ".03", ".charged")
)
VALIDATED_REACTION_SLOTS = frozenset(
    f"{prefix}.reaction.hit.{severity}"
    for prefix in ("humanoid", "enemy.biped")
    for severity in ("light", "medium", "heavy")
)


@dataclass(frozen=True)
class CharacterRigProfile:
    actor_id: str
    actor_kind: str
    rig_slot: str
    locomotion_slot: str
    idle_slot: str

    def as_dict(self) -> dict:
        return {
            "actor_id": self.actor_id,
            "actor_kind": self.actor_kind,
            "rig_slot": self.rig_slot,
            "locomotion_slot": self.locomotion_slot,
            "idle_slot": self.idle_slot,
        }


@dataclass(frozen=True)
class AnimationIntent:
    id: str
    beat_id: str
    event_id: str
    event_type: str
    actor_id: str
    role: str
    start_seconds: float
    duration_seconds: float
    asset_slot: str
    layer: str
    target_actor_id: str | None = None
    locomotion_mode: str = "none"
    root_motion_policy: str = "in_place"
    contact_policy: str = "none"
    blend_in_seconds: float = 0.12
    blend_out_seconds: float = 0.12
    priority: int = 50
    authoritative: bool = False

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "beat_id": self.beat_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "role": self.role,
            "start_seconds": round(self.start_seconds, 3),
            "duration_seconds": round(self.duration_seconds, 3),
            "asset_slot": self.asset_slot,
            "layer": self.layer,
            "target_actor_id": self.target_actor_id,
            "locomotion_mode": self.locomotion_mode,
            "root_motion_policy": self.root_motion_policy,
            "contact_policy": self.contact_policy,
            "blend_in_seconds": round(self.blend_in_seconds, 3),
            "blend_out_seconds": round(self.blend_out_seconds, 3),
            "priority": self.priority,
            "authoritative": self.authoritative,
        }


@dataclass(frozen=True)
class PresentationAnimationPlan:
    protocol: str
    source_staging_digest: str
    source_event_ids: tuple[str, ...]
    rigs: tuple[CharacterRigProfile, ...]
    intents: tuple[AnimationIntent, ...]
    digest: str
    authoritative: bool = False

    def as_dict(self) -> dict:
        return {
            "protocol": self.protocol,
            "source_staging_digest": self.source_staging_digest,
            "source_event_ids": list(self.source_event_ids),
            "authoritative": self.authoritative,
            "authority_contract": {
                "canonical_source": "crawl_event_ledger",
                "presentation_may": [
                    "select_animation_asset",
                    "blend_animation",
                    "interpolate_locomotion",
                    "apply_motion_warping",
                    "solve_inverse_kinematics",
                    "add_noncanonical_reaction_motion",
                ],
                "presentation_must_not": [
                    "change_event_order",
                    "change_event_outcome",
                    "change_participants",
                    "create_damage",
                    "create_death",
                    "create_rescue",
                    "create_canonical_events",
                ],
            },
            "rigs": [rig.as_dict() for rig in self.rigs],
            "intents": [intent.as_dict() for intent in self.intents],
            "digest": self.digest,
        }


def _digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _rig_profile(actor: StagedActor) -> CharacterRigProfile:
    if actor.actor_kind == "crawler":
        return CharacterRigProfile(
            actor_id=actor.actor_id,
            actor_kind=actor.actor_kind,
            rig_slot="rig.humanoid.crawler",
            locomotion_slot="locomotion.humanoid.standard",
            idle_slot="idle.humanoid.combat_ready",
        )
    return CharacterRigProfile(
        actor_id=actor.actor_id,
        actor_kind=actor.actor_kind,
        rig_slot="rig.enemy.biped",
        locomotion_slot="locomotion.enemy.biped",
        idle_slot="idle.enemy.biped",
    )


def _slot(actor_kind: str, suffix: str) -> str:
    prefix = "humanoid" if actor_kind == "crawler" else "enemy.biped"
    return f"{prefix}.{suffix}"


def _intent_id(beat: PresentationBeat, actor_id: str, role: str) -> str:
    token = f"{beat.id}:{beat.event_id}:{actor_id}:{role}"
    return "anim_" + sha256(token.encode("utf-8")).hexdigest()[:16]


class PresentationAnimationPlanner:
    """Translate presentation beats into deterministic semantic animation intents.

    The planner never chooses authoritative outcomes. It only describes which
    presentation motion Unreal should attempt to play for events that already
    exist in the canonical Crawl ledger.
    """

    def __init__(
        self,
        *,
        validated_attack_slots=VALIDATED_ATTACK_SLOTS,
        validated_reaction_slots=VALIDATED_REACTION_SLOTS,
        validation_attack_cycle: bool = False,
    ) -> None:
        self.validated_attack_slots = frozenset(validated_attack_slots)
        self.validated_reaction_slots = frozenset(validated_reaction_slots)
        self.validation_attack_cycle = bool(validation_attack_cycle)

    def plan(self, manifest: PresentationStagingManifest) -> PresentationAnimationPlan:
        if manifest.authoritative is not False:
            raise ValueError("animation planning only accepts non-authoritative staging manifests")

        actor_by_id = {actor.actor_id: actor for actor in manifest.actors}
        rigs = tuple(_rig_profile(actor) for actor in manifest.actors)
        intents: list[AnimationIntent] = []

        attack_index = 0
        for beat in manifest.beats:
            cycle_index = attack_index if beat.action == "attack_hit" else None
            intents.extend(
                self._beat_intents(
                    beat,
                    actor_by_id,
                    manifest.presentation_seed,
                    cycle_index,
                )
            )
            if beat.action == "attack_hit":
                attack_index += 1

        intents.sort(key=lambda item: (item.start_seconds, -item.priority, item.id))
        base = {
            "protocol": ANIMATION_PROTOCOL,
            "source_staging_digest": manifest.digest,
            "source_event_ids": list(manifest.source_event_ids),
            "rigs": [rig.as_dict() for rig in rigs],
            "intents": [intent.as_dict() for intent in intents],
            "authoritative": False,
        }
        return PresentationAnimationPlan(
            protocol=ANIMATION_PROTOCOL,
            source_staging_digest=manifest.digest,
            source_event_ids=manifest.source_event_ids,
            rigs=rigs,
            intents=tuple(intents),
            digest=_digest(base),
            authoritative=False,
        )

    def _beat_intents(
        self,
        beat: PresentationBeat,
        actor_by_id: dict[str, StagedActor],
        presentation_seed: str,
        attack_cycle_index: int | None,
    ) -> list[AnimationIntent]:
        action = beat.action
        result: list[AnimationIntent] = []

        def add(
            actor_id: str | None,
            *,
            role: str,
            suffix: str,
            layer: str,
            target_actor_id: str | None = None,
            locomotion_mode: str = "none",
            root_motion_policy: str = "in_place",
            contact_policy: str = "none",
            priority: int = 50,
            duration_scale: float = 1.0,
            asset_slot: str | None = None,
        ) -> None:
            if actor_id is None or actor_id not in actor_by_id:
                return
            actor = actor_by_id[actor_id]
            result.append(
                AnimationIntent(
                    id=_intent_id(beat, actor_id, role),
                    beat_id=beat.id,
                    event_id=beat.event_id,
                    event_type=beat.event_type,
                    actor_id=actor_id,
                    role=role,
                    start_seconds=beat.start_seconds,
                    duration_seconds=max(0.1, beat.duration_seconds * duration_scale),
                    asset_slot=asset_slot or _slot(actor.actor_kind, suffix),
                    layer=layer,
                    target_actor_id=target_actor_id if target_actor_id in actor_by_id else None,
                    locomotion_mode=locomotion_mode,
                    root_motion_policy=root_motion_policy,
                    contact_policy=contact_policy,
                    priority=priority,
                    authoritative=False,
                )
            )

        if action == "attack_hit":
            performer = actor_by_id.get(beat.performer_id)
            target = actor_by_id.get(beat.target_id)
            if performer is None or target is None:
                return result
            if self.validation_attack_cycle and attack_cycle_index is not None:
                attack_slot = validation_cycle_attack_slot(
                    attack_cycle_index,
                    performer.actor_kind,
                    self.validated_attack_slots,
                )
            else:
                attack_slot = choose_attack_slot(
                    beat.event_id,
                    beat.event_type,
                    self.validated_attack_slots,
                    actor_kind=performer.actor_kind,
                    performer_id=beat.performer_id or "",
                    target_id=beat.target_id or "",
                    presentation_seed=presentation_seed,
                )
            reaction_slot = choose_reaction_slot(
                target.actor_kind,
                attack_slot=attack_slot,
                validated_slots=self.validated_reaction_slots,
            )
            add(
                beat.performer_id,
                role="attack",
                suffix="combat.attack.default",
                asset_slot=attack_slot,
                layer="action",
                target_actor_id=beat.target_id,
                root_motion_policy="motion_warp_to_target",
                contact_policy="weapon_or_hand_contact",
                priority=90,
            )
            add(
                beat.target_id,
                role="hit_reaction",
                suffix="reaction.hit.default",
                asset_slot=reaction_slot,
                layer="reaction",
                target_actor_id=beat.performer_id,
                contact_policy="react_at_contact",
                priority=95,
            )
        elif action == "injury_reaction":
            add(
                beat.target_id,
                role="injury_reaction",
                suffix="reaction.injury",
                layer="reaction",
                target_actor_id=beat.performer_id,
                priority=96,
            )
        elif action == "near_death":
            add(
                beat.target_id,
                role="near_death",
                suffix="reaction.near_death",
                layer="reaction",
                priority=98,
            )
        elif action in {"death", "defeat"}:
            add(
                beat.target_id,
                role=action,
                suffix="reaction.death" if action == "death" else "reaction.defeat",
                layer="reaction",
                priority=100,
            )
        elif action == "retreat":
            add(
                beat.performer_id,
                role="retreat",
                suffix="locomotion.run",
                layer="locomotion",
                locomotion_mode="run_away",
                root_motion_policy="navigation_driven",
                priority=80,
            )
        elif action == "move":
            add(
                beat.performer_id,
                role="move",
                suffix="locomotion.move",
                layer="locomotion",
                locomotion_mode="move_to_stage_target",
                root_motion_policy="navigation_driven",
                priority=60,
            )
        elif action == "rescue":
            add(
                beat.performer_id,
                role="rescue",
                suffix="interaction.rescue",
                layer="action",
                target_actor_id=beat.target_id,
                root_motion_policy="motion_warp_to_target",
                contact_policy="paired_interaction",
                priority=92,
            )
            add(
                beat.target_id,
                role="rescued_reaction",
                suffix="reaction.rescued",
                layer="reaction",
                target_actor_id=beat.performer_id,
                contact_policy="paired_interaction",
                priority=91,
            )
        elif action in {"combat_start", "combat_end"}:
            add(
                beat.performer_id,
                role=action,
                suffix="combat.ready" if action == "combat_start" else "combat.disengage",
                layer="action",
                priority=55,
            )
        elif action == "observe":
            add(
                beat.performer_id,
                role="observe",
                suffix="idle.observe",
                layer="additive",
                target_actor_id=beat.target_id,
                priority=20,
            )

        return result


def validate_animation_plan(plan: PresentationAnimationPlan, staging: PresentationStagingManifest) -> bool:
    if plan.protocol != ANIMATION_PROTOCOL or plan.authoritative is not False:
        return False
    if plan.source_staging_digest != staging.digest:
        return False
    if plan.source_event_ids != staging.source_event_ids:
        return False

    staged_actor_ids = {actor.actor_id for actor in staging.actors}
    staged_beat_ids = {beat.id for beat in staging.beats}
    staged_event_ids = set(staging.source_event_ids)

    for rig in plan.rigs:
        if rig.actor_id not in staged_actor_ids:
            return False
    for intent in plan.intents:
        if intent.authoritative is not False:
            return False
        if intent.actor_id not in staged_actor_ids:
            return False
        if intent.target_actor_id is not None and intent.target_actor_id not in staged_actor_ids:
            return False
        if intent.beat_id not in staged_beat_ids:
            return False
        if intent.event_id not in staged_event_ids:
            return False
        if intent.duration_seconds <= 0:
            return False
        if not intent.asset_slot:
            return False

    return True
