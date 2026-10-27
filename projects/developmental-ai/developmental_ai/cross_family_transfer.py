"""Zero-shot policy reuse from visible-target grid to occluded-target grid.

A frozen tabular policy trained ONLY on grid-layout episodes is evaluated on a
separate occluded-goal task via the same D2 EnvironmentSession public contract.
An engineered dead-reckoning adapter converts one-time cues into the existing
3-feature state: this is NOT learned perception, new planning, or general AI.
"""
from __future__ import annotations

import random
from developmental_ai.environment_api import EnvironmentSession
from developmental_ai.occluded_navigation import greedy_action
from developmental_ai.transfer import DELTAS

SCHEMA = "developmental-ai.zero-shot-navigation-transfer/v1"


class SpatialEncoder:
    """Task-specific interpretation, no hidden position or privileged geometry."""
    def __init__(self, family):
        if family not in ("grid", "occluded"):
            raise ValueError("only navigation families supported")
        self.family = family
        self._remaining = None

    def features(self, frame):
        if (type(frame) is not dict or frame.get("family") != self.family or
                frame.get("scope") != "simulation-only" or frame.get("source") != "simulation"):
            raise ValueError("invalid navigation frame")
        obs=frame["observation"]
        if self.family == "grid":
            if set(obs) != {"target_dx","target_dy","blocked"}:
                raise ValueError("privileged or incompatible grid observation")
            dx,dy=obs["target_dx"],obs["target_dy"]
        else:
            if set(obs) != {"beacon","blocked"}:
                raise ValueError("privileged or incompatible occluded observation")
            if obs["beacon"] is not None:
                if self._remaining is not None or frame["tick"] != 0:
                    raise ValueError("repeated target beacon")
                self._remaining=list(obs["beacon"])
            dx,dy=self._remaining if self._remaining is not None else (0,0)
        if (type(dx) is not int or type(dy) is not int or type(obs["blocked"]) is not int
                or not 0 <= obs["blocked"] < 16):
            raise ValueError("invalid navigation features")
        return (max(-3,min(3,dx)),max(-3,min(3,dy)),obs["blocked"])

    def feedback(self, action, outcome):
        if self.family == "occluded" and outcome["event"] == "move":
            if type(action) is not int or action not in range(4) or self._remaining is None:
                raise ValueError("invalid movement feedback")
            dx,dy=DELTAS[action]
            self._remaining[0]-=dx
            self._remaining[1]-=dy


def trial(brain, *, family, seed, split, index, policy):
    if policy not in ("trained_grid", "untrained", "greedy") or family not in ("grid","occluded"):
        raise ValueError("invalid policy or family")
    session=EnvironmentSession(family,seed,split,index)
    encoder=SpatialEncoder(family)
    from benchmarks.environment_contract_benchmark import action_seed
    rng=random.Random(action_seed(seed,split,index,family,policy))
    reward=0.
    last=""
    while not session.done:
        frame=session.frame()
        state=encoder.features(frame)
        if policy=="greedy":action=greedy_action(state,rng)
        elif policy=="untrained":action=rng.randrange(5)
        else:action=brain._choose(state,0.,rng)
        result=session.step(action,expected_tick=session.tick)
        encoder.feedback(action,result)
        last=result["event"]
        reward+=result["reward"]
    return {"success":last in ("food","collected"),"steps":session.tick,"reward":reward}
