from __future__ import annotations

import asyncio
import threading
from contextlib import suppress

from .ai import AIAdapter
from .config import Settings
from .continent_generation import generate_continent_world
from .domain import CommandEnvelope, CommandRecord, HistoricalEvent, WorldState
from .generation import generate_world
from .persistence import Persistence
from .validated_commands import ValidatedCommandGateway
from .world_engine import FinalWorldEngine


class LivingWorldRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.persistence = Persistence(settings.database_url)
        self.persistence.initialize()
        self._lock = threading.RLock()
        self._subscribers: set[asyncio.Queue[dict]] = set()
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._hour_accumulator = 0.0
        self._background_task: asyncio.Task | None = None

        world = self.persistence.load_world()
        if world is None:
            world = self._generate_default()
        self.engine = FinalWorldEngine(world, event_sink=self._event_sink)
        self.commands = ValidatedCommandGateway(self.engine, self.persistence, self._lock)
        self.ai = AIAdapter(settings)

        if not world.recent_events:
            subjects = [world.id]
            if world.continent:
                subjects.append(world.continent.id)
            else:
                subjects.append(world.region.id)
            self.engine.emit(
                "WORLD_GENERATED",
                f"{world.name} was generated from seed {world.seed} with {world.total_population:,} inhabitants.",
                subjects,
                data={
                    "seed": world.seed,
                    "population": world.total_population,
                    "settlements": len(world.settlements),
                    "regions": len(world.regions),
                },
                importance=1.0,
            )
            self.persistence.save_world(world)

    @property
    def world(self) -> WorldState:
        """Internal authoritative state. External readers should call snapshot()."""
        return self.engine.world

    def snapshot(self) -> WorldState:
        """Return a coherent deep copy while simulation mutation is paused briefly."""
        with self._lock:
            return self.world.model_copy(deep=True)

    def _install_world(self, world: WorldState) -> WorldState:
        self.engine = FinalWorldEngine(world, event_sink=self._event_sink)
        self.commands = ValidatedCommandGateway(self.engine, self.persistence, self._lock)
        self._hour_accumulator = 0.0
        return world

    def _generate_default(self) -> WorldState:
        world = generate_world(
            seed=self.settings.world_seed,
            name=self.settings.world_name,
            target_population=self.settings.target_population,
            persistent_npcs=self.settings.persistent_npcs,
            towns=self.settings.towns,
            villages=self.settings.villages,
        )
        self.persistence.save_world(world)
        return world

    def regenerate(self, seed: str | None = None, name: str | None = None) -> WorldState:
        with self._lock:
            world = generate_world(
                seed=seed or self.settings.world_seed,
                name=name or self.settings.world_name,
                target_population=self.settings.target_population,
                persistent_npcs=self.settings.persistent_npcs,
                towns=self.settings.towns,
                villages=self.settings.villages,
            )
            return self._replace_generated_world(world, source="admin")

    def regenerate_continent(self, seed: str | None = None, name: str | None = None) -> WorldState:
        with self._lock:
            world = generate_continent_world(
                seed=seed or self.settings.world_seed,
                name=name or self.settings.world_name,
            )
            return self._replace_generated_world(world, source="admin")

    def _replace_generated_world(self, world: WorldState, source: str) -> WorldState:
        self.persistence.reset_all()
        self._install_world(world)
        subjects = [world.id]
        if world.continent:
            subjects.append(world.continent.id)
        else:
            subjects.append(world.region.id)
        self.engine.emit(
            "WORLD_GENERATED",
            f"{world.name} was generated from seed {world.seed} with {world.total_population:,} inhabitants.",
            subjects,
            data={
                "seed": world.seed,
                "population": world.total_population,
                "settlements": len(world.settlements),
                "regions": len(world.regions),
                "kingdoms": len(world.kingdoms),
                "persistent_npcs": len(world.alive_npcs()),
            },
            source=source,
            importance=1.0,
        )
        self.persistence.save_world(world)
        return world.model_copy(deep=True)

    def restore_snapshot(self, snapshot_id: str) -> WorldState:
        with self._lock:
            prior_event_sequence = self.world.next_event_sequence
            prior_entity_sequence = self.world.next_entity_sequence
            prior_date = self.world.date.model_copy(deep=True)
            world = self.persistence.restore_snapshot(snapshot_id)
            world.next_event_sequence = max(world.next_event_sequence, prior_event_sequence)
            world.next_entity_sequence = max(world.next_entity_sequence, prior_entity_sequence)
            self._install_world(world)
            self.engine.emit(
                "SNAPSHOT_RESTORED",
                f"Snapshot {snapshot_id} was restored by an administrator.",
                [world.id],
                data={"prior_date": prior_date.model_dump(mode="json"), "restored_date": world.date.model_dump(mode="json")},
                source="admin",
                importance=0.7,
            )
            self.persistence.save_world(world)
            return world.model_copy(deep=True)

    def create_snapshot(self, snapshot_id: str, note: str = "") -> str:
        with self._lock:
            return self.persistence.create_snapshot(self.world, snapshot_id, note)

    def execute_command(self, command: CommandEnvelope) -> CommandRecord:
        with self._lock:
            return self.commands.execute(command)

    def _broadcast_event(self, payload: dict) -> None:
        for queue in tuple(self._subscribers):
            with suppress(asyncio.QueueFull):
                queue.put_nowait(payload)

    def _event_sink(self, event: HistoricalEvent) -> None:
        self.persistence.append_event(event)
        payload = event.model_dump(mode="json")
        loop = self._event_loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(self._broadcast_event, payload)

    def subscribe(self) -> asyncio.Queue[dict]:
        queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict]) -> None:
        self._subscribers.discard(queue)

    def tick_once(self) -> None:
        with self._lock:
            if self.world.paused or self.world.speed_multiplier <= 0:
                return
            self._hour_accumulator += self.settings.game_hours_per_tick * self.world.speed_multiplier
            hours = int(self._hour_accumulator)
            if hours <= 0:
                return
            self._hour_accumulator -= hours
            self.engine.advance_hours(hours)
            self.persistence.save_world(self.world)

    async def start_background_loop(self) -> None:
        self._event_loop = asyncio.get_running_loop()
        if self._background_task and not self._background_task.done():
            return
        self._background_task = asyncio.create_task(self._loop(), name="livingworld-simulation-loop")

    async def stop_background_loop(self) -> None:
        if not self._background_task:
            return
        self._background_task.cancel()
        with suppress(asyncio.CancelledError):
            await self._background_task
        self._background_task = None
        with self._lock:
            self.persistence.save_world(self.world)
        self._event_loop = None

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings.tick_seconds)
            await asyncio.to_thread(self.tick_once)

    def summary(self) -> dict:
        world = self.snapshot()
        payload = {
            "id": world.id,
            "name": world.name,
            "seed": world.seed,
            "date": world.date.model_dump(),
            "date_label": world.date.label(),
            "paused": world.paused,
            "speed_multiplier": world.speed_multiplier,
            "metrics": world.metrics,
            "region": {
                "id": world.region.id,
                "name": world.region.name,
                "climate": world.region.climate,
                "magic_intensity": world.region.magic_intensity,
            },
            "regions": len(world.regions),
            "ai_enabled": self.ai.enabled,
        }
        if world.continent:
            payload["continent"] = world.continent.model_dump(mode="json")
        return payload
