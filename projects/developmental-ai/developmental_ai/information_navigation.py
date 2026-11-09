"""Belief-aware active sensing in a bounded synthetic ring (experimental).

Uses a previously learned probabilistic model and **ordinary** posterior belief;
never reads simulator positions, rewards, regime names, or hidden transitions.
The policy is hand-designed, not learned; no system actions or authority.
"""
from __future__ import annotations

import math

from developmental_ai.adaptive_dynamics import AdaptiveNavigator, ACTIONS, DELTA, READINGS, distance

SCHEMA = "information-navigation/v1"


def entropy(distribution):
    if not distribution or any(type(p) not in (float, int) or not math.isfinite(p) or p < 0 for p in distribution):
        raise ValueError("invalid probability distribution")
    if not math.isclose(sum(distribution), 1.0, rel_tol=1e-7, abs_tol=1e-7):
        raise ValueError("probabilities must sum to one")
    return -sum(p * math.log(p) for p in distribution if p)


def anticipated_observations(belief, model, action):
    """Return prior next-position belief and P(next position, odometry, marker).

    The model does not know which latent movement will actually occur. This
    enumeration marginalizes possible motions and all 9 sensor outcomes.
    """
    n = len(belief)
    if n not in (9, 11) or type(action) is not int or action not in (0, 1):
        raise ValueError("invalid spatial prediction request")
    entropy(belief)
    cmd = ACTIONS[action]
    predicted = [0.0] * n
    joint = [[[0.0] * n for _ in READINGS] for _ in DELTA]
    movements = model.motion_probs(cmd)
    if len(movements) != 3 or any(not math.isfinite(p) or p < 0 for p in movements) or not math.isclose(sum(movements), 1.0, abs_tol=1e-7):
        raise ValueError("invalid movement model")
    for old, mass in enumerate(belief):
        if mass <= 0:
            continue
        for delta, movement_p in zip((cmd, 0, -cmd), movements):
            pos = (old + delta) % n
            probability = mass * movement_p
            predicted[pos] += probability
            odometry = model.odo_probs(delta)
            markers = model.landmark_probs(n, pos)
            for oi in range(3):
                for mi in range(3):
                    joint[oi][mi][pos] += probability * odometry[oi] * markers[mi]
    if not math.isclose(sum(predicted), 1.0, abs_tol=1e-7):
        raise ValueError("invalid movement probabilities")
    if not math.isclose(sum(sum(sum(v) for v in rows) for rows in joint), 1.0, abs_tol=1e-7):
        raise ValueError("invalid sensor probabilities")
    return predicted, joint


def expected_information_gain(belief, model, action):
    """Mutual information I(next position; odometry, marker | action, belief)."""
    predicted, joint = anticipated_observations(belief, model, action)
    expected_conditional = 0.0
    for by_marker in joint:
        for by_position in by_marker:
            p_obs = sum(by_position)
            if p_obs:
                expected_conditional += p_obs * entropy([p / p_obs for p in by_position])
    gain = entropy(predicted) - expected_conditional
    if gain < -1e-8 or not math.isfinite(gain):
        raise ValueError("invalid information gain")
    return max(0.0, gain), predicted


class InformationNavigator(AdaptiveNavigator):
    """Explicit exploration/exploitation balance, with unchanged Bayes filter.

    A coefficient of zero gives the original heuristic's expected-distance
    decision; the original 0.45 terminal collection threshold is untouched.
    """
    def __init__(self, initial, goal, n, model, *, information_weight=0.0):
        if type(information_weight) not in (int, float) or not math.isfinite(information_weight) or not 0 <= information_weight <= 4:
            raise ValueError("invalid information weight")
        super().__init__(initial, goal, n, model)
        self.information_weight = float(information_weight)

    def choose(self):
        if self.information_weight == 0.0:
            return self.heuristic()  # identical legacy action and tie-breaking
        if self.probs[self.goal] >= .45:
            return 2
        utilities = []
        for action in (0, 1):
            if self.information_weight:
                gain, predicted = expected_information_gain(self.probs, self.model, action)
            else:
                predicted, _ = anticipated_observations(self.probs, self.model, action)
                gain = 0.0
            goal_distance = sum(p * distance(pos, self.goal, self.n) for pos, p in enumerate(predicted))
            utilities.append(-goal_distance + self.information_weight * gain)
        return 0 if utilities[0] > utilities[1] else 1


def run_navigation(model, seed, index, noise, layout, *, split="test", information_weight=0.0):
    """Run simulation; only benchmark harness accesses environment truth."""
    from developmental_ai.adaptive_dynamics import CalibrationWorld
    world = CalibrationWorld(seed, split, index, noise, layout)
    nav = InformationNavigator(world.initial, world.goal, world.n, model, information_weight=information_weight)
    event = None
    while not world.done:
        action = nav.choose()
        observation, _, _, event = world.step(action)
        nav.advance(action, observation)
    return event == "success"
