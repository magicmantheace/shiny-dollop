"""Local deterministic producer for the Slice 28B.2 live camera QA."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import time

from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .headless_mvp_simulation import HeadlessCrawlMVP
from .live_presentation_bridge import LiveLedgerBuffer, LivePresentationConsumer, LivePresentationScheduler
from .live_camera_director import LiveCameraConfig


QA_SEED = "crawl-v09-death-persistence"
QA_DESCENDERS = tuple(f"live_descender_{index:03d}" for index in range(12))
QA_FOCUS = ("live_descender_004",)


def _atomic_json(path: Path, value) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, indent=2, sort_keys=True).encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)
    return len(encoded)


def _wait_for(path: Path, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.1)
    raise TimeoutError(f"Timed out waiting for live presenter marker: {path}")


def run(spool: Path, *, steps: int = 90, poll_seconds: float = 0.05) -> dict:
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed=QA_SEED,
        crawler_ids=QA_DESCENDERS,
        floor_count=8,
    )
    service.start(descent)
    simulation = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=5)
    simulation.prepare(descent)

    environment_manifest_path = spool.parent / "environment_manifest.json"
    environment = (
        json.loads(environment_manifest_path.read_text(encoding="utf-8"))
        if environment_manifest_path.exists()
        else {"protocol": "crawl.presentation-environment.v1", "room_id": "accepted_stone_dungeon"}
    )
    build_result_path = spool.parent / "unreal_build_result.json"
    if build_result_path.exists():
        build_result = json.loads(build_result_path.read_text(encoding="utf-8"))
        environment["accepted_level_asset"] = build_result.get("level_asset")
        environment["accepted_map_object"] = build_result.get("map_object")

    buffer = LiveLedgerBuffer(descent.id, presentation_delay_ticks=3, maximum_events=5000)
    camera_config = LiveCameraConfig(presentation_delay_ticks=3, camera_lookahead_ticks=2)
    scheduler = LivePresentationScheduler(
        descent.id,
        presentation_seed=f"{QA_SEED}:live-28b2",
        focus_actor_ids=QA_FOCUS,
        seconds_per_tick=0.45,
        camera_config=camera_config,
    )
    bootstrap = scheduler.bootstrap(descent, environment=environment)
    bootstrap_size = _atomic_json(spool / "bootstrap.json", bootstrap)
    # A cold UE asset-registry scan on the local QA workstation can exceed
    # three minutes. This is only the one-time process readiness handshake.
    _wait_for(spool / "presenter_ready.json", 360.0)

    seen_source_ids: set[str] = set()
    delivery_index = 0
    frame_sizes: list[int] = []
    buffer_depths: list[int] = []
    sent_frames = []
    terminal_source_ticks: list[int] = []
    terminal_source_ids: list[str] = []
    reference_consumer = LivePresentationConsumer(descent.id)
    reference_consumer.apply_bootstrap(bootstrap)

    def deliver(frame, *, duplicate=False):
        nonlocal delivery_index
        delivery_index += 1
        size = _atomic_json(spool / "deliveries" / f"{delivery_index:06d}.json", frame)
        frame_sizes.append(size)
        if not duplicate:
            sent_frames.append(frame)
        reference_consumer.apply_frame(frame)

    def poll_and_schedule(*, flush=False):
        current = sorted(persistence.list_events(descent.id, limit=10000), key=lambda item: (item.tick, item.id))
        new = [item for item in current if item.id not in seen_source_ids]
        seen_source_ids.update(item.id for item in new)
        buffer.push(new)
        ready = buffer.consume_ready(flush=flush)
        if ready:
            lookahead = buffer.peek_lookahead(
                after_tick=max(item.tick for item in ready),
                lookahead_ticks=camera_config.camera_lookahead_ticks,
            )
            before = descent.fingerprint()
            frame = scheduler.schedule(
                ready,
                authoritative_tick=descent.current_tick,
                camera_lookahead_events=lookahead,
            )
            if descent.fingerprint() != before:
                raise RuntimeError("presentation scheduling mutated authoritative Descent state")
            if frame:
                for item in ready:
                    if item.event_type in {"ENEMY_DEFEATED", "CRAWLER_DIED", "CRAWLER_ELIMINATED"}:
                        terminal_source_ticks.append(item.tick)
                        terminal_source_ids.append(item.id)
                deliver(frame)
                if len(sent_frames) == 1:
                    deliver(frame, duplicate=True)
        buffer_depths.append(buffer.snapshot()["buffer_depth"])

    poll_and_schedule()
    for _ in range(steps):
        if descent.status.value != "running":
            break
        simulation.step(descent)
        poll_and_schedule()
        time.sleep(poll_seconds)
    poll_and_schedule(flush=True)

    if not terminal_source_ticks:
        raise RuntimeError("live QA did not consume a canonical terminal Ledger event")
    last_terminal_tick = max(terminal_source_ticks)
    events_after_terminal = sum(
        item.tick > last_terminal_tick
        for item in persistence.list_events(descent.id, limit=10000)
    )
    if events_after_terminal < 1:
        raise RuntimeError("live QA has no authoritative events after the terminal event")
    if reference_consumer.duplicate_frames != 1:
        raise RuntimeError("duplicate-frame integration proof did not exercise idempotency")

    resume = scheduler.reconnect_snapshot(descent, environment_digest=bootstrap["environment"].get("digest", bootstrap["digest"]))
    resumed = LivePresentationConsumer(descent.id)
    resumed.apply_resume_snapshot(resume)
    reconnect_ok = (
        resumed.latest_frame_sequence == scheduler.frame_sequence
        and resumed.terminal_actor_ids == scheduler.terminal_actor_ids
        and resumed.camera_state == resume["camera_state"]
    )
    if not reconnect_ok:
        raise RuntimeError("resume snapshot did not restore cursor and terminal actor state")

    scheduler_debug = scheduler.diagnostics()
    scheduler_debug.update({
        "qa_seed": QA_SEED,
        "simulation_steps": steps,
        "simulation_duration_seconds": descent.current_tick,
        "terminal_source_event_ids": terminal_source_ids,
        "events_after_last_terminal": events_after_terminal,
        "authoritative_fingerprint": descent.fingerprint(),
    })
    _atomic_json(spool.parent / "live_scheduler_debug.json", scheduler_debug)
    camera_debug = scheduler.camera_director.diagnostics(scheduler.presentation_seconds + 4.0)
    camera_debug.update({
        "qa_seed": QA_SEED,
        "presentation_delay_ticks": buffer.presentation_delay_ticks,
        "camera_lookahead_ticks": camera_config.camera_lookahead_ticks,
        "reconnect_restore_result": "passed" if reconnect_ok else "failed",
    })
    _atomic_json(spool.parent / "live_camera_debug.json", camera_debug)
    _atomic_json(spool.parent / "live_camera_shots.json", {
        "protocol": camera_debug["protocol"],
        "descent_id": descent.id,
        "shots": camera_debug["shots"],
        "command_digest": camera_debug["command_digest"],
    })
    producer_debug = {
        "protocol": "underreach.live-producer-debug.v1",
        "descent_id": descent.id,
        "qa_seed": QA_SEED,
        "simulation_steps": steps,
        "simulation_duration_seconds": descent.current_tick,
        "total_authoritative_ledger_events": len(seen_source_ids),
        "total_buffered_events": buffer.accepted_event_count,
        "total_consumed_events": len(scheduler.processed_event_ids),
        "duplicate_ledger_events": buffer.dropped_duplicate_count,
        "rejected_out_of_order_events": buffer.out_of_order_rejection_count,
        "bootstrap_count": scheduler.bootstrap_count,
        "incremental_frame_count": len(sent_frames),
        "delivery_count": delivery_index,
        "intentional_duplicate_deliveries": 1,
        "reference_consumer_duplicate_frames": reference_consumer.duplicate_frames,
        "reference_consumer_rejected_frames": reference_consumer.rejected_frames,
        "reconnect_result": "passed" if reconnect_ok else "failed",
        "terminal_source_event_count": len(terminal_source_ids),
        "events_after_last_terminal": events_after_terminal,
        "latest_authoritative_tick": buffer.latest_authoritative_tick,
        "latest_presentation_seconds": scheduler.presentation_seconds,
        "average_buffer_depth": sum(buffer_depths) / max(1, len(buffer_depths)),
        "maximum_buffer_depth": max(buffer_depths or [0]),
        "bootstrap_size_bytes": bootstrap_size,
        "average_bridge_frame_size_bytes": sum(frame_sizes) / max(1, len(frame_sizes)),
        "maximum_bridge_frame_size_bytes": max(frame_sizes or [0]),
        "command_stream_digest": scheduler_debug["command_stream_digest"],
        "camera_command_digest": camera_debug["command_digest"],
        "camera_shot_count": camera_debug["shots_generated"],
        "camera_cut_count": camera_debug["cuts_generated"],
        "authoritative_fingerprint": descent.fingerprint(),
    }
    _atomic_json(spool.parent / "live_producer_debug.json", producer_debug)
    _atomic_json(spool / "resume_snapshot.json", resume)
    _atomic_json(spool / "producer_complete.json", producer_debug)
    return producer_debug


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spool", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=90)
    parser.add_argument("--poll-seconds", type=float, default=0.05)
    args = parser.parse_args()
    result = run(args.spool, steps=args.steps, poll_seconds=args.poll_seconds)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
