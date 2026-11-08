# D3/D4 experimental procedural skill transfer: workshop to repair

**Status: optional research-only implementation, not completed D3 or D4.** The evaluation manifest `benchmarks/procedural_skill_protocol.json` was committed to private GitHub `main` as `c0a410cdc10ef91d21693d49ba4491d04688ab93` before the learner was implemented or tested. The six seeds have been examined in earlier projects, and are **not independent blind holdouts**.

## What is actually learned

`developmental_ai.procedural_skill.ProceduralSkill` learns a tabular preference for a small set of **engineered** public dependency-graph action features using observed workshop actions and scalar rewards. A workshop episode has two independent material preparations, a join, and a delivery plus distractors. A *separately generated* repair episode has inspection, two repairs, certification, and restoration plus distractors. Every episode shuffles its own opaque action names and dependency graph. The policy never trains on repair actions or rewards and does not use workshop action identities at evaluation.

**Crucial limitation:** Each environment provides its complete prerequisite DAG and a goal. The code explicitly computes transitive prerequisite closure as a feature for every candidate action. It is not learning prerequisites, causal structure, task decomposition, general world semantics, or planning independently. The workshop and repair tasks share that public DAG abstraction. The reward function directly reinforces goal-ancestor actions and penalizes distractors; it is shaped training feedback, not just terminal success. The engineered DAG-greedy baseline uses precisely the same public information and reaches the same score. The public graph is the key shortcut, not an incidental implementation detail.

## Frozen matched protocol and baselines

- Training: workshop `train/0..599`, 600 episodes per seed, deterministic 30% exploration on each decision, no target-family feedback. Policy values are accumulated from its own observed scalar reward.
- Evaluation: workshop and repair `test/70000..70099`, 100 episodes per family and seed. Development 14003/14009/14033; additional previously inspected 27007/27011/27017.
- Policies: trained feature-aware policy, trained feature-ablated policy that cannot use prerequisite closure, random available-action selection, an engineered public-graph greedy baseline, and a public-graph ideal-plan oracle. The latter two are functionally identical here; this is not an independent upper-bound solver.
- The initial graph's required actions are never passed as a privileged list. They are logically derivable from the visible goal and prerequisite graph. The evaluator reads the public graph and goal. All evaluation calls are read-only; no Q updates occur after workshop training.
- Checkpoints contain deterministic workshop training action traces and feature values. Restore replays **the complete training environment** and refuses mismatched action choices, values, or metadata, even if a checksum is recomputed. It does **not** authenticate the author or provide permission for any external action.

## Results

Each cohort contains 300 evaluation episodes per family; six-seed combined total is 600 per family.

| Mode | Workshop development | Workshop additional | Repair development | Repair additional |
| --- | ---: | ---: | ---: | ---: |
| Random legal action | 62/300 | 59/300 | 15/300 | 27/300 |
| Trained, no ancestor feature | 167/300 | 139/300 | 87/300 | 93/300 |
| **Workshop-trained policy reused zero-shot** | **300/300** | **300/300** | **300/300** | **300/300** |
| Public-DAG greedy | 300/300 | 300/300 | 300/300 | 300/300 |
| Public shortest-plan reference | 300/300 | 300/300 | 300/300 | 300/300 |

The transfer is deterministic and succeeds at the **engineered relational feature level**. It does **not outperform the simple graph planner** and does not demonstrate original skill discovery. There is zero evidence of learned semantics from raw workshop or maintenance observations; both simulations expose the same symbolic graph grammar.

## Reproduction and limits

```sh
python -m unittest tests.test_procedural_skill tests.test_transfer -q
python -m benchmarks.procedural_skill_benchmark --cohort development --out benchmarks/procedural_skill_results.json
python -m benchmarks.procedural_skill_benchmark --cohort additional --out benchmarks/procedural_skill_additional_results.json
python -m benchmarks.transfer_benchmark
```

The new procedural skill tests plus older transfer tests passed **14/14** locally. This local workspace contains only the tested modules and the original transfer benchmark, not a complete fresh repository checkout; **no full-suite green, GitHub Actions, or hardware test is claimed**. The transfer-v1 baseline remains 76.0%, 69.0%, 66.67% on seeds 17/23/41.

The next meaningful test should remove the explicit goal-ancestry feature and eventually the public graph itself, require learning prerequisites from action failures and delayed rewards, and test **independently authored task families** with different interfaces. Keep D1, D3, D4 open. AthenZ identity and Synveil system authority remain external and permissioned. Post-core V2A emotional development precedes and overlaps V2B virtual home.
