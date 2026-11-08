# Per-observation reward-learned write/keep control (experimental)

This adds **optional, simulation-only research** toward D3. Unlike the prior `cross_task_retention.py` episode-wide initial-vs-latest strategy selector, `online_memory_gate.MemoryGate` decides **WRITE or KEEP for each incoming source-labeled signal** while maintaining one slot. Its source utility values and symbol-to-action response table are trained on short competing-signal episodes using only terminal reward feedback. The simulator alone knows the correct response; model input includes context bit, source label, observed token and the terminal reward. Inference does not read hidden target answers.

The environment and feature assumptions remain substantial: the finite sources `A/B/N`, binary context, four-valued tokens, terminal-response space, and one-slot capacity are engineered. The policy estimates the relative reward value of *channels*, not arbitrary individual memory content or generalized semantics. The distinct memory operations are decisions, but the choice architecture is supplied. This is not an RNN, open-world episodic memory, consciousness or completed D3 generalization.

## Transfer task and boundaries

Fit each seed exclusively on `selective_memory.SignalTrial`'s **train** episodes `0..1799`, with train band `short`, then freeze the table. Evaluate competing-signal response success on `test` indices `93000..93039`. To evaluate transfer, create an occluded-grid episode through the **public D2 `EnvironmentSession`** interface; take its *initial public beacon* and generate an intentionally ambiguous five-signal candidate stream with `A`, `B` and three `N` candidates, and a random context bit. The correct candidate uses the same context/source convention as the source task. The learned gate sees only source, context and bounded token index; it does not see which beacon is correct. Its retained candidate is passed to the **already learned spatial-motion updater**, which is not retrained on occluded rewards. The navigation heuristic is engineered.

**Important evaluation limitation:** This is an *engineered task translation*. The correct beacon is obtained from an existing **public** first observation and wrapped with synthetic decoys; the occluded simulator did not naturally present this ambiguity. Shared `A/B/context` semantics were deliberately preserved to make transfer feasible. The target cue's numerical values are never used in gate selection. We compare first, last, random and hand-engineered correct-channel (oracle) selection and a wrong/no-context ablation. Navigation outcomes are not used to train or tune the gate.

Seeds **2749, 6607, 9901**, plus previously inspected **17431, 24869, 37021**, were used during development; all are **nonblind** and examined in this work. Both cohorts use identical 1,800 fitting episodes, 24 train-only grid motion-updater episodes, and 40 test episodes per family per seed. This protocol and these results were inspected during algorithm development, **not prospectively preregistered**.

## Results

Successes (240 total episodes across six seeds):

| Task/method | Successes |
| --- | ---: |
| Competing signals, learned response + write/keep | **240/240** |
| Occluded navigation, learned selector | **217/240** |
| Occluded navigation, correct-channel engineered selector | **217/240** |
| Occluded navigation, first cue only | **44/240** |
| Occluded navigation, last cue only | **49/240** |
| Occluded navigation, random write/keep | **54/240** |
| Occluded navigation, learned selector without context (context=0) | **115/240** |

The source task and transferred task are related by the **engineered reliability metadata**. The learner matches the correct-channel selector on these cohorts, but that is **not** a blinded claim of reliable general attention; transferred context/source semantics, task family similarity, and scripted synthetic candidate preparation remain major limitations.

## Persistence, constraints and reproduction

`CueMemory` limits itself to 64 public candidate events and two bounded integer payload values, freezes a copy of the learned gate, checks record digests, and on restore deterministically replays all WRITE/KEEP choices and the held slot. Recomputed hashes with inconsistent choices are rejected. Checksums are **not signatures** and do not prove owner authorization; no model is auto-promoted, no external actions are possible, and production AthenZ/Synveil controls are unaffected. A physically rewritten and internally consistent record cannot be ruled out solely by a digest.

```sh
python -m unittest tests.test_online_memory_gate tests.test_cross_task_retention tests.test_environment_api tests.test_selective_memory -v
python -m benchmarks.online_memory_gate_benchmark --seeds 2749 6607 9901 --train 1800 --episodes 40 --out benchmarks/online_memory_gate_results.json
python -m benchmarks.online_memory_gate_benchmark --seeds 17431 24869 37021 --train 1800 --episodes 40 --out benchmarks/online_memory_gate_additional_results.json
python -m benchmarks.transfer_benchmark
```

31 local targeted and related tests passed; original transfer benchmark 76.0%, 69.0%, 66.67% on seeds 17, 23, 41. The checkout is reconstructed and **not a complete fresh mirror**, so a full remote test-suite pass is not claimed; CI and hardware are not claimed. Existing prototypes/defaults remain unchanged. D1 independent evaluation, D2 production integration and D3 unrelated-task transfer remain open; versions 2A and 2B remain in their approved order.

**Next:** Precommit a *genuinely new* evaluation task that does not reuse `A/B` source semantics or numerical offset conventions, and add a learned observation encoder rather than scripting the task mapping. Include ablations for source relabeling and context corruption before considering promotion.
