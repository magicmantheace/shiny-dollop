"""Experimental hidden-precondition skill learner, sandbox only.

The simulator withholds its prerequisite DAG. Public frames provide opaque
per-episode names, stable engineered role tags, completed steps and the goal.
Training learns only from accepted/blocked actions and goal feedback. The
retained role vocabulary is a substantial transfer assumption; nothing here
is a general causal-discovery system or permitted external action.
"""
from __future__ import annotations

import hashlib
import json
import random
from collections import defaultdict

SCHEMA = 'developmental-ai.hidden-prerequisites/v1'
MODEL_SCHEMA = 'developmental-ai.hidden-precondition-skill/v1'
FRAME_SCHEMA = 'developmental-ai.hidden-procedure-frame/v1'
ROLES = ('gather_a', 'gather_b', 'assemble', 'deliver', 'inspect', 'pack', 'verify')
FAMILIES = ('workshop', 'repair')
MAX_ATTEMPTS = 12
TRAIN_EPISODES = 360


def canonical(x):
    return json.dumps(x,sort_keys=True,separators=(',', ':'),allow_nan=False)


def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()


def _rng(seed,family,split,index,label):
    if (type(seed) is not int or family not in FAMILIES or split not in ('train','test') or
            type(index) is not int or not 0<=index<1000000):
        raise ValueError('invalid bounded procedural episode')
    key=f'{SCHEMA}/{seed}/{family}/{split}/{index}/{label}'
    return random.Random(int.from_bytes(hashlib.sha256(key.encode()).digest()[:8],'big'))


class HiddenProcedure:
    """Actions may be attempted before prerequisites; a block costs one tick."""
    def __init__(self,seed,family,split,index):
        self.config={'seed':seed,'family':family,'split':split,'index':index}
        rng=_rng(seed,family,split,index,'aliases')
        aliases=[f'{"wrk" if family=="workshop" else "fix"}_{n:02d}' for n in range(7)]
        rng.shuffle(aliases)
        self.role_to_name=dict(zip(ROLES,aliases))
        self.name_to_role={v:k for k,v in self.role_to_name.items()}
        if family=='workshop':
            dependencies={'assemble':('gather_a','gather_b'),'deliver':('assemble',)}
            self.goal_role='deliver'
        else:
            dependencies={'inspect':('gather_a',),'pack':('gather_b',),'verify':('inspect','pack')}
            self.goal_role='verify'
        self._requirements={r:tuple(dependencies.get(r,())) for r in ROLES}
        self.completed=[];self.tick=0;self.done=False
        self.episode_id=digest({'config':self.config,'roles':self.role_to_name,'schema':SCHEMA})

    def frame(self):
        return {'schema':FRAME_SCHEMA,'episode_id':self.episode_id,'family':self.config['family'],
                'tick':self.tick,'roles':{name:role for name,role in sorted(self.name_to_role.items())},
                'goal':self.role_to_name[self.goal_role],
                'completed':list(self.completed),
                'available_actions':([] if self.done else sorted(name for name in self.name_to_role if name not in self.completed)),
                'remaining':MAX_ATTEMPTS-self.tick,'done':self.done,'scope':'simulation-only'}

    def step(self,action,*,expected_tick):
        f=self.frame()
        if (type(action) is not str or action not in f['available_actions'] or
                type(expected_tick) is not int or expected_tick!=self.tick or self.done):
            raise ValueError('invalid/stale simulated action')
        role=self.name_to_role[action]
        completed_roles={self.name_to_role[name] for name in self.completed}
        allowed=all(req in completed_roles for req in self._requirements[role])
        self.tick+=1
        if allowed:self.completed.append(action)
        reached=allowed and role==self.goal_role
        self.done=reached or self.tick>=MAX_ATTEMPTS
        event='goal' if reached else ('timeout' if self.done else 'accepted' if allowed else 'blocked')
        return {'frame':self.frame(),'event':event,'accepted':allowed,
                'reward':3 if reached else (0 if allowed else -1)}


def validate_frame(f):
    if (type(f) is not dict or set(f)!={'schema','episode_id','family','tick','roles','goal',
           'completed','available_actions','remaining','done','scope'} or
            f['schema']!=FRAME_SCHEMA or f['family'] not in FAMILIES or f['scope']!='simulation-only' or
            type(f['episode_id']) is not str or len(f['episode_id'])!=64 or
            type(f['roles']) is not dict or set(f['roles'].values())!=set(ROLES) or
            len(f['roles'])!=7 or any(type(a) is not str for a in f['roles']) or
            type(f['goal']) is not str or f['goal'] not in f['roles'] or
            type(f['completed']) is not list or len(set(f['completed']))!=len(f['completed']) or
            any(a not in f['roles'] for a in f['completed']) or
            type(f['tick']) is not int or not 0<=f['tick']<=MAX_ATTEMPTS or
            type(f['remaining']) is not int or f['tick']+f['remaining']!=MAX_ATTEMPTS or
            type(f['done']) is not bool or type(f['available_actions']) is not list):
        raise ValueError('invalid or privileged public frame')
    expected=[] if f['done'] else sorted(set(f['roles'])-set(f['completed']))
    if expected!=f['available_actions'] or f['done']!=(f['goal'] in f['completed'] or f['tick']==MAX_ATTEMPTS):
        raise ValueError('impossible public progress')
    return f


def _choose(f,prereqs,blocked,mode,rng=None):
    validate_frame(f)
    if not f['available_actions']:raise ValueError('finished')
    options=f['available_actions']
    if mode=='random':return rng.choice(options)
    if mode=='goal_first':
        if f['goal'] in options and f['goal'] not in blocked:
            return f['goal']
        available=[a for a in options if a not in blocked]
        return rng.choice(available if available else options)
    if mode=='role_order':
        order=('gather_a','gather_b','inspect','pack','assemble','deliver','verify')
        return min(options,key=lambda a:order.index(f['roles'][a]))
    if mode!='learned':raise ValueError('invalid control mode')
    completed={f['roles'][a] for a in f['completed']}
    goal_role=f['roles'][f['goal']]
    # Candidate roles inferred from accepted workshop interventions. A goal's
    # entire *ancestor* set may be overestimated; nothing is passed by simulator.
    needed=set(prereqs.get(goal_role,[]))|{goal_role}
    for _ in range(7):
        needed.update(*[prereqs.get(r,set()) for r in tuple(needed)])
    candidates=[]
    for a in options:
        role=f['roles'][a]
        guessed=prereqs.get(role,set())
        ready=guessed.issubset(completed)
        penalty=1 if a in blocked else 0
        candidates.append((penalty,not ready, role not in needed,
                           len(guessed-completed), role not in ('gather_a','gather_b'), a))
    return min(candidates)[-1]


class PreconditionSkill:
    """Deterministically explores workshop outcomes; keeps accepted-set evidence.

    A prerequisite is inferred only when present before EVERY accepted attempt
    at a particular role. This observational intersection can include spurious
    prerequisites; transfer to a new task is not guaranteed.
    """
    def __init__(self,seed):
        if type(seed) is not int:raise ValueError('invalid seed')
        self.seed=seed;self.traces=[];self.observed={r:[] for r in ROLES}

    def prerequisites(self):
        return {r:set.intersection(*[set(x) for x in vals]) if vals else set()
                for r,vals in self.observed.items()}

    def train(self,episodes):
        if type(episodes) is not int or episodes<1 or len(self.traces)+episodes>TRAIN_EPISODES:
            raise ValueError('invalid training episode budget')
        for _ in range(episodes):
            index=len(self.traces)
            world=HiddenProcedure(self.seed,'workshop','train',index)
            rng=_rng(self.seed,'workshop','train',index,'intervention')
            events=[]
            while not world.done:
                f=world.frame();name=rng.choice(f['available_actions'])
                role=f['roles'][name];before=sorted(f['roles'][a] for a in f['completed'])
                outcome=world.step(name,expected_tick=f['tick'])
                if outcome['accepted']:self.observed[role].append(before)
                events.append([name,outcome['event']])
            self.traces.append(events)
        return self

    def choose(self,f,blocked=()):
        if not self.traces:raise ValueError('untrained skill')
        if type(blocked) not in (set,tuple,list) or any(type(x) is not str for x in blocked):
            raise ValueError('bad local blocked action set')
        return _choose(f,self.prerequisites(),set(blocked),'learned')

    def record(self):
        if not self.traces:raise ValueError('no training evidence')
        s={'schema':MODEL_SCHEMA,'seed':self.seed,'traces':self.traces,
           'observed':{r:self.observed[r] for r in ROLES}}
        return {'state':json.loads(canonical(s)),'sha256':digest(s)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={'state','sha256'} or
                type(record['state']) is not dict or digest(record['state'])!=record['sha256']):
            raise ValueError('invalid skill record')
        s=record['state']
        if (set(s)!={'schema','seed','traces','observed'} or s['schema']!=MODEL_SCHEMA or
                type(s['traces']) is not list or not 1<=len(s['traces'])<=TRAIN_EPISODES):
            raise ValueError('unknown skill schema')
        other=cls(s['seed']).train(len(s['traces']))
        if other.record()!=record:raise ValueError('checkpoint replay differs')
        return other


def run(seed,family,index,mode,skill=None):
    world=HiddenProcedure(seed,family,'test',index)
    rng=_rng(seed,family,'test',index,'random-eval')
    blocked=set();attempts=0
    while not world.done:
        f=world.frame()
        if mode=='oracle':
            role=world.goal_role
            def resolve(r):
                for p in world._requirements[r]:
                    if world.role_to_name[p] not in world.completed:return resolve(p)
                return world.role_to_name[r]
            name=resolve(role)
        elif mode=='learned':name=skill.choose(f,blocked)
        else:name=_choose(f,{},blocked,mode,rng)
        outcome=world.step(name,expected_tick=f['tick']);attempts+=1
        if outcome['accepted']:blocked.clear()
        else:blocked.add(name)
    return {'success':world.role_to_name[world.goal_role] in world.completed,
            'attempts':attempts,'blocked':attempts-len(world.completed)}
