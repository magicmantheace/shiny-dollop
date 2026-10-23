from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query

from .camera_director import AutomatedCameraDirector
from .crawl_domain import Crawl, ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .live_channels import build_crawler_channel
from .replay_engine import ReplayArchive
from .spectator_state import (
    leaderboard,
    public_crawl,
    public_crawler,
    public_event,
    public_floor,
    public_party,
    trending_crawlers,
    visible_encounters,
)
from .story_highlights import StoryArcDetector
from .unreal_spectator_bridge import bridge_bootstrap, build_bridge_frame


class SpectatorRepository:
    """Read-only facade over crawl persistence for public/spectator clients."""

    def __init__(self, persistence: CrawlPersistence, crawl_id: str | None = None) -> None:
        self.persistence = persistence
        self.crawl_id = crawl_id

    def crawl(self) -> Crawl:
        if self.crawl_id:
            crawl = self.persistence.load_crawl(self.crawl_id)
            if crawl is None:
                raise KeyError(self.crawl_id)
            return crawl
        crawls = self.persistence.list_crawls(limit=1)
        if not crawls:
            raise KeyError("current")
        return crawls[0]

    def events(self, *, limit: int = 1000, event_type: str | None = None):
        crawl = self.crawl()
        return self.persistence.list_events(crawl.id, limit=limit, event_type=event_type)

    def search_events(self, needle: str, *, event_type: str | None = None, limit: int = 25):
        """DB-level substring search over the complete canonical Ledger."""
        crawl = self.crawl()
        return self.persistence.search_events(
            crawl.id, needle, event_type=event_type, limit=limit
        )

    def replay(self) -> ReplayArchive:
        crawl = self.crawl()
        return ReplayArchive(crawl, self.persistence.list_events(crawl.id, limit=10000))


def create_spectator_app(repository: SpectatorRepository) -> FastAPI:
    app = FastAPI(
        title="Crawl Spectator API",
        version="0.7.0",
        description="Read-only spectator, channel, camera, story, and replay interface for Crawl.",
    )

    def current() -> Crawl:
        try:
            return repository.crawl()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="crawl not found") from exc

    @app.get("/health")
    def health() -> dict[str, Any]:
        crawl = current()
        return {"status": "ok", "crawl_id": crawl.id, "tick": crawl.current_tick}

    @app.get("/api/spectator/crawl")
    def crawl_summary() -> dict[str, Any]:
        return public_crawl(current())

    @app.get("/api/spectator/floor")
    def floor_summary(floor_number: int | None = Query(default=None, ge=1)) -> dict[str, Any]:
        crawl = current()
        number = crawl.current_floor if floor_number is None else floor_number
        if number not in crawl.floors:
            raise HTTPException(status_code=404, detail="floor not found")
        return public_floor(crawl, number)

    @app.get("/api/spectator/crawlers")
    def crawler_directory(
        status: str | None = None,
        floor_number: int | None = Query(default=None, ge=1),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[dict[str, Any]]:
        crawl = current()
        ids = sorted(crawl.participants)
        if status is not None:
            ids = [npc_id for npc_id in ids if crawl.participants[npc_id].status.value == status]
        if floor_number is not None:
            ids = [npc_id for npc_id in ids if crawl.participants[npc_id].current_floor == floor_number]
        return [public_crawler(crawl, npc_id) for npc_id in ids[:limit]]

    @app.get("/api/spectator/crawlers/{npc_id}")
    def crawler_profile(npc_id: str) -> dict[str, Any]:
        crawl = current()
        if npc_id not in crawl.participants:
            raise HTTPException(status_code=404, detail="crawler not found")
        return public_crawler(crawl, npc_id, include_social=True)

    @app.get("/api/spectator/crawlers/{npc_id}/history")
    def crawler_history(npc_id: str, limit: int = Query(default=200, ge=1, le=1000)) -> list[dict[str, Any]]:
        crawl = current()
        if npc_id not in crawl.participants:
            raise HTTPException(status_code=404, detail="crawler not found")
        events = repository.events(limit=1000)
        selected = [event for event in events if npc_id in event.actor_ids][:limit]
        return [public_event(event) for event in selected]

    @app.get("/api/spectator/channels/{npc_id}")
    def crawler_channel(npc_id: str, recent_event_limit: int = Query(default=12, ge=1, le=100)) -> dict[str, Any]:
        crawl = current()
        if npc_id not in crawl.participants:
            raise HTTPException(status_code=404, detail="crawler not found")
        return build_crawler_channel(
            crawl,
            repository.events(limit=1000),
            npc_id,
            recent_event_limit=recent_event_limit,
        )

    @app.get("/api/spectator/parties")
    def parties(active_only: bool = True) -> list[dict[str, Any]]:
        crawl = current()
        items = [party for party in crawl.parties.values() if not active_only or party.active]
        return [public_party(crawl, party.id) for party in sorted(items, key=lambda item: item.id)]

    @app.get("/api/spectator/parties/{party_id}")
    def party(party_id: str) -> dict[str, Any]:
        crawl = current()
        if party_id not in crawl.parties:
            raise HTTPException(status_code=404, detail="party not found")
        return public_party(crawl, party_id)

    @app.get("/api/spectator/encounters")
    def encounters() -> list[dict[str, Any]]:
        return visible_encounters(current())

    @app.get("/api/spectator/events")
    def events(
        limit: int = Query(default=100, ge=1, le=1000),
        event_type: str | None = None,
        after_tick: int | None = Query(default=None, ge=0),
    ) -> list[dict[str, Any]]:
        items = repository.events(limit=1000, event_type=event_type)
        if after_tick is not None:
            items = [event for event in items if event.tick > after_tick]
        items.sort(key=lambda event: (event.tick, event.id))
        return [public_event(event) for event in items[-limit:]]

    @app.get("/api/spectator/deaths")
    def deaths() -> list[dict[str, Any]]:
        crawl = current()
        return [
            public_crawler(crawl, npc_id)
            for npc_id, participant in sorted(crawl.participants.items())
            if participant.status == ParticipationStatus.DEAD
        ]

    @app.get("/api/spectator/leaderboard")
    def standings(limit: int = Query(default=25, ge=1, le=100)) -> list[dict[str, Any]]:
        return leaderboard(current(), limit=limit)

    @app.get("/api/spectator/trending")
    def trending(limit: int = Query(default=20, ge=1, le=100)) -> list[dict[str, Any]]:
        crawl = current()
        return trending_crawlers(crawl, repository.events(limit=1000), limit=limit)

    @app.get("/api/spectator/highlights")
    def highlights(
        limit: int = Query(default=20, ge=1, le=100),
        minimum_score: float = Query(default=0.42, ge=0.0, le=1.0),
    ) -> list[dict[str, Any]]:
        detector = StoryArcDetector(minimum_score=minimum_score)
        return [arc.as_dict() for arc in detector.analyze(repository.replay().events, limit=limit)]

    @app.get("/api/spectator/highlights/{story_id}")
    def highlight(story_id: str) -> dict[str, Any]:
        arcs = StoryArcDetector().analyze(repository.replay().events, limit=100)
        for arc in arcs:
            if arc.id == story_id:
                return arc.as_dict()
        raise HTTPException(status_code=404, detail="highlight not found")

    @app.get("/api/spectator/camera/plan")
    def camera_plan(
        start_tick: int | None = Query(default=None, ge=0),
        end_tick: int | None = Query(default=None, ge=0),
        focus_actor_id: str | None = None,
        max_shots: int = Query(default=32, ge=1, le=64),
    ) -> dict[str, Any]:
        crawl = current()
        if focus_actor_id is not None and focus_actor_id not in crawl.participants:
            raise HTTPException(status_code=404, detail="crawler not found")
        archive = repository.replay()
        return AutomatedCameraDirector().plan(
            crawl,
            archive.events,
            start_tick=start_tick,
            end_tick=end_tick,
            focus_actor_id=focus_actor_id,
            max_shots=max_shots,
        ).as_dict()

    @app.get("/api/spectator/replay")
    def replay_manifest() -> dict[str, Any]:
        return repository.replay().manifest.as_dict()

    @app.get("/api/spectator/replay/events")
    def replay_events(
        start_tick: int | None = Query(default=None, ge=0),
        end_tick: int | None = Query(default=None, ge=0),
        actor_id: str | None = None,
        limit: int = Query(default=500, ge=1, le=5000),
    ) -> dict[str, Any]:
        return repository.replay().public_window(start_tick=start_tick, end_tick=end_tick, actor_id=actor_id, limit=limit)

    @app.get("/api/spectator/replay/events/{event_id}/causes")
    def replay_causes(event_id: str) -> list[dict[str, Any]]:
        archive = repository.replay()
        try:
            chain = archive.cause_chain(event_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="event not found") from exc
        return [public_event(event) for event in chain]

    @app.get("/api/spectator/unreal/bootstrap")
    def unreal_bootstrap() -> dict[str, Any]:
        return bridge_bootstrap(current())

    @app.get("/api/spectator/unreal/frame")
    def unreal_frame(since_tick: int | None = Query(default=None, ge=0)) -> dict[str, Any]:
        crawl = current()
        return build_bridge_frame(crawl, repository.events(limit=1000), since_tick=since_tick).as_dict()

    return app
