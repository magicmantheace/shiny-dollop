# Delayed-choice working-memory experiment — v1

**Research status:** development-set experiment. Not a digital mind, learned recurrent memory, independent goal creation, or an autonomous desktop agent.

## Hypothesis and limits

A purely reactive learner cannot use a cue that was shown only at the beginning of a trial; a learner with a working-memory gate can. The agent sees one of four arbitrary cue symbols at time zero, then 2–6 distracting signals during training, or 10–20 distracting signals in the longer test condition. At the final decision step the sensor exposes **no cue** and **no correct action**. Feedback reinforces a hidden four-way cue-to-button association. The task itself is intentionally simple and actions during the delay are predetermined `continue` transitions; learning happens only at the final four-way choice.

The retained-cue condition uses a **hand-written, correctly targeted memory gate**. This experiment tests whether an agent can *use* retained information and learn an association. It does not demonstrate learning what to remember, remembering a real-world life event, learning to navigate with invisible targets, or transfer across rich task families.

## Protocol

- Training: 800 episodes per seed, `short` (2–6 distractor) layouts, namespaces `train/short`.
- Evaluation: 400 distinct episodes from `test/short` and `test/long` (10–20 distractors) for each seed.
- Seeds: 11, 31, 73. These are public **development seeds**, not a held-secret blind test.
- Modes: `retain` (keep original cue), `reactive` (only current observation), and `overwrite` (latest visible signal replaces memory). All use the same tabular Q-learning rule and reward feedback.
- Null hypothesis: without cue retention, success tends toward one of four choices (25%), varying with small test samples and seed effects.
- Persistence: training checkpoints are saved in SQLite, tied to schema, seed, and memory mode. A database resumed with mismatching parameters fails closed. Identically seeded interrupted/resumed training reproduces an uninterrupted learner.

## Results

The stored exact results are in [`../benchmarks/delayed_choice_results.json`](../benchmarks/delayed_choice_results.json):

| Seed | Retained cue, long test | Reactive, long test | Overwrite, long test |
| --- | ---: | ---: | ---: |
| 11 | 100.00% | 19.50% | 24.75% |
| 31 | 100.00% | 21.75% | 24.75% |
| 73 | 100.00% | 25.00% | 29.00% |

The retained-cue learner recognizes a **four-symbol lookup association** even with longer interruptions. This is an intentionally solvable benchmark and no claim of open-ended memory competence should be made from its score.

## Reproduce

```bash
python -m unittest discover -s tests -v
python -m benchmarks.delayed_choice_benchmark --seeds 11 31 73 --train-episodes 800 --test-episodes 400
python -m developmental_ai.delayed_choice train --mode retain --seed 11 --episodes 800 --db delayed_brain.db
python -m developmental_ai.delayed_choice evaluate --mode retain --seed 11 --episodes 400 --band long --db delayed_brain.db
python -m developmental_ai.delayed_choice trace --mode retain --seed 11 --index 3 --band long --db delayed_brain.db > delay_trace.json
python -m developmental_ai.delayed_choice verify --trace-file delay_trace.json
```

SQLite files and local traces remain local; do not check personal or identifying input into Git. Evaluation does not change Q-values or checkpoint metadata. The trace verifier replays simulation transitions, and its checksum alone cannot prove who authored the trace.

## Next challenge

Replace the explicitly programmed memory gate with a learned recurrent controller, and demonstrate retention over novel noisy trajectories where **the relevant cue is not designated by a hard-coded phase label**. Then connect memory to visually occluded navigation and multi-step goals. Keep one frozen independent evaluation set from which hyperparameter and architecture choices are excluded.
