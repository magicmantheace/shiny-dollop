"""Deterministic Slice 28B.3 producer for multi-channel Feed validation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import threading
import time

from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .feed_channel_registry import FeedChannelRegistry
from .feed_api import create_feed_app
from .headless_mvp_simulation import HeadlessCrawlMVP
from .live_camera_director import LiveCameraConfig
from .live_presentation_bridge import LiveLedgerBuffer, LivePresentationConsumer, LivePresentationScheduler
from .spectator_api import SpectatorRepository


QA_SEED = "crawl-v09-death-persistence"
QA_DESCENDERS = tuple(f"live_descender_{index:03d}" for index in range(12))
QA_PRESENTED = ("live_descender_004", "live_descender_005")
QA_POPULATION_PRESENTED = tuple(f"live_descender_{index:03d}" for index in range(10))
QA_POPULATION_SPECIES = {
    actor_id: ("human" if index < 6 else "dwarf")
    for index, actor_id in enumerate(QA_POPULATION_PRESENTED)
}
QA_POPULATION_VARIANTS = {
    actor_id: (
        ("human_average", "human_short_heavy", "human_tall_thin")[index % 3]
        if index < 6 else
        ("dwarf_average", "dwarf_heavy", "dwarf_alt")[(index - 6) % 3]
    )
    for index, actor_id in enumerate(QA_POPULATION_PRESENTED)
}
QA_VIEWER = "qa_viewer"


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


def run(
    spool: Path,
    *,
    steps: int = 90,
    poll_seconds: float = 0.05,
    scripted_controls: bool = True,
    viewer_host: str | None = None,
    viewer_port: int = 8011,
    viewer_static_directory: Path | None = None,
    viewer_hold_seconds: float = 0.0,
    population_proof: bool = False,
) -> dict:
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(seed=QA_SEED, crawler_ids=QA_DESCENDERS, floor_count=8)
    service.start(descent)
    simulation = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=5)
    simulation.prepare(descent)

    environment_path = spool.parent / "environment_manifest.json"
    environment = (
        json.loads(environment_path.read_text(encoding="utf-8"))
        if environment_path.exists()
        else {"protocol": "crawl.presentation-environment.v1", "room_id": "accepted_stone_dungeon"}
    )
    build_result_path = spool.parent / "unreal_build_result.json"
    if build_result_path.exists():
        build = json.loads(build_result_path.read_text(encoding="utf-8"))
        environment["accepted_level_asset"] = build.get("level_asset")
        environment["accepted_map_object"] = build.get("map_object")

    buffer = LiveLedgerBuffer(descent.id, presentation_delay_ticks=3, maximum_events=5000)
    camera_config = LiveCameraConfig(presentation_delay_ticks=3, camera_lookahead_ticks=2)
    presented = QA_POPULATION_PRESENTED if population_proof else QA_PRESENTED
    scheduler = LivePresentationScheduler(
        descent.id,
        # Preserve the accepted attack/reaction selection from 28B.2. Channel
        # and focus determinism have their own registry digests and do not need
        # to perturb asset selection.
        presentation_seed=f"{QA_SEED}:live-28b2",
        focus_actor_ids=presented,
        seconds_per_tick=0.45,
        camera_config=camera_config,
        population_seed="underreach-29a2-population-proof" if population_proof else None,
        population_species=QA_POPULATION_SPECIES if population_proof else None,
        population_variants=QA_POPULATION_VARIANTS if population_proof else None,
    )
    qa_viewer_id = "viewer_local_alpha" if not scripted_controls else QA_VIEWER
    registry = FeedChannelRegistry(descent.id, default_viewer_id=qa_viewer_id)
    registry.register(descent)
    bootstrap = scheduler.bootstrap(descent, environment=environment)
    registry.register_presentation_identities({
        actor["actor_id"]: {
            key: actor.get("character_renderer_manifest", {}).get(key)
            for key in ("species", "visual_identity_digest", "visual_variant", "style_profile", "detail_tier")
        }
        for actor in bootstrap["actors"] if actor.get("character_renderer_manifest")
    })
    initial_transitions = registry.update(
        descent,
        [],
        presentation_tick=0,
        presentation_seconds=0.0,
        buffered_tick=descent.current_tick,
        camera_available_ids=presented,
        camera_state=scheduler.camera_director.snapshot(),
    )
    for transition in initial_transitions:
        scheduler.queue_focus_transition(transition.as_dict())
    bootstrap["presentation_profile"] = (
        "29a2_population" if population_proof
        else "28c1_spectator" if not scripted_controls
        else "28b3_multichannel"
    )
    bootstrap_body = {key: value for key, value in bootstrap.items() if key != "digest"}
    from .live_presentation_bridge import payload_digest
    bootstrap = {**bootstrap_body, "digest": payload_digest(bootstrap_body)}
    bootstrap_size = _atomic_json(spool / "bootstrap.json", bootstrap)

    viewer_server = None
    viewer_thread = None
    viewer_projector = None
    viewer_finished = False
    if viewer_host is not None:
        import uvicorn

        repository = SpectatorRepository(persistence, descent.id)

        def viewer_live_status():
            return {
                "protocol": "underreach.live-presentation.v1",
                "authoritative": False,
                "descent_id": descent.id,
                "status": "complete" if viewer_finished else "live",
                "connected_presenter": (spool / "presenter_ready.json").exists(),
                "simulation_tick": descent.current_tick,
                "presentation_tick": scheduler.frame_sequence,
                "frame_id": registry.latest_frame_id,
                "updated_at_unix_ms": int(time.time() * 1000),
            }

        def viewer_live_camera():
            snapshot = scheduler.camera_director.snapshot()
            return {
                **snapshot,
                "authoritative": False,
                "status": "live" if snapshot.get("active_shot") else "waiting",
                "presentation_tick": scheduler.frame_sequence,
            }

        app = create_feed_app(
            repository,
            live_status_provider=viewer_live_status,
            live_camera_provider=viewer_live_camera,
            feed_channel_registry=registry,
            focus_transition_sink=scheduler.queue_focus_transition,
            viewer_static_directory=viewer_static_directory,
        )
        viewer_projector = app.state.viewer_projector
        config = uvicorn.Config(app, host=viewer_host, port=viewer_port, log_level="warning", access_log=False)
        viewer_server = uvicorn.Server(config)
        viewer_thread = threading.Thread(target=viewer_server.run, name="underreach-viewer", daemon=True)
        viewer_thread.start()
        deadline = time.monotonic() + 20.0
        while not viewer_server.started and viewer_thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.05)
        if not viewer_server.started:
            raise RuntimeError("spectator viewer API did not start")

    _wait_for(spool / "presenter_ready.json", 360.0)

    seen_source_ids: set[str] = set()
    delivery_index = 0
    frame_sizes: list[int] = []
    buffer_depths: list[int] = []
    sent_frames: list[dict] = []
    terminal_source_ticks: list[int] = []
    terminal_source_ids: list[str] = []
    reference_consumer = LivePresentationConsumer(descent.id)
    reference_consumer.apply_bootstrap(bootstrap)
    fingerprint_immutable = True
    requests: list[dict] = []
    request_results: list[dict] = []
    duplicate_switch_frame_delivered = False
    initial_auto: str | None = None
    manual_a: str | None = None
    manual_b: str | None = None
    follow_a_done = False
    follow_b_done = False
    invalid_done = False
    release_done = False

    def deliver(frame, *, duplicate=False):
        nonlocal delivery_index
        delivery_index += 1
        size = _atomic_json(spool / "deliveries" / f"{delivery_index:06d}.json", frame)
        frame_sizes.append(size)
        if not duplicate:
            sent_frames.append(frame)
        reference_consumer.apply_frame(frame)

    def apply_request(action: str, request_id: str, descender_id: str | None = None):
        nonlocal fingerprint_immutable
        request = {
            "viewer_id": qa_viewer_id,
            "action": action,
            "request_id": request_id,
            "requested_at_presentation_tick": registry.latest_presentation_tick,
        }
        if descender_id is not None:
            request["descender_id"] = descender_id
        before = descent.fingerprint()
        result = registry.apply_request(descent, request)
        fingerprint_immutable = fingerprint_immutable and descent.fingerprint() == before
        requests.append(request)
        request_results.append(result)
        transition = result.get("transition")
        if transition:
            scheduler.queue_focus_transition(transition)
        return result

    def update_registry(ready):
        nonlocal fingerprint_immutable, initial_auto, manual_a, manual_b
        before = descent.fingerprint()
        transitions = registry.update(
            descent,
            ready,
            presentation_tick=scheduler.frame_sequence + 1,
            presentation_seconds=scheduler.presentation_seconds,
            buffered_tick=buffer.latest_authoritative_tick,
            camera_available_ids=presented,
            camera_state=scheduler.camera_director.snapshot(),
        )
        fingerprint_immutable = fingerprint_immutable and descent.fingerprint() == before
        for transition in transitions:
            scheduler.queue_focus_transition(transition.as_dict())
        if initial_auto is None:
            initial_auto = registry.active_focus(qa_viewer_id)["active_descender_id"]
            manual_a = next(item for item in presented if item != initial_auto)
            manual_b = initial_auto

    def poll_and_schedule(*, flush=False):
        nonlocal follow_a_done, follow_b_done, invalid_done, release_done
        nonlocal duplicate_switch_frame_delivered, fingerprint_immutable
        current = sorted(persistence.list_events(descent.id, limit=10000), key=lambda item: (item.tick, item.id))
        new = [item for item in current if item.id not in seen_source_ids]
        seen_source_ids.update(item.id for item in new)
        buffer.push(new)
        ready = buffer.consume_ready(flush=flush)
        if not ready:
            buffer_depths.append(buffer.snapshot()["buffer_depth"])
            return

        update_registry(ready)
        if scripted_controls and len(sent_frames) >= 6 and not follow_a_done:
            apply_request("follow", "follow_manual_a", manual_a)
            follow_a_done = True
        if scripted_controls and len(sent_frames) >= 14 and not follow_b_done:
            result = apply_request("follow", "follow_manual_b", manual_b)
            duplicate = apply_request("follow", "follow_manual_b", manual_b)
            if not duplicate.get("duplicate") or result.get("duplicate"):
                raise RuntimeError("duplicate follow request was not idempotent")
            follow_b_done = True
        if scripted_controls and len(sent_frames) >= 18 and not invalid_done:
            result = apply_request("follow", "follow_invalid", "unknown_descender")
            if result.get("reason") != "unknown_descender":
                raise RuntimeError("invalid Descender was not rejected explicitly")
            invalid_done = True
        if scripted_controls and len(sent_frames) >= 24 and not release_done:
            apply_request("release", "release_to_auto")
            release_done = True

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
        fingerprint_immutable = fingerprint_immutable and descent.fingerprint() == before
        if frame:
            for item in ready:
                if item.event_type in {"ENEMY_DEFEATED", "CRAWLER_DIED", "CRAWLER_ELIMINATED"}:
                    terminal_source_ticks.append(item.tick)
                    terminal_source_ids.append(item.id)
            deliver(frame)
            registry.latest_frame_id = frame["frame_id"]
            registry.viewers[qa_viewer_id].last_seen_frame_id = frame["frame_id"]
            if len(sent_frames) == 1:
                deliver(frame, duplicate=True)
            if (
                not duplicate_switch_frame_delivered
                and any(command.get("focus_reason") == "manual_switch" for command in frame["commands"])
            ):
                deliver(frame, duplicate=True)
                duplicate_switch_frame_delivered = True
        buffer_depths.append(buffer.snapshot()["buffer_depth"])

    poll_and_schedule()
    for _ in range(steps):
        if descent.status.value != "running":
            break
        simulation.step(descent)
        poll_and_schedule()
        time.sleep(poll_seconds)
    poll_and_schedule(flush=True)

    # Advance presentation time after the final Ledger page so automatic mode
    # can complete the accepted death hold and acquire later living activity.
    for _ in range(10):
        before = descent.fingerprint()
        transitions = registry.update(
            descent,
            [],
            presentation_tick=scheduler.frame_sequence + 1,
            presentation_seconds=scheduler.presentation_seconds,
            buffered_tick=buffer.latest_authoritative_tick,
            camera_available_ids=presented,
            camera_state=scheduler.camera_director.snapshot(),
        )
        fingerprint_immutable = fingerprint_immutable and descent.fingerprint() == before
        for transition in transitions:
            scheduler.queue_focus_transition(transition.as_dict())
        frame = scheduler.schedule([], authoritative_tick=descent.current_tick)
        if frame:
            deliver(frame)
            registry.latest_frame_id = frame["frame_id"]
            registry.viewers[qa_viewer_id].last_seen_frame_id = frame["frame_id"]

    if scripted_controls and not all((follow_a_done, follow_b_done, invalid_done, release_done)):
        raise RuntimeError("multichannel QA did not exercise the complete manual request sequence")
    if not scripted_controls:
        manual_transitions = [
            item for item in registry.transitions
            if item.mode == "manual" and item.reason in {"manual_follow", "manual_switch"}
        ]
        if len(manual_transitions) < 2 or len({item.to_descender_id for item in manual_transitions[:2]}) < 2 or registry.release_requests < 1:
            raise RuntimeError("spectator viewer QA did not exercise manual A-to-B follow and Auto release")
        follow_a_done = follow_b_done = release_done = True
        invalid_done = bool(registry.invalid_requests)
        manual_a = manual_transitions[0].to_descender_id
        manual_b = manual_transitions[1].to_descender_id
    if not terminal_source_ticks:
        raise RuntimeError("multichannel QA did not consume a canonical terminal Ledger event")
    if not fingerprint_immutable:
        raise RuntimeError("Feed projection or follow switching mutated authoritative truth")
    if not duplicate_switch_frame_delivered or reference_consumer.duplicate_frames != 2:
        raise RuntimeError("duplicate bridge delivery after focus switch was not proven")

    last_terminal_tick = max(terminal_source_ticks)
    all_events = persistence.list_events(descent.id, limit=10000)
    events_after_terminal = sum(item.tick > last_terminal_tick for item in all_events)
    if events_after_terminal < 1:
        raise RuntimeError("canonical activity did not continue after the terminal event")

    # Read every logical channel and prove the projection itself leaves truth
    # untouched. Only the two accepted mannequin slots are camera-available.
    before = descent.fingerprint()
    channels = registry.directory(descent, viewer_id=qa_viewer_id)
    fingerprint_immutable = fingerprint_immutable and descent.fingerprint() == before
    if len(channels) != len(QA_DESCENDERS):
        raise RuntimeError("logical Feed channel directory is incomplete")

    registry_snapshot = registry.reconnect_snapshot()
    restored_registry = FeedChannelRegistry(descent.id, default_viewer_id=qa_viewer_id)
    restored_registry.register(descent)
    restored_registry.restore(registry_snapshot)
    reconnect_focus_ok = restored_registry.active_focus(qa_viewer_id) == registry.active_focus(qa_viewer_id)

    scheduler_snapshot = scheduler.reconnect_snapshot(
        descent,
        environment_digest=bootstrap["environment"].get("digest", bootstrap["digest"]),
    )
    resumed = LivePresentationConsumer(descent.id)
    resumed.apply_resume_snapshot(scheduler_snapshot)
    reconnect_scheduler_ok = (
        resumed.latest_frame_sequence == scheduler.frame_sequence
        and resumed.terminal_actor_ids == scheduler.terminal_actor_ids
        and resumed.camera_state == scheduler_snapshot["camera_state"]
    )
    if not reconnect_focus_ok or not reconnect_scheduler_ok:
        raise RuntimeError("multichannel reconnect did not restore focus/camera/cursor")

    camera_debug = scheduler.camera_director.diagnostics(scheduler.presentation_seconds + 4.0)
    focus_to_camera = {
        command.get("focus_transition_id"): command
        for command in scheduler.camera_director.command_stream
        if command.get("focus_transition_id")
    }
    focus_ledger = []
    request_camera_latencies = []
    request_visible_latencies = []
    for transition in registry.transitions:
        item = transition.as_dict()
        camera_command = focus_to_camera.get(transition.transition_id)
        item["camera_shot_id"] = camera_command.get("shot_id") if camera_command else None
        item["camera_seconds"] = camera_command.get("presentation_seconds") if camera_command else None
        if transition.request_id and camera_command:
            latency = max(0.0, float(camera_command["presentation_seconds"]) - transition.presentation_seconds)
            request_camera_latencies.append(latency)
            request_visible_latencies.append(latency + 1.0 / 60.0)
        focus_ledger.append(item)

    registry_debug = registry.diagnostics()
    registry_debug.update({
        "qa_seed": QA_SEED,
        "qa_viewer_id": qa_viewer_id,
        "qa_presented_descender_ids": list(presented),
        "qa_descender_count": len(QA_DESCENDERS),
        "initial_automatic_focus": initial_auto,
        "manual_follow_sequence": [manual_a, manual_b],
        "request_results": request_results,
        "reconnect_focus_result": "passed" if reconnect_focus_ok else "failed",
        "feed_fingerprint_immutable": fingerprint_immutable,
        "channel_registry_memory_bytes": len(json.dumps(channels, sort_keys=True).encode("utf-8")),
        "average_request_to_camera_latency_seconds": sum(request_camera_latencies) / max(1, len(request_camera_latencies)),
        "maximum_request_to_camera_latency_seconds": max(request_camera_latencies or [0.0]),
        "average_request_to_visible_focus_latency_seconds": sum(request_visible_latencies) / max(1, len(request_visible_latencies)),
        "maximum_request_to_visible_focus_latency_seconds": max(request_visible_latencies or [0.0]),
    })
    _atomic_json(spool.parent / "feed_channels_debug.json", registry_debug)
    _atomic_json(spool.parent / "feed_focus_ledger.json", {
        "protocol": "underreach.feed-focus-ledger.v1",
        "authoritative": False,
        "descent_id": descent.id,
        "transitions": focus_ledger,
        "focus_sequence_digest": registry_debug["focus_sequence_digest"],
    })

    scheduler_debug = scheduler.diagnostics()
    scheduler_debug.update({
        "qa_seed": QA_SEED,
        "simulation_steps": steps,
        "simulation_duration_ticks": descent.current_tick,
        "terminal_source_event_ids": terminal_source_ids,
        "events_after_last_terminal": events_after_terminal,
        "authoritative_fingerprint": descent.fingerprint(),
        "feed_fingerprint_immutable": fingerprint_immutable,
    })
    _atomic_json(spool.parent / "live_scheduler_debug.json", scheduler_debug)
    camera_debug.update({
        "qa_seed": QA_SEED,
        "presentation_delay_ticks": buffer.presentation_delay_ticks,
        "camera_lookahead_ticks": camera_config.camera_lookahead_ticks,
        "reconnect_restore_result": "passed" if reconnect_scheduler_ok else "failed",
        "active_channel_focus": registry.active_focus(qa_viewer_id),
    })
    _atomic_json(spool.parent / "live_camera_debug.json", camera_debug)
    _atomic_json(spool.parent / "live_camera_shots.json", {
        "protocol": camera_debug["protocol"],
        "descent_id": descent.id,
        "shots": camera_debug["shots"],
        "command_digest": camera_debug["command_digest"],
    })

    producer_debug = {
        "protocol": "underreach.multichannel-producer-debug.v1",
        "descent_id": descent.id,
        "qa_seed": QA_SEED,
        "simulation_steps": steps,
        "simulation_duration_ticks": descent.current_tick,
        "total_authoritative_ledger_events": len(seen_source_ids),
        "total_buffered_events": buffer.accepted_event_count,
        "total_consumed_events": len(scheduler.processed_event_ids),
        "bootstrap_count": scheduler.bootstrap_count,
        "incremental_frame_count": len(sent_frames),
        "delivery_count": delivery_index,
        "intentional_duplicate_deliveries": 2,
        "reference_consumer_duplicate_frames": reference_consumer.duplicate_frames,
        "reference_consumer_rejected_frames": reference_consumer.rejected_frames,
        "reconnect_result": "passed" if reconnect_scheduler_ok and reconnect_focus_ok else "failed",
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
        "feed_fingerprint_immutable": fingerprint_immutable,
        "logical_channel_count": len(channels) + 1,
        "presented_descender_count": len(presented),
        "population_proof": population_proof,
    }
    _atomic_json(spool.parent / "live_producer_debug.json", producer_debug)
    _atomic_json(spool / "resume_snapshot.json", scheduler_snapshot)
    _atomic_json(spool / "producer_complete.json", producer_debug)

    viewer_finished = True
    if viewer_projector is not None:
        final_viewer_state = viewer_projector.state(qa_viewer_id)
        _atomic_json(spool.parent / "viewer_state_snapshot.json", final_viewer_state)
        viewer_debug = viewer_projector.diagnostics()
        viewer_debug.update({
            "qa_seed": QA_SEED,
            "viewer_id": qa_viewer_id,
            "descent_id": descent.id,
            "final_connection_state": final_viewer_state["connection"]["state"],
            "final_focus_mode": final_viewer_state["focus"]["mode"],
            "final_active_descender_id": final_viewer_state["focus"]["active_descender_id"],
            "terminal_descender_count": final_viewer_state["summary"]["fallen_descender_count"],
            "feed_fingerprint_immutable": fingerprint_immutable,
        })
        _atomic_json(spool.parent / "viewer_debug.json", viewer_debug)
    if viewer_hold_seconds > 0:
        time.sleep(viewer_hold_seconds)
    if viewer_server is not None:
        viewer_server.should_exit = True
        if viewer_thread is not None:
            viewer_thread.join(timeout=10.0)
    return producer_debug


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spool", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=90)
    parser.add_argument("--poll-seconds", type=float, default=0.05)
    parser.add_argument("--external-controls", action="store_true")
    parser.add_argument("--viewer-host")
    parser.add_argument("--viewer-port", type=int, default=8011)
    parser.add_argument("--viewer-static-directory", type=Path)
    parser.add_argument("--viewer-hold-seconds", type=float, default=0.0)
    parser.add_argument("--population-proof", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(
        args.spool,
        steps=args.steps,
        poll_seconds=args.poll_seconds,
        scripted_controls=not args.external_controls,
        viewer_host=args.viewer_host,
        viewer_port=args.viewer_port,
        viewer_static_directory=args.viewer_static_directory,
        viewer_hold_seconds=args.viewer_hold_seconds,
        population_proof=args.population_proof,
    ), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
