"""Precommitted transfer test: navigation-trained temporal alignment -> delayed choice.

A generator uses the delayed task's PUBLIC first cue only to synthesize a noisy
symbolic side channel. The evaluated aligner gets this side channel and labeled
candidate templates, never the first cue or hidden correct response. A separate
train-only cue-to-action policy is shared by all methods and never updated here.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import random
from developmental_ai.environment_api import EnvironmentSession,digest
from developmental_ai.raw_token_transfer import OBS,FORECAST,SOURCES
from developmental_ai.unaligned_stream import near_pairs,alignment_score
from developmental_ai.probabilistic_alignment import marginal_score,TemporalCorrespondence
from developmental_ai.variable_correspondence import VariableCorrespondence
from developmental_ai.cross_family_temporal import CrossFamilyTemporal
from developmental_ai.cross_task_retention import fit_gate
from benchmarks.unaligned_stream_benchmark import stream as nav_stream,DEV,ADDITIONAL
from benchmarks.variable_correspondence_benchmark import stream as variable_stream

SCHEMA="developmental-ai.cross-family-temporal-benchmark/v1"
TRAIN_MAPPING_START,TRAIN_MAPPING_EPISODES=89400,240
TRAIN_PARAM_START,TRAIN_PARAM_EPISODES=90500,30
TEST_START,TEST_EPISODES=99900,40
TEMPLATES=("01230123","12301230","23012301","30123012")


def _rng(seed,split,index,label):
    raw=f"{SCHEMA}/{seed}/{split}/{index}/{label}".encode()
    return random.Random(int.from_bytes(hashlib.sha256(raw).digest()[:8],"big"))


def _noise(tokens,rng,alphabet,*,max_drop):
    if len(tokens)!=8:raise ValueError("expected eight encoded base observations")
    drop=set(rng.sample(range(8),rng.randint(0,max_drop)))
    seq=[(t,i) for i,t in enumerate(tokens) if i not in drop]
    for _ in range(rng.randint(2 if max_drop<3 else 3,4)):
        seq.insert(rng.randrange(len(seq)+1),(rng.choice(alphabet),None))
    return [x for x,_ in seq],{i for _,i in seq if i is not None}


def delayed_stream(seed,split,index,initial_cue):
    """Benchmark-only generator; caller MUST withhold initial_cue from selector."""
    if (type(seed) is not int or split not in ("train","test") or
            type(index) is not int or not 0<=index<1000000 or
            type(initial_cue) is not int or initial_cue not in range(4)):
        raise ValueError("invalid synthetic source identity")
    # Navigation-learned mapping can be independently checked using cipher(seed)
    # by benchmark scoring ONLY, never by this source generator's learners.
    from benchmarks.raw_token_transfer_benchmark import cipher
    permutation=cipher(seed)
    true_core=[OBS[int(x)] for x in TEMPLATES[initial_cue]]
    observed,ids=_noise(true_core,_rng(seed,split,index,"sensor"),OBS,max_drop=3)
    guessed=[0,1,2,3,_rng(seed,split,index,"extra-class").choice([x for x in range(4) if x!=initial_cue])]
    _rng(seed,split,index,"candidate-order").shuffle(guessed)
    candidates=[];real=None;true_common=None
    for name,cue in zip(SOURCES,guessed):
        f=[FORECAST[permutation[int(x)]] for x in TEMPLATES[cue]]
        seq,other_ids=_noise(f,_rng(seed,split,index,name),FORECAST,max_drop=2)
        candidates.append([name,[cue,0],seq])
        if cue==initial_cue:real=name;true_common=len(ids&other_ids)
    return observed,candidates,real,true_common


def _nav_mapping(seed):
    # Fitted without navigation rewards, source truth, hidden cipher or test data.
    counts=[[0.]*4 for _ in range(4)]
    for i in range(TRAIN_MAPPING_EPISODES):
        idx=TRAIN_MAPPING_START+i
        ref=list(EnvironmentSession("occluded",seed,"train",idx).frame()["observation"]["beacon"])
        observed,candidates,_=nav_stream(seed,"train",idx,ref)
        for _,_,forecast in candidates:
            for key,weight in near_pairs(observed,forecast):
                counts[key//4][key%4]+=weight
    mapping=max(itertools.permutations(range(4)),key=lambda p:sum(counts[k][p[k]] for k in range(4)))
    return mapping,digest({"seed":seed,"cooccurrence":counts,"examples":TRAIN_MAPPING_EPISODES})


def train_nav_model(seed):
    mapping,fit_digest=_nav_mapping(seed)
    fixed=TemporalCorrespondence(mapping,evidence_digest=fit_digest,episodes=240)
    pairs=[]
    for i in range(TRAIN_PARAM_EPISODES):
        idx=TRAIN_PARAM_START+i
        ref=list(EnvironmentSession("occluded",seed,"train",idx).frame()["observation"]["beacon"])
        observed,candidates,_,_=variable_stream(seed,"train",idx,ref)
        chosen=_choose({name:marginal_score(observed,forecast,mapping) for name,_,forecast in candidates})
        pairs.append([observed,next(c[2] for c in candidates if c[0]==chosen)])
    fitted=VariableCorrespondence(mapping,pairs,training_digest=fit_digest)
    return CrossFamilyTemporal.restore(CrossFamilyTemporal(fitted).record()),mapping


def _choose(scores):
    return min(k for k in scores if scores[k]==max(scores.values()))


def _response(seed,index,variant,guessed_cue,q):
    # Run the real D2 delayed-choice environment; first cue is deliberately not
    # inspected by the response policy or alignment model, only by generator.
    sess=EnvironmentSession("delayed",seed,"test",index,variant=variant)
    table=q[str(guessed_cue)]
    action=min(a for a in range(4) if table[a]==max(table))
    terminal=None
    while not sess.done:
        frame=sess.frame()
        act=action if frame["observation"]["phase"]=="decision" else 4
        terminal=sess.step(act,expected_tick=frame["tick"])["event"]
    return terminal=="correct"


def measure(seeds=DEV):
    if type(seeds) not in (list,tuple) or tuple(seeds) not in (DEV,ADDITIONAL):
        raise ValueError("cohort not in frozen manifest")
    out={"schema":SCHEMA,"protocol":"benchmarks/cross_family_temporal_protocol.json",
         "blind":False,"source_fit":"navigation train/89400..89639 and train/90500..90529",
         "response_fit":"delayed train/0..299,validation train/5000..5059",
         "evaluation":"delayed test/99900..99939","rows":[]}
    for seed in seeds:
        adapter,mapping=train_nav_model(seed)
        response=fit_gate(seed,episodes=300,validation=60)
        q=response.q["initial"]
        old_weights=[1. if mapping[a]==b else -1. for a in range(4) for b in range(4)]
        methods=("variable_transfer","fixed_eight","max_path","bag","last_token","oracle_cipher_variable","correct_cue")
        successes={x:0 for x in methods};hits={x:0 for x in methods}
        errors={x:[] for x in ("estimated_common","always_six","length_minus_four")}
        for j in range(TEST_EPISODES):
            idx=TEST_START+j
            # First cue read by benchmark synthetic data generator ONLY.
            cue=EnvironmentSession("delayed",seed,"test",idx,variant="long").frame()["observation"]["token"]
            observed,candidates,correct,common=delayed_stream(seed,"test",idx,cue)
            val=adapter.evaluate(observed,candidates)
            forecasts={name:seq for name,_,seq in candidates}
            bag={name:sum(old_weights[OBS.index(a)*4+FORECAST.index(b)] for a in observed for b in seq)/(len(observed)*len(seq)) for name,seq in forecasts.items()}
            last_guess=(OBS.index(observed[-1])+1)%4
            last_name=next((name for name,offset,_ in candidates if offset[0]==last_guess),candidates[0][0])
            selection={"variable_transfer":val["source"],
                       "fixed_eight":_choose({name:marginal_score(observed,seq,mapping) for name,seq in forecasts.items()}),
                       "max_path":_choose({name:alignment_score(observed,seq,old_weights) for name,seq in forecasts.items()}),
                       "bag":_choose(bag),"last_token":last_name,
                       "oracle_cipher_variable":val["source"],  # mapping checked by scoring only below
                       "correct_cue":correct}
            # Evaluation-only oracle re-fits the model with the hidden cipher.
            from benchmarks.raw_token_transfer_benchmark import cipher
            if tuple(mapping)!=cipher(seed):
                privileged=VariableCorrespondence(cipher(seed),adapter.model.pairs,training_digest=adapter.model.training_digest)
                selection["oracle_cipher_variable"]=privileged.select(observed,candidates)
            true_forecast=forecasts[correct]
            from developmental_ai.variable_correspondence import statistics
            k=statistics(observed,true_forecast,mapping,adapter.model.match_probability,adapter.model.survival)["expected_matches"]
            errors["estimated_common"].append(abs(k-common));errors["always_six"].append(abs(6-common))
            errors["length_minus_four"].append(abs((len(observed)+len(true_forecast))/2-4-common))
            cache={}
            for method,source in selection.items():
                proposal=next(c[1][0] for c in candidates if c[0]==source)
                hits[method]+=int(proposal==cue)
                if proposal not in cache:cache[proposal]=_response(seed,idx,"long",proposal,q)
                successes[method]+=cache[proposal]
        out["rows"].append({"seed":seed,"cue_hits":hits,"delayed_task_successes":successes,
                            "fit_mapping_exact_scoring_only":list(mapping)==list(__import__('benchmarks.raw_token_transfer_benchmark',fromlist=['cipher']).cipher(seed)),
                            "emission_p":round(adapter.model.match_probability,6),"survival_p":round(adapter.model.survival,6),
                            "event_count_mae_diagnostic":{k:round(sum(v)/len(v),5) for k,v in errors.items()},
                            "model_sha256":adapter.record()["sha256"]})
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cohort",choices=("development","additional"),default="development")
    p.add_argument("--out")
    args=p.parse_args()
    output=json.dumps(measure(DEV if args.cohort=="development" else ADDITIONAL),indent=2,sort_keys=True)+"\n"
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(output)
    print(output,end="")

if __name__=="__main__":main()
