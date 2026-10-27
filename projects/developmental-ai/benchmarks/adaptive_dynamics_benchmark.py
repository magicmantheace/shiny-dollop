"""Inspected development results; independent test indices but NOT blind seeds."""
from __future__ import annotations
import argparse
import json
import tempfile
from pathlib import Path
from developmental_ai.adaptive_dynamics import CalibrationBrain, KnownPhysicsOracle, SCHEMA


def measure(seeds=(17,23,41), calibration_samples=1800, test_episodes=300):
    result={"schema":SCHEMA,"kind":"inspected-development-not-blind",
            "calibration_samples_per_phase":calibration_samples,"test_episodes":test_episodes,
            "seeds":list(seeds),"rows":[]}
    with tempfile.TemporaryDirectory(prefix="devai-dynamics-") as tmp:
        for seed in seeds:
            with CalibrationBrain(Path(tmp)/f"{seed}.db",seed) as brain:
                row={"seed":seed,"uninformed":brain.evaluate(test_episodes,"high","shifted"),
                     "privileged_oracle":brain._evaluate_model(KnownPhysicsOracle("high","shifted"),test_episodes,"high","shifted")}
                brain.train(calibration_samples,"standard","fixed")
                brain.snapshot("original")
                row["standard_frozen_on_shift"]=brain.evaluate(test_episodes,"high","shifted")
                row["standard_in_distribution"]=brain.evaluate(test_episodes,"standard","fixed")
                brain.train(calibration_samples,"high","shifted")
                brain.snapshot("adapted")
                row["retained_original_model"] = brain.evaluate_snapshot("original",test_episodes,"standard","fixed")
                row["adapted_on_shift"]=brain.evaluate(test_episodes,"high","shifted")
                row["adapted_on_old"]=brain.evaluate(test_episodes,"standard","fixed")
                result["rows"].append(row)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds",nargs="+",type=int,default=[17,23,41])
    p.add_argument("--calibration-samples",type=int,default=1800)
    p.add_argument("--test-episodes",type=int,default=300)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    if a.calibration_samples<1 or a.test_episodes<1 or len(set(a.seeds))!=len(a.seeds):
        p.error("positive samples and unique seeds required")
    result=measure(a.seeds,a.calibration_samples,a.test_episodes)
    serialized=json.dumps(result,sort_keys=True,indent=2)+"\n"
    if a.out: a.out.write_text(serialized,encoding="utf-8")
    print(serialized,end="")

if __name__ == "__main__":
    main()
