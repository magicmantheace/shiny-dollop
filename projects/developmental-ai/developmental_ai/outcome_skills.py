"""Evidence-based, bounded reusable symbolic action effects; simulations only.

Opaque per-episode action identifiers rotate. Public glyphs and fact vocabulary
are *engineered* shared semantics, not learned language understanding.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from collections import Counter

SCHEMA = "developmental-ai.outcome-skills/v1"
MAX_HISTORY = 4000
MAX_FACTS = 32
MAX_TOKEN = 64
MAX_CHECKPOINT_BYTES = 4 * 1024 * 1024


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def check_frame(frame):
    if (type(frame) is not dict or set(frame) != {"schema", "episode", "tick", "remaining", "facts", "actions", "goal", "done", "scope"}
        or frame["schema"] != SCHEMA or frame["scope"] != "simulation-only"
        or type(frame["episode"]) is not str or len(frame["episode"]) != 64
        or type(frame["tick"]) is not int or frame["tick"] < 0
        or type(frame["remaining"]) is not int or frame["remaining"] < 0
        or type(frame["done"]) is not bool
        or type(frame["facts"]) is not list or len(frame["facts"]) > MAX_FACTS
        or any(type(x) is not str or not x or len(x) > MAX_TOKEN for x in frame["facts"])
        or frame["facts"] != sorted(set(frame["facts"]))
        or type(frame["actions"]) is not list or len(frame["actions"]) > 24):
        raise ValueError("invalid public frame")
    aliases, glyphs = set(), set()
    for a in frame["actions"]:
        if (type(a) is not dict or set(a) != {"id", "glyph"}
            or any(type(x) is not str or not x or len(x) > 128 for x in a.values())
            or a["id"] in aliases or a["glyph"] in glyphs):
            raise ValueError("invalid action descriptors")
        aliases.add(a["id"]); glyphs.add(a["glyph"])
    if (type(frame["goal"]) is not str or
        (not frame["done"] and frame["goal"] not in aliases) or
        (frame["done"] and frame["actions"] != [])):
        raise ValueError("invalid target action")
    return frame


class OutcomeSkills:
    """Learn observed effects and *candidate* prerequisites from successful steps.

    Prerequisites are intersections of co-present facts, so a correlated fact
    may be mistaken for a cause. Neither acceptance alone nor a checksum proves
    causal understanding. No executable tool/system action interface exists.
    """

    def __init__(self):
        self.events = []
        self._success = {}

    def observe(self, glyph, before, after, accepted):
        if (type(glyph) is not str or not glyph or len(glyph) > MAX_TOKEN or type(accepted) is not bool
            or type(before) is not list or type(after) is not list
            or len(before) > MAX_FACTS or len(after) > MAX_FACTS
            or any(type(x) is not str or not x or len(x) > MAX_TOKEN for x in before + after)
            or before != sorted(set(before)) or after != sorted(set(after))
            or len(self.events) >= MAX_HISTORY):
            raise ValueError("invalid or oversized observation")
        if accepted and (not set(before) <= set(after) or len(after) != len(before) + 1):
            raise ValueError("accepted actions must add exactly one fact")
        if not accepted and before != after:
            raise ValueError("blocked action unexpectedly altered facts")
        row = [glyph, list(before), list(after), accepted]
        if accepted:
            effect = next(iter(set(after) - set(before)))
            item = self._success.setdefault(glyph, {"effects": Counter(), "common": None})
            item["effects"][effect] += 1
            item["common"] = set(before) if item["common"] is None else item["common"] & set(before)
        self.events.append(row)

    def knowledge(self):
        return {glyph: {"effects": dict(sorted(item["effects"].items())),
                        "possible_prerequisites": sorted(item["common"]),
                        "successes": sum(item["effects"].values())}
                for glyph, item in sorted(self._success.items())}

    def choose(self, frame, blocked=()):
        """Observation-only action proposal; never consults hidden recipe/truth."""
        check_frame(frame)
        if frame["done"]:
            raise ValueError("finished simulation")
        if type(blocked) not in (tuple, list, set) or any(type(x) is not str for x in blocked):
            raise ValueError("bad local blocked set")
        actions = {item["glyph"]: item["id"] for item in frame["actions"]}
        goal = next(item["glyph"] for item in frame["actions"] if item["id"] == frame["goal"])
        facts = set(frame["facts"])
        blocked_glyphs = {g for g, a in actions.items() if a in blocked}
        learned = self.knowledge()

        def path_to(glyph, seen):
            if glyph in seen or glyph not in actions or glyph in blocked_glyphs:
                return None
            item = learned.get(glyph)
            if not item:
                return None
            known_effects = set(item["effects"])
            if known_effects <= facts:
                return None
            for requirement in item["possible_prerequisites"]:
                if requirement in facts:
                    continue
                sources = sorted((other for other, entry in learned.items()
                                  if requirement in entry["effects"] and other in actions))
                for source in sources:
                    sub = path_to(source, seen | {glyph})
                    if sub is not None:
                        return sub
                return None
            return glyph

        # Known-goal actions with learned prerequisites take priority.
        if goal in learned and goal not in blocked_glyphs:
            option = path_to(goal, set())
            if option is not None:
                return actions[option]
        # An unknown goal is probed once, then prepare the most complex
        # previously learned subskills before retrying the goal.
        if goal not in learned and frame["tick"] == 0:
            return actions[goal]
        known = sorted((g for g in learned if g != goal and g in actions),
                       key=lambda g: (-len(learned[g]["possible_prerequisites"]), g))
        for glyph in known:
            candidate = path_to(glyph, set())
            if candidate is not None:
                return actions[candidate]
        if goal not in blocked_glyphs:
            return actions[goal]
        unknown = sorted(g for g in actions if g not in learned and g not in blocked_glyphs and g != goal)
        if unknown:
            return actions[unknown[0]]
        remaining = sorted(g for g in actions if g not in blocked_glyphs and g != goal)
        return actions[remaining[0]] if remaining else actions[goal]

    def record(self):
        if not self.events:
            raise ValueError("no training evidence")
        state = {"schema": SCHEMA, "events": self.events, "knowledge": self.knowledge()}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    def save(self, path):
        """Atomically save a bounded local checkpoint; caller controls its path."""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = canonical(self.record()) + "\n"
        if len(payload.encode("utf-8")) > MAX_CHECKPOINT_BYTES:
            raise ValueError("skill checkpoint exceeds size limit")
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=target.parent,
                                             prefix=".skill-pending-", delete=False) as file:
                temp_path = Path(file.name)
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp_path, target)
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)

    @classmethod
    def load(cls, path):
        source = Path(path)
        if source.stat().st_size > MAX_CHECKPOINT_BYTES:
            raise ValueError("skill checkpoint exceeds size limit")
        return cls.restore(json.loads(source.read_text(encoding="utf-8")))

    @classmethod
    def restore(cls, saved):
        if (type(saved) is not dict or set(saved) != {"state", "sha256"}
            or type(saved["state"]) is not dict or saved["sha256"] != digest(saved["state"])):
            raise ValueError("invalid stored skill integrity")
        state = saved["state"]
        if (set(state) != {"schema", "events", "knowledge"} or state["schema"] != SCHEMA
            or type(state["events"]) is not list or not 1 <= len(state["events"]) <= MAX_HISTORY):
            raise ValueError("incompatible memory schema")
        learner = cls()
        for row in state["events"]:
            if type(row) is not list or len(row) != 4:
                raise ValueError("invalid saved observation")
            learner.observe(*row)
        if learner.record() != saved:
            raise ValueError("learned skill knowledge does not replay")
        return learner
