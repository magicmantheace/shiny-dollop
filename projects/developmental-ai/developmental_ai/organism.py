"""An intentionally small, inspectable autonomous learning organism.

Uses off-policy tabular Q-learning plus a decaying intrinsic novelty reward.
It is *not* a biologically realistic brain or a general-purpose AI.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ACTIONS = ("north", "south", "west", "east", "eat")
MOVES = {0: (0, -1), 1: (0, 1), 2: (-1, 0), 3: (1, 0)}
FOOD_SITES = ((5, 0), (5, 5))
HAZARDS = {(2, 0), (2, 4), (4, 3)}
START = (0, 2)
WIDTH = HEIGHT = 6
MAX_STEPS = 50


class Arena:
    """Tiny visible-cue grid: the organism can sense which food site is active.

    It does not know the map, safety of each cell, or how to reach the food.
    """

    def __init__(self, rng: random.Random, goal: int | None = None):
        self.goal_id = rng.randrange(len(FOOD_SITES)) if goal is None else goal
        self.position = START
        self.steps = 0
        self.finished = False

    def observe(self) -> tuple[int, int, int]:
        # x, y, visible food scent identifier; no provided route or hazard map
        return (*self.position, self.goal_id)

    def step(self, action: int) -> tuple[tuple[int, int, int], float, bool, str]:
        if self.finished:
            raise RuntimeError("Episode finished")
        if action not in range(len(ACTIONS)):
            raise ValueError("Unknown action")
        self.steps += 1
        reward = -0.04  # gentle pressure toward accomplishing goals
        event = "move"
        if action == 4:
            if self.position == FOOD_SITES[self.goal_id]:
                reward += 10.0
                event = "food"
                self.finished = True
            else:
                reward -= 0.5
                event = "empty_eat"
        else:
            dx, dy = MOVES[action]
            nx, ny = self.position[0] + dx, self.position[1] + dy
            if not (0 <= nx < WIDTH and 0 <= ny < HEIGHT):
                reward -= 0.5
                event = "wall"
            else:
                self.position = (nx, ny)
                if self.position in HAZARDS:
                    reward -= 2.0
                    event = "hazard"
        if self.steps >= MAX_STEPS and not self.finished:
            self.finished = True
            reward -= 2.0
            event = "timeout"
        return self.observe(), reward, self.finished, event


class Memory:
    """SQLite episodic traces, semantic landmarks, and persistent skills."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS skills (
                state TEXT NOT NULL, action INTEGER NOT NULL, value REAL NOT NULL,
                PRIMARY KEY(state, action)
            );
            CREATE TABLE IF NOT EXISTS visits (
                state TEXT PRIMARY KEY, count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY, timestamp INTEGER NOT NULL,
                food_goal INTEGER NOT NULL, steps INTEGER NOT NULL,
                success INTEGER NOT NULL, external_reward REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY, episode_id INTEGER NOT NULL,
                step INTEGER NOT NULL, position TEXT NOT NULL,
                action TEXT NOT NULL, event TEXT NOT NULL,
                outcome REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS knowledge (
                location TEXT NOT NULL, kind TEXT NOT NULL,
                observations INTEGER NOT NULL,
                PRIMARY KEY(location, kind)
            );
            """
        )

    def load_skills(self) -> dict[tuple[tuple[int, int, int], int], float]:
        return {(tuple(json.loads(k)), action): value
                for k, action, value in self.conn.execute(
                    "SELECT state,action,value FROM skills")}

    def load_visits(self) -> dict[tuple[int, int, int], int]:
        return {tuple(json.loads(s)): n for s, n in
                self.conn.execute("SELECT state,count FROM visits")}

    def save_learning(self, q: dict, visits: dict) -> None:
        # Atomic replacement guarantees restart sees coherent updates.
        with self.conn:
            self.conn.execute("DELETE FROM skills")
            self.conn.executemany(
                "INSERT INTO skills VALUES (?,?,?)",
                ((json.dumps(state), action, value)
                 for (state, action), value in q.items())
            )
            self.conn.execute("DELETE FROM visits")
            self.conn.executemany(
                "INSERT INTO visits VALUES (?,?)",
                ((json.dumps(state), count) for state, count in visits.items())
            )

    def record_episode(self, goal: int, steps: int, success: bool,
                       external_reward: float, events: list[tuple]) -> None:
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO episodes(timestamp,food_goal,steps,success,external_reward) "
                "VALUES (?,?,?,?,?)", (int(time.time()), goal, steps,
                                         int(success), external_reward))
            episode_id = cursor.lastrowid
            for step, pos, action, event, reward in events:
                self.conn.execute(
                    "INSERT INTO experiences(episode_id,step,position,action,event,outcome) "
                    "VALUES (?,?,?,?,?,?)",
                    (episode_id, step, json.dumps(pos), action, event, reward))
                if event in ("hazard", "food"):
                    self.conn.execute(
                        "INSERT INTO knowledge(location,kind,observations) VALUES (?,?,1) "
                        "ON CONFLICT(location,kind) DO UPDATE SET observations=observations+1",
                        (json.dumps(pos), event))

    def inspect(self, limit: int = 10) -> dict[str, Any]:
        episodes = self.conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(success),0) FROM episodes").fetchone()
        recent = self.conn.execute(
            "SELECT id,food_goal,steps,success,ROUND(external_reward,2) "
            "FROM episodes ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        experiences = self.conn.execute(
            "SELECT event,position,action,ROUND(outcome,2) "
            "FROM experiences ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        knowledge = self.conn.execute(
            "SELECT kind,location,observations FROM knowledge "
            "ORDER BY observations DESC,kind LIMIT 20").fetchall()
        return {"total_episodes": episodes[0], "total_successes": episodes[1],
                "recent_episodes": recent,
                "recent_significant_experiences": experiences,
                "learned_landmarks": knowledge,
                "learned_state_action_values": self.conn.execute(
                    "SELECT COUNT(*) FROM skills").fetchone()[0]}

    def close(self) -> None:
        self.conn.close()


@dataclass
class Result:
    goal: int
    steps: int
    success: bool
    reward: float


class Organism:
    def __init__(self, memory: Memory, seed: int = 7):
        self.memory = memory
        self.rng = random.Random(seed)
        self.q = memory.load_skills()
        self.visits = defaultdict(int, memory.load_visits())
        self.training_episodes = memory.conn.execute(
            "SELECT COUNT(*) FROM episodes").fetchone()[0]

    def value(self, state: tuple[int, int, int], action: int) -> float:
        return self.q.get((state, action), 0.0)

    def choose(self, state: tuple[int, int, int], epsilon: float) -> int:
        if self.rng.random() < epsilon:
            return self.rng.randrange(len(ACTIONS))
        scores = [self.value(state, action) for action in range(len(ACTIONS))]
        highest = max(scores)
        best = [i for i, score in enumerate(scores) if abs(score - highest) < 1e-10]
        return self.rng.choice(best)

    def episode(self, learning: bool = True, goal: int | None = None) -> Result:
        world = Arena(self.rng, goal)
        external_total = 0.0
        significant = []
        success = False
        # Decay exploration only during training; reload honors earlier training.
        epsilon = max(0.035, 0.85 * (0.996 ** self.training_episodes)) if learning else 0.0
        for _ in range(MAX_STEPS):
            old = world.observe()
            action = self.choose(old, epsilon)
            state, environmental_reward, done, event = world.step(action)
            external_total += environmental_reward
            success = event == "food"
            if learning:
                # Novelty is an internal, self-driven exploration incentive.
                self.visits[state] += 1
                intrinsic_reward = (0.25 / math.sqrt(self.visits[state])
                                    if action < 4 and old != state else 0.0)
                reward = environmental_reward + intrinsic_reward
                target = reward + (0.0 if done else 0.95 * max(
                    self.value(state, a) for a in range(len(ACTIONS))))
                current = self.value(old, action)
                self.q[(old, action)] = current + 0.26 * (target - current)
                if event in ("food", "hazard"):
                    significant.append((world.steps, world.position, ACTIONS[action],
                                        event, environmental_reward))
            if done:
                break
        if learning:
            self.training_episodes += 1
            self.memory.record_episode(world.goal_id, world.steps, success,
                                       external_total, significant)
        return Result(world.goal_id, world.steps, success, round(external_total, 3))

    def train(self, episodes: int, batch: int = 250) -> list[dict]:
        summaries = []
        completed = 0
        while completed < episodes:
            count = min(batch, episodes - completed)
            results = [self.episode(learning=True) for _ in range(count)]
            completed += count
            self.memory.save_learning(self.q, self.visits)
            summaries.append({
                "trained": completed,
                "success_rate": round(sum(r.success for r in results) / count, 3),
                "mean_steps": round(sum(r.steps for r in results) / count, 2),
                "mean_external_reward": round(sum(r.reward for r in results) / count, 2),
            })
        return summaries

    def watch(self, goal: int = 0) -> list[dict]:
        """Show greedy actions without training, updating visits, or writing memory."""
        if not 0 <= goal < len(FOOD_SITES):
            raise ValueError("Food site must be 0 or 1")
        world = Arena(self.rng, goal)
        trace = [{"step": 0, "position": world.position, "action": "start",
                  "event": "start", "reward": 0.0}]
        for _ in range(MAX_STEPS):
            action = self.choose(world.observe(), epsilon=0.0)
            _, reward, finished, event = world.step(action)
            trace.append({"step": world.steps, "position": world.position,
                          "action": ACTIONS[action], "event": event,
                          "reward": round(reward, 2)})
            if finished:
                break
        return trace

    def evaluate(self, episodes: int) -> dict:
        # Balanced evaluation across goals, no DB writes or weight updates.
        results = [self.episode(learning=False, goal=i % len(FOOD_SITES))
                   for i in range(episodes)]
        return {"episodes": episodes,
                "success_rate": round(sum(r.success for r in results) / episodes, 3),
                "mean_steps": round(sum(r.steps for r in results) / episodes, 2),
                "mean_external_reward": round(sum(r.reward for r in results) / episodes, 2),
                "by_goal": {str(goal): round(
                    sum(r.success for r in results if r.goal == goal) /
                    max(1, sum(r.goal == goal for r in results)), 3)
                    for goal in range(len(FOOD_SITES))}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["train", "evaluate", "remember", "watch"])
    parser.add_argument("--db", type=Path, default=Path("brain.db"))
    parser.add_argument("--episodes", type=int, default=3000)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--last", type=int, default=10)
    parser.add_argument("--goal", type=int, default=0, choices=[0, 1])
    args = parser.parse_args()
    if args.episodes < 1 or args.last < 1:
        parser.error("--episodes and --last must be positive")
    memory = Memory(args.db)
    try:
        organism = Organism(memory, args.seed)
        if args.command == "train":
            print("Before:", json.dumps(organism.evaluate(200)))
            for stats in organism.train(args.episodes):
                print(json.dumps(stats))
            print("After:", json.dumps(organism.evaluate(200)))
        elif args.command == "evaluate":
            print(json.dumps(organism.evaluate(args.episodes), indent=2))
        elif args.command == "remember":
            print(json.dumps(memory.inspect(args.last), indent=2))
        else:
            print(json.dumps(organism.watch(args.goal), indent=2))
    finally:
        memory.close()


if __name__ == "__main__":
    main()
