"""Optional sequential sensor-channel fault diagnostics, simulation only.

Learns run-length reference cutoffs without sensor truth or environment labels;
keeps the original model-surprise guard unchanged. Repeated zero odometry and
repeated non-null landmark readings are *fault signatures*, NOT generic novelty.
No physical actuation, model promotion, or permission changes.
"""
from __future__ import annotations

import copy
import math
from developmental_ai.adaptive_dynamics import canonical, index_of, reading_index
from developmental_ai.novelty_guard import NoveltyGuard, _bounded_stream, verify_guard
from developmental_ai.switching_belief import _bank, _digest

SCHEMA = 'channel-novelty/v1'
CHANNELS = ('zero_odometry', 'constant_landmark')
FLOORS = {'zero_odometry': 5, 'constant_landmark': 4}
MAX_EVENTS = 55


def _advance_stats(state, action, observation):
    if (type(action) is not int or action not in (0, 1, 2) or
            type(observation) is not dict or set(observation) != {'beacon', 'odometry', 'landmark'} or
            observation['beacon'] is not None):
        raise ValueError('invalid ordinary sensor event')
    index_of(observation['odometry'])
    reading_index(observation['landmark'])
    # Collect has no commanded displacement: a zero odometry is expected.
    zero = state['zero_count'] + 1 if action in (0, 1) and observation['odometry'] == 0 else 0
    mark = observation['landmark'] if action in (0, 1) else None
    constant = state['mark_count'] + 1 if mark is not None and mark == state['prev_mark'] else (1 if mark is not None else 0)
    state['zero_count'],state['prev_mark'],state['mark_count'] = zero,mark,constant
    state['max_zero'] = max(zero, state['max_zero'])
    state['max_mark'] = max(constant, state['max_mark'])


def _new_stats():
    return {'zero_count':0, 'prev_mark':None, 'mark_count':0, 'max_zero':0, 'max_mark':0}


def _profile(record):
    _bounded_stream(record)
    state = _new_stats()
    for act, ob in record['observations']:
        _advance_stats(state, act, ob)
    return {'zero_odometry':state['max_zero'], 'constant_landmark':state['max_mark']}


def calibrate_channels(models, streams, *, alpha=.10):
    """Bonferroni-corrected upper-tail run thresholds from train-only streams.

    Per-channel quantiles use ceil((n+1)*(1-alpha/2)). Fixed lower floors
    avoid reacting to short innocuous runs. The rank has conditional coverage
    only for exchangeable sensor streams matching the reference protocol.
    """
    bank = _bank(models)
    if (type(streams) not in (list,tuple) or not 40 <= len(streams) <= 300 or
            type(alpha) not in (int,float) or not math.isfinite(alpha) or not .04 <= alpha <= .20):
        raise ValueError('invalid channel calibration configuration')
    hashes=[_digest(s) for s in streams]
    if len(set(hashes)) != len(hashes):
        raise ValueError('duplicate calibration streams')
    scores=[_profile(s) for s in streams]
    rank=math.ceil((len(streams)+1)*(1-alpha/len(CHANNELS)))
    if rank>len(streams):
        raise ValueError('insufficient reference streams for joint cutoff')
    cutoffs={c:max(FLOORS[c],sorted(s[c] for s in scores)[rank-1]) for c in CHANNELS}
    state={'schema':SCHEMA,'bank':bank,'alpha':float(alpha),'reference_size':len(streams),
           'cutoffs':cutoffs,'reference_digest':_digest(sorted(hashes))}
    return {'state':state,'sha256':_digest(state)}


def verify_channels(receipt,models):
    if (type(receipt) is not dict or set(receipt)!= {'state','sha256'} or
            type(receipt.get('state')) is not dict or type(receipt.get('sha256')) is not str or
            _digest(receipt['state']) != receipt['sha256']):
        raise ValueError('invalid channel receipt')
    s=receipt['state']
    if (set(s)!= {'schema','bank','alpha','reference_size','cutoffs','reference_digest'} or
            s['schema']!=SCHEMA or s['bank']!=_bank(models) or
            type(s['alpha']) not in (int,float) or not math.isfinite(s['alpha']) or not .04<=s['alpha']<=.20 or
            type(s['reference_size']) is not int or not 40<=s['reference_size']<=300 or
            math.ceil((s['reference_size']+1)*(1-s['alpha']/len(CHANNELS)))>s['reference_size'] or
            type(s['cutoffs']) is not dict or set(s['cutoffs'])!=set(CHANNELS) or
            any(type(v) is not int or not FLOORS[k]<=v<=MAX_EVENTS for k,v in s['cutoffs'].items()) or
            type(s['reference_digest']) is not str or len(s['reference_digest'])!=64 or
            any(c not in '0123456789abcdef' for c in s['reference_digest'])):
        raise ValueError('incompatible channel receipt')
    return s


class ChannelGuard:
    def __init__(self,models,receipt):
        s=verify_channels(receipt,models)
        self.bank = _bank(models)
        self.receipt = copy.deepcopy(receipt)
        self.stats = _new_stats()
        self.alarms=[]
        self.log=[]

    @property
    def alarm(self):
        return bool(self.alarms)

    def advance(self,action,observation):
        if len(self.log)>=MAX_EVENTS:
            raise ValueError('exhausted channel monitor')
        updated=copy.deepcopy(self.stats)
        _advance_stats(updated,action,observation)
        self.stats=updated
        self.log.append([action,dict(observation)])
        cut=self.receipt['state']['cutoffs']
        if self.stats['max_zero']>cut['zero_odometry'] and 'zero_odometry' not in self.alarms:
            self.alarms.append('zero_odometry')
        if self.stats['max_mark']>cut['constant_landmark'] and 'constant_landmark' not in self.alarms:
            self.alarms.append('constant_landmark')
        return {'alarm':self.alarm,'channels':list(self.alarms),'steps':len(self.log)}

    def snapshot(self):
        s={'schema':SCHEMA,'bank':self.bank,'receipt_digest':_digest(self.receipt),
           'stats':self.stats,'alarms':self.alarms,'log':self.log}
        return {'state':s,'sha256':_digest(s)}

    @classmethod
    def restore(cls,record,models,receipt):
        if (type(record) is not dict or set(record)!={'state','sha256'} or
                type(record['state']) is not dict or _digest(record['state'])!=record['sha256']):
            raise ValueError('invalid channel checkpoint')
        s=record['state']
        obj=cls(models,receipt)
        if (set(s)!={'schema','bank','receipt_digest','stats','alarms','log'} or
                s['schema']!=SCHEMA or s['bank']!=obj.bank or s['receipt_digest']!=_digest(receipt) or
                type(s['log']) is not list or len(s['log'])>MAX_EVENTS):
            raise ValueError('incompatible channel checkpoint')
        for event in s['log']:
            if type(event) is not list or len(event)!=2:
                raise ValueError('invalid channel replay event')
            obj.advance(*event)
        if obj.stats!=s['stats'] or obj.alarms!=s['alarms']:
            raise ValueError('channel replay mismatch')
        return obj


class LayeredGuard:
    """Read-only diagnostic union; does not alter or wrap the action policy."""
    def __init__(self,initial,goal,n,models,surprise_receipt,channel_receipt):
        self.surprise=NoveltyGuard(initial,goal,n,models,surprise_receipt)
        self.channels=ChannelGuard(models,channel_receipt)

    @property
    def alarm(self):
        return self.surprise.alarm or self.channels.alarm

    def advance(self,action,observation):
        # Validate before mutating either component. Both use identical vocabularies.
        _advance_stats(_new_stats(),action,observation)
        if (len(self.channels.log)>=MAX_EVENTS or len(self.surprise.log)>=MAX_EVENTS or
                _bank(self.surprise.models)!=self.surprise.nav.fingerprints):
            raise ValueError("exhausted or altered layered guard")
        channel = self.channels.advance(action,observation)
        surprise = self.surprise.advance(action,observation)
        return {'alarm':self.alarm,'model_surprise':surprise['alarm'],'channel_alarm':channel['alarm'],
                'channels':channel['channels'],'steps':surprise['steps']}

    def snapshot(self):
        state={'schema':'layered-guard/v1','surprise':self.surprise.snapshot(),'channels':self.channels.snapshot()}
        return {'state':state,'sha256':_digest(state)}

    @classmethod
    def restore(cls,record,models,surprise_receipt,channel_receipt):
        if (type(record) is not dict or set(record)!={'state','sha256'} or
                type(record['state']) is not dict or _digest(record['state'])!=record['sha256']):
            raise ValueError('invalid layered checkpoint')
        s=record['state']
        if set(s)!={'schema','surprise','channels'} or s['schema']!='layered-guard/v1':
            raise ValueError('invalid layered schema')
        a=NoveltyGuard.restore(s['surprise'],models,surprise_receipt)
        b=ChannelGuard.restore(s['channels'],models,channel_receipt)
        if a.log!=b.log:
            raise ValueError('layered evidence mismatch')
        obj=cls(a.nav.initial,a.nav.goal,a.nav.n,models,surprise_receipt,channel_receipt)
        obj.surprise,obj.channels=a,b
        return obj


class LayeredNavigation:
    """Optional pause adapter: inherits no external action capability."""

    def __init__(self,proposal,hazard_receipt,surprise_receipt,channel_receipt,initial,goal,n):
        from developmental_ai.closed_loop_adaptation import models_from_proposal
        from developmental_ai.novelty_guard import GuardedNavigation
        self.session=GuardedNavigation(proposal,hazard_receipt,surprise_receipt,initial,goal,n)
        self.channels=ChannelGuard(models_from_proposal(proposal),channel_receipt)
        if self.channels.bank!=self.session.guard.nav.fingerprints:
            raise ValueError('incompatible navigation model bank')

    @property
    def alarm(self):
        return self.session.guard.alarm or self.channels.alarm

    def select_action(self):
        return None if self.alarm else self.session.select_action()

    def advance(self,action,observation,*,done=False):
        if self.alarm:
            raise ValueError('paused due to anomalous sensor evidence')
        _advance_stats(_new_stats(),action,observation)
        outcome=self.session.advance(action,observation,done=done)
        diagnostic=self.channels.advance(action,observation)
        return {**outcome,'channel_trust':diagnostic,'paused':self.alarm}

    def snapshot(self):
        state={'schema':'layered-navigation/v1','session':self.session.snapshot(),
               'channels':self.channels.snapshot()}
        return {'state':state,'sha256':_digest(state)}

    @classmethod
    def restore(cls,record,proposal,hazard_receipt,surprise_receipt,channel_receipt):
        from developmental_ai.novelty_guard import GuardedNavigation
        from developmental_ai.closed_loop_adaptation import models_from_proposal
        if (type(record) is not dict or set(record)!={'state','sha256'} or
                type(record['state']) is not dict or _digest(record['state'])!=record['sha256']):
            raise ValueError('invalid layered-navigation checkpoint')
        s=record['state']
        if set(s)!={'schema','session','channels'} or s['schema']!='layered-navigation/v1':
            raise ValueError('incompatible navigation checkpoint')
        old=GuardedNavigation.restore(s['session'],proposal,hazard_receipt,surprise_receipt)
        channels=ChannelGuard.restore(s['channels'],models_from_proposal(proposal),channel_receipt)
        if (len(old.session.log)!=len(channels.log) or
                any(a!=event['action'] or observation!=event['observation']
                    for (a,observation),event in zip(channels.log,old.session.log))):
            raise ValueError('divergent sensor evidence on restore')
        obj=cls(proposal,hazard_receipt,surprise_receipt,channel_receipt,
                old.session.nav.initial,old.session.nav.goal,old.session.nav.n)
        obj.session,obj.channels=old,channels
        return obj
