# Repeated hidden reward reversals: archive reidentification study (D3/D4)

**Status:** optional simulation-only negative-result research. The broad six-stage
protocol was previously frozen in `benchmarks/repeated_reversal_protocol.json`;
the exact fixed budgets and episode schedule were committed in
`benchmarks/repeated_reversal_schedule.json` before this experiment's outcomes.
D1/D3/D4 remain open. The test seeds were examined in earlier studies: neither
cohort is independently blind.

## What was implemented

`developmental_ai.repeated_reversal.RepeatedReversalMemory` retains one
immutable bootstrap archive of 200 reward-labelled *agent decisions*, in
addition to a live 32-reward window. A read-only likelihood comparison uses
the most recent 16 action/reward events as evidence for either the old archive
or the *preceding* 32-event window. It selects old archive predictions only
when its log-evidence exceeds the recent reference by 1.5; otherwise it uses
the recent window. This margin is a fixed heuristic, **not** a calibrated
confidence level, a model promotion gate or automatic rediscovery of skills.

The agent sees only bounded observed tokens, an engineered context integer,
its own inferred selected event, and terminal success/failure feedback. Phase
names, true event labels and hidden reward preferences are accessible only to
the benchmark generator for scoring, not to any training or selection API.
`frozen`, `cumulative`, `window32`, `archive_recall`, and `raw_window32`
controllers train on the same number of episodes but receive rewards from
**their own decisions**. The privileged available-target reference is a score
upper bound, not an equally informed controller. The decoded four-state HMM,
context mapping, action budget and phase scheduling remain engineered.

Training: HMM source-burst `train/0..159`; A bootstrap
`source_bursts/train/2000..2199`; then 80 reward-only shifted-burst
`train/7000+100*stage` episodes per stage. Independent, frozen, read-only test
indices are `shifted_bursts/test/96000+100*stage` (40 per seed and stage).
The six stages are **A→B→A→B→A→A**. The final A is deliberately *not*
a new reversal and checks unnecessary archive reidentification; it is not an
independent 30-day stationary safety evaluation.

## Frozen six-seed evaluation

Six previously inspected seeds; **240 episodes per stage**, 1,440 episodes per
method across six phases. Higher completed retrievals are better.

| Phase | Frozen-A | Cumulative | Recent-32 | Archive+recent | Raw-run recent | Available-target oracle |
|---|---:|---:|---:|---:|---:|---:|
| A (first) | 178 | 178 | 178 | 178 | 74 | 224 |
| B (first reversal) | 33 | 41 | **167** | 159 | 71 | 219 |
| A (return) | 161 | 160 | **161** | 158 | 72 | 212 |
| B (second reversal) | 28 | 37 | 168 | 168 | 80 | 218 |
| A (second return) | 162 | 163 | 160 | **163** | 69 | 218 |
| A (no change control) | 168 | 169 | 157 | 157 | 74 | 222 |
| **Total** | **730** | **748** | **991** | **983** | **440** | **1,313** |

The archive heuristic does **not** beat the recent-32 baseline overall:
**983 vs 991 successes**, regressing on the first B and first return phases,
with a three-task gain on the second A return. Its 40-test-episode read-only
anchor-choice counts by stage were **80, 0, 120, 0, 40, 0** out of 240. Zero
anchor choices in the final no-change A stage do not imply a calibrated false
alarm rate or robust regime recognition. Independent experience histories
vary after policy divergence; these are same-budget comparisons rather than
fully paired actions/rewards.

A noteworthy positive but limited result: on the first 20 online adaptation
trials per seed in the second A return, the archive controller earned **42/120**
rewards versus **23/120** for the recent window, but this prequential
improvement did not yield a consistent final held-out advantage. The task has
no long-range unrelated skill transfer or independent blind evaluation.

## Validation, persistence and boundaries

- 11 new local unit tests and 54 total tests across seven modules in the
  reconstructed local checkout passed; this is **not** a complete fresh GitHub
  test or GitHub Actions/CI claim.
- `python -m benchmarks.transfer_benchmark` remained 76.0%, 69.0%, 66.67%
  successes on the existing three seeds.
- A bound, versioned checksum checkpoint stores only the agent's local
  synthetic training episodes, selected spans, and terminal booleans.
  Checkpoint loading replays **every selected action** and reconstructs source
  decisions and rewards; rejects impossible choices and mismatched model.
  SHA-256 is **not** a signature: a fully forged but internally consistent
  reward history may pass replay and cannot establish owner approval.
- Neither the archive nor the HMM has the authority to write human identity
  memories, change permissions, promote models or act on Synveil.
- Versions 2A (affective cognition) before and overlapping 2B (virtual home)
  remain planned after core v1.

## Reproduce

```sh
python -m unittest tests.test_repeated_reversal tests.test_outcome_event_memory tests.test_event_segmentation -q
python -m benchmarks.repeated_reversal_benchmark --cohort development --out benchmarks/repeated_reversal_results.json
python -m benchmarks.repeated_reversal_benchmark --cohort additional --out benchmarks/repeated_reversal_additional_results.json
python -m benchmarks.transfer_benchmark
```

**Next research question:** test actual archive reidentification and *task* value
on independently authored environments, with a simple recent-window policy
and a no-change control. Stop optimizing fixed four-state context labels unless
they produce a reproducible advantage over elementary controls. D1, D3 and D4
remain open.
