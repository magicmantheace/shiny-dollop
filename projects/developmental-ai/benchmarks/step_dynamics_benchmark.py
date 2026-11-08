"""Development benchmark: causal per-step switching and quarantined novel physics.

All regime names and labels stay in this scorer, never passed to the detector.
The candidate is fitted to ordinary training histories, NOT auto-promoted.
"""
from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path

from developmental_ai.online_dynamics import ModelBank, fit, trajectory, score
from developmental_ai.step_dynamics import StepDetector, CandidateStore, catalogue, SCHEMA

KNOWN = {"original": ("standard", "fixed"), "changed": ("high", "shifted")}
NOVEL = ("high", "fixed")


def measure(seeds=(17,23,41), train_episodes=130, iterations=6, phase_episodes=12,
            candidate_episodes=80, test_episodes=80, floor=-3.3):
    if (not seeds or len(seeds)!=len(set(seeds)) or any(type(s) is not int for s in seeds)
        or min(train_episodes,iterations,phase_episodes,candidate_episodes,test_episodes)<=0
        or phase_episodes*3*14>4000):
        raise ValueError("invalid benchmark parameters")
    report = {"schema":SCHEMA,"kind":"inspected-development-not-blind",
              "seeds":list(seeds),"known_train_episodes":train_episodes,
              "candidate_training_episodes":candidate_episodes, "test_episodes":test_episodes,
              "fit_iterations":iterations,"phase_episodes":phase_episodes,"floor":floor,
              "notes":"Ring topology and reset beacon known; labels used for measurement only. Candidate fitted from ordinary sequences then quarantined. Novelty floor uncalibrated.",
              "rows":[]}
    with tempfile.TemporaryDirectory(prefix="devai-step-") as d:
        root=Path(d)
        for seed in seeds:
            with ModelBank(root/f"models_{seed}.db",seed) as bank:
                for name,(noise,layout) in KNOWN.items():
                    prior=[trajectory(seed,"train",i,noise,layout) for i in range(train_episodes)]
                    model,_=fit(prior,iterations=iterations)
                    bank.save(name,model,len(prior))
                models, fingerprint=catalogue(bank)
                phases=[]
                with StepDetector(root/f"steps_{seed}.db",bank,floor=floor) as detector:
                    phase_order=("original","changed","original")
                    for stage, name in enumerate(phase_order):
                        noise,layout=KNOWN[name]
                        events=[]
                        for i in range(phase_episodes):
                            # Test-only independent of train and candidate experience.
                            h=trajectory(seed,"test",6000+stage*phase_episodes+i,noise,layout)
                            detector.begin(h["n"],h["initial"])
                            events.extend(detector.step(*obs) for obs in h["observations"])
                            detector.finish()
                        first=next((i+1 for i,e in enumerate(events) if e["active"]==name),None)
                        phases.append({"regime_for_scoring_only":name,
                                       "correct_step_fraction":round(sum(e['active']==name for e in events)/len(events),4),
                                       "first_correct_observation":first,
                                       "switches":sum(e['status']=='switch' for e in events),
                                       "unknown_observations":sum(e['status']=='unknown' for e in events),
                                       "final_selected":detector.state['active']})
                    detector.events()
                # Candidate fit uses only train sequences; these data are not simulator truth labels.
                with CandidateStore(root/f"candidate_{seed}.db",seed,fingerprint) as staged:
                    for i in range(candidate_episodes):
                        staged.add(trajectory(seed,"train",2000+i,*NOVEL),catalogue=fingerprint)
                    ticket=staged.propose(min_histories=12,iterations=iterations)
                    candidate,_=staged.get_candidate()
                    bank_size=bank.conn.execute("SELECT COUNT(*) FROM online_models").fetchone()[0]
                    target=[trajectory(seed,"test",12000+i,*NOVEL) for i in range(test_episodes)]
                    losses={n:round(-score(m,target),4) for n,m in models.items()}
                    losses['quarantined_candidate']=round(-score(candidate,target),4)
                    best=min(losses[name] for name in KNOWN)
                    assert bank_size==2, 'benchmark must never promote without explicit approval'
                    report['rows'].append({"seed":seed,"phases":phases,
                                           "novel_candidate":{"status":ticket['status'],
                                            "training_histories":candidate_episodes,
                                            "held_out_negative_log_likelihoods":losses,
                                            "candidate_improvement_over_best_known":round(best-losses['quarantined_candidate'],4),
                                            "automatic_promotions":bank_size-2}})
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--seeds',nargs='+',type=int,default=[17,23,41])
    p.add_argument('--train-episodes',type=int,default=130)
    p.add_argument('--iterations',type=int,default=6)
    p.add_argument('--phase-episodes',type=int,default=12)
    p.add_argument('--candidate-episodes',type=int,default=80)
    p.add_argument('--test-episodes',type=int,default=80)
    p.add_argument('--floor',type=float,default=-3.3)
    p.add_argument('--out',type=Path)
    a=p.parse_args()
    result=measure(a.seeds,a.train_episodes,a.iterations,a.phase_episodes,a.candidate_episodes,a.test_episodes,a.floor)
    output=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if a.out:a.out.write_text(output,encoding='utf-8')
    print(output,end='')

if __name__=='__main__':main()
