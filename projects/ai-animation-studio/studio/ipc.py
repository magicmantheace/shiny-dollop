"""Structured director-to-engine IPC contract (F2.4).

Formalizes the channel that already existed informally: the director side
(the CLI) writes a scene document into the preview's data directory and the
engine picks it up at startup. The transport is unchanged — offline,
file-based, one JSON document per message — but the document is now a
versioned envelope with a defined shape, and the engine answers with a
result document the director can read back.

Envelope (director -> engine):

    {"ipc_version": "1.0.0", "kind": "scene",
     "issued_at": "<ISO-8601 UTC>", "payload": <scene document>}

Result (engine -> director):

    {"ipc_version": "1.0.0", "kind": "result", "scene_id": <id>,
     "accepted": true|false, "detail": "<human-readable reason>"}

`ipc_version` versions the envelope itself and is independent of the
scene's `schema_version` (studio/schema.py VERSION): envelope "1.0.0"
carries scene schema "1.0.0". An unknown version or kind is refused with
an `IpcError` naming the reason — never guessed at or partially applied.
The Godot preview mirrors IPC_VERSION in godot/main.gd (parity guarded by
tests/test_ipc.py) and writes its result to `scene_result.json` next to
the runtime scene; bare (unenveloped) scene files still load exactly as
before and are not acknowledged.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

try:
    from .schema import ID, ValidationError, validate_scene
except ImportError:  # standalone module use (studio/ on sys.path)
    from schema import ID, ValidationError, validate_scene  # type: ignore[no-redef]

IPC_VERSION = "1.0.0"
SCENE_KIND = "scene"
RESULT_KIND = "result"

_ENVELOPE_KEYS = frozenset({"ipc_version", "kind", "issued_at", "payload"})
_RESULT_KEYS = frozenset({"ipc_version", "kind", "scene_id", "accepted", "detail"})


class IpcError(ValueError):
    """An IPC envelope or result document was refused, with a named reason."""


def _check_version(doc: dict, what: str) -> None:
    version = doc.get("ipc_version")
    if version != IPC_VERSION:
        raise IpcError(
            f"{what}: unsupported ipc_version {version!r} (expected {IPC_VERSION!r})")


def _check_keys(doc: dict, allowed: frozenset, what: str) -> None:
    unknown = set(doc) - allowed
    if unknown:
        raise IpcError(f"{what}: unknown keys {sorted(unknown)}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def wrap_scene(scene: dict, issued_at: str | None = None) -> dict:
    """Validate a scene and wrap it in a director->engine envelope."""
    validate_scene(scene)
    if issued_at is None:
        issued_at = _utc_now()
    if not isinstance(issued_at, str) or not issued_at:
        raise IpcError("issued_at must be a non-empty ISO-8601 string")
    return {
        "ipc_version": IPC_VERSION,
        "kind": SCENE_KIND,
        "issued_at": issued_at,
        "payload": scene,
    }


def unwrap_scene(envelope: dict) -> dict:
    """Validate an envelope and return its scene payload, fully validated."""
    if not isinstance(envelope, dict):
        raise IpcError("ipc envelope must be a JSON object")
    _check_keys(envelope, _ENVELOPE_KEYS, "ipc envelope")
    _check_version(envelope, "ipc envelope")
    kind = envelope.get("kind")
    if kind != SCENE_KIND:
        raise IpcError(f"ipc envelope: unknown kind {kind!r} (expected {SCENE_KIND!r})")
    if "issued_at" in envelope:
        issued = envelope["issued_at"]
        if not isinstance(issued, str) or not issued:
            raise IpcError("ipc envelope: issued_at must be a non-empty string")
    if "payload" not in envelope:
        raise IpcError("ipc envelope: missing 'payload'")
    payload = envelope["payload"]
    if not isinstance(payload, dict):
        raise IpcError("ipc envelope: payload must be a scene object")
    try:
        return validate_scene(payload)
    except ValidationError as exc:
        raise IpcError(f"ipc envelope: payload failed scene validation: {exc}") from exc


def write_ipc(path: Path, scene: dict, issued_at: str | None = None) -> dict:
    """Wrap a scene and write it as the engine's runtime document."""
    envelope = wrap_scene(scene, issued_at=issued_at)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(envelope, indent=2) + "\n", encoding="utf-8")
    return envelope


def _read_json(path: Path, what: str) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IpcError(f"cannot read {what} file {path}: {exc}") from exc
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IpcError(f"invalid JSON in {what} file {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise IpcError(f"{what} file {path} must contain a JSON object")
    return doc


def read_ipc(path: Path) -> dict:
    """Read an enveloped scene document and return the validated scene."""
    return unwrap_scene(_read_json(path, "ipc"))


def make_result(scene_id: str, accepted: bool, detail: str) -> dict:
    """Build a validated engine->director result document."""
    doc = {
        "ipc_version": IPC_VERSION,
        "kind": RESULT_KIND,
        "scene_id": scene_id,
        "accepted": accepted,
        "detail": detail,
    }
    return validate_result(doc)


def validate_result(doc: dict) -> dict:
    """Shape-check a result document; returns it unchanged when valid."""
    if not isinstance(doc, dict):
        raise IpcError("result document must be a JSON object")
    _check_keys(doc, _RESULT_KEYS, "result document")
    _check_version(doc, "result document")
    kind = doc.get("kind")
    if kind != RESULT_KIND:
        raise IpcError(f"result document: unknown kind {kind!r} (expected {RESULT_KIND!r})")
    scene_id = doc.get("scene_id")
    if not isinstance(scene_id, str) or not ID.fullmatch(scene_id):
        raise IpcError(f"result document: invalid scene_id {scene_id!r}")
    if type(doc.get("accepted")) is not bool:
        raise IpcError("result document: accepted must be a boolean")
    detail = doc.get("detail")
    if not isinstance(detail, str) or len(detail) > 1000:
        raise IpcError("result document: detail must be a string of at most 1000 chars")
    return doc


def write_result(path: Path, scene_id: str, accepted: bool, detail: str) -> dict:
    """Build, validate and write a result document; returns the document."""
    doc = make_result(scene_id, accepted, detail)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return doc


def read_result(path: Path) -> dict:
    """Read and validate a result document written by the engine side."""
    return validate_result(_read_json(path, "result"))
