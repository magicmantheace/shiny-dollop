"""Frozen cross-family D1/D2 baseline; not evidence of general intelligence.

Three distinct simulator families use the same public API. Task-specific
heuristics and a four-token reward-learned delayed association are clearly
labelled baselines, NOT a universal learned controller. A reserved future
cohort must not be run without explicit --unlock-reserved and independent review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

from developmental_ai.environment_api import EnvironmentSession, canonical

PROTOCOL = Path(__file__).with_name("frozen_environment_protocol.json")


def load_protocol():
    raw = PROTOCOL.read_bytes()
    obj = json.loads(raw)
    if (type(obj) is not dict or obj.get("schema") != "developmental-ai.cross-family-protocol/v1" or
            obj.get("interface_schema") != "developmental-ai.environment-session/v1" or
            [x.get("id") for x in obj["task_families"]] != ["grid", "occluded", "delayed"] or
            obj.get("baselines") != ["random", "family_specific"]):
        raise ValueError("invalid frozen protocol")
    return obj, hashlib.sha256(raw).hexdigest()


def action_seed(seed, split, index, family, policy):
    raw = f"environment-contract/v1/{seed}/{split}/{index}/{family}/{policy}".encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


class FamilySpecificPolicy:
    """Conspicuously hand-designed navigation memory and reward-trained cue map."""
    def __init__(self, family, cue_map=None):
        self.family = family
        self.remaining = None
        self.cue = None
        self.mapping = {} if cue_map is None else dict(cue_map)

    def choose(self, frame, rng):
        obs = frame["observation"]
        if self.family == "delayed":
            if obs["phase"] == "cue": self.cue = obs["token"]
            if frame["available_actions"] == [4]: return 4
            return self.mapping.get(self.cue, 0)
        if self.family == "grid":
            dx, dy = obs["target_dx"], obs["target_dy"]
        else:
            if obs["beacon"] is not None:
                self.remaining = list(obs["beacon"])
            dx, dy = self.remaining if self.remaining is not None else (0,0)
        if dx == dy == 0: return 4
        mask = obs["blocked"]
        directions = [0, 1, 2, 3]
        rng.shuffle(directions)
        directions.sort(key=lambda a: (dy if a == 1 else -dy if a == 0 else dx if a == 3 else -dx), reverse=True)
        for action in directions:
            if not mask & (1 << action): return action
        return 4

    def learn_result(self, action, result):
        if self.family == "occluded" and self.remaining is not None and result["event"] == "move":
            dx, dy = ((0,-1),(0,1),(-1,0),(1,0))[action]
            self.remaining[0] -= dx
            self.remaining[1] -= dy


def train_delayed_mapping(seed, episodes):
    """Learn cue->button association only from train-namespace rewards.

    Uses manual cue retention. No access to the simulator's hidden mapping.
    """
    success = {cue:[0] * 4 for cue in range(4)}
    tried = {cue:[0] * 4 for cue in range(4)}
    for index in range(episodes):
        session = EnvironmentSession("delayed",seed,"train",index,"short")
        cue = session.frame()["observation"]["token"]
        while session.frame()["available_actions"] == [4]:
            session.step(4,expected_tick=session.tick)
        action = index % 4
        terminal = session.step(action,expected_tick=session.tick)
        tried[cue][action] += 1
        success[cue][action] += int(terminal["event"] == "correct")
    return {cue:max(range(4),key=lambda a:(success[cue][a]/tried[cue][a] if tried[cue][a] else -1,a))
            for cue in range(4)}


def run_episode(family, variant, seed, split, index, policy, *, cue_map=None):
    session = EnvironmentSession(family, seed, split, index, variant)
    rng = random.Random(action_seed(seed,split,index,family,policy))
    agent = FamilySpecificPolicy(family,cue_map)
    total = 0.0
    last = ""
    while not session.done:
        frame = session.frame()
        if policy == "random": action = rng.choice(frame["available_actions"])
        else: action = agent.choose(frame,rng)
        result = session.step(action,expected_tick=session.tick)
        agent.learn_result(action,result)
        total += result["reward"]
        last = result["event"]
    return {"success":last in {"food","collected","correct"}, "steps":session.tick,"reward":total,
            "valid_actions":session.tick}


def evaluate(*, profile="development", unlock_reserved=False):
    protocol, checksum = load_protocol()
    if profile not in ("development","reserved"):
        raise ValueError("invalid protocol profile")
    if profile == "reserved" and not unlock_reserved:
        raise ValueError("reserved profile requires deliberate, separately recorded unlock")
    settings = protocol["development" if profile == "development" else "reserved_not_yet_executed"]
    if type(settings["start_index"]) is not int or settings["start_index"] < 0:
        raise ValueError("invalid suite start")
    result={"schema":"developmental-ai.cross-family-results/v1","protocol_sha256":checksum,
            "profile":profile,"independent_blind":False,
            "warning":"All evaluated seeds become inspected. Task-specific policies are NOT cross-family transfer.",
            "rows":[]}
    for family_cfg in protocol["task_families"]:
        family=family_cfg["id"]
        for seed in settings["seeds"]:
            mapping=(train_delayed_mapping(seed, protocol["training"]["episodes_per_seed_delayed"])
                     if family == "delayed" else None)
            for policy in protocol["baselines"]:
                outcomes=[run_episode(family,family_cfg["variant"],seed,settings["split"],settings["start_index"]+i,policy,cue_map=mapping)
                          for i in range(settings["episodes_per_seed_family"])]
                n=len(outcomes)
                result["rows"].append({"family":family,"seed":seed,"policy":policy,"episodes":n,
                    "successes":sum(o["success"] for o in outcomes),
                    "terminal_success_rate":round(sum(o["success"] for o in outcomes)/n,4),
                    "mean_steps":round(sum(o["steps"] for o in outcomes)/n,4),
                    "mean_reward":round(sum(o["reward"] for o in outcomes)/n,4),
                    "valid_action_fraction":1.0})
    return result


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--profile",choices=("development","reserved"),default="development")
    cli.add_argument("--unlock-reserved",action="store_true")
    cli.add_argument("--out",type=Path)
    args=cli.parse_args()
    data=evaluate(profile=args.profile,unlock_reserved=args.unlock_reserved)
    encoded=json.dumps(data,indent=2,sort_keys=True)+"\n"
    if args.out: args.out.write_text(encoded,encoding="utf-8")
    print(encoded,end="")

if __name__=="__main__":main()
