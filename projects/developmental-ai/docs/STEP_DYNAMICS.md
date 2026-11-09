# Step-by-step dynamics detection and quarantined candidate learning (`step-dynamics/v1`)

**Research prototype only.** No human identity data, network calls, real-world actions, self-promotion, privileged simulator trajectory truth, or system actuators. This module is independent of AthenZ and Synveil. It does **not** solve continual learning or robust novelty detection.

## What has been implemented

- `StepDetector.begin(n, initial)`: accepts the initial location beacon on a pre-known 9- or 11-position ring. The model bank is frozen and bound to a content fingerprint on monitor creation.
- `StepDetector.step(command, odometry, landmark)`: processes a single ordinary action/sensor observation. Each model maintains a separate latent-position posterior. The incremental forward-filter observation probability agrees numerically with the full `online_dynamics.forward_backward` likelihood. A bounded recent score window, minimum evidence, margin and repeated confirmations govern switching. The previous episode's score tail can inform later decisions; no actual position or regime label is supplied.
- Each begin, sensor observation and finish writes a simulation-only hash-linked record and a resumable filter checkpoint in one SQLite transaction. A restart halfway through an episode preserves the exact next decision. Invalid observations, incompatible catalogue fingerprints, missing records and basic digest tampering fail closed. SHA-256 hashes are *not* signed provenance or an authorization mechanism.
- `CandidateStore` stores only validated, de-duplicated observation histories, bound to the current bank fingerprint. A candidate is learned with the existing latent-state EM fitter **without ground-truth latent position labels**, but the model structure, known topology, action alphabet and episode start beacon are engineered.
- A fitted candidate is **frozen for review**, never auto-installed. An **independent held-out predictive review** must now pass before `promote(..., approval_digest=...)` will accept the review digest (the candidate-model digest is insufficient). This is a simple programmatic approval gate, **not human identity authentication**. Bank entries are immutable and a promotion invalidates old monitors until a new reviewed session is started.

## Reproduction

From repository root (Python 3.10+, standard library):

```sh
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark
python -m benchmarks.step_dynamics_benchmark --seeds 17 23 41 --out benchmarks/step_dynamics_results.json
```

The candidate is fitted from `train` histories with unseen indices. Existing bank models use other `train` indices. Sensor/forward-filter events and candidate quality are measured on `test` histories with non-overlapping indices. The benchmark chooses the unfamiliar **high-motion-noise / original-landmarks combination** by experimental design to collect candidate data; the detector does **not** automatically discover or mine a clean training batch from the stream. This is not an end-to-end autonomous learning loop.

## Results / negative findings (development seeds, not blind)

With 130 histories per known model, six EM iterations, 12 observed episodes per phase, a 24-step rolling window, minimum 5 current-episode steps, three confirmations and per-step log-likelihood floor -3.3:

| Seed | Original step accuracy | Changed step accuracy | Returned-original step accuracy | Candidate vs best known model, held-out NLL gain |
|---|---:|---:|---:|---:|
| 17 | 79.17% | 79.17% | 87.50% | +0.0015 |
| 23 | 86.11% | **0.00%** | 100.00% | -0.0083 |
| 41 | 95.83% | **0.00%** | 100.00% | -0.0359 |

Positive candidate NLL gain means the candidate predicts held-out data better than the strongest saved bank model; negative means it is **worse**. Two of three seeds did not detect the changed regime at all. Candidate learning from just 80 unlabelled histories does not reliably beat the saved models. A more expensive, 350-history/10-iteration exploratory run was attempted but **timed out**, so no results from that run are reported.

**Interpretation:** per-step causal inference, durable state and quarantine/approval boundaries work in these tests. The detector is **not** reliable enough for autonomous decisions. It must abstain when uncertain; no production confidence calibration exists. The held-out indices still come from the same simulator family, and the benchmark seeds were inspected during development.

## Known risks and next development

1. A time-varying environment **within one trajectory** is not represented by the present generator; this is cross-episode regime switching evaluated at individual sensor steps, not a demonstrated within-trajectory regime change.
2. The scoring floor and margin are heuristics. Unseen-condition detection can fail silently; selection is not statistically calibrated. More data, cross-validation and independent blind audit are needed.
3. Model discrimination at 12 steps can be poor, and finite-history EM may find weak solutions. Improve calibration and evaluate genuinely novel regimes beyond simple recombinations of the existing two physical factors.
4. A separate frozen validation review is now required by the code (see [`CANDIDATE_REVIEW.md`](CANDIDATE_REVIEW.md)). Evaluation provenance is not cryptographically proven and generalization beyond simulator distributions remains open. No model is ever automatically installed from outliers.
5. Current digest matching is not authenticated human approval. Integrate with AthenZ's actual owner-consent and signature/permission service before treating any promotion as authorized in a real deployment.
6. Historical `continuous_dynamics` remains a separate *per-episode* baseline. Do not silently overwrite its results or its state schema.
