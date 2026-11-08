"""Learn action/outcome-conditioned spatial memory updates in one public world.

Training uses *visible relative-target sensor changes* on the public grid API;
zero privileged world coordinates or evaluation episodes. The resulting finite
transition table can maintain a one-slot target-offset memory in an occluded
world. The one-time cue *write* and policy representation are engineered; only
how observations should update the memory slot is learned. No external actions.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from collections import Counter, defaultdict

from developmental_ai.environment_api import EnvironmentSession, FRAME_SCHEMA, canonical, digest

SCHEMA = "developmental-ai.learned-offset-updater/v1"
MEMORY_SCHEMA = "developmental-ai.offset-memory/v1"
EVENTS = ("move", "blocked", "empty_eat", "food", "timeout", "budget_exhausted")
PUBLIC_EVENT_ALIASES = {"empty_interact": "empty_eat", "collected": "food"}
MAX_EPISODES = 2000


def action_seed(seed, index):
    b = f"{SCHEMA}/train/{seed}/{index}/explore".encode()
    return int.from_bytes(hashlib.sha256(b).digest()[:8], "big")


def _validate_frame(frame, family, expected_tick):
    if (type(frame) is not dict or frame.get("schema") != FRAME_SCHEMA or
            frame.get("source") != "simulation" or frame.get("scope") != "simulation-only" or
            frame.get("family") != family or type(frame.get("tick")) is not int or
            frame["tick"] != expected_tick or type(frame.get("observation")) is not dict or
            type(frame.get("available_actions")) is not list):
        raise ValueError("invalid or stale public simulation frame")
    expected = {"target_dx", "target_dy", "blocked"} if family == "grid" else {"beacon", "blocked"}
    if set(frame["observation"]) != expected:
        raise ValueError("invalid or privileged observation")
    obs = frame["observation"]
    if type(obs["blocked"]) is not int or not 0 <= obs["blocked"] < 16:
        raise ValueError("invalid obstacle mask")
    if family == "grid":
        if any(type(obs[k]) is not int or abs(obs[k]) > 3 for k in ("target_dx", "target_dy")):
            raise ValueError("invalid visible target")
    elif obs["beacon"] is not None and (type(obs["beacon"]) is not list or
            len(obs["beacon"]) != 2 or any(type(x) is not int or abs(x) > 8 for x in obs["beacon"])):
        raise ValueError("invalid initial beacon")


class LearnedOffsetUpdater:
    """Immutable, finite learned transition table with a source-data digest."""

    def __init__(self, counts, *, seed, episodes):
        if (type(seed) is not int or type(episodes) is not int or not 1 <= episodes <= MAX_EPISODES or
                type(counts) is not dict):
            raise ValueError("invalid learned update metadata")
        self.seed, self.episodes = seed, episodes
        self.counts = {}
        for key, vals in counts.items():
            if (type(key) is not str or type(vals) is not dict or
                    len(key.split("|")) != 2):
                raise ValueError("invalid learned transition key")
            action_text, event = key.split("|")
            if action_text not in ("0", "1", "2", "3", "4") or event not in EVENTS:
                raise ValueError("invalid learned transition identity")
            rows = {}
            for pair, tally in vals.items():
                if (type(pair) is not str or len(pair.split(",")) != 2 or
                        type(tally) is not int or tally < 1):
                    raise ValueError("invalid learned transition count")
                try:
                    dx, dy = map(int, pair.split(","))
                except ValueError as exc:
                    raise ValueError("invalid update displacement") from exc
                if abs(dx) > 2 or abs(dy) > 2 or pair != f"{dx},{dy}":
                    raise ValueError("invalid update size")
                rows[pair] = tally
            if not rows:
                raise ValueError("empty learned evidence")
            self.counts[key] = rows
        if not all(f"{a}|move" in self.counts for a in range(4)):
            raise ValueError("missing a learned directional transition")
        self._record = {"schema": SCHEMA, "seed": seed, "episodes": episodes, "counts": self.counts}
        self.fingerprint = digest(self._record)
        self.updates = {}
        for key, rows in self.counts.items():
            winner = max(sorted(rows), key=lambda p: rows[p])
            self.updates[key] = tuple(map(int, winner.split(",")))

    def update(self, action, event):
        if type(action) is not int or action not in range(5) or type(event) is not str or event not in EVENTS:
            raise ValueError("invalid public action or outcome")
        if event in ("timeout", "budget_exhausted", "food"):
            return (0, 0)  # terminal; no future action requires an update
        key = f"{action}|{event}"
        if key not in self.updates:
            # Missing observations are NOT guessed from known simulator geometry.
            raise ValueError("untrained action/outcome combination")
        return self.updates[key]

    def record(self):
        return {"data": json.loads(canonical(self._record)), "digest": self.fingerprint}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"data", "digest"} or
                type(record["data"]) is not dict or digest(record["data"]) != record["digest"] or
                set(record["data"]) != {"schema", "seed", "episodes", "counts"} or
                record["data"]["schema"] != SCHEMA):
            raise ValueError("invalid or altered learned updater")
        d = record["data"]
        return cls(d["counts"], seed=d["seed"], episodes=d["episodes"])


def train_grid_updates(seed, episodes=80):
    """Fit public action/outcome -> clipped target-feature delta using TRAIN only."""
    if type(seed) is not int or type(episodes) is not int or not 1 <= episodes <= MAX_EPISODES:
        raise ValueError("invalid training schedule")
    hist = defaultdict(Counter)
    for i in range(episodes):
        session = EnvironmentSession("grid", seed, "train", i)
        rng = random.Random(action_seed(seed, i))
        while not session.done:
            before = session.frame()
            action = rng.randrange(5)  # Train updates from ordinary public sensor differences.
            result = session.step(action, expected_tick=before["tick"])
            after = result["frame"]
            _validate_frame(before, "grid", before["tick"])
            _validate_frame(after, "grid", before["tick"] + 1)
            old, new = before["observation"], after["observation"]
            # Saturation of the public +/-3 displacement sensor hides actual
            # feature changes. Use only pairs away from clipped boundaries.
            if all(abs(obs[name]) < 3 for obs in (old, new) for name in ("target_dx", "target_dy")):
                x = new["target_dx"] - old["target_dx"]
                y = new["target_dy"] - old["target_dy"]
                hist[f"{action}|{result['event']}"][f"{x},{y}"] += 1
    # Train-only identified stillness responses: blocked samples may be absent
    # in low-obstacle seeds, but the learner must see them rather than assume.
    counts = {key: dict(rows) for key, rows in hist.items()}
    return LearnedOffsetUpdater(counts, seed=seed, episodes=episodes)


class PortableOffsetMemory:
    """One-slot cue memory whose motion update is learned, not preprogrammed."""

    def __init__(self, updater, *, retain=True):
        if not isinstance(updater, LearnedOffsetUpdater) or type(retain) is not bool:
            raise ValueError("invalid portable memory config")
        self.updater = LearnedOffsetUpdater.restore(updater.record())
        self.retain = retain
        self.initial = None
        self.remaining = None
        self.tick = 0
        self.events = []

    def features(self, frame):
        _validate_frame(frame, "occluded", self.tick)
        obs = frame["observation"]
        if self.tick == 0:
            if self.initial is not None or obs["beacon"] is None:
                raise ValueError("missing initial cue")
            self.initial = tuple(obs["beacon"])
            self.remaining = list(self.initial)
        elif obs["beacon"] is not None:
            raise ValueError("unexpected repeated beacon")
        x, y = self.remaining if self.remaining is not None else (0, 0)
        return (max(-3, min(3, x)), max(-3, min(3, y)), obs["blocked"])

    def feedback(self, action, result):
        if (type(result) is not dict or set(result) != {"frame", "reward", "event"} or
                type(result["event"]) is not str or result["event"] not in EVENTS + tuple(PUBLIC_EVENT_ALIASES) or
                type(result["reward"]) not in (int, float) or not math.isfinite(result["reward"]) or
                self.initial is None or type(action) is not int or action not in range(5)):
            raise ValueError("invalid public feedback")
        _validate_frame(result["frame"], "occluded", self.tick + 1)
        movement = self.updater.update(action, PUBLIC_EVENT_ALIASES.get(result["event"], result["event"]))
        if self.retain and self.remaining is not None:
            self.remaining[0] += movement[0]
            self.remaining[1] += movement[1]
        else:
            self.remaining = None
        self.events.append([action, result["event"]])
        self.tick += 1

    def snapshot(self):
        if self.initial is None:
            raise ValueError("memory has not seen initial cue")
        state = {"schema": MEMORY_SCHEMA, "updater": self.updater.fingerprint,
                 "retain": self.retain, "initial": list(self.initial),
                 "events": self.events, "remaining": self.remaining, "tick": self.tick}
        return {"data": json.loads(canonical(state)), "digest": digest(state)}

    @classmethod
    def restore(cls, saved, updater):
        if (type(saved) is not dict or set(saved) != {"data", "digest"} or
                type(saved["data"]) is not dict or digest(saved["data"]) != saved["digest"]):
            raise ValueError("altered memory snapshot")
        s = saved["data"]
        if (set(s) != {"schema", "updater", "retain", "initial", "events", "remaining", "tick"} or
                s["schema"] != MEMORY_SCHEMA or s["updater"] != updater.fingerprint or
                type(s["retain"]) is not bool or type(s["tick"]) is not int or
                not 0 <= s["tick"] <= 200 or type(s["initial"]) is not list or
                len(s["initial"]) != 2 or any(type(v) is not int or abs(v)>8 for v in s["initial"]) or
                type(s["events"]) is not list or len(s["events"]) != s["tick"]):
            raise ValueError("invalid memory state")
        rebuilt = cls(updater, retain=s["retain"])
        rebuilt.initial = tuple(s["initial"])
        rebuilt.remaining = list(s["initial"])
        for entry in s["events"]:
            if type(entry) is not list or len(entry) != 2:
                raise ValueError("invalid memory history")
            act, event = entry
            dx, dy = rebuilt.updater.update(act, PUBLIC_EVENT_ALIASES.get(event, event))
            if rebuilt.retain and rebuilt.remaining is not None:
                rebuilt.remaining[0] += dx
                rebuilt.remaining[1] += dy
            else:
                rebuilt.remaining = None
            rebuilt.events.append([act, event])
            rebuilt.tick += 1
        if rebuilt.remaining != s["remaining"]:
            raise ValueError("inconsistent saved memory contents")
        return rebuilt
