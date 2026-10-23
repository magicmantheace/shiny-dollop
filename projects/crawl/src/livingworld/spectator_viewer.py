"""Human-readable, read-only projections for the Underreach spectator viewer.

The viewer is deliberately downstream of canonical Descent state and the
presentation-only Feed registry.  It composes those existing projections; it
never writes simulation state or invents gameplay facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from time import perf_counter, time
from typing import Any, Callable

from .crawl_domain import Crawl
from .feed_channel_registry import FeedChannelRegistry
from .feed_state import public_descent, public_ledger_event, public_stratum
from .spectator_api import SpectatorRepository


VIEWER_PROTOCOL = "underreach.spectator-viewer.v1"
VIEWER_VERSION = "29a2.1"
DEFAULT_STALE_AFTER_MS = 3_000


def _clone(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True))


def descender_label(descender_id: str | None) -> str:
    if not descender_id:
        return "No active Descender"
    suffix = descender_id.rsplit("_", 1)[-1]
    return f"Descender {suffix.upper()}" if suffix != descender_id else descender_id


def _event_label(item: dict[str, Any]) -> str:
    event_type = str(item.get("event_type", "LEDGER_EVENT"))
    readable = event_type.replace("_", " ").title()
    readable = readable.replace("Crawler", "Descender").replace("Crawl", "Descent").replace("Floor", "Stratum")
    actors = [descender_label(actor) for actor in item.get("actor_ids", []) if str(actor).startswith("live_descender_")]
    if actors:
        return f"{', '.join(actors)} — {readable}"
    return readable


def _camera_projection(camera: dict[str, Any], focus: dict[str, Any]) -> dict[str, Any]:
    active = camera.get("active_shot") or camera.get("current_shot") or {}
    targets = list(active.get("target_actor_ids") or camera.get("target_actor_ids") or [])
    return {
        "status": camera.get("status", "live" if active else "waiting"),
        "mode": active.get("mode") or camera.get("mode") or "waiting",
        "shot_id": active.get("shot_id") or camera.get("shot_id"),
        "target_actor_ids": targets,
        "focus_descender_id": focus.get("active_descender_id"),
        "focus_confirmed": (
            not focus.get("active_descender_id")
            or focus.get("active_descender_id") in targets
            or not targets
        ),
        "presentation_tick": int(focus.get("presentation_tick", camera.get("presentation_tick", 0)) or 0),
        "presentation_seconds": float(focus.get("presentation_seconds", 0.0) or 0.0),
    }


def build_viewer_state(
    descent: Crawl,
    events: list[Any],
    registry: FeedChannelRegistry,
    *,
    viewer_id: str,
    live_status: dict[str, Any] | None = None,
    live_camera: dict[str, Any] | None = None,
    runtime_health: dict[str, Any] | None = None,
    stale_after_ms: int = DEFAULT_STALE_AFTER_MS,
    generated_at_unix_ms: int | None = None,
) -> dict[str, Any]:
    """Compose one immutable browser payload from existing public projections."""

    generated_ms = int(time() * 1000) if generated_at_unix_ms is None else int(generated_at_unix_ms)
    status = _clone(live_status or {})
    camera = _clone(live_camera or {})
    focus = registry.active_focus(viewer_id)
    channels = registry.directory(descent, viewer_id=viewer_id)
    projected_events = [public_ledger_event(event) for event in sorted(events, key=lambda item: (item.tick, item.id))[-30:]]

    connected = bool(status.get("connected_presenter", False))
    provider_status = str(status.get("status", "offline"))
    buffered_tick = int(registry.latest_buffered_tick or 0)
    authoritative_tick = int(registry.latest_authoritative_tick or descent.current_tick)
    freshness_ticks = max(0, authoritative_tick - buffered_tick)
    updated_ms = int(status.get("updated_at_unix_ms", generated_ms) or generated_ms)
    stale_duration_ms = max(0, generated_ms - updated_ms)
    stale = connected and (freshness_ticks > 3 or stale_duration_ms > stale_after_ms)
    connection_state = "offline" if not connected or provider_status == "offline" else "stale" if stale else "live"

    rows: list[dict[str, Any]] = []
    for channel in channels:
        descender = channel["descender"]
        identity = channel.get("presentation_identity") or {}
        recent = channel.get("recent_ledger_events") or []
        rows.append({
            "descender_id": descender["descender_id"],
            "display_name": descender_label(descender["descender_id"]),
            "species": identity.get("species"),
            "visual_identity_digest": identity.get("visual_identity_digest"),
            "visual_variant": identity.get("visual_variant"),
            "style_profile": identity.get("style_profile"),
            "channel_id": channel["channel_id"],
            "status": channel["status"],
            "terminal": bool(channel["terminal"]),
            "health": float(channel["health"]),
            "stratum_number": int(channel["current_stratum"]),
            "sector_id": channel.get("current_sector_id"),
            "activity": _event_label(recent[-1]) if recent else "Awaiting Ledger activity",
            "in_active_encounter": channel.get("active_encounter") is not None,
            "currently_followed": bool(channel["currently_manually_followed"]),
            "currently_auto_focused": bool(channel["currently_automatic_focus"]),
            "camera_available": bool(channel.get("camera_available", True)),
            "interest_score": float(channel.get("recent_interest_score", 0.0)),
        })

    active_id = focus.get("active_descender_id")
    rows.sort(key=lambda row: (
        row["descender_id"] != active_id,
        not row["currently_auto_focused"],
        not row["in_active_encounter"],
        row["terminal"],
        row["descender_id"],
    ))
    living = sum(not item["terminal"] for item in rows)
    terminal = len(rows) - living
    stratum = public_stratum(descent)
    descent_public = public_descent(descent)

    return {
        "protocol": VIEWER_PROTOCOL,
        "viewer_version": VIEWER_VERSION,
        "authoritative": False,
        "generated_at_unix_ms": generated_ms,
        "viewer": {"viewer_id": viewer_id, "local_only": True},
        "connection": {
            "state": connection_state,
            "connected_presenter": connected,
            "stale": stale,
            "stale_after_ms": int(stale_after_ms),
            "stale_duration_ms": stale_duration_ms,
            "latest_authoritative_tick": authoritative_tick,
            "latest_buffered_tick": buffered_tick,
            "latest_ledger_tick": max([int(item["tick"]) for item in projected_events] or [0]),
            "latest_frame_id": registry.latest_frame_id,
        },
        "descent": {
            key: descent_public[key]
            for key in (
                "id", "world", "competition", "broadcast", "record", "status",
                "current_tick", "current_stratum", "stratum_count",
                "starting_descender_count", "surviving_descender_count",
                "eliminated_descender_count",
            )
        },
        "stratum": {
            "number": stratum["number"],
            "theme": stratum["theme"],
            "status": stratum["status"],
            "sector_count": len(stratum["sectors"]),
            "refuge_sector_ids": list(stratum["refuge_sector_ids"]),
        },
        "summary": {
            "living_descender_count": living,
            "fallen_descender_count": terminal,
            "logical_channel_count": len(rows) + 1,
        },
        "focus": {
            "mode": focus["focus_mode"],
            "active_channel_id": focus["active_channel_id"],
            "active_descender_id": active_id,
            "active_descender_name": descender_label(active_id),
            "manual_follow_descender_id": focus["manual_follow_descender_id"],
            "automatic_focus_descender_id": focus["automatic_focus_descender_id"],
            "presentation_tick": focus["presentation_tick"],
            "presentation_seconds": focus["presentation_seconds"],
            "last_seen_frame_id": focus["last_seen_frame_id"],
        },
        "camera": _camera_projection(camera, focus),
        "runtime": _clone(runtime_health) if runtime_health is not None else None,
        "descenders": rows,
        "ledger": [
            {
                "id": item["id"],
                "tick": item["tick"],
                "event_type": item["event_type"],
                "label": _event_label(item),
                "actor_ids": item["actor_ids"],
                "sector_id": item["sector_id"],
                "terminal": item["event_type"] in {"DESCENDER_DIED", "DESCENDER_ELIMINATED", "ENEMY_DEFEATED"},
            }
            for item in reversed(projected_events)
        ],
    }


@dataclass
class ViewerStateProjector:
    """Measured aggregate-state provider used by the API and QA diagnostics."""

    repository: SpectatorRepository
    registry: FeedChannelRegistry
    live_status_provider: Callable[[], dict[str, Any]] | None = None
    live_camera_provider: Callable[[], dict[str, Any]] | None = None
    runtime_health_provider: Callable[[], dict[str, Any]] | None = None
    stale_after_ms: int = DEFAULT_STALE_AFTER_MS
    response_times_ms: list[float] = field(default_factory=list)
    payload_sizes_bytes: list[int] = field(default_factory=list)
    request_count: int = 0

    def state(self, viewer_id: str) -> dict[str, Any]:
        started = perf_counter()
        descent = self.repository.crawl()
        before = descent.fingerprint()
        result = build_viewer_state(
            descent,
            self.repository.events(limit=1000),
            self.registry,
            viewer_id=viewer_id,
            live_status=self.live_status_provider() if self.live_status_provider else None,
            live_camera=self.live_camera_provider() if self.live_camera_provider else None,
            runtime_health=self.runtime_health_provider() if self.runtime_health_provider else None,
            stale_after_ms=self.stale_after_ms,
        )
        if descent.fingerprint() != before:
            raise RuntimeError("spectator viewer projection mutated authoritative Descent state")
        elapsed = (perf_counter() - started) * 1000.0
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.response_times_ms.append(elapsed)
        self.payload_sizes_bytes.append(len(encoded))
        self.request_count += 1
        self.response_times_ms = self.response_times_ms[-1024:]
        self.payload_sizes_bytes = self.payload_sizes_bytes[-1024:]
        return result

    def diagnostics(self) -> dict[str, Any]:
        times = self.response_times_ms or [0.0]
        sizes = self.payload_sizes_bytes or [0]
        return {
            "protocol": "underreach.spectator-viewer-debug.v1",
            "viewer_version": VIEWER_VERSION,
            "authoritative": False,
            "request_count": self.request_count,
            "average_viewer_state_latency_ms": sum(times) / len(times),
            "maximum_viewer_state_latency_ms": max(times),
            "average_viewer_state_payload_bytes": sum(sizes) / len(sizes),
            "maximum_viewer_state_payload_bytes": max(sizes),
            "polling_interval_ms": 750,
            "stale_after_ms": self.stale_after_ms,
        }
