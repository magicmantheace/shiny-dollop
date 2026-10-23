"""Deterministic incremental Ledger-to-presentation bridge for Slice 28B.1.

The objects in this module are deliberately independent of Unreal and wall-clock
time.  The simulation remains authoritative; this layer only turns immutable
Ledger events into idempotent, presentation-only commands.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from hashlib import sha256
import json
import math
from time import perf_counter
from typing import Any, Iterable

from .attack_variety import choose_attack_slot, choose_reaction_slot
from .character_dna import CharacterDNAGenerator
from .character_factory import CharacterFactory
from .descender_population import DescenderPopulationGenerator
from .crawl_domain import Crawl, CrawlEvent
from .live_camera_director import LiveCameraConfig, LiveCameraDirector
from .presentation_facing import desired_facing_for_movement, plan_turn


LIVE_PROTOCOL = "underreach.live-presentation.v1"
SCHEDULER_VERSION = "29a2.1"
TERMINAL_EVENT_TYPES = {"ENEMY_DEFEATED", "CRAWLER_DIED", "CRAWLER_ELIMINATED"}
VALIDATED_ATTACK_SLOTS = {
    "humanoid.combat.attack.default",
    "humanoid.combat.attack.02",
    "humanoid.combat.attack.03",
    "humanoid.combat.attack.charged",
    "enemy.biped.combat.attack.default",
    "enemy.biped.combat.attack.02",
    "enemy.biped.combat.attack.03",
    "enemy.biped.combat.attack.charged",
}
VALIDATED_REACTION_SLOTS = {
    "humanoid.reaction.hit.default",
    "humanoid.reaction.hit.light",
    "humanoid.reaction.hit.medium",
    "humanoid.reaction.hit.heavy",
    "enemy.biped.reaction.hit.default",
    "enemy.biped.reaction.hit.light",
    "enemy.biped.reaction.hit.medium",
    "enemy.biped.reaction.hit.heavy",
}
ATTACK_PRESENTATION = {
    # duration, contact phase, measured +Y reach, measured local +X reach,
    # contact effector.  These values are the accepted root-locked AnimPose
    # measurements used by the Slice 28A contact solver.
    "humanoid.combat.attack.default": (1.0, 0.4083333333333333, 93.7539, -0.2642, "hand_r"),
    "humanoid.combat.attack.02": (1.0, 0.4708333333333333, 97.7749, 9.3016, "hand_l"),
    "humanoid.combat.attack.03": (1.6666666269, 0.31666666666666665, 124.5260, -2.7440, "foot_r"),
    "humanoid.combat.attack.charged": (1.8333333731, 0.6083333333333333, 98.0318, -9.2859, "hand_r"),
}
PROCEDURAL_ATTACK_PRESENTATION = {
    # UE 5.8 evaluated hand_r vectors at frame 25/45 after FBX conversion and
    # per-identity scale.  Local +Y is attack-forward; -90 yaw maps it to +X.
    # ``target_surface_offset_cm`` moves the contact target from the opponent's
    # spine centre to the near surface of its torso.  A centre-bone target made
    # two complete bodies interpenetrate and read as one four-armed Human.
    "human": {
        "duration_seconds": 1.5,
        "contact_phase": 25.0 / 45.0,
        "forward_reach_cm": 51.9084,
        "lateral_reach_cm": -14.2380,
        "contact_effector": "hand_r",
        "target_surface_offset_cm": 28.0,
        "minimum_visual_root_separation_cm": 70.0,
    },
    "dwarf": {
        "duration_seconds": 1.5,
        "contact_phase": 25.0 / 45.0,
        "forward_reach_cm": 36.25,
        "lateral_reach_cm": -9.92,
        "contact_effector": "hand_r",
        "target_surface_offset_cm": 28.0,
        "minimum_visual_root_separation_cm": 60.0,
    },
}
PROCEDURAL_DESCENDER_IDS = {"live_descender_004", "live_descender_005"}


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def payload_digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _event_key(event: CrawlEvent) -> tuple[int, str]:
    return (int(event.tick), str(event.id))


def _public_event(event: CrawlEvent) -> dict[str, Any]:
    """Copy only presentation inputs; never return/mutate the source model."""
    return event.model_dump(mode="json")


@dataclass
class LiveLedgerBuffer:
    descent_id: str
    presentation_delay_ticks: int = 3
    maximum_events: int = 4096
    _events: deque[CrawlEvent] = field(default_factory=deque, init=False, repr=False)
    _seen_ids: set[str] = field(default_factory=set, init=False, repr=False)
    _latest_key: tuple[int, str] | None = field(default=None, init=False, repr=False)
    _consumed_key: tuple[int, str] | None = field(default=None, init=False, repr=False)
    dropped_duplicate_count: int = 0
    out_of_order_rejection_count: int = 0
    accepted_event_count: int = 0

    def __post_init__(self) -> None:
        if self.presentation_delay_ticks < 0:
            raise ValueError("presentation_delay_ticks cannot be negative")
        if self.maximum_events < 1:
            raise ValueError("maximum_events must be positive")

    @property
    def latest_authoritative_tick(self) -> int:
        return self._latest_key[0] if self._latest_key else -1

    @property
    def latest_buffered_event_id(self) -> str | None:
        return self._latest_key[1] if self._latest_key else None

    @property
    def latest_consumed_event_id(self) -> str | None:
        return self._consumed_key[1] if self._consumed_key else None

    def push(self, events: Iterable[CrawlEvent]) -> list[CrawlEvent]:
        accepted: list[CrawlEvent] = []
        # A persistence poll may not preserve order inside one page. Canonicalize
        # that page, while still rejecting events older than an earlier page.
        for event in sorted(events, key=_event_key):
            if event.crawl_id != self.descent_id:
                raise ValueError("Ledger event belongs to a different Descent")
            if event.id in self._seen_ids:
                self.dropped_duplicate_count += 1
                continue
            key = _event_key(event)
            if self._latest_key is not None and key < self._latest_key:
                self.out_of_order_rejection_count += 1
                continue
            self._events.append(event.model_copy(deep=True))
            self._seen_ids.add(event.id)
            self._latest_key = key
            self.accepted_event_count += 1
            accepted.append(event)
            while len(self._events) > self.maximum_events:
                removed = self._events.popleft()
                if self._consumed_key is None or _event_key(removed) > self._consumed_key:
                    raise RuntimeError("live Ledger window overflowed before presentation consumed it")
        return accepted

    def consume_ready(self, *, flush: bool = False) -> list[CrawlEvent]:
        if not self._events:
            return []
        ready_tick = math.inf if flush else self.latest_authoritative_tick - self.presentation_delay_ticks
        ready = [
            event.model_copy(deep=True)
            for event in self._events
            if (self._consumed_key is None or _event_key(event) > self._consumed_key)
            and event.tick <= ready_tick
        ]
        if ready:
            self._consumed_key = _event_key(ready[-1])
        return ready

    def peek_lookahead(self, *, after_tick: int, lookahead_ticks: int) -> list[CrawlEvent]:
        """Copy only the bounded future window visible to live presentation."""
        if lookahead_ticks < 0:
            raise ValueError("lookahead_ticks cannot be negative")
        end_tick = int(after_tick) + int(lookahead_ticks)
        return [
            event.model_copy(deep=True)
            for event in self._events
            if int(after_tick) < int(event.tick) <= end_tick
        ]

    def snapshot(self) -> dict[str, Any]:
        pending = [e for e in self._events if self._consumed_key is None or _event_key(e) > self._consumed_key]
        body = {
            "descent_id": self.descent_id,
            "latest_authoritative_tick": self.latest_authoritative_tick,
            "latest_buffered_event_id": self.latest_buffered_event_id,
            "latest_consumed_event_id": self.latest_consumed_event_id,
            "buffer_depth": len(pending),
            "retained_event_count": len(self._events),
            "presentation_delay_ticks": self.presentation_delay_ticks,
            "dropped_duplicate_count": self.dropped_duplicate_count,
            "out_of_order_rejection_count": self.out_of_order_rejection_count,
            "accepted_event_count": self.accepted_event_count,
        }
        return {**body, "digest": payload_digest(body)}


@dataclass
class LiveActorState:
    actor_id: str
    actor_kind: str
    sector_id: str | None = None
    spawned: bool = False
    terminal: bool = False
    transform: dict[str, float] = field(default_factory=dict)
    role: str = "idle"
    current_target: str | None = None
    last_command_id: str | None = None
    last_frame_id: str | None = None
    character_dna: dict[str, Any] | None = None
    character_renderer_manifest: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "actor_id": self.actor_id,
            "actor_kind": self.actor_kind,
            "sector_id": self.sector_id,
            "spawned": self.spawned,
            "terminal": self.terminal,
            "transform": dict(self.transform),
            "role": self.role,
            "current_target": self.current_target,
            "last_command_id": self.last_command_id,
            "last_frame_id": self.last_frame_id,
            "character_dna": json.loads(canonical_json(self.character_dna)) if self.character_dna else None,
            "character_renderer_manifest": json.loads(canonical_json(self.character_renderer_manifest)) if self.character_renderer_manifest else None,
        }


class LivePresentationScheduler:
    """Stateful scheduler which processes each Ledger event exactly once."""

    def __init__(
        self,
        descent_id: str,
        *,
        presentation_seed: str,
        focus_actor_ids: Iterable[str] = (),
        seconds_per_tick: float = 0.45,
        camera_config: LiveCameraConfig | None = None,
        population_seed: str | None = None,
        population_species: dict[str, str] | None = None,
        population_variants: dict[str, str] | None = None,
    ) -> None:
        if seconds_per_tick <= 0:
            raise ValueError("seconds_per_tick must be positive")
        self.descent_id = descent_id
        self.presentation_seed = presentation_seed
        self.focus_actor_ids = set(focus_actor_ids)
        self.seconds_per_tick = float(seconds_per_tick)
        self.actors: dict[str, LiveActorState] = {}
        self.processed_event_ids: set[str] = set()
        self.terminal_actor_ids: set[str] = set()
        self.frame_sequence = 0
        self.presentation_seconds = 0.0
        self.latest_processed_key: tuple[int, str] | None = None
        self.bootstrap_count = 0
        self.command_stream: list[dict[str, Any]] = []
        self.ignored_duplicate_event_count = 0
        self.suppressed_terminal_command_count = 0
        self.generated_command_count = 0
        self.scheduling_times_ms: list[float] = []
        self.presentation_latencies_ticks: list[int] = []
        self.camera_config = camera_config or LiveCameraConfig()
        self.population_seed = population_seed
        self.population_species = dict(population_species or {})
        self.population_variants = dict(population_variants or {})
        self.population_generator = (
            DescenderPopulationGenerator(population_seed) if population_seed else None
        )
        self.camera_director: LiveCameraDirector | None = None
        self.pending_focus_transitions: list[dict[str, Any]] = []
        self.applied_focus_transition_count = 0
        self.maximum_transient_history = 4096
        self.character_generator = CharacterDNAGenerator("underreach-live-descenders-29a1")
        self.character_factory = CharacterFactory()

    def _turn_actors(
        self,
        values: list[tuple[LiveActorState, float, str, dict[str, float]]],
        commands: list[dict[str, Any]],
        *,
        source_event_id: str,
    ) -> None:
        """Emit parallel presentation-only turns, then advance by the longest."""
        plans = []
        for state, desired_yaw, mode, movement in values:
            if state.actor_id in self.terminal_actor_ids or state.terminal:
                continue
            plan = plan_turn(float(state.transform.get("yaw", 0.0)), desired_yaw, mode=mode)
            if plan["turn_action"] == "aligned":
                state.transform["yaw"] = plan["desired_yaw"]
                continue
            commands.append(self._command("turn_actor", state.actor_id, {
                **plan,
                "movement_vector": dict(movement),
                "source_event_id": source_event_id,
                "semantic_intent": "humanoid.facing." + mode,
            }))
            state.transform["yaw"] = plan["desired_yaw"]
            plans.append(plan)
        if plans:
            self.presentation_seconds += max(float(item["duration_seconds"]) for item in plans)

    @staticmethod
    def _character_species(actor_id: str) -> str:
        """Stable proof assignment: even Descenders are Human, odd are Dwarf."""
        try:
            ordinal = int(actor_id.rsplit("_", 1)[-1])
        except (TypeError, ValueError):
            ordinal = int.from_bytes(sha256(actor_id.encode("utf-8")).digest()[:2], "big")
        return "human" if ordinal % 2 == 0 else "dwarf"

    def _attach_character_identity(self, state: LiveActorState) -> None:
        if state.actor_kind != "descender" or state.character_dna is not None:
            return
        if self.population_generator is not None:
            entry = self.population_generator.generate_entry(
                state.actor_id,
                species=self.population_species.get(state.actor_id),
                detail_tier="focused" if state.actor_id in self.focus_actor_ids else "background",
                visual_variant=self.population_variants.get(state.actor_id),
            )
            state.character_dna = entry.dna.model_dump(mode="json")
            state.character_renderer_manifest = {
                **entry.renderer_manifest.model_dump(mode="json"),
                "visual_identity_digest": entry.visual_identity_digest,
                "style_profile": entry.style_profile,
                "detail_tier": entry.detail_tier,
                "loadout_authority": entry.loadout_authority,
            }
            return
        if state.actor_id not in PROCEDURAL_DESCENDER_IDS:
            return
        species = self._character_species(state.actor_id)
        dna = self.character_generator.generate(state.actor_id, species)
        manifest = self.character_factory.map(dna)
        state.character_dna = dna.model_dump(mode="json")
        state.character_renderer_manifest = manifest.model_dump(mode="json")

    def queue_focus_transition(self, transition: dict[str, Any]) -> bool:
        """Queue one presentation-only focus transition for the next frame."""
        required = {"transition_id", "to_descender_id", "mode", "reason"}
        if not required.issubset(transition):
            raise ValueError("incomplete Feed focus transition")
        transition_id = str(transition["transition_id"])
        if any(item["transition_id"] == transition_id for item in self.pending_focus_transitions):
            return False
        self.pending_focus_transitions.append(json.loads(canonical_json(transition)))
        return True

    @staticmethod
    def _kind(actor_id: str) -> str:
        return "enemy" if actor_id.startswith("enemy_") else "descender"

    def _lane_y(self, actor_id: str) -> float:
        """Give concurrently presented Descenders distinct readable lanes."""
        descenders = sorted(item for item in self.focus_actor_ids if self._kind(item) == "descender")
        if len(descenders) <= 1 or actor_id not in descenders:
            return 0.0
        index = descenders.index(actor_id)
        if len(descenders) > 4:
            # Population proof: a compact 5x2 formation remains inside the
            # accepted room and lets a wide establishing shot show everyone.
            column = index % 5
            return (column - 2.0) * 175.0
        return (index - (len(descenders) - 1) / 2.0) * 300.0

    def _pose(self, actor_id: str) -> dict[str, float]:
        digest = sha256(f"{self.presentation_seed}:{actor_id}".encode()).digest()
        side = -1.0 if self._kind(actor_id) == "descender" else 1.0
        x = side * (260.0 + digest[0] % 100)
        if self._kind(actor_id) == "descender" and len(self.focus_actor_ids) > 4:
            descenders = sorted(item for item in self.focus_actor_ids if self._kind(item) == "descender")
            row = descenders.index(actor_id) // 5 if actor_id in descenders else 0
            x = -430.0 + row * 280.0
        return {
            "x": x,
            "y": self._lane_y(actor_id) if self._kind(actor_id) == "descender" else float((digest[1] % 401) - 200),
            "z": 94.0,
            "yaw": 0.0 if side < 0 else 180.0,
        }

    def _ensure_actor(self, actor_id: str, sector_id: str | None, commands: list[dict[str, Any]]) -> LiveActorState:
        state = self.actors.get(actor_id)
        if state is None:
            state = LiveActorState(
                actor_id=actor_id,
                actor_kind=self._kind(actor_id),
                sector_id=sector_id,
                transform=self._pose(actor_id),
            )
            self.actors[actor_id] = state
        self._attach_character_identity(state)
        if not state.spawned:
            state.spawned = True
            commands.append(self._command("spawn_actor", actor_id, {"actor": state.as_dict()}))
        return state

    def _command(self, kind: str, actor_id: str | None, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            "type": kind,
            "actor_id": actor_id,
            "presentation_seconds": round(self.presentation_seconds, 6),
            **payload,
        }
        return {"command_id": f"cmd_{payload_digest(body)[:20]}", **body}

    def bootstrap(self, crawl: Crawl, *, environment: dict[str, Any]) -> dict[str, Any]:
        if self.bootstrap_count:
            raise RuntimeError("live presentation bootstrap may only be emitted once per scheduler")
        self.bootstrap_count = 1
        self.camera_director = LiveCameraDirector(
            self.descent_id,
            presentation_seed=f"{self.presentation_seed}:camera",
            environment=environment,
            config=self.camera_config,
        )
        actors = []
        selected = self.focus_actor_ids or set(crawl.participants)
        for actor_id in sorted(selected):
            participant = crawl.participants.get(actor_id)
            if participant is None:
                continue
            state = LiveActorState(
                actor_id=actor_id,
                actor_kind="descender",
                sector_id=participant.current_location_id,
                spawned=True,
                terminal=participant.status.value in {"dead", "eliminated"},
                transform=self._pose(actor_id),
            )
            self.actors[actor_id] = state
            self._attach_character_identity(state)
            if state.terminal:
                self.terminal_actor_ids.add(actor_id)
            actors.append(state.as_dict())
        body = {
            "protocol": LIVE_PROTOCOL,
            "authoritative": False,
            "message_type": "bootstrap",
            "descent_id": self.descent_id,
            "scheduler_version": SCHEDULER_VERSION,
            "simulation_tick": crawl.current_tick,
            "presentation": {"tick": 0, "seconds": 0.0},
            "stratum_number": crawl.current_floor,
            "sector_id": next((a["sector_id"] for a in actors if a["sector_id"]), None),
            "environment": json.loads(canonical_json(environment)),
            "actors": actors,
            "resume_cursor": {"frame_sequence": 0, "ledger_event_id": None},
        }
        return {**body, "digest": payload_digest(body)}

    def _is_relevant(self, event: CrawlEvent) -> bool:
        if not self.focus_actor_ids:
            return True
        if self.focus_actor_ids.intersection(event.actor_ids):
            return True
        return any(actor_id in self.actors for actor_id in event.actor_ids) and event.event_type in TERMINAL_EVENT_TYPES

    def schedule(
        self,
        events: Iterable[CrawlEvent],
        *,
        authoritative_tick: int,
        camera_lookahead_events: Iterable[CrawlEvent] = (),
    ) -> dict[str, Any] | None:
        started = perf_counter()
        ordered = sorted(events, key=_event_key)
        new_events: list[CrawlEvent] = []
        for event in ordered:
            if event.id in self.processed_event_ids:
                self.ignored_duplicate_event_count += 1
                continue
            key = _event_key(event)
            if self.latest_processed_key is not None and key < self.latest_processed_key:
                raise ValueError("scheduler cannot rewind the authoritative Ledger cursor")
            self.processed_event_ids.add(event.id)
            self.latest_processed_key = key
            new_events.append(event)
        camera_has_pending_focus = bool(
            self.camera_director is not None
            and self.camera_director.pending_focus_transition is not None
        )
        if not new_events and not self.pending_focus_transitions and not camera_has_pending_focus:
            return None

        from_seconds = self.presentation_seconds
        commands: list[dict[str, Any]] = []
        focus_transition = self.pending_focus_transitions.pop(0) if self.pending_focus_transitions else None
        if focus_transition:
            focus_transition = dict(focus_transition)
            # Feed controls arrive on simulation ticks. Stamp their actual
            # presentation request time here so camera acquisition latency is
            # measured from the live scheduler cursor rather than from zero.
            focus_transition["presentation_seconds"] = round(from_seconds, 6)
            commands.append(self._command("focus_change", None, {
                "transition_id": focus_transition["transition_id"],
                "viewer_id": focus_transition.get("viewer_id"),
                "focus_mode": focus_transition["mode"],
                "focus_reason": focus_transition["reason"],
                "from_channel": focus_transition.get("from_channel"),
                "to_channel": focus_transition.get("to_channel"),
                "to_descender_id": focus_transition["to_descender_id"],
                "request_id": focus_transition.get("request_id"),
            }))
            self.applied_focus_transition_count += 1
        tick_seen: set[tuple[int, str]] = set()
        for event in new_events:
            if not self._is_relevant(event):
                continue
            actor_ids = list(event.actor_ids)
            primary = actor_ids[0] if actor_ids else None
            target = actor_ids[1] if len(actor_ids) > 1 else primary
            if (
                event.event_type in ({"COMBAT_HIT"} | TERMINAL_EVENT_TYPES)
                and target
                and self._kind(target) == "enemy"
                and target not in self.actors
                and any(state.actor_kind == "enemy" for state in self.actors.values())
            ):
                # A focused live channel follows one readable encounter at a
                # time. The full Ledger cursor still advances; unrelated later
                # enemies are not piled into the same presentation room.
                continue
            if event.event_type in TERMINAL_EVENT_TYPES and target:
                state = self._ensure_actor(target, event.location_id, commands)
                if not state.terminal:
                    state.terminal = True
                    state.role = "terminal"
                    self.terminal_actor_ids.add(target)
                    commands.append(self._command("play_terminal", target, {
                        "asset_slot": "enemy.biped.reaction.defeat" if state.actor_kind == "enemy" else "humanoid.reaction.death",
                        "source_event_id": event.id,
                        "duration_seconds": 1.1,
                        "force_root_lock": True,
                    }))
                    commands.append(self._command("hold_terminal_pose", target, {
                        "source_event_id": event.id,
                        "starts_after_seconds": 1.1,
                    }))
            elif event.event_type == "COMBAT_HIT" and primary and target:
                if primary in self.terminal_actor_ids or target in self.terminal_actor_ids:
                    self.suppressed_terminal_command_count += 1
                    continue
                # One readable combat exchange per actor/tick; every Ledger event
                # is still consumed and represented in the frame's source cursor.
                marker = (event.tick, primary)
                if marker in tick_seen:
                    continue
                tick_seen.add(marker)
                attacker = self._ensure_actor(primary, event.location_id, commands)
                victim = self._ensure_actor(target, event.location_id, commands)
                attacker_kind = "crawler" if attacker.actor_kind == "descender" else "enemy"
                victim_kind = "crawler" if victim.actor_kind == "descender" else "enemy"
                attack_slot = choose_attack_slot(
                    event.id,
                    event.event_type,
                    VALIDATED_ATTACK_SLOTS,
                    event.data,
                    attacker_kind,
                    performer_id=primary,
                    target_id=target,
                    presentation_seed=self.presentation_seed,
                )
                reaction_slot = choose_reaction_slot(
                    victim_kind, event.data, attack_slot, VALIDATED_REACTION_SLOTS
                )
                humanoid_slot = attack_slot.replace("enemy.biped", "humanoid", 1)
                attack_duration, contact_phase, forward_reach, lateral_reach, effector = ATTACK_PRESENTATION[humanoid_slot]
                # Manny's authored attack-forward axis is local +Y; the
                # measured profile's -90 degree root offset maps it onto +X.
                lane_actor = primary if attacker.actor_kind == "descender" else target
                lane_y = self._lane_y(lane_actor)
                procedural_species = (
                    attacker.character_renderer_manifest or {}
                ).get("species")
                if procedural_species in PROCEDURAL_ATTACK_PRESENTATION:
                    procedural_profile = PROCEDURAL_ATTACK_PRESENTATION[procedural_species]
                    attack_duration = procedural_profile["duration_seconds"]
                    contact_phase = procedural_profile["contact_phase"]
                    forward_reach = procedural_profile["forward_reach_cm"]
                    lateral_reach = procedural_profile["lateral_reach_cm"]
                    effector = procedural_profile["contact_effector"]
                    target_surface_offset = procedural_profile["target_surface_offset_cm"]
                    minimum_visual_root_separation = procedural_profile["minimum_visual_root_separation_cm"]
                    self._turn_actors([
                        (attacker, -90.0, "align_to_target", {"x": 1.0, "y": 0.0}),
                        (victim, 90.0, "align_to_target", {"x": -1.0, "y": 0.0}),
                    ], commands, source_event_id=event.id)
                    victim.transform.update({"x": 60.0, "y": lane_y})
                    attacker.transform.update({
                        "x": 60.0 - forward_reach - target_surface_offset,
                        "y": lane_y + lateral_reach,
                    })
                else:
                    target_surface_offset = 0.0
                    minimum_visual_root_separation = 0.0
                    self._turn_actors([
                        (attacker, -90.0, "align_to_target", {"x": 1.0, "y": 0.0}),
                        (victim, 90.0, "align_to_target", {"x": -1.0, "y": 0.0}),
                    ], commands, source_event_id=event.id)
                    victim.transform.update({"x": 60.0, "y": lane_y})
                # At yaw -90, Manny's measured local +X lateral component maps
                # onto world -Y. Offset the root by the opposite amount so the
                # selected hand/foot reaches the victim's torso rather than
                # merely placing both actor roots on one lane.
                    attacker.transform.update({
                        "x": 60.0 - forward_reach,
                        "y": lane_y + lateral_reach,
                    })
                commands.append(self._command("move_actor", primary, {
                    "transform": dict(attacker.transform), "duration_seconds": 0.2,
                    "source_event_id": event.id,
                }))
                commands.append(self._command("move_actor", target, {
                    "transform": dict(victim.transform), "duration_seconds": 0.2,
                    "source_event_id": event.id,
                }))
                commands.append(self._command("play_attack", primary, {
                    "asset_slot": attack_slot, "target_actor_id": target,
                    "source_event_id": event.id, "duration_seconds": attack_duration,
                    "contact_phase": contact_phase, "contact_effector": effector,
                    "expected_root_separation_cm": forward_reach + target_surface_offset,
                    "measured_effector_reach_cm": forward_reach,
                    "target_surface_offset_cm": target_surface_offset,
                    "minimum_visual_root_separation_cm": minimum_visual_root_separation,
                    "expected_lateral_reach_cm": lateral_reach,
                    "procedural_species": procedural_species,
                    "desired_yaw": float(attacker.transform["yaw"]),
                    "facing_mode": "align_to_target",
                    "force_root_lock": True,
                }))
                commands.append(self._command("play_reaction", target, {
                    "asset_slot": reaction_slot, "source_event_id": event.id,
                    "delay_seconds": round(attack_duration * contact_phase + (1.0 / 60.0), 6),
                    "duration_seconds": 0.8,
                }))
                attacker.role, attacker.current_target = "attack", target
                victim.role, victim.current_target = "reaction", primary
                self.presentation_seconds += attack_duration + 0.4
            elif event.event_type == "CRAWLER_MOVED" and primary and primary not in self.terminal_actor_ids:
                marker = (event.tick, primary)
                if marker in tick_seen:
                    continue
                tick_seen.add(marker)
                state = self._ensure_actor(primary, event.location_id, commands)
                lane_y = self._lane_y(primary)
                destination_y = lane_y + (70.0 if event.tick % 2 else -70.0)
                movement_x = 0.0
                movement_y = destination_y - float(state.transform["y"])
                distance = math.hypot(movement_x, movement_y)
                desired_yaw = desired_facing_for_movement(
                    movement_x, movement_y, current_yaw=float(state.transform.get("yaw", 0.0))
                )
                self._turn_actors([
                    (state, desired_yaw, "align_to_movement", {"x": movement_x, "y": movement_y})
                ], commands, source_event_id=event.id)
                state.transform["y"] = destination_y
                commands.append(self._command("move_actor", primary, {
                    "transform": dict(state.transform), "duration_seconds": 0.7,
                    "source_event_id": event.id,
                }))
                commands.append(self._command("play_locomotion", primary, {
                    "asset_slot": "locomotion.humanoid.standard",
                    "source_event_id": event.id, "duration_seconds": 0.7,
                    "world_speed_cm_s": round(distance / 0.7, 3),
                    "desired_yaw": desired_yaw,
                    "movement_vector": {"x": movement_x, "y": movement_y},
                    "facing_mode": "align_to_movement",
                }))
                state.role = "locomotion"
                self.presentation_seconds += 0.72

        if self.presentation_seconds == from_seconds:
            self.presentation_seconds += self.seconds_per_tick
        if self.camera_director is None:
            raise RuntimeError("live camera director was not initialized by bootstrap")
        camera_commands = self.camera_director.direct(
            frame_sequence=self.frame_sequence + 1,
            current_events=new_events,
            lookahead_events=list(camera_lookahead_events),
            commands=commands,
            actor_states=self.actors,
            from_seconds=from_seconds,
            to_seconds=self.presentation_seconds,
            authoritative_tick=authoritative_tick,
            focus_transition=focus_transition,
        )
        commands.extend(camera_commands)
        self.frame_sequence += 1
        body = {
            "protocol": LIVE_PROTOCOL,
            "authoritative": False,
            "message_type": "incremental_frame",
            "descent_id": self.descent_id,
            "scheduler_version": SCHEDULER_VERSION,
            "frame_sequence": self.frame_sequence,
            "source": {
                "from_tick": min((event.tick for event in new_events), default=authoritative_tick),
                "to_tick": max((event.tick for event in new_events), default=authoritative_tick),
                "ledger_event_ids": [event.id for event in new_events],
            },
            "presentation": {
                "from_seconds": round(from_seconds, 6),
                "to_seconds": round(self.presentation_seconds, 6),
            },
            "commands": commands,
            "terminal_actor_ids": sorted(self.terminal_actor_ids),
            "camera_state": self.camera_director.snapshot(),
            "focus_transition": focus_transition,
        }
        body["frame_id"] = f"frame_{payload_digest(body)[:20]}"
        frame = {**body, "digest": payload_digest(body)}
        for command in commands:
            state = self.actors.get(command.get("actor_id"))
            if state:
                state.last_command_id = command["command_id"]
                state.last_frame_id = frame["frame_id"]
        self.command_stream.extend(json.loads(canonical_json(commands)))
        if len(self.command_stream) > self.maximum_transient_history:
            del self.command_stream[:-self.maximum_transient_history]
        if len(self.processed_event_ids) > self.maximum_transient_history:
            # Runtime delivery never replays an event older than the persisted
            # Ledger cursor.  Keep a bounded recent duplicate window while the
            # canonical SQLite Ledger retains complete history.
            recent_ids = [event.id for event in new_events]
            keep = set(recent_ids[-self.maximum_transient_history :])
            if len(keep) < self.maximum_transient_history:
                keep.update(sorted(self.processed_event_ids)[-self.maximum_transient_history + len(keep) :])
            self.processed_event_ids = keep
        self.scheduling_times_ms = self.scheduling_times_ms[-self.maximum_transient_history :]
        self.presentation_latencies_ticks = self.presentation_latencies_ticks[-self.maximum_transient_history :]
        self.generated_command_count += len(commands)
        self.scheduling_times_ms.append((perf_counter() - started) * 1000.0)
        self.presentation_latencies_ticks.append(max(0, authoritative_tick - frame["source"]["to_tick"]))
        return frame

    def reconnect_snapshot(self, crawl: Crawl, *, environment_digest: str) -> dict[str, Any]:
        body = {
            "protocol": LIVE_PROTOCOL,
            "authoritative": False,
            "message_type": "resume_snapshot",
            "descent_id": self.descent_id,
            "simulation_tick": crawl.current_tick,
            "presentation_seconds": round(self.presentation_seconds, 6),
            "resume_cursor": {
                "frame_sequence": self.frame_sequence,
                "ledger_event_id": self.latest_processed_key[1] if self.latest_processed_key else None,
            },
            "environment_digest": environment_digest,
            "actors": [self.actors[key].as_dict() for key in sorted(self.actors)],
            "terminal_actor_ids": sorted(self.terminal_actor_ids),
            "camera_state": self.camera_director.snapshot() if self.camera_director else None,
            "pending_focus_transitions": json.loads(canonical_json(self.pending_focus_transitions)),
        }
        return {**body, "digest": payload_digest(body)}

    def restore_reconnect_snapshot(self, snapshot: dict[str, Any], crawl: Crawl) -> None:
        """Restore non-authoritative presenter state after a canonical resume."""
        body = {key: value for key, value in snapshot.items() if key != "digest"}
        if snapshot.get("digest") != payload_digest(body):
            raise ValueError("invalid presentation reconnect digest")
        if snapshot.get("protocol") != LIVE_PROTOCOL or snapshot.get("descent_id") != self.descent_id:
            raise ValueError("presentation snapshot belongs to another Descent")
        self.frame_sequence = int(snapshot.get("resume_cursor", {}).get("frame_sequence", 0))
        self.presentation_seconds = float(snapshot.get("presentation_seconds", 0.0))
        self.actors = {
            item["actor_id"]: LiveActorState(**item)
            for item in snapshot.get("actors", [])
        }
        self.terminal_actor_ids = set(snapshot.get("terminal_actor_ids", []))
        self.pending_focus_transitions = json.loads(canonical_json(snapshot.get("pending_focus_transitions", [])))
        cursor_id = snapshot.get("resume_cursor", {}).get("ledger_event_id")
        if cursor_id:
            try:
                index = crawl.history_event_ids.index(cursor_id)
                self.latest_processed_key = (crawl.current_tick, crawl.history_event_ids[index])
            except ValueError:
                self.latest_processed_key = None
        if self.camera_director is None:
            raise RuntimeError("presentation bootstrap must initialize camera before restore")
        if snapshot.get("camera_state"):
            self.camera_director.restore(snapshot["camera_state"])

    def diagnostics(self) -> dict[str, Any]:
        kinds: dict[str, int] = {}
        for command in self.command_stream:
            kinds[command["type"]] = kinds.get(command["type"], 0) + 1
        times = self.scheduling_times_ms or [0.0]
        latency = self.presentation_latencies_ticks or [0]
        body = {
            "protocol": LIVE_PROTOCOL,
            "scheduler_version": SCHEDULER_VERSION,
            "descent_id": self.descent_id,
            "processed_event_count": len(self.processed_event_ids),
            "ignored_duplicate_event_count": self.ignored_duplicate_event_count,
            "active_actor_count": len(self.actors),
            "terminal_actor_count": len(self.terminal_actor_ids),
            "terminal_actor_ids": sorted(self.terminal_actor_ids),
            "generated_command_count": self.generated_command_count,
            "applied_focus_transition_count": self.applied_focus_transition_count,
            "command_counts": kinds,
            "frame_count": self.frame_sequence,
            "presentation_seconds": round(self.presentation_seconds, 6),
            "average_scheduling_ms": sum(times) / len(times),
            "maximum_scheduling_ms": max(times),
            "average_presentation_latency_ticks": sum(latency) / len(latency),
            "maximum_presentation_latency_ticks": max(latency),
            "suppressed_terminal_command_count": self.suppressed_terminal_command_count,
            "actor_states": [self.actors[key].as_dict() for key in sorted(self.actors)],
            "command_stream_digest": payload_digest(self.command_stream),
            "camera": self.camera_director.diagnostics(self.presentation_seconds) if self.camera_director else None,
        }
        return {**body, "digest": payload_digest(body)}


class LivePresentationConsumer:
    """Transport-neutral idempotency/order gate mirrored by the Unreal client."""

    def __init__(self, descent_id: str) -> None:
        self.descent_id = descent_id
        self.bootstrap_count = 0
        self.environment_bootstrap_count = 0
        self.latest_frame_sequence = 0
        self.latest_frame_id: str | None = None
        self.applied_frame_ids: set[str] = set()
        self.applied_command_ids: set[str] = set()
        self.terminal_actor_ids: set[str] = set()
        self.duplicate_frames = 0
        self.rejected_frames = 0
        self.missing_ranges: list[dict[str, int]] = []
        self.reconnect_count = 0
        self.camera_state: dict[str, Any] | None = None

    @staticmethod
    def _verify(message: dict[str, Any]) -> None:
        if message.get("protocol") != LIVE_PROTOCOL:
            raise ValueError("unsupported live presentation protocol")
        supplied = message.get("digest")
        body = {key: value for key, value in message.items() if key != "digest"}
        if supplied != payload_digest(body):
            raise ValueError("live presentation message digest mismatch")

    def apply_bootstrap(self, message: dict[str, Any]) -> bool:
        self._verify(message)
        if message.get("descent_id") != self.descent_id:
            raise ValueError("bootstrap belongs to a different Descent")
        if self.bootstrap_count:
            return False
        self.bootstrap_count = 1
        if message.get("environment"):
            self.environment_bootstrap_count = 1
        for actor in message.get("actors", []):
            if actor.get("terminal"):
                self.terminal_actor_ids.add(actor["actor_id"])
        return True

    def apply_frame(self, frame: dict[str, Any]) -> list[dict[str, Any]]:
        self._verify(frame)
        if frame.get("descent_id") != self.descent_id:
            raise ValueError("frame belongs to a different Descent")
        frame_id = frame["frame_id"]
        sequence = int(frame["frame_sequence"])
        if frame_id in self.applied_frame_ids:
            self.duplicate_frames += 1
            return []
        if sequence <= self.latest_frame_sequence:
            self.rejected_frames += 1
            return []
        if sequence != self.latest_frame_sequence + 1:
            self.missing_ranges.append({"from": self.latest_frame_sequence + 1, "to": sequence - 1})
            self.rejected_frames += 1
            return []
        applied = []
        for command in frame.get("commands", []):
            command_id = command["command_id"]
            if command_id in self.applied_command_ids:
                continue
            actor_id = command.get("actor_id")
            if actor_id in self.terminal_actor_ids and command["type"] not in {"hold_terminal_pose"}:
                raise ValueError("terminal-state violation in incremental frame")
            if command["type"] == "play_terminal" and actor_id:
                self.terminal_actor_ids.add(actor_id)
            self.applied_command_ids.add(command_id)
            applied.append(command)
        self.applied_frame_ids.add(frame_id)
        self.latest_frame_sequence = sequence
        self.latest_frame_id = frame_id
        self.camera_state = json.loads(canonical_json(frame.get("camera_state"))) if frame.get("camera_state") else self.camera_state
        return applied

    def apply_resume_snapshot(self, message: dict[str, Any]) -> None:
        self._verify(message)
        if message.get("descent_id") != self.descent_id:
            raise ValueError("resume snapshot belongs to a different Descent")
        cursor = message["resume_cursor"]
        self.latest_frame_sequence = int(cursor["frame_sequence"])
        self.terminal_actor_ids = set(message.get("terminal_actor_ids", []))
        self.camera_state = json.loads(canonical_json(message.get("camera_state"))) if message.get("camera_state") else None
        self.reconnect_count += 1

    def status(self, *, simulation_tick: int, buffer_snapshot: dict[str, Any], presentation_seconds: float) -> dict[str, Any]:
        return {
            "protocol": LIVE_PROTOCOL,
            "authoritative": False,
            "descent_id": self.descent_id,
            "simulation_tick": simulation_tick,
            "latest_ledger_tick": buffer_snapshot["latest_authoritative_tick"],
            "latest_buffered_tick": buffer_snapshot["latest_authoritative_tick"],
            "presentation_tick": self.latest_frame_sequence,
            "presentation_seconds": round(presentation_seconds, 6),
            "buffer_depth": buffer_snapshot["buffer_depth"],
            "connected_presenter": self.bootstrap_count == 1,
            "last_frame_id": self.latest_frame_id,
            "bridge_protocol": LIVE_PROTOCOL,
            "status": "streaming" if self.bootstrap_count else "waiting_for_presenter",
        }
