# Optional channel-fault novelty diagnostics (`channel-novelty/v1`)

**Scope: simulation only; read-only diagnosis and optional pause of action suggestions.** The existing `novelty_guard.py` and default navigation policy remain unchanged. Neither this module nor its SHA-256 receipt authenticates an owner, grants permissions, retrains world models, or proves unfamiliar-world detection. The source is pure standard-library Python.

## Why this experiment

A whole-stream sensor-surprise guard detected all landmark-stuck faults in the original benchmark, but only **44 of 144** odometry-stuck episodes. We added a separate channel signature that counts consecutive **zero odometry** readings while a left/right movement is commanded. It also tracks repeated *non-null* landmark readings while moving. It intentionally ignores collect actions, for which zero displacement is normal.

`calibrate_channels(models, train_only_references, alpha=0.10)` computes per-channel upper-tail cutoffs from 64 distinct, ordinary-sensor reference streams in the matched benchmark. Reference streams alternate normal and known-shift conditions; they have the same action policy as evaluation. Bonferroni allocation plus fixed minimal floors avoids overly sensitive cutoffs (in all six cases the frozen thresholds were >5 consecutive zero-odometry readings and >4 identical non-null landmark readings). The receipt is bound to the exact model-bank fingerprint and references. The optional `LayeredGuard` exposes the logical OR of this signal with the unchanged model-surprise alarm. **The OR of two separately calibrated 10% checks is not itself calibrated to 10%.** The finite-sample rank has no guarantee under different action policies, correlated histories, shifted distributions, or adversarial faults.

`LayeredNavigation` composes the existing `GuardedNavigation` and channel signal, returning `None` instead of a subsequent action after an alarm. It changes no action choice before an alarm and never invents an alternative action. Frozen session/state snapshots restore only by replaying both components' observation histories. A restart checksum is accidental-change detection, not a signature.

## Reproduce

```sh
python -m unittest tests.test_channel_novelty tests.test_novelty_guard -v
python -m benchmarks.channel_novelty_benchmark --seeds 17 23 41 --out benchmarks/channel_novelty_results.json
python -m benchmarks.channel_novelty_benchmark --seeds 1009 1013 1031 --out benchmarks/channel_novelty_audit_results.json
python -m benchmarks.transfer_benchmark
```

Each cohort uses 48 model-fit and 16 validation episodes, two EM iterations, 12 hazard-calibration streams, 64 novelty-reference streams, 24 evaluation episodes **per condition and seed**, and 24 closed-loop evaluation episodes per selected fault and seed. Disjoint stream indices: fit `train/0+`, validation `train/10000+`, hazard `train/40000+`, novelty `train/50000+`, evaluation `test/93000+`, and navigation `test/97000+`. The mixed-world learner's training harness still groups conditions to generate the dataset. All six seeds were previously inspected, **not blind**; test outcomes never enter the receipt fit.

### Passive-fault alarms (all six inspected seeds, 144 streams per condition)

| Condition | Existing model-surprise guard | Combined model + channel guard |
| --- | ---: | ---: |
| Normal (false alarms) | 8/144 | **10/144** |
| Known regime shift (false alarms) | 10/144 | **12/144** |
| Injected stuck landmark | 144/144 | **144/144** |
| Injected stuck odometry | 44/144 | **144/144** |
| Unfamiliar rotated-landmark layout | 48/144 | **49/144** |

The new detector flags a fully stuck-zero odometer within at most six movement readings because of its fixed minimum threshold. That does not imply it can detect drifting, biased, intermittently faulty or adversarial odometry; unknown layouts are largely still missed. The two extra ordinary false positives and two additional known-shift false positives must be retained, not tuned away using the evaluated streams.

### Closed-loop pause cost (144 episodes per condition)

| Environment | Unguarded task success | Previous guarded success | New layered success | Previous guard pauses | Layered pauses |
| --- | ---: | ---: | ---: | ---: | ---: |
| Normal | 105 | 101 | 101 | 9 | 9 |
| Odometry stuck at zero | 44 | 37 | 21 | 36 | **115** |
| Landmark stuck | 25 | 21 | 21 | 122 | 122 |

When odometry is stuck, the layered guard pauses much more often and task completion falls: **this is a deliberate diagnostic interruption, not an improvement in task success.** The normal-case pause count is unchanged in this small closed-loop evaluation even though passive normal false positives rose by two. This distinction matters because the action policies differ between passive reference/evaluation and closed-loop navigation.

## Open problems

- Detect intermittent and biased odometry errors without increasing false alarms in ordinary or shifted environments.
- Detect unknown landmark layouts that fit some existing models despite being wrong.
- Verify separate, genuinely blind out-of-family data and longer continuous streams before claiming a calibrated unknown-world detector.
- Evaluate reset/resume and optional pause in the eventual service/host interfaces; no physical actions, automation approval, or model promotion are permitted.
- Keep V2A affective cognition and V2B virtual home planned **after the core v1.0 gates** and in the agreed overlap sequence.
