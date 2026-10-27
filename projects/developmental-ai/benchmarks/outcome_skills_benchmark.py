"""Development-only symbolic skill composition with rotated action identifiers.

The action glyphs and fact names are engineered invariants, so this does not
validate transfer between independently designed task domains.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from developmental_ai.outcome_skills import OutcomeSkills, SCHEMA, canonical, digest

TRAIN = ("metal", "wood")
TEST = ("assembly", "delivery")
RECIPES = {
    "collect_ore": ((), "ore"),
    "smelt": (("ore",), "ingot"),
    "collect_wood": ((), "wood"),
    "cut": (("wood",), "plank"),
    "assemble": (("ingot", "plank"), "tool"),
    "package": (("tool",), "parcel"),
    "deliver": (("parcel",), "sent"),
    "dye": ((), "color"),
    "polish": ((), "shine"),
    "inspect": ((), "check"),
}
FAMILIES = {
    "metal": ("collect_ore", "smelt", "inspect"),
    "wood": ("collect_wood", "cut", "polish"),
    "assembly": ("collect_ore", "smelt", "collect_wood", "cut", "assemble", "dye", "polish", "inspect"),
    "delivery": ("collect_ore", "smelt", "collect_wood", "cut", "assemble", "package", "deliver", "dye", "polish", "inspect"),
}
GOAL = {"metal":"smelt", "wood":"cut", "assembly":"assemble", "delivery":"deliver"}
LIMIT = {"metal":6,"wood":6,"assembly":8,"delivery":10}
DEV = (17011, 17021, 17027)
EXTRA = (33011, 33023, 33031)
EPISODES = 60
TRAIN_EPISODES = 80


def seeded(seed, split, index, family):
    if type(seed) is not int or split not in ("train", "test") or type(index) is not int or not 0 <= index < 1000000 or family not in FAMILIES:
        raise ValueError("invalid simulator configuration")
    h = hashlib.sha256(canonical([SCHEMA, seed, split, index, family]).encode()).digest()
    return random.Random(int.from_bytes(h[:8], "big"))


class SkillWorld:
    """Hidden recipes; the public frame exposes only action glyphs and facts."""
    def __init__(self, seed, family, split, index):
        rng = seeded(seed, split, index, family)
        self.family = family
        self.goal = GOAL[family]
        self.limit = LIMIT[family]
        self.names = {g: f"act_{rng.getrandbits(56):014x}" for g in FAMILIES[family]}
        self.reverse = {v:k for k,v in self.names.items()}
        self.order = list(FAMILIES[family])
        rng.shuffle(self.order)
        self.facts = set()
        self.completed = set()
        self.tick = 0
        self.done = False
        self.episode = digest([SCHEMA, seed, split, index, family])

    def frame(self):
        return {"schema":SCHEMA, "episode":self.episode, "tick":self.tick,
                "remaining":self.limit-self.tick,
                "facts":sorted(self.facts),
                "actions":[{"id":self.names[g], "glyph":g} for g in self.order if g not in self.completed] if not self.done else [],
                "goal":self.names[self.goal], "done":self.done, "scope":"simulation-only"}

    def step(self, action, expected_tick):
        if (self.done or expected_tick != self.tick or type(action) is not str
            or action not in self.reverse or self.reverse[action] in self.completed):
            raise ValueError("invalid, stale or unavailable simulated action")
        glyph = self.reverse[action]
        req, effect = RECIPES[glyph]  # hidden from learner
        accepted = set(req) <= self.facts
        self.tick += 1
        if accepted:
            self.facts.add(effect)
            self.completed.add(glyph)
        success = accepted and glyph == self.goal
        self.done = success or self.tick == self.limit
        return {"accepted": accepted, "event": "goal" if success else ("timeout" if self.done else ("accepted" if accepted else "blocked")),
                "frame":self.frame()}


def run(seed, family, split, index, agent=None, policy="learned", learning=False):
    if policy not in ("learned", "random", "oracle", "no_memory"):
        raise ValueError("invalid evaluation method")
    world = SkillWorld(seed, family, split, index)
    rng = seeded(seed, split, index, family)
    blocked = set()
    total_blocked = 0
    while not world.done:
        frame = world.frame()
        if policy == "oracle":
            def resolve(glyph):
                for req in RECIPES[glyph][0]:
                    if req not in world.facts:
                        provider = next(g for g in FAMILIES[family] if RECIPES[g][1] == req)
                        return resolve(provider)
                return glyph
            pick = world.names[resolve(world.goal)]
        elif policy == "random":
            pick = rng.choice([a["id"] for a in frame["actions"]])
        else:
            picker = agent if policy == "learned" else OutcomeSkills()
            pick = picker.choose(frame, blocked)
        outcome = world.step(pick, frame["tick"])
        total_blocked += not outcome["accepted"]
        if learning and policy == "learned":
            agent.observe(world.reverse[pick], frame["facts"], outcome["frame"]["facts"], outcome["accepted"])
        if outcome["accepted"]:
            blocked.clear()
        else:
            blocked.add(pick)
    return {"success": GOAL[family] in world.completed, "attempts": world.tick, "blocked": total_blocked}


def learn(seed, train_families=TRAIN, episodes=TRAIN_EPISODES):
    agent = OutcomeSkills()
    for i in range(episodes):
        family = train_families[i % len(train_families)]
        run(seed, family, "train", i, agent, learning=True)
    return agent


def measure(seeds=DEV):
    if tuple(seeds) not in (DEV, EXTRA):
        raise ValueError("development cohorts are predeclared")
    output = {"schema":"developmental-ai.outcome-skills-benchmark/v1", "blind":False,
              "engineered_shared_glyphs":True, "train_families":list(TRAIN),
              "evaluation_families":list(TEST), "episodes_per_family":EPISODES,
              "training_episodes":TRAIN_EPISODES, "rows":[]}
    for seed in seeds:
        agent = learn(seed)
        restored = OutcomeSkills.restore(agent.record())
        target_only = learn(seed, TEST)
        scores = {}
        for family in TEST:
            scores[family] = {}
            for method in ("learned", "target_only", "no_memory", "random", "oracle"):
                learner = (restored if method == "learned" else target_only if method == "target_only" else None)
                policy = "learned" if method in ("learned", "target_only") else method
                out = [run(seed, family, "test", 90000+j, learner, policy) for j in range(EPISODES)]
                scores[family][method] = {"success":sum(r["success"] for r in out),
                    "mean_attempts":round(sum(r["attempts"] for r in out)/EPISODES, 3),
                    "mean_blocked":round(sum(r["blocked"] for r in out)/EPISODES, 3)}
        output["rows"].append({"seed":seed,"scores":scores,
                               "learned_glyphs":len(agent.knowledge()),
                               "sha256": agent.record()["sha256"]})
    return output


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--cohort",choices=("dev","additional"),default="dev")
    args=ap.parse_args()
    print(json.dumps(measure(DEV if args.cohort=="dev" else EXTRA),indent=2,sort_keys=True))


if __name__ == "__main__":
    main()
