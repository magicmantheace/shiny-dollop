"""Empirical sensor/physics calibration in a bounded stochastic ring.

A simulator calibration instrument reveals *actual* move displacement and
position to the trainer. It is deliberately privileged SUPERVISION, not a
self-discovered world model. Evaluation/navigation only see ordinary sensors.
No external actions, person records, learned identity or network access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
from pathlib import Path

from developmental_ai.uncertain_navigation import (
    ACTIONS, RingWorld, canonical, distance, seed_for, signed_distance,
)

SCHEMA = "adaptive-dynamics/v1"
NOISE = ("standard", "high")
LAYOUTS = ("fixed", "shifted")
READINGS = (None, 0, 1)
DELTA = (-1, 0, 1)
DECAY = 0.997
PRIOR = .5


class CalibrationWorld(RingWorld):
    """The movement and odometry simulator with a configurable landmark map."""

    def __init__(self, seed, split, index, noise="standard", layout="fixed"):
        if layout not in LAYOUTS:
            raise ValueError("invalid landmark layout")
        super().__init__(seed, split, index, noise=noise, landmarks=True)
        self.layout = layout

    def _landmark(self):
        offset = 0 if self.layout == "fixed" else 2
        pos0, pos1 = offset, self.n // 2 + offset
        mark = 0 if self.pos == pos0 else 1 if self.pos == pos1 else None
        draw = self.rng.random()
        if mark is None:
            return 0 if draw < .01 else 1 if draw < .02 else None
        return mark if draw < .85 else 1-mark if draw < .86 else None


def calibration_sample(seed, split, index, noise="standard", layout="fixed"):
    """One independent instrumented transition; truth is *training-only* data."""
    if noise not in NOISE or layout not in LAYOUTS:
        raise ValueError("invalid condition")
    world = CalibrationWorld(seed, split, index, noise, layout)
    action = random.Random(seed_for(seed, split, index, "policy")).randrange(2)
    before = world.pos
    sensed, _, _, _ = world.step(action)
    actual_delta = signed_distance(before, world.pos, world.n)
    return {"n": world.n, "position": world.pos, "command": ACTIONS[action],
            "delta": actual_delta, "odo": sensed["odometry"],
            "landmark": sensed["landmark"]}


def blank_counts():
    return {"motion": [[0.0] * 3 for _ in range(2)],
            "odo": [[0.0] * 3 for _ in range(3)],
            "landmark": {str(n): [[0.0] * 3 for _ in range(n)] for n in (9, 11)}}


def index_of(value):
    if value not in DELTA or type(value) is not int:
        raise ValueError("invalid displacement")
    return value + 1


def reading_index(value):
    if value is None:
        return 0
    if type(value) is not int or value not in (0, 1):
        raise ValueError("invalid landmark observation")
    return value + 1


class DynamicsModel:
    """Decayed categorical counts of commanded movement and sensor outputs."""

    def __init__(self, counts=None):
        self.counts = blank_counts() if counts is None else counts
        self.validate()

    def validate(self):
        template = blank_counts()
        if type(self.counts) is not dict or set(self.counts) != set(template):
            raise ValueError("invalid dynamics checkpoint structure")
        for key in ("motion", "odo"):
            expected = template[key]
            rows = self.counts[key]
            if type(rows) is not list or len(rows) != len(expected):
                raise ValueError("invalid dynamics rows")
            self._validate_rows(rows, expected)
        lm = self.counts["landmark"]
        if type(lm) is not dict or set(lm) != {"9", "11"}:
            raise ValueError("invalid landmark models")
        for n in (9, 11):
            self._validate_rows(lm[str(n)], template["landmark"][str(n)])

    @staticmethod
    def _validate_rows(rows, expected):
        if type(rows) is not list or len(rows) != len(expected):
            raise ValueError("invalid matrix rows")
        for row in rows:
            if type(row) is not list or len(row) != 3 or any(
                type(x) not in (int, float) or not math.isfinite(x) or x < 0 or x > 1e8 for x in row
            ):
                raise ValueError("invalid matrix values")

    @staticmethod
    def probs(row):
        total = sum(row) + 3 * PRIOR
        return tuple((x + PRIOR) / total for x in row)

    def motion_probs(self, command):
        if command not in (-1, 1):
            raise ValueError("movement-only model")
        # Indices are intended/slip/reverse, not absolute displacements.
        return self.probs(self.counts["motion"][0 if command == -1 else 1])

    def odo_probs(self, delta):
        return self.probs(self.counts["odo"][index_of(delta)])

    def landmark_probs(self, n, position):
        if n not in (9, 11) or type(position) is not int or not (0 <= position < n):
            raise ValueError("invalid location")
        return self.probs(self.counts["landmark"][str(n)][position])

    def observe(self, sample):
        """Use privileged simulator calibration; never call with held-out samples."""
        if type(sample) is not dict or set(sample) != {"n", "position", "command", "delta", "odo", "landmark"}:
            raise ValueError("invalid calibration sample")
        n, position, cmd = sample["n"], sample["position"], sample["command"]
        actual, odo, mark = sample["delta"], sample["odo"], sample["landmark"]
        if n not in (9, 11) or type(n) is not int or type(position) is not int or not 0 <= position < n:
            raise ValueError("invalid calibration position")
        if type(cmd) is not int or cmd not in (-1, 1) or type(actual) is not int or actual not in (-1, 0, 1):
            raise ValueError("invalid calibration movement")
        index_of(odo)
        mark_ix = reading_index(mark)
        # Exponential forgetting allows later observations to revise a model.
        for matrix in (self.counts["motion"], self.counts["odo"], *self.counts["landmark"].values()):
            for row in matrix:
                for i in range(3):
                    row[i] *= DECAY
        motion_class = 0 if actual == cmd else 1 if actual == 0 else 2
        self.counts["motion"][0 if cmd == -1 else 1][motion_class] += 1
        self.counts["odo"][index_of(actual)][index_of(odo)] += 1
        self.counts["landmark"][str(n)][position][mark_ix] += 1

    def loss(self, sample):
        """Held-out negative log likelihood; does not update the model."""
        cmd, actual = sample["command"], sample["delta"]
        ix = 0 if actual == cmd else 1 if actual == 0 else 2
        return (-math.log(self.motion_probs(cmd)[ix])
                -math.log(self.odo_probs(actual)[index_of(sample["odo"])])
                -math.log(self.landmark_probs(sample["n"], sample["position"])[reading_index(sample["landmark"])]) )


class KnownPhysicsOracle:
    """Privileged simulator probability baseline; cannot learn or access the agent."""
    def __init__(self, noise="high", layout="shifted"):
        if noise not in NOISE or layout not in LAYOUTS:
            raise ValueError("invalid oracle configuration")
        self.noise = noise
        self.layout = layout

    def motion_probs(self, command):
        if type(command) is not int or command not in (-1, 1):
            raise ValueError("movement-only oracle")
        p = .70 if self.noise == "standard" else .48
        return (p, .20, 1 - p - .20)

    def odo_probs(self, delta):
        index_of(delta)
        p = .72 if self.noise == "standard" else .48
        return tuple(p if value == delta else (1 - p) / 2 for value in DELTA)

    def landmark_probs(self, n, position):
        if n not in (9,11) or type(n) is not int or type(position) is not int or not 0 <= position < n:
            raise ValueError("invalid oracle location")
        offset = 0 if self.layout == "fixed" else 2
        mark = 0 if position == offset else 1 if position == n//2+offset else None
        if mark is None:
            return (.98, .01, .01)
        return (.14, .85, .01) if mark == 0 else (.14, .01, .85)

    def loss(self, sample):
        return DynamicsModel.loss(self, sample)


class AdaptiveNavigator:
    """Engineered Bayes filter using learned *observation-model parameters*."""

    def __init__(self, initial, goal, n, model):
        self.n = n
        self.goal = goal
        self.model = model
        self.probs = [float(i == initial) for i in range(n)]

    def advance(self, action, observation):
        if type(action) is not int or action not in range(3):
            raise ValueError("invalid action")
        odo = observation["odometry"]
        mark_ix = reading_index(observation["landmark"])
        index_of(odo)
        candidates = [0.0] * self.n
        if action == 2:
            candidates = self.probs[:]
        else:
            cmd = ACTIONS[action]
            for old, mass in enumerate(self.probs):
                for delta, chance in zip((cmd, 0, -cmd), self.model.motion_probs(cmd)):
                    candidates[(old + delta) % self.n] += mass * chance * self.model.odo_probs(delta)[index_of(odo)]
        candidates = [p * self.model.landmark_probs(self.n, pos)[mark_ix] for pos, p in enumerate(candidates)]
        total = sum(candidates)
        if total <= 0 or not math.isfinite(total):
            raise ValueError("invalid posterior")
        self.probs = [p / total for p in candidates]

    def heuristic(self):
        if self.probs[self.goal] >= .45:
            return 2
        losses = []
        for action in (0, 1):
            cmd = ACTIONS[action]
            deltas = (cmd, 0, -cmd)
            loss = 0.0
            for pos, weight in enumerate(self.probs):
                loss += weight * sum(p * distance((pos + d) % self.n, self.goal, self.n)
                                     for d, p in zip(deltas, self.model.motion_probs(cmd)))
            losses.append(loss)
        return 0 if losses[0] < losses[1] else 1


def navigate(model, seed, index, noise, layout):
    world = CalibrationWorld(seed, "test", index, noise, layout)
    nav = AdaptiveNavigator(world.initial, world.goal, world.n, model)
    last = None
    while not world.done:
        action = nav.heuristic()
        sensed, _, _, last = world.step(action)
        nav.advance(action, sensed)
    return last == "success"


class CalibrationBrain:
    """SQLite checkpoint for exact reproducible supervised calibration."""

    def __init__(self, db, seed=17):
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        path = Path(db)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        try:
            self.conn.execute("CREATE TABLE IF NOT EXISTS dynamics_state (id INTEGER PRIMARY KEY CHECK(id=1), schema TEXT NOT NULL, seed INTEGER NOT NULL, trained INTEGER NOT NULL, counts TEXT NOT NULL)")
            self.conn.execute("CREATE TABLE IF NOT EXISTS dynamics_snapshots (name TEXT PRIMARY KEY, schema TEXT NOT NULL, seed INTEGER NOT NULL, trained INTEGER NOT NULL, counts TEXT NOT NULL, digest TEXT NOT NULL)")
            row = self.conn.execute("SELECT schema,seed,trained,counts FROM dynamics_state WHERE id=1").fetchone()
            if row is None:
                self.model = DynamicsModel()
                self.trained = 0
            else:
                schema, stored_seed, trained, content = row
                if schema != SCHEMA or stored_seed != seed or type(trained) is not int or trained < 0:
                    raise ValueError("incompatible calibration checkpoint")
                self.model = DynamicsModel(json.loads(content))
                self.trained = trained
            self.seed = seed
        except Exception:
            self.conn.close()
            raise

    def train(self, samples, noise="standard", layout="fixed"):
        if type(samples) is not int or samples < 1 or noise not in NOISE or layout not in LAYOUTS:
            raise ValueError("invalid training batch")
        for _ in range(samples):
            record = calibration_sample(self.seed, "train", self.trained, noise, layout)
            self.model.observe(record)
            self.trained += 1
        self.persist()

    def persist(self):
        self.model.validate()
        with self.conn:
            self.conn.execute("INSERT INTO dynamics_state (id,schema,seed,trained,counts) VALUES (1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET schema=excluded.schema,seed=excluded.seed,trained=excluded.trained,counts=excluded.counts",
                              (SCHEMA,self.seed,self.trained,canonical(self.model.counts)))

    def evaluate(self, episodes=200, noise="high", layout="shifted"):
        return self._evaluate_model(self.model, episodes, noise, layout)

    def snapshot(self, name):
        """Immutable named experiment model; never overwrite existing knowledge."""
        if type(name) is not str or not (1 <= len(name) <= 40) or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
            raise ValueError("invalid snapshot name")
        contents = canonical(self.model.counts)
        digest = hashlib.sha256(contents.encode("utf-8")).hexdigest()
        with self.conn:
            self.conn.execute("INSERT INTO dynamics_snapshots(name,schema,seed,trained,counts,digest) VALUES (?,?,?,?,?,?)",
                              (name,SCHEMA,self.seed,self.trained,contents,digest))
        return digest

    def load_snapshot(self, name):
        """Read-only retrieval; no model or file mutation."""
        if type(name) is not str:
            raise ValueError("invalid snapshot name")
        row = self.conn.execute("SELECT schema,seed,trained,counts,digest FROM dynamics_snapshots WHERE name=?",(name,)).fetchone()
        if row is None:
            raise ValueError("snapshot does not exist")
        schema, seed, trained, counts, digest = row
        if (schema != SCHEMA or seed != self.seed or type(trained) is not int or trained < 0 or
            hashlib.sha256(counts.encode("utf-8")).hexdigest() != digest):
            raise ValueError("invalid snapshot integrity")
        return DynamicsModel(json.loads(counts))

    def evaluate_snapshot(self, name, episodes=200, noise="high", layout="shifted"):
        model = self.load_snapshot(name)
        return self._evaluate_model(model, episodes, noise, layout)

    def _evaluate_model(self, model, episodes, noise, layout):
        if type(episodes) is not int or episodes < 1 or noise not in NOISE or layout not in LAYOUTS:
            raise ValueError("invalid evaluation")
        samples = [calibration_sample(self.seed, "test", i, noise, layout) for i in range(episodes)]
        return {"schema":SCHEMA,"seed":self.seed,"trained":self.trained,"noise":noise,"layout":layout,
                "episodes":episodes,"mean_nll":round(sum(model.loss(s) for s in samples)/len(samples),5),
                "navigation_success":round(sum(navigate(model,self.seed,i,noise,layout) for i in range(episodes))/episodes,4)}

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self,*_):
        self.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("train", "evaluate", "snapshot", "evaluate-snapshot"))
    p.add_argument("--db", type=Path, default=Path("calibration.db"))
    p.add_argument("--seed", type=int, default=17)
    p.add_argument("--samples", type=int, default=1200)
    p.add_argument("--name", default="")
    p.add_argument("--noise", choices=NOISE, default="standard")
    p.add_argument("--layout", choices=LAYOUTS, default="fixed")
    args=p.parse_args()
    with CalibrationBrain(args.db,args.seed) as brain:
        if args.command == "train":
            brain.train(args.samples,args.noise,args.layout)
            print(canonical({"schema":SCHEMA,"seed":brain.seed,"trained":brain.trained,"scope":"simulation-only"}))
        elif args.command == "evaluate":
            print(canonical(brain.evaluate(args.samples,args.noise,args.layout)))
        elif args.command == "snapshot":
            print(canonical({"name":args.name,"digest":brain.snapshot(args.name),"trained":brain.trained}))
        else:
            print(canonical(brain.evaluate_snapshot(args.name,args.samples,args.noise,args.layout)))


if __name__ == "__main__":
    main()
