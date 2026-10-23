"""Public Underreach Feed API.

This is the preferred viewer-facing API surface for Slice 28B and later. The
legacy spectator API remains available as a compatibility interface, but new
clients should use these names and routes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

from .camera_director import AutomatedCameraDirector
from .crawl_domain import Crawl, ParticipationStatus
from .echoes import EchoDetector, public_echo
from .feed_channels import build_descender_channel
from .feed_channel_registry import FeedChannelRegistry, descender_channel_id
from .feed_state import (
    ledger_standings,
    public_descender,
    public_descent,
    public_ledger_event,
    public_party,
    public_stratum,
    trending_descenders,
    visible_encounters,
)
from .spectator_api import SpectatorRepository
from .spectator_viewer import ViewerStateProjector
from .underreach_terminology import FEED_NAME, UNDERREACH_NAME, legacy_event_type


def create_feed_app(
    repository: SpectatorRepository,
    live_status_provider: Callable[[], dict[str, Any]] | None = None,
    live_camera_provider: Callable[[], dict[str, Any]] | None = None,
    feed_channel_registry: FeedChannelRegistry | None = None,
    focus_transition_sink: Callable[[dict[str, Any]], bool] | None = None,
    viewer_static_directory: str | Path | None = None,
    runtime_health_provider: Callable[[], dict[str, Any]] | None = None,
) -> FastAPI:
    """Create the read-only public API for The Feed."""

    app = FastAPI(
        title="Underreach Feed API",
        version="0.8.0",
        description=(
            "Read-only Feed, Ledger, Echo, camera, and Descender interface for "
            "The Underreach. Simulation truth remains authoritative."
        ),
    )

    def current() -> Crawl:
        try:
            return repository.crawl()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="descent not found") from exc

    def channels() -> FeedChannelRegistry:
        if feed_channel_registry is None:
            raise HTTPException(status_code=503, detail="live Feed channel registry unavailable")
        return feed_channel_registry

    viewer_projector = (
        ViewerStateProjector(
            repository,
            feed_channel_registry,
            live_status_provider=live_status_provider,
            live_camera_provider=live_camera_provider,
            runtime_health_provider=runtime_health_provider,
        )
        if feed_channel_registry is not None
        else None
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        descent = current()
        return {
            "status": "ok",
            "world": UNDERREACH_NAME,
            "service": FEED_NAME,
            "descent_id": descent.id,
            "tick": descent.current_tick,
        }

    @app.get("/api/feed/descent")
    def descent_summary() -> dict[str, Any]:
        return public_descent(current())

    @app.get("/api/feed/live/status")
    def live_status() -> dict[str, Any]:
        """Read-only projection of the non-authoritative presenter health."""
        if live_status_provider is None:
            descent = current()
            return {
                "descent_id": descent.id,
                "simulation_tick": descent.current_tick,
                "status": "offline",
                "connected_presenter": False,
                "bridge_protocol": "underreach.live-presentation.v1",
                "authoritative": False,
            }
        # Round-trip through JSON-compatible structures so a provider cannot
        # leak mutable references to either the Feed client or simulation.
        import json

        return json.loads(json.dumps(live_status_provider(), sort_keys=True))

    @app.get("/api/feed/live/camera")
    def live_camera() -> dict[str, Any]:
        """Read-only projection of the non-authoritative live camera state."""
        if live_camera_provider is None:
            descent = current()
            return {
                "descent_id": descent.id,
                "presentation_tick": 0,
                "status": "offline",
                "camera_protocol": "underreach.live-camera.v1",
                "authoritative": False,
            }
        import json

        projected = json.loads(json.dumps(live_camera_provider(), sort_keys=True))
        projected["authoritative"] = False
        return projected

    @app.get("/api/feed/runtime/health")
    def runtime_health() -> dict[str, Any]:
        """Read-only operational health; never an authoritative input."""
        import json

        if runtime_health_provider is None:
            descent = current()
            return {
                "protocol": "underreach.alpha-runtime.v1",
                "authoritative": False,
                "runtime_id": None,
                "overall_status": "offline",
                "uptime_seconds": 0.0,
                "simulation_tick": descent.current_tick,
                "ledger_tick": descent.current_tick,
                "presentation_tick": 0,
                "presentation_lag_ticks": descent.current_tick,
                "unreal_connected": False,
                "latest_checkpoint": None,
                "restart_count": 0,
                "recovery_count": 0,
                "components": {},
            }
        return json.loads(json.dumps(runtime_health_provider(), sort_keys=True))

    @app.get("/api/feed/stratum")
    def stratum_summary(
        stratum_number: int | None = Query(default=None, ge=1),
    ) -> dict[str, Any]:
        descent = current()
        number = descent.current_floor if stratum_number is None else stratum_number
        if number not in descent.floors:
            raise HTTPException(status_code=404, detail="stratum not found")
        return public_stratum(descent, number)

    @app.get("/api/feed/descenders")
    def descender_directory(
        status: str | None = None,
        stratum_number: int | None = Query(default=None, ge=1),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        descent = current()
        ids = sorted(descent.participants)
        if status is not None:
            wanted = status.lower()
            ids = [
                descender_id
                for descender_id in ids
                if public_descender(descent, descender_id)["status"] == wanted
            ]
        if stratum_number is not None:
            ids = [
                descender_id
                for descender_id in ids
                if descent.participants[descender_id].current_floor == stratum_number
            ]
        return [public_descender(descent, descender_id) for descender_id in ids[:limit]]

    @app.get("/api/feed/descenders/{descender_id}")
    def descender_profile(descender_id: str) -> dict[str, Any]:
        descent = current()
        if descender_id not in descent.participants:
            raise HTTPException(status_code=404, detail="descender not found")
        return public_descender(descent, descender_id, include_social=True)

    @app.get("/api/feed/descenders/{descender_id}/ledger")
    def descender_history(
        descender_id: str,
        limit: int = Query(default=200, ge=1, le=1000),
    ) -> list[dict[str, Any]]:
        descent = current()
        if descender_id not in descent.participants:
            raise HTTPException(status_code=404, detail="descender not found")
        selected = [
            event
            for event in repository.events(limit=1000)
            if descender_id in event.actor_ids
        ][:limit]
        return [public_ledger_event(event) for event in selected]

    @app.get("/api/feed/channels")
    def channel_directory(viewer_id: str = "default_viewer") -> list[dict[str, Any]]:
        """Read-only live channel directory over one authoritative Descent."""
        return channels().directory(current(), viewer_id=viewer_id)

    def _feed_channel_payload(
        channel_id: str,
        viewer_id: str,
        recent_event_limit: int,
    ) -> dict[str, Any]:
        """Shared feed-channel resolution; takes a plain int limit.

        The FastAPI routes delegate here so a direct call never receives a
        ``Query`` descriptor as ``recent_event_limit`` (which previously
        raised ``TypeError`` when the app ran without a feed-channel
        registry).
        """
        descent = current()
        # Preserve the original per-Descender path while accepting the new
        # deterministic ``feed:descender:<id>`` channel contract.
        descender_id = (
            channel_id.removeprefix("feed:descender:")
            if channel_id.startswith("feed:descender:")
            else channel_id
        )
        if descender_id not in descent.participants:
            raise HTTPException(status_code=404, detail="Feed channel not found")
        if feed_channel_registry is not None:
            return feed_channel_registry.channel(descent, descender_id, viewer_id=viewer_id)
        return build_descender_channel(
            descent,
            repository.events(limit=1000),
            descender_id,
            recent_event_limit=recent_event_limit,
        )

    @app.get("/api/feed/channels/{channel_id:path}")
    def feed_channel(
        channel_id: str,
        viewer_id: str = "default_viewer",
        recent_event_limit: int = Query(default=12, ge=1, le=100),
    ) -> dict[str, Any]:
        return _feed_channel_payload(channel_id, viewer_id, recent_event_limit)

    @app.get("/api/feed/descenders/{descender_id}/channel")
    def descender_live_channel(descender_id: str, viewer_id: str = "default_viewer") -> dict[str, Any]:
        descent = current()
        if descender_id not in descent.participants:
            raise HTTPException(status_code=404, detail="descender not found")
        return _feed_channel_payload(descender_channel_id(descender_id), viewer_id, 12)

    @app.get("/api/feed/live/focus")
    def live_focus(viewer_id: str = "default_viewer") -> dict[str, Any]:
        """Presentation-only active channel/focus state."""
        return channels().active_focus(viewer_id)

    @app.get("/api/feed/viewer/state")
    def viewer_state(viewer_id: str = "viewer_local_alpha") -> dict[str, Any]:
        """Aggregate, read-only product projection for the local spectator viewer."""
        if viewer_projector is None:
            raise HTTPException(status_code=503, detail="spectator viewer state unavailable")
        try:
            return viewer_projector.state(viewer_id)
        except KeyError:
            return {
                "protocol": "underreach.spectator-viewer.v1",
                "viewer_version": "29a2.1",
                "authoritative": False,
                "viewer": {"viewer_id": viewer_id, "local_only": True},
                "connection": {"state": "offline", "stale": False},
                "descent": None,
                "stratum": None,
                "summary": {"living_descender_count": 0, "fallen_descender_count": 0, "logical_channel_count": 0},
                "focus": None,
                "camera": None,
                "runtime": json.loads(json.dumps(runtime_health_provider(), sort_keys=True)) if runtime_health_provider else None,
                "descenders": [],
                "ledger": [],
            }

    @app.get("/api/feed/viewer/diagnostics")
    def viewer_diagnostics() -> dict[str, Any]:
        if viewer_projector is None:
            raise HTTPException(status_code=503, detail="spectator viewer diagnostics unavailable")
        return viewer_projector.diagnostics()

    @app.post("/api/feed/live/follow")
    def follow_live_feed(request: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Change presentation/session focus; authoritative truth is untouched."""
        payload = dict(request)
        payload["action"] = "follow"
        result = channels().apply_request(current(), payload)
        if result["status"] == "rejected":
            status = 404 if result["reason"] == "unknown_descender" else 409 if result["reason"] == "stale_request" else 422
            raise HTTPException(status_code=status, detail=result)
        if result.get("transition") and not result.get("duplicate") and focus_transition_sink is not None:
            focus_transition_sink(result["transition"])
        return result

    @app.post("/api/feed/live/release")
    def release_live_feed(request: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Release manual focus back to deterministic automatic presentation."""
        payload = dict(request)
        payload["action"] = "release"
        result = channels().apply_request(current(), payload)
        if result["status"] == "rejected":
            status = 409 if result["reason"] == "stale_request" else 422
            raise HTTPException(status_code=status, detail=result)
        if result.get("transition") and not result.get("duplicate") and focus_transition_sink is not None:
            focus_transition_sink(result["transition"])
        return result

    @app.get("/api/feed/parties")
    def parties(active_only: bool = True) -> list[dict[str, Any]]:
        descent = current()
        items = [party for party in descent.parties.values() if not active_only or party.active]
        return [public_party(descent, party.id) for party in sorted(items, key=lambda item: item.id)]

    @app.get("/api/feed/encounters")
    def encounters() -> list[dict[str, Any]]:
        return visible_encounters(current())

    @app.get("/api/feed/ledger/events")
    def ledger_events(
        limit: int = Query(default=100, ge=1, le=1000),
        event_type: str | None = None,
        after_tick: int | None = Query(default=None, ge=0),
    ) -> list[dict[str, Any]]:
        stored_type = legacy_event_type(event_type) if event_type else None
        items = repository.events(limit=1000, event_type=stored_type)
        if after_tick is not None:
            items = [event for event in items if event.tick > after_tick]
        items.sort(key=lambda event: (event.tick, event.id))
        return [public_ledger_event(event) for event in items[-limit:]]

    @app.get("/api/feed/ledger/standings")
    def standings(limit: int = Query(default=25, ge=1, le=100)) -> list[dict[str, Any]]:
        return ledger_standings(current(), limit=limit)

    @app.get("/api/feed/fallen")
    def fallen() -> list[dict[str, Any]]:
        descent = current()
        return [
            public_descender(descent, descender_id)
            for descender_id, participant in sorted(descent.participants.items())
            if participant.status == ParticipationStatus.DEAD
        ]

    @app.get("/api/feed/trending")
    def trending(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
        descent = current()
        return trending_descenders(
            descent,
            repository.events(limit=1000),
            limit=limit,
        )

    @app.get("/api/feed/echoes")
    def echoes(
        limit: int = Query(default=20, ge=1, le=100),
        minimum_score: float = Query(default=0.42, ge=0.0, le=1.0),
    ) -> list[dict[str, Any]]:
        detector = EchoDetector(minimum_score=minimum_score)
        return [public_echo(echo) for echo in detector.analyze(repository.replay().events, limit=limit)]

    @app.get("/api/feed/echoes/{echo_id}")
    def echo(echo_id: str) -> dict[str, Any]:
        for candidate in EchoDetector().analyze(repository.replay().events, limit=100):
            if candidate.id == echo_id:
                return public_echo(candidate)
        raise HTTPException(status_code=404, detail="echo not found")

    @app.get("/api/feed/camera/plan")
    def camera_plan(
        start_tick: int | None = Query(default=None, ge=0),
        end_tick: int | None = Query(default=None, ge=0),
        focus_descender_id: str | None = None,
        max_shots: int = Query(default=32, ge=1, le=64),
    ) -> dict[str, Any]:
        descent = current()
        if focus_descender_id is not None and focus_descender_id not in descent.participants:
            raise HTTPException(status_code=404, detail="descender not found")
        archive = repository.replay()
        return AutomatedCameraDirector().plan(
            descent,
            archive.events,
            start_tick=start_tick,
            end_tick=end_tick,
            focus_actor_id=focus_descender_id,
            max_shots=max_shots,
        ).as_dict()

    if viewer_static_directory is not None:
        static_path = Path(viewer_static_directory)
        if static_path.is_dir():
            app.mount("/", StaticFiles(directory=static_path, html=True), name="underreach-viewer")

    app.state.viewer_projector = viewer_projector
    return app
