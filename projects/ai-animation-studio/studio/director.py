"""Local LLM direction (F3 slice 1): adapter interface + bounded planner.

An *adapter* proposes a candidate scene document for a director context.
Its output is UNTRUSTED: a proposal is data, never commands. Nothing an
adapter returns is scheduled, written or executed until the bounded
planner has run it through the full scene validator (`validate_scene`)
and the IPC envelope validation (`wrap_scene`) — the prompt/output
separation rule from AGENTS.md. The planner never writes files or
runtime state; it returns a `PlanResult` and the CLI/IPC layer decides
what to persist.

Adapters:

- `StubAdapter` — deterministic, offline, no randomness: stages the
  context's cast + lines as a small conversation scene. Always
  available; doubles as the planner's fallback and the test fixture.
- `HttpAdapter` — talks to a local Ollama-style HTTP endpoint
  (`/api/generate`) using only the stdlib. Loopback endpoints only —
  no cloud endpoint is accepted, ever. The HTTP call goes through an
  injectable `transport` callable so tests exercise the full
  request/parse path without a server.

Director context (a plain dict, JSON-shaped):

    {"scene_id": "planned_scene", "environment_id": "preview_stage",
     "cast":  [{"id": ..., "recipe_id": ..., "color": "#rrggbb"}, ...],
     "lines": [{"actor_id": ..., "line": ...}, ...]}

On a retry the planner adds a "rejection" key naming why the previous
candidate was refused; adapters may use it (HttpAdapter quotes it in
the prompt) or ignore it (StubAdapter does).
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

try:
    from .ipc import IpcError, wrap_scene
    from .schema import ValidationError, validate_scene
    from .timing import DEFAULT_TIMING, speak_hold_ms
except ImportError:  # standalone module use (studio/ on sys.path)
    from ipc import IpcError, wrap_scene  # type: ignore[no-redef]
    from schema import ValidationError, validate_scene  # type: ignore[no-redef]
    from timing import DEFAULT_TIMING, speak_hold_ms  # type: ignore[no-redef]


class AdapterError(ValueError):
    """An adapter could not produce a candidate (bad context, transport
    failure, or an unparseable / incomplete model reply)."""


class PlannerError(ValueError):
    """Every attempt was rejected AND the stub fallback could not produce
    a valid scene, so no plan exists. The message names all reasons."""


# ---------------------------------------------------------------------------
# Stub adapter
# ---------------------------------------------------------------------------

_FIRST_SPEAK_MS = 800
_LINE_GAP_MS = 400
_CAMERA_TAIL_MS = 600


class StubAdapter:
    """Deterministic offline proposer: stages the context as written.

    Cast members spawn at t=0 spread across the stage; lines are spoken
    in order, each next line starting after the previous line's speak
    hold (studio.timing derivation) plus a fixed pause; one camera beat
    closes the scene. Same context in -> byte-identical scene out.
    """

    name = "stub"

    def propose(self, context: dict) -> dict:
        if not isinstance(context, dict):
            raise AdapterError("context must be an object")
        cast = context.get("cast")
        if not isinstance(cast, list) or not cast:
            raise AdapterError("context.cast must be a non-empty list")
        actors = []
        for entry in cast:
            if not isinstance(entry, dict) or not all(
                isinstance(entry.get(key), str) and entry.get(key)
                for key in ("id", "recipe_id", "color")
            ):
                raise AdapterError(
                    "context.cast entries need string id, recipe_id and color")
            actors.append({
                "id": entry["id"],
                "recipe_id": entry["recipe_id"],
                "color": entry["color"],
            })
        lines = context.get("lines")
        if not isinstance(lines, list) or not lines:
            raise AdapterError("context.lines must be a non-empty list")
        cast_ids = {a["id"] for a in actors}
        for entry in lines:
            if not isinstance(entry, dict) or not isinstance(entry.get("line"), str) \
                    or not entry.get("line"):
                raise AdapterError("context.lines entries need a non-empty line")
            if entry.get("actor_id") not in cast_ids:
                raise AdapterError(
                    f"context.lines actor {entry.get('actor_id')!r} is not in the cast")

        count = len(actors)
        events: list[dict] = []
        for i, actor in enumerate(actors):
            x = (i - (count - 1) / 2) * 3.0
            events.append({
                "at_ms": 0, "op": "spawn", "actor_id": actor["id"],
                "position": [x, 0, 0],
            })
        cursor = _FIRST_SPEAK_MS
        last_hold = 0
        for entry in lines:
            events.append({
                "at_ms": cursor, "op": "speak",
                "actor_id": entry["actor_id"], "line": entry["line"],
            })
            last_hold = speak_hold_ms(entry["line"], timing=DEFAULT_TIMING)
            cursor += last_hold + _LINE_GAP_MS
        events.append({
            "at_ms": cursor - _LINE_GAP_MS + _CAMERA_TAIL_MS,
            "op": "camera",
            "shot": "two_shot" if count >= 2 else "wide",
        })
        return {
            "schema_version": "1.0.0",
            "scene_id": context.get("scene_id", "planned_scene"),
            "environment_id": context.get("environment_id", "preview_stage"),
            "actors": actors,
            "events": events,
        }


# ---------------------------------------------------------------------------
# HTTP adapter (local Ollama-style endpoint)
# ---------------------------------------------------------------------------

_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _urllib_transport(url: str, payload: dict, timeout_s: float) -> dict:
    """Default transport: POST JSON via urllib, return the parsed reply."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, OSError) as exc:
        raise AdapterError(f"transport failed for {url}: {exc}") from exc
    try:
        doc = json.loads(body)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"endpoint reply was not JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise AdapterError("endpoint reply was not a JSON object")
    return doc


def _extract_scene(text: str) -> dict:
    """Pull a scene object out of a model reply, tolerating code fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        fence_lines = stripped.splitlines()[1:]
        if fence_lines and fence_lines[-1].strip().startswith("```"):
            fence_lines = fence_lines[:-1]
        stripped = "\n".join(fence_lines).strip()
    try:
        doc = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start == -1 or end <= start:
            raise AdapterError("model reply contained no JSON object")
        try:
            doc = json.loads(stripped[start:end + 1])
        except json.JSONDecodeError as exc:
            raise AdapterError(f"model reply was not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise AdapterError("model reply JSON was not an object")
    missing = [key for key in ("schema_version", "scene_id", "actors", "events")
               if key not in doc]
    if missing:
        raise AdapterError(f"model reply scene missing fields: {missing}")
    return doc


class HttpAdapter:
    """Proposes scenes via a local Ollama-style `/api/generate` endpoint.

    Loopback only: the constructor refuses any non-loopback or non-http
    endpoint, so this adapter can never call a cloud service. `transport`
    is injectable for tests; the default is a stdlib urllib POST.
    """

    name = "http"
    DEFAULT_ENDPOINT = "http://localhost:11434"
    DEFAULT_MODEL = "qwen2.5:3b"

    def __init__(self, endpoint: str = DEFAULT_ENDPOINT,
                 model: str = DEFAULT_MODEL, transport=None,
                 timeout_s: float = 30.0):
        parsed = urllib.parse.urlparse(endpoint)
        if parsed.scheme != "http" or (parsed.hostname or "") not in _LOOPBACK_HOSTS:
            raise AdapterError(
                f"endpoint must be a loopback http URL (local models only), "
                f"got {endpoint!r}")
        if not isinstance(model, str) or not model:
            raise AdapterError("model must be a non-empty string")
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.transport = transport if transport is not None else _urllib_transport
        self.timeout_s = timeout_s

    def _prompt(self, context: dict) -> str:
        parts = [
            "You are the scene director for an offline animation studio.",
            "Stage the cast and lines below as one scene document.",
            "Reply with ONLY the scene JSON (schema_version \"1.0.0\"): keys "
            "schema_version, scene_id, environment_id, actors, events. "
            "Event ops: spawn, move, speak, emote, camera. Events must be "
            "in nondecreasing at_ms order and every actor must spawn first.",
            f"scene_id: {context.get('scene_id', 'planned_scene')}",
            f"environment_id: {context.get('environment_id', 'preview_stage')}",
            "cast: " + json.dumps(context.get("cast", [])),
            "lines: " + json.dumps(context.get("lines", [])),
        ]
        if context.get("rejection"):
            parts.append(
                f"A previous proposal was rejected: {context['rejection']}. "
                "Fix that problem.")
        return "\n".join(parts)

    def propose(self, context: dict) -> dict:
        if not isinstance(context, dict):
            raise AdapterError("context must be an object")
        url = f"{self.endpoint}/api/generate"
        payload = {
            "model": self.model,
            "prompt": self._prompt(context),
            "stream": False,
            "format": "json",
        }
        try:
            reply = self.transport(url, payload, self.timeout_s)
        except AdapterError:
            raise
        except Exception as exc:  # injected transports may raise anything
            raise AdapterError(f"transport failed for {url}: {exc}") from exc
        if not isinstance(reply, dict):
            raise AdapterError("endpoint reply was not a JSON object")
        text = reply.get("response")
        if not isinstance(text, str) or not text:
            raise AdapterError("endpoint reply missing the 'response' text field")
        return _extract_scene(text)


# ---------------------------------------------------------------------------
# Bounded planner
# ---------------------------------------------------------------------------

@dataclass
class PlanResult:
    """Outcome of a planning run. `scene` is always fully validated.

    `adapter` names the adapter that produced the accepted scene;
    `attempts` counts propose calls made to the requested adapter;
    `rejections` holds one reason per refused attempt, in order;
    `fallback` is True when the scene came from the stub fallback after
    the requested adapter exhausted its attempts.
    """

    scene: dict
    adapter: str
    attempts: int
    rejections: list = field(default_factory=list)
    fallback: bool = False


def plan_scene(adapter, context: dict, *, max_attempts: int = 3) -> PlanResult:
    """Plan one validated scene from `adapter` within `max_attempts`.

    Each candidate runs the full validation gate (`validate_scene` plus
    IPC `wrap_scene`); a refusal is recorded and the next attempt sees
    the reason under the context's "rejection" key. When every attempt
    is refused, the deterministic StubAdapter stages the original
    context and the result is marked as a fallback. Raises PlannerError
    only when even the fallback cannot produce a valid scene (e.g. a
    malformed context). Never writes files or runtime state.
    """
    if type(max_attempts) is not int or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")
    if not isinstance(context, dict):
        raise ValueError("context must be an object")
    adapter_name = getattr(adapter, "name", type(adapter).__name__)
    rejections: list[str] = []
    attempt_context = dict(context)
    for attempt in range(1, max_attempts + 1):
        try:
            candidate = adapter.propose(attempt_context)
        except AdapterError as exc:
            rejections.append(f"attempt {attempt}: adapter error: {exc}")
        else:
            try:
                if not isinstance(candidate, dict):
                    raise ValidationError("candidate scene must be an object")
                validate_scene(candidate)
                wrap_scene(candidate)
            except (ValidationError, IpcError) as exc:
                rejections.append(f"attempt {attempt}: rejected: {exc}")
            else:
                return PlanResult(scene=candidate, adapter=adapter_name,
                                  attempts=attempt, rejections=rejections,
                                  fallback=False)
        attempt_context = {**context, "rejection": rejections[-1]}

    stub = StubAdapter()
    try:
        scene = stub.propose(dict(context))
        validate_scene(scene)
        wrap_scene(scene)
    except (AdapterError, ValidationError, IpcError) as exc:
        raise PlannerError(
            f"all {max_attempts} attempt(s) refused and the stub fallback "
            f"failed ({exc}); rejections: {rejections}") from exc
    return PlanResult(scene=scene, adapter=stub.name, attempts=max_attempts,
                      rejections=rejections, fallback=True)


__all__ = [
    "AdapterError",
    "PlannerError",
    "PlanResult",
    "StubAdapter",
    "HttpAdapter",
    "plan_scene",
]
