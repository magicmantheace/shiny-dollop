"""No-context, bounded plan-repair research in a hidden-prerequisite sandbox.

Public frames reveal only opaque stable role tags, shuffled action names,
completed actions and accepted/blocked outcomes. The hidden graph and phase
are simulator-private. Learned successful plans are *whole-trace cache items*,
not general causal skills. No tool or OS operations are exposed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random

SCHEMA = 'developmental-ai.plan-repair/v1'
FRAME_SCHEMA = 'developmental-ai.plan-repair-frame/v1'
MAX_STEPS = 7
MAX_EVENTS = 1000
MODES = ('repair', 'latest', 'reset', 'reactive')


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()


def rng(seed, *parts):
    return random.Random(int.from_bytes(hashlib.sha256(canonical([SCHEMA, seed, *parts]).encode()).digest()[:8], 'big'))


def opaque_roles(seed):
    if type(seed) is not int:
        raise ValueError('invalid seed')
    return [f'role_{digest([SCHEMA, seed, i])[:12]}' for i in range(7)]


class RepairWorld:
    """Private A/B/A hidden graphs; never publishes its phase or requirements."""

    def __init__(self, seed, split, index):
        if (type(seed) is not int or split not in ('train', 'test') or
                type(index) is not int or not 0 <= index < 1000000):
            raise ValueError('invalid simulated episode')
        self.seed, self.split, self.index = seed, split, index
        role = opaque_roles(seed)
        aliases = [f'act_{i}_{rng(seed, split, index, i).getrandbits(32):08x}' for i in range(7)]
        rng(seed, split, index, 'shuffle').shuffle(aliases)
        self.role_to_name = dict(zip(role, aliases))
        self.name_to_role = {name: key for key, name in self.role_to_name.items()}
        phase = (index - 87000) % 80
        self._variant = 'B' if 20 <= phase < 60 else 'A'
        extra = role[3] if self._variant == 'B' else role[1]
        self._requirements = {role[2]: (role[0], extra), role[6]: (role[2],)}
        self.goal = self.role_to_name[role[6]]
        self.completed = []
        self.tick = 0
        self.done = False
        self.id = digest([SCHEMA, seed, split, index, self.name_to_role])

    def frame(self):
        return {'schema': FRAME_SCHEMA, 'episode_id': self.id,
                'roles': dict(sorted(self.name_to_role.items())),
                'goal': self.goal, 'tick': self.tick, 'remaining': MAX_STEPS-self.tick,
                'completed': list(self.completed), 'done': self.done,
                'available_actions': [] if self.done else sorted(set(self.name_to_role)-set(self.completed)),
                'scope': 'simulation-only'}

    def step(self, action, *, expected_tick):
        before = self.frame()
        if (self.done or type(action) is not str or action not in before['available_actions'] or
                type(expected_tick) is not int or expected_tick != self.tick):
            raise ValueError('illegal or stale sandbox action')
        role = self.name_to_role[action]
        prior = {self.name_to_role[name] for name in self.completed}
        accepted = all(p in prior for p in self._requirements.get(role, ()))
        if accepted:
            self.completed.append(action)
        self.tick += 1
        goal = accepted and action == self.goal
        self.done = goal or self.tick == MAX_STEPS
        event = 'goal' if goal else 'timeout' if self.done else 'accepted' if accepted else 'blocked'
        return {'frame': self.frame(), 'accepted': accepted, 'event': event}


def check_frame(f):
    fields = {'schema','episode_id','roles','goal','tick','remaining','completed','done','available_actions','scope'}
    if (type(f) is not dict or set(f) != fields or f['schema'] != FRAME_SCHEMA or
            f['scope'] != 'simulation-only' or type(f['episode_id']) is not str or
            len(f['episode_id']) != 64 or type(f['roles']) is not dict or
            len(f['roles']) != 7 or len(set(f['roles'].values())) != 7 or
            any(type(k) is not str or type(v) is not str or not v.startswith('role_') for k,v in f['roles'].items()) or
            type(f['goal']) is not str or f['goal'] not in f['roles'] or
            type(f['tick']) is not int or not 0 <= f['tick'] <= MAX_STEPS or
            type(f['remaining']) is not int or f['remaining'] != MAX_STEPS-f['tick'] or
            type(f['completed']) is not list or len(f['completed']) != len(set(f['completed'])) or
            any(type(a) is not str or a not in f['roles'] for a in f['completed']) or
            len(f['completed']) > f['tick'] or type(f['done']) is not bool or
            f['done'] != (f['goal'] in f['completed'] or f['tick'] == MAX_STEPS) or
            type(f['available_actions']) is not list):
        raise ValueError('invalid or privileged public frame')
    if f['available_actions'] != ([] if f['done'] else sorted(set(f['roles']) - set(f['completed']))):
        raise ValueError('forged available actions')
    return f


class RepairPlanMemory:
    """Replay-checked accepted-plan cache with per-stage blocked-action recovery."""

    def __init__(self, seed, *, mode='repair'):
        if type(seed) is not int or mode not in MODES:
            raise ValueError('invalid memory configuration')
        self.seed, self.mode = seed, mode
        self.plans = []
        self.events = []
        self.pending = None
        self.last = None
        self.accepted_order = []

    def _blocked(self, frame):
        size = len(frame['completed'])
        return {e['action'] for e in self.events if
                e['before']['episode_id'] == frame['episode_id'] and
                len(e['before']['completed']) == size and not e['result']['accepted']}

    def _pick(self, frame):
        roles = frame['roles']
        done = {roles[name] for name in frame['completed']}
        blocked = self._blocked(frame) if self.mode in ('repair','reactive') else set()
        actions = frame['available_actions']
        plan = None if self.mode in ('reset','reactive') else (self.plans[-1] if self.plans else None)
        if plan:
            # Old plan actions that just failed cannot be retried until progress.
            for role in plan:
                if role not in done:
                    action = next((a for a in actions if roles[a] == role), None)
                    if action is not None and action not in blocked:
                        return action
                    if action in blocked:
                        if self.mode == 'latest':
                            return action  # deliberate unprotected historical baseline
                        break  # repair the missing prerequisite before later cached steps
            else:
                # Every cached prerequisite has been accepted.
                if frame['goal'] in actions and frame['goal'] not in blocked:
                    return frame['goal']
        # Explore untried roles at this *progress level*; action names change
        # between episodes but stable role labels permit recall.
        candidates = [a for a in actions if a not in blocked and a != frame['goal']]
        if candidates:
            if self.mode == 'repair' and plan:
                used = set(plan)
                unseen = [a for a in candidates if roles[a] not in used]
                if unseen:
                    candidates = unseen
            return min(candidates, key=lambda a: digest([SCHEMA, self.seed, frame['episode_id'], roles[a]]))
        if frame['goal'] in actions and frame['goal'] not in blocked:
            return frame['goal']
        return None

    def propose(self, frame):
        check_frame(frame)
        if self.pending is not None or len(self.events) >= MAX_EVENTS or frame['done']:
            raise ValueError('invalid proposal state')
        if self.last is not None:
            if frame['episode_id'] == self.last['episode_id']:
                if frame != self.last:
                    raise ValueError('non-contiguous frame')
            elif not self.last['done'] or frame['tick'] != 0:
                raise ValueError('cannot abandon unfinished episode')
            else:
                self.accepted_order = []
        action = self._pick(frame)
        if action is not None:
            self.pending = {'before':copy.deepcopy(frame),'action':action}
        return action

    def feedback(self, result):
        if self.pending is None or type(result) is not dict or set(result) != {'frame','accepted','event'}:
            raise ValueError('unrequested feedback')
        before, action = self.pending['before'], self.pending['action']
        after = check_frame(result['frame'])
        accepted = result['accepted']
        if (type(accepted) is not bool or after['episode_id'] != before['episode_id'] or
                after['roles'] != before['roles'] or after['goal'] != before['goal'] or
                after['tick'] != before['tick']+1 or
                after['completed'] != before['completed'] + ([action] if accepted else [])):
            raise ValueError('inconsistent action feedback')
        reached = accepted and action == before['goal']
        end = reached or after['tick'] == MAX_STEPS
        label = 'goal' if reached else 'timeout' if end else 'accepted' if accepted else 'blocked'
        if after['done'] != end or result['event'] != label:
            raise ValueError('inconsistent completion event')
        if accepted:
            self.accepted_order.append(before['roles'][action])
        if reached and self.mode not in ('reset','reactive'):
            plan = list(self.accepted_order)
            if plan not in self.plans:
                if self.mode == 'latest':
                    self.plans = [plan]
                else:
                    self.plans.append(plan)
                    self.plans = self.plans[-16:]
        self.events.append({'before':copy.deepcopy(before),'action':action,'result':copy.deepcopy(result)})
        self.pending = None
        self.last = copy.deepcopy(after)

    def record(self):
        if self.pending is not None or len(self.events) > MAX_EVENTS:
            raise ValueError('cannot snapshot pending or oversized session')
        state = {'schema':SCHEMA,'seed':self.seed,'mode':self.mode,'plans':copy.deepcopy(self.plans),
                 'events':copy.deepcopy(self.events),'last':copy.deepcopy(self.last),
                 'accepted_order':list(self.accepted_order)}
        return {'state':state,'sha256':digest(state)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record) != {'state','sha256'} or
                type(record['state']) is not dict or digest(record['state']) != record['sha256']):
            raise ValueError('invalid checkpoint integrity')
        s = record['state']
        if (set(s) != {'schema','seed','mode','plans','events','last','accepted_order'} or
                s['schema'] != SCHEMA or type(s['events']) is not list or len(s['events']) > MAX_EVENTS):
            raise ValueError('unsupported checkpoint schema')
        obj = cls(s['seed'], mode=s['mode'])
        for e in s['events']:
            if type(e) is not dict or set(e) != {'before','action','result'}:
                raise ValueError('malformed saved action')
            if obj.propose(e['before']) != e['action']:
                raise ValueError('saved action disagrees with deterministic policy')
            obj.feedback(e['result'])
        if canonical(obj.record()) != canonical(record):
            raise ValueError('saved plans or progress do not replay')
        return obj
