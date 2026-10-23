"""Atomic canonical checkpoints for the unattended Underreach runtime."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any, Iterable

from .crawl_domain import Crawl, CrawlEvent


CHECKPOINT_PROTOCOL = "underreach.alpha-checkpoint.v1"
CHECKPOINT_VERSION = "28c2.1"


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def payload_digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def ledger_digest(events: Iterable[CrawlEvent]) -> str:
    ordered = sorted(events, key=lambda item: (item.tick, item.id))
    return payload_digest([item.model_dump(mode="json") for item in ordered])


@dataclass(frozen=True)
class LoadedCheckpoint:
    path: Path
    payload: dict[str, Any]
    crawl: Crawl


class CheckpointError(RuntimeError):
    pass


class AlphaCheckpointStore:
    """Write, validate, retain, and discover canonical runtime checkpoints.

    The SQLite Ledger remains the durable event store.  A checkpoint records
    the complete canonical Descent state and a digest of the exact Ledger
    prefix that state references.  Resume refuses to continue if that prefix
    cannot be proven from persistence.
    """

    def __init__(self, directory: str | Path, *, retention: int = 12) -> None:
        if retention < 2:
            raise ValueError("checkpoint retention must be at least 2")
        self.directory = Path(directory)
        self.retention = retention
        self.latest_path = self.directory / "latest.json"

    @staticmethod
    def _body(
        runtime_id: str,
        crawl: Crawl,
        events: list[CrawlEvent],
        *,
        simulation_config: dict[str, Any],
        presentation_snapshot: dict[str, Any] | None,
        feed_snapshot: dict[str, Any] | None,
        reason: str,
        created_at_unix_ms: int,
    ) -> dict[str, Any]:
        by_id = {item.id: item for item in events}
        ids = list(crawl.history_event_ids)
        if len(by_id) != len(ids) or set(by_id) != set(ids):
            raise CheckpointError("canonical state and durable Ledger disagree")
        ordered = [by_id[event_id] for event_id in ids]
        return {
            "protocol": CHECKPOINT_PROTOCOL,
            "checkpoint_version": CHECKPOINT_VERSION,
            "runtime_id": runtime_id,
            "reason": reason,
            "created_at_unix_ms": int(created_at_unix_ms),
            "canonical": {
                "descent_id": crawl.id,
                "seed": crawl.seed,
                "tick": crawl.current_tick,
                "state": crawl.model_dump(mode="json"),
                "simulation_fingerprint": crawl.fingerprint(),
                "rng_state": "stateless_sha256_seed_tick",
                "simulation_config": json.loads(canonical_json(simulation_config)),
                "ledger_cursor": {
                    "event_count": len(ordered),
                    "last_event_id": ids[-1] if ids else None,
                    "last_event_tick": ordered[-1].tick if ordered else None,
                    "event_ids_digest": payload_digest(ids),
                    "ledger_digest": ledger_digest(ordered),
                },
            },
            "presentation": json.loads(canonical_json(presentation_snapshot)) if presentation_snapshot else None,
            "feed": json.loads(canonical_json(feed_snapshot)) if feed_snapshot else None,
        }

    @staticmethod
    def validate(payload: dict[str, Any]) -> Crawl:
        if payload.get("protocol") != CHECKPOINT_PROTOCOL:
            raise CheckpointError("unsupported checkpoint protocol")
        supplied = payload.get("digest")
        body = {key: value for key, value in payload.items() if key != "digest"}
        if not isinstance(supplied, str) or supplied != payload_digest(body):
            raise CheckpointError("checkpoint digest mismatch")
        canonical = body.get("canonical")
        if not isinstance(canonical, dict):
            raise CheckpointError("checkpoint canonical state is missing")
        crawl = Crawl.model_validate(canonical.get("state"))
        if crawl.id != canonical.get("descent_id") or crawl.seed != canonical.get("seed"):
            raise CheckpointError("checkpoint identity does not match canonical state")
        if crawl.current_tick != canonical.get("tick"):
            raise CheckpointError("checkpoint tick does not match canonical state")
        if crawl.fingerprint() != canonical.get("simulation_fingerprint"):
            raise CheckpointError("checkpoint simulation fingerprint mismatch")
        cursor = canonical.get("ledger_cursor") or {}
        ids = list(crawl.history_event_ids)
        if int(cursor.get("event_count", -1)) != len(ids):
            raise CheckpointError("checkpoint Ledger cursor count mismatch")
        if cursor.get("last_event_id") != (ids[-1] if ids else None):
            raise CheckpointError("checkpoint Ledger cursor tail mismatch")
        if cursor.get("event_ids_digest") != payload_digest(ids):
            raise CheckpointError("checkpoint Ledger ID digest mismatch")
        return crawl

    def write(
        self,
        runtime_id: str,
        crawl: Crawl,
        events: list[CrawlEvent],
        *,
        simulation_config: dict[str, Any],
        presentation_snapshot: dict[str, Any] | None = None,
        feed_snapshot: dict[str, Any] | None = None,
        reason: str = "scheduled",
        created_at_unix_ms: int,
    ) -> LoadedCheckpoint:
        self.directory.mkdir(parents=True, exist_ok=True)
        body = self._body(
            runtime_id,
            crawl,
            events,
            simulation_config=simulation_config,
            presentation_snapshot=presentation_snapshot,
            feed_snapshot=feed_snapshot,
            reason=reason,
            created_at_unix_ms=created_at_unix_ms,
        )
        payload = {**body, "digest": payload_digest(body)}
        filename = f"checkpoint-{crawl.current_tick:010d}-{payload['digest'][:12]}.json"
        path = self.directory / filename
        temporary = path.with_suffix(".json.tmp")
        encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
        with temporary.open("wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        reread = json.loads(temporary.read_text(encoding="utf-8"))
        self.validate(reread)
        os.replace(temporary, path)
        pointer = {
            "protocol": "underreach.alpha-checkpoint-pointer.v1",
            "path": path.name,
            "digest": payload["digest"],
            "tick": crawl.current_tick,
            "descent_id": crawl.id,
        }
        pointer_tmp = self.latest_path.with_suffix(".json.tmp")
        pointer_tmp.write_text(json.dumps(pointer, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(pointer_tmp, self.latest_path)
        self._prune(exclude=path)
        return LoadedCheckpoint(path=path, payload=payload, crawl=crawl.model_copy(deep=True))

    def _prune(self, *, exclude: Path) -> None:
        candidates = sorted(
            (item for item in self.directory.glob("checkpoint-*.json") if item != exclude),
            key=lambda item: item.stat().st_mtime_ns,
            reverse=True,
        )
        for stale in candidates[max(0, self.retention - 1) :]:
            stale.unlink(missing_ok=True)

    def load_latest(self) -> LoadedCheckpoint:
        if self.latest_path.exists():
            try:
                pointer = json.loads(self.latest_path.read_text(encoding="utf-8"))
                candidates = [self.directory / str(pointer["path"])]
            except (OSError, KeyError, TypeError, json.JSONDecodeError):
                candidates = []
        else:
            candidates = []
        candidates.extend(
            item for item in sorted(self.directory.glob("checkpoint-*.json"), reverse=True)
            if item not in candidates
        )
        errors: list[str] = []
        for path in candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                crawl = self.validate(payload)
                return LoadedCheckpoint(path=path, payload=payload, crawl=crawl)
            except (OSError, ValueError, TypeError, json.JSONDecodeError, CheckpointError) as exc:
                errors.append(f"{path.name}: {exc}")
        raise CheckpointError("no valid checkpoint available" + (f" ({'; '.join(errors)})" if errors else ""))
