# D3/D4 experiment: Online probing for hidden prerequisites

**Status:** optional simulation-only research; NOT a completed D1, D3, or D4 milestone. The frozen protocol was committed on October 18, 2026 (`benchmarks/online_prerequisite_probing_protocol.json`, commit `3a1a931c0c4a08c136bde9fbb2f4ee1ac31ac718`) before these test outcomes. Development seeds and additional seeds have been inspected repeatedly in older benchmarks; neither is blind.

## Why the experiment exists

The existing `hidden_prerequisites.py` workshop-only skill achieved 480/480 on workshop tasks but just 222/480 on zero-shot repair tasks. It learned an overfitted set of workshop prerequisite guesses. A manually supplied stable role vocabulary meant this earlier work did not establish independent causal reasoning.

This study tests **learning by attempting target-world actions and observing acceptance or refusal**, both within an episode and over subsequent episodes. The original hidden simulator is unchanged. It never exposes the actual DAG. The learner consumes only its ordinary public frame (`goal`, opaque action aliases, engineered stable role tags, completed list, budget) and its own attempted actions plus accepted/blocked and goal outcomes. It does not get the missing predecessor on a block, hidden dependencies, true positions, or a privileged oracle.

`OnlinePrerequisiteAgent` maintains a Bayesian hypothesis distribution over all 64 subsets of potential prerequisites for each role. Observing an acceptance rules out prerequisite sets that aren't contained in the completed roles; observing a block rules out sets that are already satisfied. The policy probes the goal early, doesn't retry a blocked action without progress, and preferentially selects actions predicted to be ready and possibly relevant to the goal. It uses public role tags, an engineered prior, a graph-style transitive relevance computation, a hand-set probability threshold and deterministic episode hashing. **The learner does not discover a new action vocabulary or infer task semantics from language.** No task permissions, policy promotion or real-world execution are provided.

## Frozen procedure and controls

- Six **previously inspected** seeds: development 14003/14009/14033, additional 27007/27011/27017; two families: workshop and repair.
- For every seed and family, online evaluation uses 80 consecutive `test/83000..83079` episodes, with the public frame and outcomes from **the current and preceding episodes only**. The first 20 are cold-start and the last 60 permit accumulated experience. This is a sequential **online-adaptation evaluation**, not a conventional no-training test set. The policy is reset between families and seeds.
- Every episode has at most 12 attempted actions. An unsuccessful attempt consumes budget. The underlying simulator and seed schedules were not modified.
- Controls use identical episodes: random; goal-first; goal-first then uniformly untried/renewed actions; workshop-only pretrained static skill (360 workshop episodes); hard-coded role order; hidden-DAG oracle (privileged, benchmark only).
- Success, cold/warm successes, total attempts and blocked attempts are reported by family and seed. The frozen protocol and raw result files are retained.

## Six-seed results

| Policy | Workshop success /480 | Repair success /480 | Mean blocked attempts per episode, both |
|---|---:|---:|---:|
| Random | 370 | 315 | 3.91 |
| Goal-first | 161 | 83 | 6.47 |
| Goal-first then untried / newly viable | 423 | 387 | 3.68 |
| Workshop-only learned skill | 480 | **232** | 2.60 |
| **Online prerequisite probe learner** | **480** | **480** | **1.05** |
| Hand-programmed role order | **480** | **480** | **0.00** |
| Privileged hidden-DAG oracle | **480** | **480** | **0.00** |

The online learner succeeded on all **240 cold-start** episodes and all **720 subsequent** episodes across the two families. Its average action count was **6.26 attempts** versus **4.50** for the privileged oracle and **6.50** for role order. The result demonstrates useful *feedback-aware adaptation* in a small, bounded and structurally repetitive simulator. It does not establish that the persistent Bayesian knowledge causes a success advantage: the online policy already succeeds perfectly from the beginning with 12 actions, and the fixed role-order heuristic also succeeds perfectly. Further experiments should reduce the action budget, change role vocabularies and DAG structures, and evaluate cold-start resource efficiency independently rather than post-hoc tuning these fixed results.

## Integrity and limits

Versioned checkpoints store public action/outcome traces and the learned prerequisite weights. Restoration replays the policy choices and posterior updates, detecting impossible saved choices and modified counters, even if a checksum was recomputed. This **does not authenticate** a completely rewritten but internally coherent history, and does not constitute owner permission. No external tools, network requests, OS calls, protected identity records, or unreviewed model promotion are added.

The test checkout used a local transcription of `HiddenProcedure`, `PreconditionSkill` and baseline runner that was checked against current GitHub source; this test mirror is **not committed**. The experiment's new module imports the actual existing GitHub simulator when installed. New targeted unit tests passed; `python -m benchmarks.transfer_benchmark` from the archived original source separately retained 76.0% / 69.0% / 66.67% on seeds 17/23/41. A full clean GitHub checkout and full CI are **not verified**.

## Reproduce

```sh
python -m unittest tests.test_online_prerequisite_probing tests.test_hidden_prerequisites -v
python -m benchmarks.online_prerequisite_probing_benchmark --cohort development --out benchmarks/online_prerequisite_probing_results.json
python -m benchmarks.online_prerequisite_probing_benchmark --cohort additional --out benchmarks/online_prerequisite_probing_additional_results.json
python -m benchmarks.transfer_benchmark
```

**Next:** Freeze a new benchmark with independently generated prerequisite graphs, unfamiliar role schemas, strict action budgets and an explicit cost of exploration. Compare against plan-search and Bayesian/no-memory baselines. Keep D1 blind generalization, D3 real cross-family transfer and D4 composable skills open. V2A affective cognition precedes and overlaps V2B persistent virtual home as approved.
