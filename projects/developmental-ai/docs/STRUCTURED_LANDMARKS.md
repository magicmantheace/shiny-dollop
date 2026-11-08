# Structured landmark-map learning (`structured-landmarks/v1`, experimental)

**Status:** optional observation-only world-model experiment. Not promoted to the default navigator or approved as an autonomous agent service. This explicitly tests an inductive bias, not discovery of arbitrary physical laws, consciousness, or humanlike understanding.

## What changed, and what the learner knows

Earlier `online_dynamics.fit` learns an **independent three-outcome landmark probability distribution for each position on each ring**, from partial histories via latent-state expectation maximization (EM). This is high-dimensional for the available data and often develops incorrect/overconfident map likelihoods under noise.

The new `fit_structured` uses a **specified structural prior**: a 9- or 11-position ring has **exactly two distinguishable landmark sites**, separated by `n//2` positions, and background sites share one emission distribution. It still does not know the landmark origin/offset for either ring size, or the categorical motion/odometry/landmark response rates. It selects each offset using *marginal observation likelihood* from **the model-fitting train partition only**, then performs forward/backward EM on ordinary sequences to learn movement, odometry and shared landmark emissions. The learner receives:

- The ordinary **one-time initial position beacon** and ring size, and each chosen movement command, noisy odometry and landmark reading;
- **No** subsequent simulator position or realized delta, physics regime name, reward, result/score or evaluation hidden state;
- A manually supplied assumption of sparse two-landmark geometry, identical sensor vocabulary and a small fixed 9/11-position map family. Initial sensor/motion likelihoods are **engineered priors**, not discovered from scratch.

The original independent-emission baseline, heuristics and physically privileged probability oracle stay unchanged. The structured model plugs into `AdaptiveNavigator` through read-only `motion_probs`, `odo_probs` and `landmark_probs`. Its checkpoint has schema, seed binding and a SHA-256 corruption indicator, **not** a cryptographic attestation or authenticated approval. No new system permissions or automatic model promotion are provided.

## Frozen, reproducible comparisons

```
python -m benchmarks.structured_landmarks_benchmark --seeds 17 23 41 --train 90 --test 40 --iterations 6 --navigation 60 --out benchmarks/structured_landmarks_results.json
python -m benchmarks.structured_landmarks_benchmark --seeds 1009 1013 1031 --train 90 --test 40 --iterations 6 --navigation 60 --out benchmarks/structured_landmarks_audit_results.json
python -m benchmarks.structured_landmark_novelty_benchmark --seeds 17 23 41 --offset 3 --train 90 --iterations 6 --test 40 --navigation 60 --out benchmarks/structured_landmark_novelty_results.json
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark
```

Both methods receive **identical** 90 train-namespace histories and six EM passes per seed/regime (the structured method also searches offsets). Forty `test/28000+` histories measure held-out *observation* log likelihood; 60 separate `test/34000+` seeded navigation worlds measure closed-loop success. The novelty experiment substitutes previously unmodeled offset `3` (rather than the original simulator offsets `0` and `2`) and uses separate `test/41000+` and `test/47000+` windows. The benchmark alone knows the regime/true landmark locations; no labels enter fitting or control. All these seeds have been inspected; none are a clean independently blind validation, and the method was selected after inspecting previous experiment failures.

### Navigation success, 60 worlds per seed/regime

| Cohort and regime | Unconstrained observation EM | New structured model | Physics oracle |
|---|---:|---:|---:|
| Development 17/23/41, original | 77.2% | 75.6% | 77.8% |
| Development 17/23/41, shifted high-noise | 23.9% | **56.1%** | 55.6% |
| Inspected audit 1009/1013/1031, original | 86.1% | 81.7% | 77.8% |
| Inspected audit 1009/1013/1031, shifted high-noise | 13.3% | **55.0%** | 51.7% |
| Development 17/23/41, *new* offset 3 high-noise | 25.6% | **56.1%** | 55.0% |

The structured fit improved **held-out marginal observation likelihood in all 12 standard/shifted development-plus-audit cases**, and in all three offset-3 cases. It recovered the correct landmark origin for **both** ring sizes on every seed and condition in those runs. Scores slightly exceeding the physics oracle are sampling noise from finite navigation episodes, *not* proof the model beats true simulator probabilities or performs universally better. The structured model sometimes reduces success in the original environment compared with unconstrained EM; do not conceal this trade-off.

### What this does not establish

- Correct general spatial representation outside **the chosen two-site ring geometry**, ring sizes 9/11, fixed action vocabulary or observed sensor processes.
- Independent, truly blind/held-out procedural family generalization, variable numbers of landmarks, unreliable landmark identities, obstacle maps, multi-room environments, or arbitrary maps with no initial-position beacon.
- Genuine **automatic detection** that a novel map is present, unsupervised grouping into new regimes, or self-authorized changes to the model bank. The benchmark *groups fitting histories by simulator regime*, although the fit does not see regime labels.
- Reliable navigation on a real robot, the OS, or the V2B room. No interface to AthenZ/Synveil and no changes to V2A/V2B timelines.

**Next:** fit with uncertain numbers/identities/locations of landmarks, evaluate maps with changed topology and odometry reliability, learn observation grouping without regime labels, and freeze a fresh independent seed/task-family audit. Favor runtime/resource profiling before considering default policy promotion. Continue applying held-out candidate review and explicit user approval rules for any bank installation.
