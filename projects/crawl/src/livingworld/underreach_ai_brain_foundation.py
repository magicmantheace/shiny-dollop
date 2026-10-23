"""Read-only AI brain proposal foundation for Underreach Slice 30B.1.

The deterministic simulation remains authoritative. A brain may inspect a
bounded observation and propose an intent, but it may not mutate canonical
Descent state. Proposal execution is intentionally out of scope for 30B.1.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .crawl_domain import CrawlStatus, ParticipationStatus
from .runtime_checkpoint import payload_digest
from .underreach_domain import Descent
from .underreach_full_autonomous_descent import METADATA_KEY as AUTONOMOUS_METADATA_KEY
from .underreach_resources_survival import METADATA_KEY as SURVIVAL_METADATA_KEY
from .underreach_resources_survival import validate_resources_survival


PROTOCOL = "underreach.ai-brain-foundation.v1"
IMPLEMENTATION_VERSION = "30b1.1"
OBSERVATION_PROTOCOL = "underreach.ai-brain-observation.v1"
INTENT_PROTOCOL = "underreach.ai-brain-intent.v1"
ALLOWED_ACTIONS = (
    "consume_supply",
    "explore",
    "recover",
    "seek_cache",
    "seek_exit",
    "seek_safety",
    "wait",
)


class AIBrainFoundationError(ValueError):
    """Raised when a brain proposal violates the 30B.1 authority contract."""


class BrainObservation(BaseModel):
    """Immutable, epistemically bounded input exposed to a brain provider."""

    model_config = ConfigDict(frozen=True)

    protocol: str = OBSERVATION_PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    descent_id: str
    descender_id: str
    tick: int = Field(ge=0)
    stratum_number: int = Field(ge=1)
    descent_status: str
    current_sector_id: str
    current_sector_kind: str
    health: float = Field(ge=0.0, le=1.0)
    stamina: float = Field(ge=0.0, le=1.0)
    hydration: float = Field(ge=0.0, le=1.0)
    nutrition: float = Field(ge=0.0, le=1.0)
    survival_risk_band: str
    at_exit: bool
    at_safe_area: bool
    known_neighbor_sector_ids: tuple[str, ...]
    known_safe_sector_ids: tuple[str, ...]
    known_exit_sector_ids: tuple[str, ...]
    inventory_item_ids: tuple[str, ...]
    owned_supply_item_ids: tuple[str, ...]
    owned_supply_kinds: tuple[str, ...]
    current_cache_status: str | None
    current_cache_sector_known: bool
    autonomous_steps_in_stratum: int = Field(ge=0)
    observation_digest: str


class BrainIntent(BaseModel):
    """A proposal only. This model has no method capable of changing Descent state."""

    model_config = ConfigDict(frozen=True)

    protocol: str = INTENT_PROTOCOL
    implementation_version: str = IMPLEMENTATION_VERSION
    provider_id: str
    proposal_id: str
    descender_id: str
    observation_digest: str
    action: str
    target_sector_id: str | None = None
    target_item_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_action_shape(self) -> "BrainIntent":
        if self.action not in ALLOWED_ACTIONS:
            raise ValueError("brain intent action is outside the bounded 30B.1 vocabulary")
        if self.action == "consume_supply" and not self.target_item_id:
            raise ValueError("consume_supply requires target_item_id")
        if self.action != "consume_supply" and self.target_item_id is not None:
            raise ValueError("only consume_supply may target an item in 30B.1")
        if self.action in {"recover", "wait", "consume_supply"} and self.target_sector_id is not None:
            raise ValueError("non-navigation intent cannot target a Sector")
        return self


class BrainProvider(Protocol):
    """Pluggable proposal source. Implementations receive observation only."""

    provider_id: str

    def propose(self, observation: BrainObservation) -> BrainIntent:
        ...


def _stable_id(prefix: str, *parts: object) -> str:
    body = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(body.encode('utf-8')).hexdigest()[:20]}"


def _canonical_state_digest(descent: Descent) -> str:
    return payload_digest(descent.model_dump(mode="json"))


def _current_cache(descent: Descent) -> dict[str, Any] | None:
    loot = descent.modifiers.get("_loot_cache_relic")
    if not isinstance(loot, dict):
        return None
    candidates = [
        cache
        for cache in loot.get("caches", [])
        if int(cache.get("stratum_number", 0)) == descent.current_floor
    ]
    return min(candidates, key=lambda value: value.get("cache_id", "")) if candidates else None


def _supply_kind_map(descent: Descent) -> dict[str, str]:
    survival = descent.modifiers.get(SURVIVAL_METADATA_KEY)
    if not isinstance(survival, dict):
        return {}
    result: dict[str, str] = {}
    for cache in survival.get("supply_caches", []):
        for blueprint in cache.get("blueprints", []):
            item_id = blueprint.get("id")
            kind = blueprint.get("resource_kind")
            if isinstance(item_id, str) and isinstance(kind, str):
                result[item_id] = kind
    return result


def build_brain_observation(descent: Descent, descender_id: str) -> BrainObservation:
    """Build a deterministic observation without exposing hidden world truth."""
    validate_resources_survival(descent)
    if descent.status != CrawlStatus.RUNNING:
        raise AIBrainFoundationError("brain observation requires a running Descent")
    participant = descent.participants.get(descender_id)
    if participant is None:
        raise KeyError(f"Descender {descender_id!r} is not participating")
    if participant.status != ParticipationStatus.ACTIVE or participant.current_floor != descent.current_floor:
        raise AIBrainFoundationError("brain observation requires an active current-Stratum Descender")
    if participant.current_location_id is None or participant.agent is None:
        raise AIBrainFoundationError("brain observation requires canonical location and agent state")

    floor = descent.floors[descent.current_floor]
    current = floor.locations[participant.current_location_id]
    knowledge = participant.agent.knowledge
    current_knowledge = knowledge.get(current.id)
    known_neighbors = tuple(sorted(current_knowledge.known_neighbors)) if current_knowledge is not None else ()
    known_safe = tuple(
        sorted(
            item.location_id
            for item in knowledge.values()
            if item.location_id in floor.locations and item.believed_safe
        )
    )
    known_exits = tuple(
        sorted(
            item.location_id
            for item in knowledge.values()
            if item.location_id in floor.locations and item.believed_exit
        )
    )

    survival = descent.modifiers[SURVIVAL_METADATA_KEY]["descenders"][descender_id]
    inventory = tuple(sorted(participant.gameplay.inventory_item_ids))
    supply_kinds = _supply_kind_map(descent)
    owned_supply_ids = tuple(sorted(item_id for item_id in inventory if item_id in supply_kinds))
    # Parallel to owned_supply_item_ids so a provider can reason about each item
    # without receiving the mutable canonical CrawlItem object.
    owned_supply_kinds = tuple(supply_kinds[item_id] for item_id in owned_supply_ids)
    cache = _current_cache(descent)
    cache_status = str(cache.get("status")) if cache is not None else None
    cache_sector_known = bool(
        cache is not None
        and isinstance(cache.get("sector_id"), str)
        and cache["sector_id"] in knowledge
    )
    autonomous = descent.modifiers.get(AUTONOMOUS_METADATA_KEY, {})
    stratum_steps = 0
    if isinstance(autonomous, dict):
        stratum_steps = int((autonomous.get("stratum_step_counts") or {}).get(str(descent.current_floor), 0))

    body = {
        "protocol": OBSERVATION_PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "descent_id": descent.id,
        "descender_id": descender_id,
        "tick": descent.current_tick,
        "stratum_number": descent.current_floor,
        "descent_status": descent.status.value,
        "current_sector_id": current.id,
        "current_sector_kind": current.kind.value,
        "health": round(float(participant.health), 6),
        "stamina": round(float(participant.gameplay.stamina), 6),
        "hydration": round(float(survival["hydration"]), 6),
        "nutrition": round(float(survival["nutrition"]), 6),
        "survival_risk_band": str(survival["risk_band"]),
        "at_exit": current.id in floor.exit_location_ids,
        "at_safe_area": current.id in floor.safe_area_ids,
        "known_neighbor_sector_ids": known_neighbors,
        "known_safe_sector_ids": known_safe,
        "known_exit_sector_ids": known_exits,
        "inventory_item_ids": inventory,
        "owned_supply_item_ids": owned_supply_ids,
        "owned_supply_kinds": owned_supply_kinds,
        "current_cache_status": cache_status,
        "current_cache_sector_known": cache_sector_known,
        "autonomous_steps_in_stratum": stratum_steps,
    }
    return BrainObservation(**body, observation_digest=payload_digest(body))


def validate_brain_intent(intent: BrainIntent, observation: BrainObservation) -> bool:
    """Validate proposal shape against only what the brain was allowed to know."""
    if intent.protocol != INTENT_PROTOCOL or intent.implementation_version != IMPLEMENTATION_VERSION:
        raise AIBrainFoundationError("brain intent protocol or version mismatch")
    if observation.protocol != OBSERVATION_PROTOCOL or observation.implementation_version != IMPLEMENTATION_VERSION:
        raise AIBrainFoundationError("brain observation protocol or version mismatch")
    if intent.descender_id != observation.descender_id:
        raise AIBrainFoundationError("brain intent targets a different Descender")
    if intent.observation_digest != observation.observation_digest:
        raise AIBrainFoundationError("brain intent is not bound to the supplied observation")
    if intent.action not in ALLOWED_ACTIONS:
        raise AIBrainFoundationError("brain intent escaped bounded action vocabulary")
    if intent.target_sector_id is not None:
        allowed_targets = set(observation.known_neighbor_sector_ids)
        allowed_targets.update(observation.known_safe_sector_ids)
        allowed_targets.update(observation.known_exit_sector_ids)
        if intent.target_sector_id not in allowed_targets:
            raise AIBrainFoundationError("brain intent targets a Sector outside observed knowledge")
    if intent.action == "consume_supply" and intent.target_item_id not in observation.owned_supply_item_ids:
        raise AIBrainFoundationError("brain intent targets a supply item the Descender does not own")
    if intent.action == "recover" and not observation.at_safe_area:
        raise AIBrainFoundationError("recover intent requires an observed canonical safe area")
    if intent.action == "wait" and intent.target_sector_id is not None:
        raise AIBrainFoundationError("wait intent cannot move the Descender")
    return True


class DeterministicReferenceBrain:
    """Reference provider used to prove the proposal contract without an LLM."""

    provider_id = "deterministic-reference-v1"

    def propose(self, observation: BrainObservation) -> BrainIntent:
        action = "explore"
        target_item_id: str | None = None
        reasons: list[str] = []
        minimum_resource = min(observation.hydration, observation.nutrition)

        if observation.at_exit:
            action = "wait"
            reasons.append("exit_reached")
        elif minimum_resource <= 0.54 and observation.owned_supply_item_ids:
            desired_kind = "hydration" if observation.hydration <= observation.nutrition else "nutrition"
            supply_map = dict(zip(observation.owned_supply_item_ids, observation.owned_supply_kinds))
            matches = sorted(
                item_id
                for item_id in observation.owned_supply_item_ids
                if supply_map.get(item_id) == desired_kind
            )
            if not matches:
                matches = list(observation.owned_supply_item_ids)
            action = "consume_supply"
            target_item_id = matches[0]
            reasons.extend(("resource_pressure", desired_kind))
        elif observation.stamina <= 0.42 and observation.at_safe_area:
            action = "recover"
            reasons.append("low_stamina_safe_area")
        elif observation.survival_risk_band == "critical":
            action = "seek_exit"
            reasons.append("critical_survival_pressure")
        elif observation.current_cache_status == "sealed" and observation.autonomous_steps_in_stratum < 14:
            action = "seek_cache"
            reasons.append("bounded_cache_search")
        elif observation.known_exit_sector_ids:
            action = "seek_exit"
            reasons.append("known_exit")
        elif observation.stamina <= 0.42 and observation.known_safe_sector_ids:
            action = "seek_safety"
            reasons.append("known_safe_area")
        else:
            action = "explore"
            reasons.append("bounded_exploration")

        confidence = 0.9 if action in {"consume_supply", "recover", "wait"} else 0.72
        proposal_id = _stable_id(
            "brain_intent",
            self.provider_id,
            observation.observation_digest,
            action,
            target_item_id or "",
            "|".join(reasons),
        )
        return BrainIntent(
            provider_id=self.provider_id,
            proposal_id=proposal_id,
            descender_id=observation.descender_id,
            observation_digest=observation.observation_digest,
            action=action,
            target_item_id=target_item_id,
            confidence=confidence,
            reason_codes=tuple(reasons),
        )


class AIBrainFoundationService:
    """Read-only proposal gate over accepted canonical Descent state."""

    def __init__(self, provider: BrainProvider | None = None) -> None:
        self.provider: BrainProvider = provider or DeterministicReferenceBrain()

    def observe(self, descent: Descent, descender_id: str) -> BrainObservation:
        return build_brain_observation(descent, descender_id)

    def propose(self, descent: Descent, descender_id: str) -> BrainIntent:
        before_fingerprint = descent.fingerprint()
        before_state_digest = _canonical_state_digest(descent)
        before_history = tuple(descent.history_event_ids)
        observation = self.observe(descent, descender_id)
        intent = self.provider.propose(observation)

        # Check authority before even accepting the proposal shape. A provider
        # that somehow holds an out-of-band mutable reference cannot hide a
        # canonical mutation behind an otherwise-invalid response.
        if descent.fingerprint() != before_fingerprint:
            raise AIBrainFoundationError("brain provider mutated canonical Descent fingerprint")
        if _canonical_state_digest(descent) != before_state_digest:
            raise AIBrainFoundationError("brain provider mutated canonical Descent state")
        if tuple(descent.history_event_ids) != before_history:
            raise AIBrainFoundationError("brain provider appended canonical Ledger events")
        if intent.provider_id != self.provider.provider_id:
            raise AIBrainFoundationError("brain intent provider identity mismatch")
        validate_brain_intent(intent, observation)
        return intent

    def proposal_bundle(self, descent: Descent) -> dict[str, Any]:
        """Return deterministic proposals for every active current-Stratum Descender.

        The bundle is external advisory data. It is not written into the Descent.
        """
        before = _canonical_state_digest(descent)
        proposals: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
        for descender_id in sorted(descent.participants):
            participant = descent.participants[descender_id]
            if participant.status != ParticipationStatus.ACTIVE or participant.current_floor != descent.current_floor:
                continue
            observation = self.observe(descent, descender_id)
            intent = self.propose(descent, descender_id)
            observations.append(observation.model_dump(mode="json"))
            proposals.append(intent.model_dump(mode="json"))
        if _canonical_state_digest(descent) != before:
            raise AIBrainFoundationError("proposal bundle mutated canonical Descent state")
        body = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": False,
            "advisory_only": True,
            "simulation_execution_required": True,
            "descent_id": descent.id,
            "tick": descent.current_tick,
            "stratum_number": descent.current_floor,
            "provider_id": self.provider.provider_id,
            "observations": observations,
            "proposals": proposals,
            "canonical_state_digest": before,
        }
        return {**body, "digest": payload_digest(body)}
