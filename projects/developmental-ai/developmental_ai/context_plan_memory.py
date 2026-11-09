"""Experimental context-keyed procedural episode reuse, simulation-only.

Public frames show stable opaque role tokens and an opaque context; hidden
prerequisites never reach a policy. A successful ordered action trace is an
engineered plan-memory item, not discovered semantics or general D4 skills.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random

SCHEMA = 'developmental-ai.context-plan/v1'
FRAME = 'developmental-ai.context-plan-frame/v1'
MAX_STEPS = 7
MAX_EVENTS = 3000
MODES = ('context', 'latest', 'reset')


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode()).hexdigest()


def _rand(seed, *parts):
    return random.Random(int.from_bytes(hashlib.sha256(canonical([SCHEMA, seed, *parts]).encode()).digest()[:8], 'big'))


def labels(seed):
    if type(seed) is not int:
        raise ValueError('invalid seed')
    rng = _rand(seed, 'role-labels')
    roles = [f'key_{rng.getrandbits(32):08x}' for _ in range(7)]
    if len(set(roles)) != 7:raise ValueError('role collision')
    contexts = [f'case_{rng.getrandbits(32):08x}' for _ in range(2)]
    return roles, contexts


class NovelProcedure:
    """Separate simulator; its private graph is inaccessible in public frames."""
    def __init__(self, seed, split, index):
        if (type(seed) is not int or split not in ('test', 'train') or
                type(index) is not int or not 0 <= index < 1000000):
            raise ValueError('invalid simulated episode namespace')
        self.seed, self.split, self.index = seed, split, index
        roles, contexts = labels(seed)
        self.context = contexts[index % 2]
        rng = _rand(seed, split, index, 'action-aliases')
        aliases = [f'item_{i}_{rng.getrandbits(24):06x}' for i in range(7)]
        rng.shuffle(aliases)
        self.names = dict(zip(roles, aliases))
        self.alias_roles = {name: role for role, name in self.names.items()}
        if index % 2 == 0:
            self._requirements = {roles[2]: (roles[0], roles[1]), roles[6]: (roles[2],)}
        else:
            self._requirements = {roles[4]: (roles[3],), roles[5]: (roles[4],), roles[6]: (roles[5],)}
        self.goal = self.names[roles[6]]
        self.completed = []
        self.tick = 0
        self.done = False
        self.episode_id = digest([SCHEMA, seed, split, index, self.context, self.alias_roles])

    def frame(self):
        return {'schema': FRAME, 'episode_id': self.episode_id,
                'context': self.context, 'roles': dict(sorted(self.alias_roles.items())),
                'goal': self.goal, 'tick': self.tick, 'done': self.done,
                'completed': list(self.completed), 'remaining': MAX_STEPS-self.tick,
                'available_actions': [] if self.done else sorted(set(self.alias_roles)-set(self.completed)),
                'scope': 'simulation-only'}

    def step(self, action, *, expected_tick):
        f = self.frame()
        if (self.done or type(action) is not str or action not in f['available_actions'] or
                type(expected_tick) is not int or expected_tick != self.tick):
            raise ValueError('invalid or stale proposed action')
        role = self.alias_roles[action]
        held = {self.alias_roles[a] for a in self.completed}
        accepted = all(p in held for p in self._requirements.get(role, ()))
        if accepted:self.completed.append(action)
        self.tick += 1
        reached = accepted and action == self.goal
        self.done = reached or self.tick == MAX_STEPS
        return {'frame': self.frame(), 'accepted': accepted,
                'event': 'goal' if reached else 'timeout' if self.done else 'accepted' if accepted else 'blocked'}


def validate_frame(frame):
    if (type(frame) is not dict or set(frame) != {'schema','episode_id','context','roles','goal','tick','done',
                                                 'completed','remaining','available_actions','scope'} or
            frame['schema'] != FRAME or frame['scope'] != 'simulation-only' or
            type(frame['episode_id']) is not str or len(frame['episode_id']) != 64 or
            type(frame['context']) is not str or not frame['context'].startswith('case_') or
            type(frame['roles']) is not dict or len(frame['roles']) != 7 or
            any(type(k) is not str or type(v) is not str for k,v in frame['roles'].items()) or
            len(set(frame['roles'].values())) != 7 or
            type(frame['goal']) is not str or frame['goal'] not in frame['roles'] or
            type(frame['tick']) is not int or not 0 <= frame['tick'] <= MAX_STEPS or
            type(frame['done']) is not bool or type(frame['completed']) is not list or
            len(set(frame['completed'])) != len(frame['completed']) or
            any(name not in frame['roles'] for name in frame['completed']) or
            len(frame['completed']) > frame['tick'] or type(frame['remaining']) is not int or
            frame['remaining'] != MAX_STEPS-frame['tick'] or
            frame['done'] != (frame['goal'] in frame['completed'] or frame['tick'] == MAX_STEPS) or
            type(frame['available_actions']) is not list):
        raise ValueError('invalid public procedure frame')
    expected = [] if frame['done'] else sorted(set(frame['roles'])-set(frame['completed']))
    if frame['available_actions'] != expected:
        raise ValueError('forged action set')
    return frame


class ContextPlanMemory:
    """Replayable plan library learned strictly from the agent's own outcomes."""
    def __init__(self, seed, *, mode='context'):
        if type(seed) is not int or mode not in MODES:
            raise ValueError('invalid plan memory mode')
        self.seed, self.mode = seed, mode
        self.plans = {}
        self.events = []
        self.pending = None
        self.last = None
        self.accepted_order = []

    def _plan(self, context):
        return self.plans.get(context if self.mode == 'context' else '*') if self.mode != 'reset' else None

    def _pick(self, frame):
        roles = frame['roles']
        completed = {roles[n] for n in frame['completed']}
        relevant = self._plan(frame['context'])
        if relevant:
            for role in relevant:
                if role not in completed:
                    name = next((n for n in frame['available_actions'] if roles[n] == role), None)
                    if name is not None:
                        return name
        prior = [e for e in self.events if e['before']['episode_id'] == frame['episode_id']]
        blocked = {(e['action'], len(e['before']['completed'])) for e in prior if not e['result']['accepted']}
        # Never repeat blocked attempts until progress is observed.
        candidates = [a for a in frame['available_actions'] if
                      (a, len(frame['completed'])) not in blocked and a != frame['goal']]
        if len(frame['completed']) >= 3 and frame['goal'] in frame['available_actions'] and (frame['goal'],len(frame['completed'])) not in blocked:
            return frame['goal']
        if candidates:
            # Unknown role meanings: use reproducible *episode*-specific exploration order.
            return min(candidates, key=lambda name: digest([SCHEMA, self.seed, frame['episode_id'], roles[name]]))
        if frame['goal'] in frame['available_actions'] and (frame['goal'],len(frame['completed'])) not in blocked:
            return frame['goal']
        return None

    def propose(self, frame):
        validate_frame(frame)
        if self.pending is not None or len(self.events) >= MAX_EVENTS:
            raise ValueError('pending or event cap')
        if self.last is not None:
            if frame['episode_id'] == self.last['episode_id']:
                if frame != self.last or self.last['done']:
                    raise ValueError('invalid same-episode continuation')
            elif not self.last['done'] or frame['tick'] != 0:
                raise ValueError('unfinished previous episode')
            else:
                self.accepted_order = []
        picked = self._pick(frame)
        if picked is None: return None
        self.pending = {'before': copy.deepcopy(frame), 'action': picked}
        return picked

    def feedback(self, result):
        if self.pending is None or type(result) is not dict or set(result) != {'frame','accepted','event'}:
            raise ValueError('invalid or unrequested feedback')
        before = self.pending['before']
        after = result['frame']
        validate_frame(after)
        name = self.pending['action']
        accepted = result['accepted']
        if type(accepted) is not bool or before['episode_id'] != after['episode_id'] or before['roles'] != after['roles'] or before['context'] != after['context'] or before['goal'] != after['goal'] or after['tick'] != before['tick']+1:
            raise ValueError('inconsistent public outcome')
        if after['completed'] != before['completed'] + ([name] if accepted else []):
            raise ValueError('impossible action outcome')
        reached = accepted and name == before['goal']
        done = reached or after['tick'] == MAX_STEPS
        expected_event = 'goal' if reached else 'timeout' if done else 'accepted' if accepted else 'blocked'
        if after['done'] != done or result['event'] != expected_event:
            raise ValueError('inconsistent terminal outcome')
        if accepted:self.accepted_order.append(before['roles'][name])
        if reached and self.mode != 'reset':
            key = before['context'] if self.mode == 'context' else '*'
            candidate = list(self.accepted_order)
            previous = self.plans.get(key)
            if self.mode == 'latest' or previous is None or len(candidate) < len(previous):self.plans[key] = candidate
        self.events.append({'before': before, 'action': name, 'result': copy.deepcopy(result)})
        self.pending = None
        self.last = copy.deepcopy(after)

    def record(self):
        if self.pending is not None:raise ValueError('cannot persist pending action')
        state = {'schema':SCHEMA, 'seed':self.seed, 'mode':self.mode,
                 'plans':copy.deepcopy(self.plans), 'events':copy.deepcopy(self.events),
                 'last':copy.deepcopy(self.last), 'accepted_order':list(self.accepted_order)}
        return {'state':state, 'sha256':digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {'state','sha256'} or type(record['state']) is not dict or
                record['sha256'] != digest(record['state'])):
            raise ValueError('invalid checkpoint checksum')
        s = record['state']
        if set(s) != {'schema','seed','mode','plans','events','last','accepted_order'} or s['schema'] != SCHEMA or type(s['events']) is not list or len(s['events']) > MAX_EVENTS:
            raise ValueError('unknown plan memory schema')
        obj = cls(s['seed'], mode=s['mode'])
        for event in s['events']:
            if type(event) is not dict or set(event) != {'before','action','result'}:
                raise ValueError('invalid plan history')
            if obj.propose(event['before']) != event['action']:
                raise ValueError('saved action contradicts policy replay')
            obj.feedback(event['result'])
        if canonical(obj.record()) != canonical(record):
            raise ValueError('checkpoint state cannot be reconstructed')
        return obj
