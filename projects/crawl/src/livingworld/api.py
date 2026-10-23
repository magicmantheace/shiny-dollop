from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .commands import parse_basic_command
from .config import Settings, get_settings
from .domain import CommandEnvelope, CommandStatus, Region
from .runtime import LivingWorldRuntime


class GenerateWorldRequest(BaseModel):
    seed: str | None = None
    name: str | None = None


class NaturalCommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    issuer: str = "admin-dashboard"
    allow_ai_fallback: bool = True


class SnapshotRequest(BaseModel):
    id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")
    note: str = Field(default="", max_length=1000)


class RestoreSnapshotRequest(BaseModel):
    id: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    runtime = LivingWorldRuntime(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await runtime.start_background_loop()
        try:
            yield
        finally:
            await runtime.stop_background_loop()

    app = FastAPI(
        title="LivingWorld API",
        version="0.2.1",
        description="Authoritative persistent medieval-fantasy continent simulation API",
        lifespan=lifespan,
    )
    app.state.runtime = runtime
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def admin_key(x_admin_key: Annotated[str | None, Header()] = None) -> None:
        if not settings.admin_key or x_admin_key != settings.admin_key:
            raise HTTPException(status_code=401, detail="invalid admin key")

    def region_payload(world, item: Region) -> dict[str, Any]:
        population = sum(
            world.settlements[sid].population
            for sid in item.settlement_ids
            if sid in world.settlements
        )
        return {
            **item.model_dump(mode="json"),
            "population": population,
            "settlement_count": len(item.settlement_ids),
            "kingdom_count": len(item.kingdom_ids),
        }

    @app.get("/health")
    def health() -> dict[str, Any]:
        world = runtime.snapshot()
        return {"status": "ok", "world_date": world.date.label(), "paused": world.paused}

    @app.get("/api/world")
    def world_summary() -> dict[str, Any]:
        return runtime.summary()

    @app.get("/api/world/state")
    def full_world_state() -> dict[str, Any]:
        return runtime.snapshot().model_dump(mode="json")

    @app.get("/api/continent")
    def continent() -> dict[str, Any]:
        world = runtime.snapshot()
        if not world.continent:
            raise HTTPException(status_code=404, detail="world does not contain a generated continent")
        return {
            **world.continent.model_dump(mode="json"),
            "population": world.total_population,
            "region_count": len(world.regions),
            "kingdom_count": len(world.kingdoms),
            "settlement_count": len(world.settlements),
            "persistent_npcs": len(world.alive_npcs()),
            "refugee_camp_count": sum(1 for camp in world.refugee_camps.values() if camp.status.value != "closed"),
            "refugee_camp_population": sum(camp.people for camp in world.refugee_camps.values() if camp.status.value != "closed"),
        }

    @app.get("/api/map")
    def world_map() -> dict[str, Any]:
        world = runtime.snapshot()
        bounds = world.continent.bounds if world.continent else world.region.bounds
        regions = [region_payload(world, item) for item in world.regions.values()]
        landmarks = [
            landmark.model_dump(mode="json")
            for item in world.regions.values()
            for landmark in item.landmarks
        ]
        return {
            "bounds": bounds,
            "continent": world.continent.model_dump(mode="json") if world.continent else None,
            "region": world.region.model_dump(mode="json", exclude={"settlement_ids", "kingdom_ids"}),
            "regions": regions,
            "kingdoms": [
                {
                    "id": k.id,
                    "name": k.name,
                    "capital_settlement_id": k.capital_settlement_id,
                    "dominant_ancestry": k.dominant_ancestry.value,
                    "stability": k.stability,
                    "border_policy": k.border_policy.value,
                    "refugee_policy": k.refugee_policy.value,
                    "settlement_ids": k.settlement_ids,
                }
                for k in world.kingdoms.values()
            ],
            "settlements": [
                {
                    "id": s.id,
                    "name": s.name,
                    "type": s.type.value,
                    "kingdom_id": s.kingdom_id,
                    "region_id": s.region_id,
                    "position": s.position.model_dump(),
                    "population": s.population,
                    "biome": s.biome,
                    "food_security": s.food_security,
                    "stability": s.stability,
                    "magic_intensity": s.magic_intensity,
                }
                for s in world.settlements.values()
            ],
            "trade_routes": [route.model_dump(mode="json") for route in world.trade_routes.values()],
            "armies": [army.model_dump(mode="json") for army in world.armies.values() if army.active],
            "landmarks": landmarks,
            "refugee_camps": [camp.model_dump(mode="json") for camp in world.refugee_camps.values() if camp.status.value != "closed"],
        }

    @app.get("/api/regions")
    def regions() -> list[dict[str, Any]]:
        world = runtime.snapshot()
        return [region_payload(world, item) for item in world.regions.values()]

    @app.get("/api/regions/{region_id}")
    def region(region_id: str) -> dict[str, Any]:
        world = runtime.snapshot()
        item = world.regions.get(region_id)
        if not item:
            raise HTTPException(status_code=404, detail="region not found")
        return region_payload(world, item)

    @app.get("/api/kingdoms")
    def kingdoms() -> list[dict[str, Any]]:
        world = runtime.snapshot()
        return [k.model_dump(mode="json") for k in world.kingdoms.values()]

    @app.get("/api/kingdoms/{kingdom_id}")
    def kingdom(kingdom_id: str) -> dict[str, Any]:
        world = runtime.snapshot()
        item = world.kingdoms.get(kingdom_id)
        if not item:
            raise HTTPException(status_code=404, detail="kingdom not found")
        population = sum(world.settlements[s].population for s in item.settlement_ids if s in world.settlements)
        ruler = world.npcs.get(item.ruler_npc_id or "")
        camps = [camp for camp in world.refugee_camps.values() if camp.host_kingdom_id == item.id and camp.status.value != "closed"]
        return {
            **item.model_dump(mode="json"),
            "population": population,
            "ruler": ruler.model_dump(mode="json") if ruler else None,
            "refugee_camps": len(camps),
            "camp_population": sum(camp.people for camp in camps),
        }

    @app.get("/api/kingdoms/{kingdom_id}/decision")
    def kingdom_decision(kingdom_id: str) -> dict[str, Any]:
        world = runtime.snapshot()
        item = world.kingdoms.get(kingdom_id)
        if not item:
            raise HTTPException(status_code=404, detail="kingdom not found")
        return {"kingdom_id": kingdom_id, "decision": item.last_decision.model_dump(mode="json") if item.last_decision else None}

    @app.get("/api/settlements")
    def settlements(
        kingdom_id: str | None = None,
        region_id: str | None = None,
        settlement_type: str | None = Query(default=None, alias="type"),
    ) -> list[dict[str, Any]]:
        world = runtime.snapshot()
        items = list(world.settlements.values())
        if kingdom_id:
            items = [s for s in items if s.kingdom_id == kingdom_id]
        if region_id:
            items = [s for s in items if s.region_id == region_id]
        if settlement_type:
            items = [s for s in items if s.type.value == settlement_type]
        return [s.model_dump(mode="json") for s in items]

    @app.get("/api/settlements/{settlement_id}")
    def settlement(settlement_id: str) -> dict[str, Any]:
        world = runtime.snapshot()
        item = world.settlements.get(settlement_id)
        if not item:
            raise HTTPException(status_code=404, detail="settlement not found")
        residents = [n for n in world.npcs.values() if n.settlement_id == settlement_id and n.alive]
        routes = [r for r in world.trade_routes.values() if settlement_id in {r.origin_settlement_id, r.destination_settlement_id}]
        camps = [camp for camp in world.refugee_camps.values() if camp.host_settlement_id == settlement_id and camp.status.value != "closed"]
        return {
            **item.model_dump(mode="json"),
            "persistent_residents": [n.id for n in residents],
            "trade_route_ids": [r.id for r in routes],
            "refugee_camp_ids": [camp.id for camp in camps],
            "refugee_camp_population": sum(camp.people for camp in camps),
        }

    @app.get("/api/npcs")
    def npcs(
        kingdom_id: str | None = None,
        settlement_id: str | None = None,
        alive: bool | None = None,
        search: str | None = None,
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        world = runtime.snapshot()
        items = list(world.npcs.values())
        if kingdom_id:
            items = [n for n in items if n.kingdom_id == kingdom_id]
        if settlement_id:
            items = [n for n in items if n.settlement_id == settlement_id]
        if alive is not None:
            items = [n for n in items if n.alive == alive]
        if search:
            needle = search.lower()
            items = [n for n in items if needle in n.name.lower() or needle in n.occupation.lower() or needle in (n.title or "").lower()]
        return [n.model_dump(mode="json") for n in items[:limit]]

    @app.get("/api/npcs/{npc_id}")
    def npc(npc_id: str) -> dict[str, Any]:
        world = runtime.snapshot()
        item = world.npcs.get(npc_id)
        if not item:
            raise HTTPException(status_code=404, detail="NPC not found")
        return item.model_dump(mode="json")

    @app.get("/api/trade-routes")
    def trade_routes() -> list[dict[str, Any]]:
        world = runtime.snapshot()
        return [r.model_dump(mode="json") for r in world.trade_routes.values()]

    @app.get("/api/armies")
    def armies() -> list[dict[str, Any]]:
        world = runtime.snapshot()
        return [a.model_dump(mode="json") for a in world.armies.values()]

    @app.get("/api/wars")
    def wars(active_only: bool = False) -> list[dict[str, Any]]:
        world = runtime.snapshot()
        items = world.active_wars() if active_only else list(world.wars.values())
        return [w.model_dump(mode="json") for w in items]

    @app.get("/api/migrations")
    def migrations(
        limit: int = Query(default=100, ge=1, le=500),
        refugees_only: bool = False,
    ) -> list[dict[str, Any]]:
        refugees = runtime.persistence.list_events(limit, "REFUGEE_MOVEMENT")
        if refugees_only:
            items = refugees
        else:
            items = refugees + runtime.persistence.list_events(limit, "MIGRATION")
        items.sort(key=lambda event: (event.occurred_at.ordinal_hour(), event.id), reverse=True)
        return [event.model_dump(mode="json") for event in items[:limit]]

    @app.get("/api/refugee-camps")
    def refugee_camps(
        host_kingdom_id: str | None = None,
        origin_kingdom_id: str | None = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        world = runtime.snapshot()
        items = list(world.refugee_camps.values())
        if host_kingdom_id:
            items = [camp for camp in items if camp.host_kingdom_id == host_kingdom_id]
        if origin_kingdom_id:
            items = [camp for camp in items if camp.origin_kingdom_id == origin_kingdom_id]
        if active_only:
            items = [camp for camp in items if camp.status.value != "closed"]
        return [camp.model_dump(mode="json") for camp in items]

    @app.get("/api/events")
    def events(
        limit: int = Query(default=100, ge=1, le=1000),
        event_type: str | None = None,
        before_world_hour: int | None = None,
    ) -> list[dict[str, Any]]:
        return [event.model_dump(mode="json") for event in runtime.persistence.list_events(limit, event_type, before_world_hour)]

    @app.get("/api/chronicle")
    def chronicle(limit: int = Query(default=500, ge=1, le=1000)) -> dict[str, Any]:
        history = list(reversed(runtime.persistence.list_events(limit)))
        years: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for event in history:
            if event.importance >= 0.3:
                years[event.occurred_at.year].append({
                    "id": event.id,
                    "date": event.occurred_at.model_dump(),
                    "type": event.type,
                    "summary": event.summary,
                    "source": event.source,
                    "importance": event.importance,
                })
        return {"world": runtime.snapshot().name, "years": dict(years)}

    @app.get("/api/commands", dependencies=[Depends(admin_key)])
    def command_audit(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
        return [record.model_dump(mode="json") for record in runtime.persistence.list_commands(limit)]

    @app.post("/api/commands", dependencies=[Depends(admin_key)])
    def execute_command(command: CommandEnvelope) -> dict[str, Any]:
        record = runtime.execute_command(command)
        status_code = 200 if record.status == CommandStatus.COMPLETED else 400
        if status_code != 200:
            raise HTTPException(status_code=status_code, detail=record.model_dump(mode="json"))
        return record.model_dump(mode="json")

    @app.post("/api/commands/natural", dependencies=[Depends(admin_key)])
    def execute_natural(request: NaturalCommandRequest) -> dict[str, Any]:
        command = parse_basic_command(request.text, issuer=request.issuer)
        parser = "deterministic"
        if command is None and request.allow_ai_fallback:
            if not runtime.ai.enabled:
                raise HTTPException(status_code=422, detail="command was not recognized by the offline parser and AI fallback is disabled")
            try:
                command = runtime.ai.parse_command(request.text, runtime.snapshot(), issuer=request.issuer)
                parser = "ai"
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"AI command parser failed: {exc}") from exc
        if command is None:
            raise HTTPException(status_code=422, detail="command not recognized")
        record = runtime.execute_command(command)
        if record.status != CommandStatus.COMPLETED:
            raise HTTPException(status_code=400, detail=record.model_dump(mode="json"))
        return {"parser": parser, "command": command.model_dump(mode="json"), "record": record.model_dump(mode="json")}

    @app.post("/api/admin/world/generate", dependencies=[Depends(admin_key)])
    def regenerate(request: GenerateWorldRequest) -> dict[str, Any]:
        runtime.regenerate(seed=request.seed, name=request.name)
        return runtime.summary()

    @app.post("/api/admin/world/generate-continent", dependencies=[Depends(admin_key)])
    def regenerate_continent(request: GenerateWorldRequest) -> dict[str, Any]:
        runtime.regenerate_continent(seed=request.seed, name=request.name)
        return runtime.summary()

    @app.post("/api/admin/snapshots", dependencies=[Depends(admin_key)])
    def create_snapshot(request: SnapshotRequest) -> dict[str, Any]:
        try:
            snapshot_id = runtime.create_snapshot(request.id, request.note)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"id": snapshot_id}

    @app.get("/api/admin/snapshots", dependencies=[Depends(admin_key)])
    def snapshots(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
        return runtime.persistence.list_snapshots(limit)

    @app.post("/api/admin/snapshots/restore", dependencies=[Depends(admin_key)])
    def restore_snapshot(request: RestoreSnapshotRequest) -> dict[str, Any]:
        try:
            runtime.restore_snapshot(request.id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return runtime.summary()

    @app.post("/api/ai/kingdoms/{kingdom_id}/advise", dependencies=[Depends(admin_key)])
    def advise_kingdom(kingdom_id: str) -> dict[str, Any]:
        world = runtime.snapshot()
        kingdom_item = world.kingdoms.get(kingdom_id)
        if not kingdom_item:
            raise HTTPException(status_code=404, detail="kingdom not found")
        if not runtime.ai.enabled:
            raise HTTPException(status_code=409, detail="AI provider is disabled")
        try:
            return runtime.ai.advise_kingdom(kingdom_item, world)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"AI provider request failed: {exc}") from exc

    @app.websocket("/api/stream")
    async def event_stream(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = runtime.subscribe()
        try:
            await websocket.send_json({"type": "connected", "world": runtime.summary()})
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=20)
                    await websocket.send_json({"type": "event", "event": event})
                except TimeoutError:
                    await websocket.send_json({"type": "heartbeat", "world_date": runtime.snapshot().date.model_dump()})
        except WebSocketDisconnect:
            pass
        finally:
            runtime.unsubscribe(queue)

    return app
