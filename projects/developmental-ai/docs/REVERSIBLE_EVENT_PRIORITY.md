# D3/D4 experiment — reversible reward priorities, not yet reusable lifelong memory

**Status:** optional simulation-only experiment; no default-policy changes, no D3 or D4 gate completion. Evaluation protocol `benchmarks/reversible_event_memory_protocol.json` was committed at `74ae276326db63efc661b18f91e8db03b4bd3434` before any of these test outcomes were inspected. The additional seed cohort was tested without algorithm changes. All six seeds have been used in earlier experiments and are **not independent blind holdouts**.

## Motivation

The earlier `OutcomeEventMemory` learns cumulative reward evidence for fixed public contexts and HMM-inferred four-state event labels. That works if the underlying reward meaning is stationary, but an obsolete goal can dominate lifetime counts. This experiment measures *original rule → unannounced reversal → original rule returns*, without passing a phase name, private target label, true event boundaries, or goal transition signal into learner APIs.

## Implementation

`ReversibleEventPriority` accepts only a public context (0/1), a bounded sequence of observed tokens (0..3), its own previously suggested span, and a terminal boolean reward. The event model is **fitted separately** from raw `source_bursts/train/0..159` and frozen. The new priority learner retains a maximum of three per-context reward hypotheses. It uses bounded reward-only surprise to start a new hypothesis and checks whether existing hypotheses explain recent observed action outcomes better before revisiting one. A SHA-256 checksum protects serialization integrity and deterministic replay checks recorded decisions, rewards and bank statistics; it is **not authentication**, a signed owner approval, or evidence of a trustworthy history if a caller can forge a completely consistent history.

Matching comparisons observe equal episodes and feedback in original/reversal/return training phases:

- **Bank:** bounded archive, surprise-triggered new hypotheses and replayed state.
- **Cumulative:** empirical context/label successes over all training feedback.
- **Window:** empirical context/label successes over the most recent 32 rewards per context.
- **Frozen:** trained on the original phase only and not updated later. Its later low-reversal/high-return scores are expected.
- **Longest event:** longest span selected by a fixed learned HMM; no outcome adaptation.
- **Available-goal oracle:** simulator-only upper reference, checks whether the true desired event appears anywhere in a stream; this is not an equally informed algorithm.

Phase 1 uses 200 `source_bursts/train/2000..2199` rewards. Phase 2 changes both hidden context targets to the next cyclic label using 96 `train/2300..2395` episodes. Phase 3 restores the first targets for 96 `train/2500..2595` episodes. **The learner is not told when these changes happen.** After each phase, the model is round-tripped through replay validation; **48 different `shifted_bursts/test` evaluation streams per seed** are evaluated read-only. There are 6 seeds × 48 = **288 episodes per phase**. Original/reversal/return test ranges are `95000..95047`, `95100..95147`, `95200..95247`, respectively. All methods are evaluated on the same trials.

## Results

| Read-only phase, 288 episodes | Archived bank | Sliding window (32) | Cumulative | Frozen original | Longest HMM | Available-goal oracle |
|---|---:|---:|---:|---:|---:|---:|
| Original | **188** | 187 | 188 | 188 | 80 | 266 |
| Reversal | **178** | **177** | 45 | 28 | 62 | 247 |
| Return | 201 | 201 | **202** | **202** | 75 | 258 |

**Important:** The new archive is *not measurably superior* to a simple sliding-window controller. It performs almost identically on reversal and return and can be slightly worse than using the old frozen memory when a previous goal reappears. The bank creates 2–3 hypotheses per context; repeatedly creating a new expert when the old goal returns does **not prove it has identified or efficiently reused its historical hypothesis**. Nor do these results prove lifelong learning, autonomous goal selection, or transfer beyond the engineered context/label structure.

### Per-seed success counts (48 episodes per cell)

| Seed | Original bank/window | Reversal bank/window/cumulative | Return bank/window/cumulative |
|---|---:|---:|---:|
| 14003 | 30 / 30 | 39 / 38 / 7 | 42 / 42 / 42 |
| 14009 | 27 / 27 | 20 / 20 / 5 | 32 / 32 / 32 |
| 14033 | 29 / 28 | 29 / 29 / 15 | 34 / 34 / 34 |
| 27007 | 43 / 43 | 28 / 28 / 3 | 34 / 34 / 35 |
| 27011 | 27 / 27 | 23 / 23 / 5 | 29 / 29 / 29 |
| 27017 | 32 / 32 | 39 / 39 / 10 | 30 / 30 / 30 |

The first 20 *training* experiences in each phase also show mixed adaptation speed: in the return phase the archive succeeds 34/120, versus 75/120 for the cumulative controller; it therefore **does not show faster reacquisition**. These counts are from rewarded training interactions, separate from read-only held-out evaluations.

## Tests and use

```sh
python -m unittest tests.test_reversible_event_priority tests.test_outcome_event_memory tests.test_event_segmentation tests.test_environment_api tests.test_delayed_choice tests.test_occluded_navigation tests.test_transfer -q
python -m benchmarks.reversible_event_priority_benchmark --cohort development --out benchmarks/reversible_event_priority_results.json
python -m benchmarks.reversible_event_priority_benchmark --cohort additional --out benchmarks/reversible_event_priority_additional_results.json
python -m benchmarks.transfer_benchmark
```

57/57 available relevant regression tests passed locally (10 new). The original transfer benchmark remains at 76.0%, 69.0%, and 66.67% navigation success for seeds 17,23,41. This is a reconstructed checkout: the full remote suite, GitHub Actions, and physical hardware have not been verified.

## What to do next

The archive's existence is not sufficient. Next evaluate **explicit posterior recall versus a recency window**, detection latency, regime re-identification on repeated A/B/A/B transitions, longer-run retention, and false switches on never-changing controls. An independent D1 holdout and genuine D3 family transfer remain necessary. Nothing in this experiment grants AthenZ consent/identity authority, Synveil actuators, external execution permissions, automatic model promotion, or claims about consciousness. V2A affective cognition and V2B virtual home remain planned in their agreed order.
