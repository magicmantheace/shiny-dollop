"""Missing-action reports (F5.2): scene clip needs vs the manifest map.

A scene's events make the Godot preview play animation clips by
*semantic key*: the manifest's ``clips`` table maps each key to a clip
in an approved animation file, and dispatch looks keys up in that map
(``_play_tag_on`` in godot/main.gd warns "No clip mapped for tag ..."
and plays nothing when a key is absent). A missing key is therefore a
real, nameable capability gap — the action is in the scene but the
library cannot perform it — which is exactly what this report lists.

The need mapping below is derived from the preview's dispatch code,
not invented per op:

- ``spawn`` plays the ``idle`` clip on the base player right after
  the actor appears (``_dispatch`` spawn branch).
- ``move`` plays ``walk`` on the base player while travelling; on
  arrival it re-plays ``idle``, which the actor's spawn already
  requires, so ``idle`` is attributed to the spawn event only.
- ``speak`` plays the ``speak`` gesture on the overlay player
  (``_play_overlay_tag``; the base player is the fallback when an
  actor has no overlay — the key is the same either way).
- ``emote`` consumes NO clip in the current preview: dispatch only
  prints the emotion line. The manifest's ``emote_*`` keys are not
  referenced by any dispatch path, so emote events never produce
  records here. If emote gains clip dispatch, its need belongs in
  this table at the same time.
- ``camera`` consumes no clip (it only frames a shot).
- ``interact`` (``_dispatch_interact``): ``pick_up`` plays ``pickup``
  and ``drink`` plays ``consume`` and ``put_down`` plays ``interact``,
  all on the overlay player; ``sit`` plays ``sit_enter`` then settles
  into ``sit_idle``, both on the base player.

`missing_action_report` is a pure function: the scene is expected to
have passed `validate_scene` (the job handler and the CLI validate
first), unknown ops/actions are ignored rather than guessed at, and
the input is never mutated.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping

# (op, interact action or None) -> ((clip key, dispatch beat), ...).
# The beat names where in godot/main.gd the key is requested, so a
# record's reason can point at the real consumer.
CLIP_NEEDS: dict[tuple[str, str | None], tuple[tuple[str, str], ...]] = {
    ("spawn", None): (
        ("idle", "spawn plays the 'idle' clip on the base player"),
    ),
    ("move", None): (
        ("walk", "move plays the 'walk' clip on the base player "
                 "while travelling"),
    ),
    ("speak", None): (
        ("speak", "speak plays the 'speak' gesture clip on the "
                  "overlay player"),
    ),
    ("interact", "pick_up"): (
        ("pickup", "interact pick_up plays the 'pickup' clip on the "
                   "overlay player"),
    ),
    ("interact", "drink"): (
        ("consume", "interact drink plays the 'consume' clip on the "
                    "overlay player"),
    ),
    ("interact", "put_down"): (
        ("interact", "interact put_down plays the 'interact' clip on "
                     "the overlay player"),
    ),
    ("interact", "sit"): (
        ("sit_enter", "interact sit plays the 'sit_enter' clip on "
                      "the base player"),
        ("sit_idle", "interact sit settles into the 'sit_idle' clip "
                     "on the base player"),
    ),
}


def clip_keys_from_manifest(manifest: object) -> list[str]:
    """The sorted clip keys a manifest document provides."""
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    clips = manifest.get("clips", {})
    if not isinstance(clips, dict):
        raise ValueError("manifest 'clips' must be a JSON object")
    return sorted(clips)


def missing_action_report(scene: dict,
                          clip_keys: Iterable[str] | Mapping) -> list[dict]:
    """One record per clip key a scene event needs but the map lacks.

    `clip_keys` is the set of provided keys — an iterable of key
    strings, or a mapping (e.g. a manifest's ``clips`` table) whose
    keys are used. Each record is {"scene_id", "event_index", "op",
    "actor_id", "needed", "reason"}; events whose needs are fully
    covered produce no records, so a covered scene returns [].
    """
    provided = (set(clip_keys) if not isinstance(clip_keys, Mapping)
                else set(clip_keys.keys()))
    scene_id = scene.get("scene_id")
    records = []
    for index, event in enumerate(scene.get("events", [])):
        if not isinstance(event, dict):
            continue
        op = event.get("op")
        action = event.get("action") if op == "interact" else None
        needs = CLIP_NEEDS.get((op, action))
        if not needs:
            continue
        for key, beat in needs:
            if key in provided:
                continue
            records.append({
                "scene_id": scene_id,
                "event_index": index,
                "op": op,
                "actor_id": event.get("actor_id"),
                "needed": key,
                "reason": (f"clip key '{key}' is absent from the clip "
                           f"map: {beat}"),
            })
    return records
