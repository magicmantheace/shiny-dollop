"""Per-observation one-slot WRITE/KEEP learner with outcome-based source utility.

Source/context labels and one-slot capacity are engineered. Only decisions and
response values are learned from simulated terminal rewards; no privileged
correct-source, hidden response, true navigation positions or OS actions.
"""
from __future__ import annotations
import hashlib
import json
import math
import random
from developmental_ai.selective_memory import SignalTrial, episode_seed
from developmental_ai.environment_api import canonical, digest

SCHEMA='developmental-ai.online-memory-gate/v1'
SOURCES=('A','B','N')


def _outcome_feedback(trial, action):
    """Simulation boundary: only a terminal reward reaches the learner."""
    return 1.0 if action == trial.correct_action else -1.0


def choose(rng,values,epsilon):
    if rng.random()<epsilon:
        return rng.randrange(len(values))
    best=max(values)
    return rng.choice([i for i,v in enumerate(values) if v==best])

class MemoryGate:
    """Train-only source-value and symbol-to-response bandits; per-event control."""
    def __init__(self,seed,*,trained=0,source=None,response=None):
        if type(seed) is not int or type(trained) is not int or not 0<=trained<=10000:
            raise ValueError('invalid model identity')
        if source is None:source={f'{c}:{ch}':[0.0,0.0] for c in (0,1) for ch in SOURCES}
        if response is None:response={str(s):[0.0]*4 for s in range(4)}
        if (type(source) is not dict or set(source)!={f'{c}:{ch}' for c in (0,1) for ch in SOURCES} or
            type(response) is not dict or set(response)!={str(s) for s in range(4)} or
            any(type(v) is not list or len(v)!=2 or (type(v[0]) not in (int,float) or not math.isfinite(v[0]) or not -1<=v[0]<=1 or type(v[1]) not in (int,float) or not math.isfinite(v[1]) or not 0<=v[1]<=10000) for v in source.values()) or
            any(type(v) is not list or len(v)!=4 or any(type(x) not in (int,float) or not math.isfinite(x) or abs(x)>2 for x in v) for v in response.values())):
            raise ValueError('invalid learned tables')
        self.seed,self.trained=seed,trained
        self.source=json.loads(canonical(source));self.response=json.loads(canonical(response))

    def decide(self,context,held,candidate,*,rng=None,epsilon=0.0):
        if (type(context) is not int or context not in (0,1) or
            (held is not None and (type(held) not in (tuple,list) or len(held)!=2 or held[0] not in SOURCES or type(held[1]) is not int or held[1] not in range(4))) or
            type(candidate) not in (tuple,list) or len(candidate)!=2 or candidate[0] not in SOURCES or type(candidate[1]) is not int or candidate[1] not in range(4) or
            type(epsilon) not in (int,float) or not math.isfinite(epsilon) or not 0<=epsilon<=1):
            raise ValueError('invalid or privileged memory input')
        if held is None:return True
        # Binary learned WRITE/KEEP choice at every incoming observation.
        # Learned values estimate terminal reward when this channel was kept.
        keep=self.source[f'{context}:{held[0]}'][0]
        write=self.source[f'{context}:{candidate[0]}'][0]
        if rng is not None and rng.random()<epsilon:return bool(rng.randrange(2))
        return write>keep

    def choose_action(self,held,rng,epsilon=0.0):
        if type(held) not in (tuple,list) or len(held)!=2 or type(held[1]) is not int or held[1] not in range(4):
            raise ValueError('missing retained memory')
        return choose(rng,self.response[str(held[1])],epsilon)

    def trial(self,split,index,*,band='long',learn=False):
        if split not in ('train','test') or band not in ('short','long') or type(index) is not int or index<0 or (learn and (split!='train' or index!=self.trained)):
            raise ValueError('invalid episode or training split')
        trial=SignalTrial(episode_seed(self.seed,split,index,band),band)
        rng=random.Random(int.from_bytes(hashlib.sha256(f'{SCHEMA}/{self.seed}/{split}/{index}'.encode()).digest()[:8],'big'))
        ctx=None;held=None;writes=0;keeps=0
        for obs in trial.observations():
            if obs['kind']=='context':ctx=obs['value']
            elif obs['kind']=='signal':
                can=(obs['channel'],obs['symbol'])
                write=self.decide(ctx,held,can,rng=rng,epsilon=(.22 if learn else 0))
                if write:held=can;writes+=1
                else:keeps+=1
            else:
                action=self.choose_action(held,rng,.32 if learn else 0)
        # Terminal feedback is delivered by the simulator, not by inspecting
        # the hidden answer while choosing a memory operation.
        reward_signal = _outcome_feedback(trial, action)
        correct = reward_signal > 0
        if learn:
            reward=1.0 if correct else 0.0
            key=f'{ctx}:{held[0]}'
            val=self.source[key]
            val[1]+=1
            val[0]+=(reward-val[0])/(val[1]**.65)
            rs=self.response[str(held[1])]
            rs[action]+=.25*(reward-rs[action])
            self.trained+=1
        return {'success':correct,'writes':writes,'keeps':keeps,'held_source':held[0]}

    def train(self,n):
        if type(n) is not int or n<1 or n+self.trained>10000:raise ValueError('invalid train budget')
        for _ in range(n):self.trial('train',self.trained,band='short',learn=True)
        return self

    def record(self):
        data={'schema':SCHEMA,'seed':self.seed,'trained':self.trained,'source':self.source,'response':self.response}
        return {'data':data,'digest':digest(data)}

    @classmethod
    def restore(cls,record):
        if (type(record) is not dict or set(record)!={'data','digest'} or type(record['data']) is not dict or
            record['digest']!=digest(record['data']) or set(record['data'])!={'schema','seed','trained','source','response'} or record['data']['schema']!=SCHEMA):
            raise ValueError('invalid model checkpoint')
        d=record['data']
        return cls(d['seed'],trained=d['trained'],source=d['source'],response=d['response'])


class CueMemory:
    """Bounded read-only memory session; snapshot restored by deterministic replay.

    Candidate payloads are two integer values to keep the research protocol
    inspectable; learned policy sees context/source/token, never payload truth.
    """
    MAX_EVENTS=64
    def __init__(self,gate,context):
        if not isinstance(gate,MemoryGate) or type(context) is not int or context not in (0,1):
            raise ValueError('invalid memory session')
        self.gate=MemoryGate.restore(gate.record())
        self.context=context
        self.events=[]
        self.held=None

    def observe(self,source,token,payload):
        if (type(source) is not str or source not in SOURCES or
            type(token) is not int or token not in range(4) or
            type(payload) not in (list,tuple) or len(payload)!=2 or
            any(type(x) is not int or abs(x)>8 for x in payload) or
            len(self.events)>=self.MAX_EVENTS):
            raise ValueError('invalid or exhausted public cue')
        candidate=(source,token)
        old=(self.held['source'],self.held['token']) if self.held is not None else None
        write=self.gate.decide(self.context,old,candidate)
        event={'source':source,'token':token,'payload':list(payload),'write':write}
        if write:self.held={k:event[k] for k in ('source','token','payload')}
        self.events.append(event)
        return {'operation':'write' if write else 'keep','held':json.loads(canonical(self.held))}

    def snapshot(self):
        state={'schema':'developmental-ai.cue-memory/v1','context':self.context,
               'model_digest':self.gate.record()['digest'],'events':self.events,'held':self.held}
        return {'state':json.loads(canonical(state)),'digest':digest(state)}

    @classmethod
    def restore(cls,record,gate):
        if (type(record) is not dict or set(record)!={'state','digest'} or
            type(record['state']) is not dict or record['digest']!=digest(record['state']) or
            set(record['state'])!={'schema','context','model_digest','events','held'} or
            record['state']['schema']!='developmental-ai.cue-memory/v1' or
            type(record['state']['events']) is not list or len(record['state']['events'])>cls.MAX_EVENTS):
            raise ValueError('invalid cue memory checkpoint')
        s=record['state']
        obj=cls(gate,s['context'])
        if obj.gate.record()['digest']!=s['model_digest']:
            raise ValueError('memory model mismatch')
        for e in s['events']:
            if type(e) is not dict or set(e)!={'source','token','payload','write'} or type(e['write']) is not bool:
                raise ValueError('invalid replay event')
            operation=obj.observe(e['source'],e['token'],e['payload'])
            if (operation['operation']=='write')!=e['write']:
                raise ValueError('inconsistent saved choice')
        if obj.held != s['held']:
            raise ValueError('inconsistent saved memory')
        return obj
