"""Brain-driven unattended Underreach orchestration for Slice 30B.3.

30B.1 defined an advisory brain proposal contract and 30B.2 defined the
simulation-owned validation/execution membrane. 30B.3 wires those contracts
into the accepted 30A.5 unattended Descent loop without moving authority out
of the deterministic simulation.

The brain is consulted once per active Descender per simulation step. A valid
proposal is executed only through 30B.2. Provider errors, rejected proposals,
and non-progressing navigation fall back to the accepted deterministic 30A.5
policy so an external/model-backed provider cannot deadlock canonical runtime.
Time, encounters, caches, loot, survival safety nets, Stratum progression,
completion, and extinction remain simulation-owned.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .crawl_domain import CrawlStatus, ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .runtime_checkpoint import payload_digest
from .underreach_ai_brain_foundation import (
    ALLOWED_ACTIONS,
    AIBrainFoundationService,
    BrainIntent,
)
from .underreach_brain_intent_execution import (
    BrainIntentExecutionResult,
    BrainIntentExecutionService,
)
from .underreach_domain import Descent
from .underreach_full_autonomous_descent import (
    METADATA_KEY as AUTONOMOUS_METADATA_KEY,
    SAFE_RECOVERY_STAMINA_THRESHOLD,
    FullAutonomousDescentError,
    FullAutonomousDescentService,
    _active_ids,
    _metadata as autonomous_metadata,
    _record_body as autonomous_record_body,
    build_full_autonomous_snapshot,
    validate_full_autonomous_descent,
)
from .underreach_resources_survival import validate_resources_survival


PROTOCOL = "underreach.brain-driven-descent.v1"
IMPLEMENTATION_VERSION = "30b3.1"
METADATA_KEY = "_brain_driven_descent"
BRAIN_CADENCE_STEPS = 1
NAVIGATION_ACTIONS = {"explore", "seek_cache", "seek_exit", "seek_safety"}


class BrainDrivenDescentError(ValueError):
    """Raised when brain-driven orchestration would violate canonical authority."""


@dataclass(frozen=True)
class BrainDrivenRunResult:
    outcome: str
    steps_executed: int
    current_tick: int
    current_stratum_number: int
    surviving_descenders: int
    eliminated_descenders: int
    completed: bool
    extinguished: bool
    step_limit_reached: bool
    brain_proposals: int
    brain_executions: int
    fallback_invocations: int


def _metadata(descent: Descent) -> dict[str, Any]:
    value = descent.modifiers.get(METADATA_KEY)
    if not isinstance(value, dict):
        raise BrainDrivenDescentError("Descent is missing 30B.3 brain-driven metadata")
    if value.get("protocol") != PROTOCOL or value.get("implementation_version") != IMPLEMENTATION_VERSION:
        raise BrainDrivenDescentError("brain-driven Descent protocol or version mismatch")
    if value.get("authoritative") is not True:
        raise BrainDrivenDescentError("brain-driven orchestration must remain simulation authoritative")
    if value.get("brain_provider_can_mutate") is not False:
        raise BrainDrivenDescentError("brain provider cannot own canonical mutation")
    if value.get("presentation_feedback_allowed") is not False:
        raise BrainDrivenDescentError("presentation feedback cannot steer brain-driven truth")
    if not isinstance(value.get("step_records"), list):
        raise BrainDrivenDescentError("brain-driven step trace is invalid")
    return value


def _canonical_state_digest(descent: Descent) -> str:
    return payload_digest(descent.model_dump(mode="json"))


def _record_body(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"digest", "ledger_event_id"}}


def _provider_id(service: AIBrainFoundationService) -> str:
    return str(getattr(service.provider, "provider_id", "unknown-provider"))


def _normalized_autonomous_action(action: str) -> str:
    if action == "seek_cache":
        return "explore"
    if action == "consume_supply":
        return "wait"
    if action in {"explore", "seek_exit", "seek_safety", "recover", "wait"}:
        return action
    return "wait"


def validate_brain_driven_descent(descent: Descent) -> bool:
    """Validate 30B.3 trace while preserving every accepted 30A.5 invariant."""
    validate_full_autonomous_descent(descent)
    metadata = _metadata(descent)
    source = autonomous_metadata(descent)

    if metadata.get("extends_slice") != "30B.2":
        raise BrainDrivenDescentError("30B.3 source-slice boundary changed")
    if metadata.get("execution_membrane") != "underreach.brain-intent-execution.v1":
        raise BrainDrivenDescentError("30B.3 execution membrane changed")
    if int(metadata.get("brain_cadence_steps", 0)) != BRAIN_CADENCE_STEPS:
        raise BrainDrivenDescentError("30B.3 brain cadence changed")
    if int(metadata.get("step_count", -1)) != len(metadata["step_records"]):
        raise BrainDrivenDescentError("brain-driven step count diverged from trace")
    if metadata.get("run_outcome") != source.get("run_outcome"):
        raise BrainDrivenDescentError("brain-driven outcome diverged from accepted autonomous source state")

    history_ids = set(descent.history_event_ids)
    previous_index = -1
    previous_tick = -1
    for record in metadata["step_records"]:
        if not isinstance(record, dict):
            raise BrainDrivenDescentError("brain-driven step record is invalid")
        index = int(record.get("step_index", -1))
        if index != previous_index + 1:
            raise BrainDrivenDescentError("brain-driven step indices are not contiguous")
        tick = int(record.get("tick", -1))
        if tick < previous_tick:
            raise BrainDrivenDescentError("brain-driven step tick moved backwards")
        if record.get("digest") != payload_digest(_record_body(record)):
            raise BrainDrivenDescentError("brain-driven step digest mismatch")
        if record.get("ledger_event_id") not in history_ids:
            raise BrainDrivenDescentError("brain-driven step is not Ledger bound")
        if record.get("autonomous_step_event_id") not in history_ids:
            raise BrainDrivenDescentError("brain-driven step lost accepted 30A.5 step binding")
        decisions = record.get("decisions")
        if not isinstance(decisions, list):
            raise BrainDrivenDescentError("brain-driven decision trace is invalid")
        seen: set[str] = set()
        for item in decisions:
            if not isinstance(item, dict):
                raise BrainDrivenDescentError("brain-driven decision item is invalid")
            descender_id = str(item.get("descender_id", ""))
            if not descender_id or descender_id in seen:
                raise BrainDrivenDescentError("brain-driven step contains duplicate/invalid Descender decision")
            seen.add(descender_id)
            brain_action = item.get("brain_action")
            if brain_action is not None and brain_action not in ALLOWED_ACTIONS:
                raise BrainDrivenDescentError("brain-driven trace escaped the accepted brain action vocabulary")
            if item.get("outcome") not in {"executed", "provider_error", "rejected"}:
                raise BrainDrivenDescentError("brain-driven decision outcome is invalid")
            if item.get("fallback_used") not in {True, False}:
                raise BrainDrivenDescentError("brain-driven fallback flag is invalid")
        previous_index = index
        previous_tick = tick

    metrics = metadata.get("metrics")
    if not isinstance(metrics, dict):
        raise BrainDrivenDescentError("brain-driven metrics are invalid")
    required_metrics = {
        "brain_proposals",
        "brain_executions",
        "brain_rejections",
        "provider_errors",
        "brain_moves",
        "brain_nonprogress_navigation",
        "fallback_invocations",
        "fallback_moves",
    }
    if not required_metrics.issubset(metrics):
        raise BrainDrivenDescentError("brain-driven metrics are incomplete")
    for key in required_metrics:
        if int(metrics[key]) < 0:
            raise BrainDrivenDescentError(f"brain-driven metric {key} cannot be negative")

    outcome = metadata.get("run_outcome")
    if outcome not in {"planned", "running", "completed", "extinguished"}:
        raise BrainDrivenDescentError("brain-driven run outcome is invalid")
    if outcome == "planned" and descent.status != CrawlStatus.PLANNED:
        raise BrainDrivenDescentError("planned brain-driven outcome disagrees with canonical Descent")
    if outcome == "running" and descent.status != CrawlStatus.RUNNING:
        raise BrainDrivenDescentError("running brain-driven outcome disagrees with canonical Descent")
    if outcome == "completed" and descent.status != CrawlStatus.COMPLETED:
        raise BrainDrivenDescentError("completed brain-driven outcome disagrees with canonical Descent")
    if outcome == "extinguished" and descent.status != CrawlStatus.RUNNING:
        raise BrainDrivenDescentError("extinguished brain-driven outcome must preserve valid source status")

    for event_key in ("initialized_event_id", "started_event_id", "terminal_event_id"):
        value = metadata.get(event_key)
        if value is not None and value not in history_ids:
            raise BrainDrivenDescentError("brain-driven lifecycle event is missing from the Ledger")
    return True


def build_brain_driven_snapshot(descent: Descent) -> dict[str, Any]:
    validate_brain_driven_descent(descent)
    metadata = _metadata(descent)
    records = [dict(record) for record in metadata["step_records"]]
    body = {
        "protocol": PROTOCOL,
        "implementation_version": IMPLEMENTATION_VERSION,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "brain_provider_can_mutate": False,
        "presentation_feedback_allowed": False,
        "descent_id": descent.id,
        "seed": descent.seed,
        "status": descent.status.value,
        "run_outcome": metadata["run_outcome"],
        "provider_id": metadata["provider_id"],
        "brain_cadence_steps": metadata["brain_cadence_steps"],
        "current_tick": descent.current_tick,
        "current_stratum_index": descent.current_floor - 1,
        "configured_stratum_count": len(descent.floors),
        "step_count": metadata["step_count"],
        "step_records": records,
        "step_trace_digest": payload_digest(records),
        "metrics": dict(sorted(metadata["metrics"].items())),
        "source_autonomous_snapshot_digest": build_full_autonomous_snapshot(descent)["digest"],
        "surviving_descender_count": descent.surviving_crawler_count,
        "eliminated_descender_count": descent.eliminated_crawler_count,
        "history_event_ids_digest": payload_digest(list(descent.history_event_ids)),
        "canonical_descent_fingerprint": descent.fingerprint(),
    }
    return {**body, "digest": payload_digest(body)}


class BrainDrivenDescentService:
    """Simulation-owned unattended runner that consults the accepted brain contract."""

    def __init__(
        self,
        persistence: CrawlPersistence | None = None,
        *,
        brain: AIBrainFoundationService | None = None,
    ) -> None:
        self.autonomous = FullAutonomousDescentService(persistence)
        self.survival = self.autonomous.survival
        self.lifecycle = self.autonomous.lifecycle
        self.brain = brain or AIBrainFoundationService()
        self.executor = BrainIntentExecutionService(brain=self.brain, survival=self.survival)

    def create(
        self,
        *,
        seed: str,
        descender_ids: Iterable[str],
        stratum_count: int = 4,
        descent_id: str | None = None,
    ) -> Descent:
        descent = self.autonomous.create(
            seed=seed,
            descender_ids=descender_ids,
            stratum_count=stratum_count,
            descent_id=descent_id,
        )
        metadata = {
            "protocol": PROTOCOL,
            "implementation_version": IMPLEMENTATION_VERSION,
            "authoritative": True,
            "canonical_owner": "deterministic_simulation",
            "brain_provider_can_mutate": False,
            "presentation_feedback_allowed": False,
            "extends_slice": "30B.2",
            "execution_membrane": "underreach.brain-intent-execution.v1",
            "provider_id": _provider_id(self.brain),
            "brain_cadence_steps": BRAIN_CADENCE_STEPS,
            "deterministic_fallback": "accepted-30a5-policy-v1",
            "run_outcome": "planned",
            "step_count": 0,
            "step_records": [],
            "metrics": {
                "brain_proposals": 0,
                "brain_executions": 0,
                "brain_rejections": 0,
                "provider_errors": 0,
                "brain_moves": 0,
                "brain_nonprogress_navigation": 0,
                "fallback_invocations": 0,
                "fallback_moves": 0,
            },
            "initialized_event_id": None,
            "started_event_id": None,
            "terminal_event_id": None,
        }
        descent.modifiers[METADATA_KEY] = metadata
        event = self.lifecycle.record_event(
            descent,
            "BRAIN_DRIVEN_DESCENT_INITIALIZED",
            "Brain-driven deterministic Descent orchestration initialized.",
            data={
                "protocol": PROTOCOL,
                "provider_id": metadata["provider_id"],
                "execution_membrane": metadata["execution_membrane"],
                "state_changes": {"brain_driven_run_outcome": "planned"},
            },
        )
        metadata["initialized_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_brain_driven_descent(descent)
        return descent

    def start(self, descent: Descent, *, tick: int = 0) -> Descent:
        validate_brain_driven_descent(descent)
        metadata = _metadata(descent)
        if metadata["run_outcome"] != "planned":
            raise BrainDrivenDescentError("only a planned brain-driven Descent can start")
        if metadata["provider_id"] != _provider_id(self.brain):
            raise BrainDrivenDescentError("configured brain provider differs from persisted 30B.3 provider identity")
        self.autonomous.start(descent, tick=tick)
        metadata["run_outcome"] = "running"
        event = self.lifecycle.record_event(
            descent,
            "BRAIN_DRIVEN_DESCENT_STARTED",
            "Brain-driven unattended Descent execution started.",
            actor_ids=_active_ids(descent),
            data={
                "provider_id": metadata["provider_id"],
                "brain_cadence_steps": BRAIN_CADENCE_STEPS,
                "state_changes": {"brain_driven_run_outcome": "running"},
            },
        )
        metadata["started_event_id"] = event.id
        self.lifecycle.save(descent)
        validate_brain_driven_descent(descent)
        return descent

    def _invoke_fallback(
        self,
        descent: Descent,
        descender_id: str,
        *,
        reason: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        metadata = _metadata(descent)
        metadata["metrics"]["fallback_invocations"] += 1
        origin = descent.participants[descender_id].current_location_id
        action = self.autonomous._choose_and_move(descent, descender_id)
        destination = descent.participants[descender_id].current_location_id
        if destination != origin:
            metadata["metrics"]["fallback_moves"] += 1
        detail = {
            "descender_id": descender_id,
            "provider_id": metadata["provider_id"],
            "proposal_id": None,
            "brain_action": None,
            "outcome": "rejected" if reason.startswith("rejected:") else "provider_error",
            "reason_code": reason,
            "execution_event_id": None,
            "fallback_used": True,
            "fallback_action": action.get("action"),
            "origin_sector_id": origin,
            "resolved_sector_id": destination,
        }
        action = {
            **action,
            "brain_action": None,
            "brain_fallback_reason": reason,
            "brain_fallback_used": True,
        }
        return action, detail

    def _brain_action(self, descent: Descent, descender_id: str) -> tuple[dict[str, Any], dict[str, Any], int, set[str]]:
        """Propose/execute one brain action, with deterministic 30A.5 liveness fallback."""
        metadata = _metadata(descent)
        metrics = metadata["metrics"]
        before_digest = _canonical_state_digest(descent)
        before_fingerprint = descent.fingerprint()
        before_history = tuple(descent.history_event_ids)
        intent: BrainIntent | None = None

        try:
            intent = self.brain.propose(descent, descender_id)
        except Exception as exc:  # provider adapters may raise arbitrary runtime errors
            if (
                _canonical_state_digest(descent) != before_digest
                or descent.fingerprint() != before_fingerprint
                or tuple(descent.history_event_ids) != before_history
            ):
                raise BrainDrivenDescentError(
                    "brain provider errored after mutating canonical state; fallback refused"
                ) from exc
            metrics["provider_errors"] += 1
            action, detail = self._invoke_fallback(
                descent,
                descender_id,
                reason=f"provider_error:{type(exc).__name__}",
            )
            return action, detail, 0, set()

        metrics["brain_proposals"] += 1
        execute_before_digest = _canonical_state_digest(descent)
        execute_before_fingerprint = descent.fingerprint()
        execute_before_history = tuple(descent.history_event_ids)
        try:
            result = self.executor.execute(descent, intent)
        except Exception as exc:
            if (
                _canonical_state_digest(descent) != execute_before_digest
                or descent.fingerprint() != execute_before_fingerprint
                or tuple(descent.history_event_ids) != execute_before_history
            ):
                raise BrainDrivenDescentError(
                    "brain execution failed after partial canonical mutation; fallback refused"
                ) from exc
            metrics["brain_rejections"] += 1
            action, detail = self._invoke_fallback(
                descent,
                descender_id,
                reason=f"rejected:execution_error:{type(exc).__name__}",
            )
            detail["proposal_id"] = intent.proposal_id
            detail["brain_action"] = intent.action
            return action, detail, 0, set()

        if not result.executed:
            metrics["brain_rejections"] += 1
            action, detail = self._invoke_fallback(
                descent,
                descender_id,
                reason=f"rejected:{result.reason_code}",
            )
            detail["proposal_id"] = intent.proposal_id
            detail["brain_action"] = intent.action
            return action, detail, 0, set()

        metrics["brain_executions"] += 1
        origin = result.origin_sector_id
        resolved = result.resolved_sector_id
        moved = intent.action in NAVIGATION_ACTIONS and resolved is not None and resolved != origin
        if moved:
            metrics["brain_moves"] += 1
            autonomous_metadata(descent)["metrics"]["moves"] += 1
        elif intent.action in NAVIGATION_ACTIONS:
            metrics["brain_nonprogress_navigation"] += 1

        supply_consumptions = 0
        recovered_ids: set[str] = set()
        if intent.action == "consume_supply":
            autonomous_metadata(descent)["metrics"]["supply_consumptions"] += 1
            supply_consumptions = 1
        elif intent.action == "recover":
            autonomous_metadata(descent)["metrics"]["safe_recoveries"] += 1
            recovered_ids.add(descender_id)
        elif intent.action == "wait":
            autonomous_metadata(descent)["metrics"]["waits"] += 1

        detail = {
            "descender_id": descender_id,
            "provider_id": intent.provider_id,
            "proposal_id": intent.proposal_id,
            "brain_action": intent.action,
            "outcome": "executed",
            "reason_code": result.reason_code,
            "execution_event_id": result.execution_event_id,
            "fallback_used": False,
            "fallback_action": None,
            "origin_sector_id": origin,
            "resolved_sector_id": resolved,
        }

        # A valid navigation proposal can still be a canonical no-op because the
        # crawler lacks a known route. Invoke the accepted policy in that case;
        # this is where deterministic hidden-path discovery remains available.
        wait_outside_exit = False
        if intent.action == "wait":
            participant = descent.participants[descender_id]
            floor = descent.floors[descent.current_floor]
            wait_outside_exit = participant.current_location_id not in floor.exit_location_ids
        if (intent.action in NAVIGATION_ACTIONS and not moved) or wait_outside_exit:
            metrics["fallback_invocations"] += 1
            fallback_origin = descent.participants[descender_id].current_location_id
            fallback = self.autonomous._choose_and_move(descent, descender_id)
            fallback_destination = descent.participants[descender_id].current_location_id
            if fallback_destination != fallback_origin:
                metrics["fallback_moves"] += 1
            detail["fallback_used"] = True
            detail["fallback_action"] = fallback.get("action")
            detail["reason_code"] = "executed_then_no_progress_fallback"
            action = {
                **fallback,
                "brain_action": intent.action,
                "brain_proposal_id": intent.proposal_id,
                "brain_execution_event_id": result.execution_event_id,
                "brain_fallback_used": True,
            }
            return action, detail, supply_consumptions, recovered_ids

        edge_cost = 0.0
        if moved and origin is not None and resolved is not None:
            floor = descent.floors[descent.current_floor]
            edge_cost = round(float(floor.locations[origin].adjacency[resolved]), 6)
        action = {
            "descender_id": descender_id,
            "action": _normalized_autonomous_action(intent.action),
            "origin_sector_id": origin,
            "destination_sector_id": resolved,
            "edge_cost": edge_cost,
            "brain_action": intent.action,
            "brain_proposal_id": intent.proposal_id,
            "brain_execution_event_id": result.execution_event_id,
            "brain_fallback_used": False,
        }
        return action, detail, supply_consumptions, recovered_ids

    def _mark_terminal(self, descent: Descent, outcome: str) -> None:
        metadata = _metadata(descent)
        metadata["run_outcome"] = outcome
        if outcome == "completed":
            event_type = "BRAIN_DRIVEN_DESCENT_COMPLETED"
            summary = "Brain-driven unattended execution completed the final Stratum."
        else:
            event_type = "BRAIN_DRIVEN_DESCENT_EXTINGUISHED"
            summary = "Brain-driven unattended execution ended with no active Descenders."
        event = self.lifecycle.record_event(
            descent,
            event_type,
            summary,
            actor_ids=_active_ids(descent),
            data={"state_changes": {"brain_driven_run_outcome": outcome}},
        )
        metadata["terminal_event_id"] = event.id

    def step(self, descent: Descent) -> dict[str, Any]:
        validate_brain_driven_descent(descent)
        metadata = _metadata(descent)
        source = autonomous_metadata(descent)
        if metadata["provider_id"] != _provider_id(self.brain):
            raise BrainDrivenDescentError("runtime brain provider differs from persisted provider identity")
        if metadata["run_outcome"] != "running" or source["run_outcome"] != "running":
            raise BrainDrivenDescentError("brain-driven step requires a running Descent")
        if descent.status != CrawlStatus.RUNNING:
            raise BrainDrivenDescentError("brain-driven step requires canonical running status")

        if not _active_ids(descent):
            source["run_outcome"] = "extinguished"
            source_terminal = self.lifecycle.record_event(
                descent,
                "FULL_AUTONOMOUS_DESCENT_EXTINGUISHED",
                "No active Descenders remain; autonomous execution terminated.",
                data={"state_changes": {"autonomous_run_outcome": "extinguished"}},
            )
            source["terminal_event_id"] = source_terminal.id
            self._mark_terminal(descent, "extinguished")
            self.lifecycle.save(descent)
            validate_brain_driven_descent(descent)
            return {"outcome": "extinguished", "step_index": metadata["step_count"]}

        step_index = int(source["step_count"])
        if step_index != int(metadata["step_count"]):
            raise BrainDrivenDescentError("30A.5 and 30B.3 step counters diverged")
        stratum_before = descent.current_floor
        source["stratum_step_counts"][str(stratum_before)] = int(
            source["stratum_step_counts"].get(str(stratum_before), 0)
        ) + 1

        # 30A.4 remains the sole canonical resource clock owner.
        self.survival.advance_time(descent, descent.current_tick + 1)

        actions: list[dict[str, Any]] = []
        decisions: list[dict[str, Any]] = []
        brain_supply_consumptions = 0
        recovered_by_brain: set[str] = set()
        for descender_id in list(_active_ids(descent)):
            participant = descent.participants[descender_id]
            if participant.status != ParticipationStatus.ACTIVE:
                continue
            action, detail, consumed_count, recovered_ids = self._brain_action(descent, descender_id)
            actions.append(action)
            decisions.append(detail)
            brain_supply_consumptions += consumed_count
            recovered_by_brain.update(recovered_ids)

        # All non-decision consequences remain the accepted deterministic stack.
        encounters = self.autonomous._resolve_occupied_encounters(descent)
        opened_caches = self.autonomous._open_reached_caches(descent)
        loot_claims, supply_claims, consumed_during_collection = self.autonomous._collect_ground_items(descent)

        safety_consumed: list[str] = []
        for descender_id in list(_active_ids(descent)):
            safety_consumed.extend(self.autonomous._consume_needed_supply(descent, descender_id))
            participant = descent.participants[descender_id]
            if (
                descender_id not in recovered_by_brain
                and participant.current_location_id in descent.floors[descent.current_floor].safe_area_ids
                and participant.gameplay.stamina <= SAFE_RECOVERY_STAMINA_THRESHOLD
            ):
                self.survival.recover_at_safe_area(descent, descender_id)
                source["metrics"]["safe_recoveries"] += 1

        advanced = False
        completed = False
        if not _active_ids(descent):
            source["run_outcome"] = "extinguished"
            terminal = self.lifecycle.record_event(
                descent,
                "FULL_AUTONOMOUS_DESCENT_EXTINGUISHED",
                "All Descenders were eliminated during brain-driven execution.",
                data={"state_changes": {"autonomous_run_outcome": "extinguished"}},
            )
            source["terminal_event_id"] = terminal.id
            self._mark_terminal(descent, "extinguished")
        else:
            floor = descent.floors[descent.current_floor]
            if all(
                descent.participants[descender_id].current_location_id in floor.exit_location_ids
                for descender_id in _active_ids(descent)
            ):
                if descent.current_floor == max(descent.floors):
                    self.survival.complete(descent, advance_ticks=0)
                    source["run_outcome"] = "completed"
                    completed = True
                    terminal = self.lifecycle.record_event(
                        descent,
                        "FULL_AUTONOMOUS_DESCENT_COMPLETED",
                        "Brain-driven execution completed the final Stratum.",
                        actor_ids=sorted(
                            descender_id
                            for descender_id, participant in descent.participants.items()
                            if participant.status == ParticipationStatus.ADVANCED
                        ),
                        data={"state_changes": {"autonomous_run_outcome": "completed"}},
                    )
                    source["terminal_event_id"] = terminal.id
                    self._mark_terminal(descent, "completed")
                else:
                    self.survival.advance(descent, advance_ticks=0)
                    source["metrics"]["strata_advanced"] += 1
                    advanced = True

        source_record = {
            "step_index": step_index,
            "tick": descent.current_tick,
            "stratum_before": stratum_before,
            "stratum_after": descent.current_floor,
            "actions": sorted(actions, key=lambda value: value["descender_id"]),
            "encounter_ids": sorted(encounters),
            "opened_cache_ids": sorted(opened_caches),
            "loot_claim_count": loot_claims,
            "supply_claim_count": supply_claims,
            "supply_consumption_count": (
                brain_supply_consumptions + len(consumed_during_collection) + len(safety_consumed)
            ),
            "advanced": advanced,
            "completed": completed,
            "run_outcome": source["run_outcome"],
            "surviving_descender_count": descent.surviving_crawler_count,
            "eliminated_descender_count": descent.eliminated_crawler_count,
        }
        source_record["digest"] = payload_digest(autonomous_record_body(source_record))
        source_event = self.lifecycle.record_event(
            descent,
            "AUTONOMOUS_STEP_RESOLVED",
            f"Autonomous Descent step {step_index} resolved deterministically.",
            actor_ids=_active_ids(descent),
            data={
                "step_index": step_index,
                "step_digest": source_record["digest"],
                "stratum_before": stratum_before,
                "stratum_after": descent.current_floor,
                "run_outcome": source["run_outcome"],
            },
        )
        source_record["ledger_event_id"] = source_event.id
        source["step_records"].append(source_record)
        source["step_count"] = step_index + 1

        metadata["run_outcome"] = source["run_outcome"]
        brain_record = {
            "step_index": step_index,
            "tick": descent.current_tick,
            "stratum_before": stratum_before,
            "stratum_after": descent.current_floor,
            "provider_id": metadata["provider_id"],
            "decisions": sorted(decisions, key=lambda value: value["descender_id"]),
            "autonomous_step_event_id": source_event.id,
            "advanced": advanced,
            "completed": completed,
            "run_outcome": metadata["run_outcome"],
        }
        brain_record["digest"] = payload_digest(_record_body(brain_record))
        brain_event = self.lifecycle.record_event(
            descent,
            "BRAIN_DRIVEN_STEP_RESOLVED",
            f"Brain-driven Descent step {step_index} resolved through deterministic authority.",
            actor_ids=_active_ids(descent),
            data={
                "protocol": PROTOCOL,
                "step_index": step_index,
                "step_digest": brain_record["digest"],
                "autonomous_step_event_id": source_event.id,
                "run_outcome": metadata["run_outcome"],
            },
        )
        brain_record["ledger_event_id"] = brain_event.id
        metadata["step_records"].append(brain_record)
        metadata["step_count"] = step_index + 1

        self.lifecycle.save(descent)
        validate_brain_driven_descent(descent)
        return brain_record

    def run(
        self,
        descent: Descent,
        *,
        max_steps: int = 2_000,
        start_if_planned: bool = True,
    ) -> BrainDrivenRunResult:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        validate_brain_driven_descent(descent)
        metadata = _metadata(descent)
        if metadata["provider_id"] != _provider_id(self.brain):
            raise BrainDrivenDescentError("runtime brain provider differs from persisted provider identity")
        if metadata["run_outcome"] == "planned":
            if not start_if_planned:
                raise BrainDrivenDescentError("planned brain-driven Descent requires start_if_planned")
            self.start(descent, tick=descent.current_tick)

        executed = 0
        while executed < max_steps and _metadata(descent)["run_outcome"] == "running":
            self.step(descent)
            executed += 1

        metadata = _metadata(descent)
        metrics = metadata["metrics"]
        outcome = str(metadata["run_outcome"])
        return BrainDrivenRunResult(
            outcome=outcome,
            steps_executed=executed,
            current_tick=descent.current_tick,
            current_stratum_number=descent.current_floor,
            surviving_descenders=descent.surviving_crawler_count,
            eliminated_descenders=descent.eliminated_crawler_count,
            completed=outcome == "completed",
            extinguished=outcome == "extinguished",
            step_limit_reached=executed >= max_steps and outcome == "running",
            brain_proposals=int(metrics["brain_proposals"]),
            brain_executions=int(metrics["brain_executions"]),
            fallback_invocations=int(metrics["fallback_invocations"]),
        )

    def snapshot(self, descent: Descent) -> dict[str, Any]:
        return build_brain_driven_snapshot(descent)
