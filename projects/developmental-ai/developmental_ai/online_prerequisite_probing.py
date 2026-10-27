"""Bounded in-task prerequisite learning from public accepted/blocked action feedback.

The learner never sees the simulator's hidden DAG. It maintains an explicit
posterior over possible prerequisite subsets for every role and environment
family; within an episode it avoids repeating a blocked action until progress.
Nothing here authorizes real actions, learns new action semantics, or supplies
system permissions. This is simulation-only D3/D4 research.
"""
from __future__ import annotations

import copy
import hashlib
import math

from developmental_ai.hidden_prerequisites import (
    ROLES, FAMILIES, MAX_ATTEMPTS, validate_frame, canonical, digest,
)

SCHEMA = "developmental-ai.online-prerequisite-probing/v1"
PRIOR_EDGE = .18
MAX_HISTORY = 2500
OTHER = {role: tuple(r for r in ROLES if r != role) for role in ROLES}


def _weights():
    return {role: [PRIOR_EDGE ** mask.bit_count() * (1-PRIOR_EDGE) ** (6-mask.bit_count())
                    for mask in range(64)] for role in ROLES}


def _readiness(weights, role, present):
    options = OTHER[role]
    current_mask = sum(1 << j for j, pre in enumerate(options) if pre in present)
    row = weights[role]
    return sum(p for mask, p in enumerate(row) if mask & ~current_mask == 0)


def _edge(weights, target, before):
    bit = 1 << OTHER[target].index(before)
    return sum(w for mask, w in enumerate(weights[target]) if mask & bit)


def _update(weights, role, present, accepted):
    current_mask = sum(1 << j for j, pre in enumerate(OTHER[role]) if pre in present)
    old = weights[role]
    row = [w if ((mask & ~current_mask == 0) == accepted) else 0.
           for mask, w in enumerate(old)]
    z = sum(row)
    if z < 1e-20:
        raise ValueError("inconsistent attempted prerequisite evidence")
    weights[role] = [v/z for v in row]


def _score_tiebreak(seed, episode_id, role):
    b = hashlib.sha256(f'{SCHEMA}/{seed}/{episode_id}/{role}'.encode()).digest()
    return int.from_bytes(b[:8], 'big') / 2**64


class OnlinePrerequisiteAgent:
    """Replayable target-environment online learner with one pending proposal.

    Every action is made solely from a public frame and previous outcomes.
    Each role's prerequisite hypothesis is a mixture over its 64 possible
    subsets. No hidden graph, reward schema changes, true role order or
    simulator state is ever passed to the policy.
    """

    def __init__(self, seed):
        if type(seed) is not int:
            raise ValueError("invalid agent seed")
        self.seed = seed
        self.weights = {family: _weights() for family in FAMILIES}
        self.events = []
        self.pending = None
        self.last = None

    def _choose(self, frame):
        validate_frame(frame)
        fam = frame['family']
        weights = self.weights[fam]
        completed = {frame['roles'][a] for a in frame['completed']}
        goal_role = frame['roles'][frame['goal']]
        current = frame['episode_id']
        previous = [e for e in self.events if e['before']['episode_id'] == current]
        blocked = {e['action']: len(e['before']['completed']) for e in previous if not e['result']['accepted']}
        available = frame['available_actions']
        if not available: raise ValueError("finished environment")
        if not previous: return frame['goal']  # bounded first-hand goal probe, not role-order rule
        goal_prob = _readiness(weights, goal_role, completed)
        if goal_prob >= .76 and (frame['goal'] not in blocked or len(frame['completed']) > blocked[frame['goal']]):
            return frame['goal']
        relevance = {r: 0. for r in ROLES}
        relevance[goal_role] = 1.
        for _ in range(5):
            newer = dict(relevance)
            for target in ROLES:
                for before in OTHER[target]:
                    newer[before] = max(newer[before], .92 * relevance[target] * _edge(weights, target, before))
            relevance = newer
        scores = []
        for name in available:
            role = frame['roles'][name]
            ready = _readiness(weights, role, completed)
            same_state_retry = name in blocked and len(frame['completed']) <= blocked[name]
            if same_state_retry: continue
            # Avoid needless goal retries when there is poor evidence it is ready.
            base = 1.65*ready + 1.4*relevance[role] + .12 * (1-ready)
            if name == frame['goal'] and goal_prob < .55: base -= 1.0
            scores.append((base, _score_tiebreak(self.seed, current, role), name))
        if not scores:
            # No action can be repeated profitably without a completed precondition;
            # the episode is effectively stuck and may stop before budget exhaustion.
            return None
        return max(scores)[2]

    def propose(self, frame):
        if self.pending is not None or len(self.events) >= MAX_HISTORY:
            raise ValueError("already pending or event budget exhausted")
        validate_frame(frame)
        if self.last is not None:
            old = self.last
            if frame['episode_id'] == old['episode_id']:
                if old['done'] or frame != old:
                    raise ValueError("unexpected frame progression")
            elif not old['done']:
                raise ValueError("cannot abandon an unfinished episode")
            elif frame['tick'] != 0:
                raise ValueError("new episode must begin at tick zero")
        action = self._choose(frame)
        if action is None:
            return None
        self.pending = {'before': copy.deepcopy(frame), 'action': action}
        return action

    def feedback(self, result):
        if self.pending is None or type(result) is not dict or set(result) != {'frame','event','accepted','reward'}:
            raise ValueError("missing pending action or malformed outcome")
        before = self.pending['before']
        chosen = self.pending['action']
        after = result['frame']
        validate_frame(after)
        if (before['episode_id'] != after['episode_id'] or before['family'] != after['family'] or
                before['roles'] != after['roles'] or before['goal'] != after['goal'] or
                after['tick'] != before['tick']+1 or
                type(result['accepted']) is not bool or
                type(result['reward']) is not int or result['reward'] not in (-1,0,3)):
            raise ValueError("inconsistent simulator feedback")
        success = result['accepted']
        expected_completed = before['completed'] + ([chosen] if success else [])
        if after['completed'] != expected_completed:
            raise ValueError("forged accepted/blocked transition")
        reached = success and chosen == before['goal']
        done = reached or after['tick'] == MAX_ATTEMPTS
        event = 'goal' if reached else ('timeout' if done else 'accepted' if success else 'blocked')
        if (after['done'] != done or result['event'] != event or
                result['reward'] != (3 if reached else 0 if success else -1)):
            raise ValueError("inconsistent feedback event or reward")
        family = before['family']
        role = before['roles'][chosen]
        present = {before['roles'][a] for a in before['completed']}
        _update(self.weights[family], role, present, success)
        self.events.append({'before': before, 'action': chosen, 'result': copy.deepcopy(result)})
        self.last = copy.deepcopy(after)
        self.pending = None

    def record(self):
        if self.pending is not None: raise ValueError("cannot save pending action")
        state = {'schema': SCHEMA, 'seed': self.seed, 'events': self.events,
                 'weights': self.weights, 'last': self.last}
        return {'state': copy.deepcopy(state), 'sha256': digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {'state','sha256'} or
                type(record['state']) is not dict or digest(record['state']) != record['sha256']):
            raise ValueError("invalid checksum record")
        state = record['state']
        if (set(state) != {'schema','seed','events','weights','last'} or state['schema'] != SCHEMA or
                type(state['events']) is not list or len(state['events']) > MAX_HISTORY):
            raise ValueError("invalid checkpoint schema")
        replay = cls(state['seed'])
        for e in state['events']:
            if type(e) is not dict or set(e) != {'before','action','result'}:
                raise ValueError("invalid episode trace")
            chosen = replay.propose(e['before'])
            if chosen != e['action']:
                raise ValueError("saved action disagrees with replayed policy")
            replay.feedback(e['result'])
        # floating-point and replayed posterior must agree; SHA alone does not suffice
        if canonical(replay.record()) != canonical(record):
            raise ValueError("stored evidence/posterior inconsistent with replay")
        return replay
