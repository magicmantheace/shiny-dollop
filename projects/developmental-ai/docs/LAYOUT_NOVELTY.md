# Alternative-map novelty check (`layout-novelty/v1`)

**Experimental, simulation-only, disabled by default.** This experiment addresses the weakness of `novelty_guard` and `channel_novelty` on a rotated two-marker map. It uses counterfactual **known-topology** landmark offsets, not discovery of open-ended geometry. Neither this code nor its warning may authorize tool use, promote a model, override AthenZ permissions, or interact with Synveil hardware.

## Method

The known 9- or 11-position ring and one-time start/goal beacon come from the environment. Each step supplies exactly the commanded action, odometry and landmark reading. A pre-fitted `StructuredModel` bank (one or two entries) supplies motion, odometry and marker-emission probabilities. The detector evaluates the joint likelihood of observations under the unchanged bank's `SwitchingBelief` and independently under a collection of counterfactual maps. Each alternative copies a saved model but changes the **marker origin** for the current ring size. The alternatives retain the *engineered* two-marker, half-ring spatial relationship and learned categorical emission types; no model weights are fitted from the evaluated stream.

A sequential statistic records the maximum positive log-likelihood advantage of any alternative over the saved model bank, across prefixes of at least eight observations. This searches many hypotheses and prefixes; an absolute raw advantage would cause overfitting. Calibration therefore measures this **entire maximum** on distinct train-namespace reference episodes and selects an upper empirical quantile. An alert latches when the statistic exceeds the receipt-bound cutoff. The calibration receipt includes a model-bank fingerprint, hazard, history digests and an accidental-integrity SHA-256 checksum. Neither digest nor reference rank is an authenticated signature, actual approval, or distribution-free safety guarantee.

`CalibratedLayoutGuard` records strictly ordinary observations and validates checkpoint restoration by recomputing its decisions and likelihoods from the full bounded log. The existing navigation controller and all prior guards are untouched. The new diagnostic is currently **not wired into any automatic pause or action loop**.

## Comparable experiments (all six seeds previously inspected)

Matched models and actions against the existing **two-layer guard** (model surprise plus sensor run-length), which is unchanged. Fit: 48 mixed train histories; validation: 16; hazard selection: 12; reference cutoff: 64 independent train streams, alternating normal and known-within-episode-shift; evaluation: 24 `test` episodes per condition per seed. No test observations enter fitting or threshold selection. These datasets have been previously inspected repeatedly and are not a blind holdout.

| Condition | Existing two-layer | Map overlay, alpha=.10 | Conservative exploratory overlay, alpha=.04 |
| --- | ---: | ---: | ---: |
| Rotated layout flagged | 49/144 | **92/144** | **67/144** |
| Normal episodes falsely flagged | 10/144 | 22/144 | 13/144 |
| Known environmental changes falsely flagged | 12/144 | 23/144 | 14/144 |
| Stuck-landmark episodes flagged | 144/144 | 144/144 | 144/144 |
| Stuck-odometry episodes flagged | 144/144 | 144/144 | 144/144 |

The first overlay was a **predefined alpha=.10 reference-rank** trial; it nearly doubles rotated-map detection but causes too many false alarms. The alpha=.04 threshold was explored **after inspecting the alpha=.10 results**. It has materially fewer additional false alarms but reduced detection; the second trial **is not a new independent validation**, even though its numeric cutoff was calculated entirely from train-only reference data. No tuning on test outcomes is allowed before a separately frozen evaluation.

The 144-count aggregates combine six seeds, each supplying 24 distinct episodes per condition. Detailed seed-wise threshold, alert sources and first-alert step appear in the attached JSON; negative control regimes and all false alarms are retained.

## Reproduction

```sh
python -m unittest discover -s tests -p test_layout_novelty.py -v
python -m benchmarks.layout_novelty_benchmark --seeds 17 23 41 --train 48 --validation 16 --hazard-calibration 12 --reference 64 --episodes 24 --iterations 2 --rounds 1 --layout-alpha .10 --out benchmarks/layout_novelty_results.json
python -m benchmarks.layout_novelty_benchmark --seeds 1009 1013 1031 --train 48 --validation 16 --hazard-calibration 12 --reference 64 --episodes 24 --iterations 2 --rounds 1 --layout-alpha .10 --out benchmarks/layout_novelty_audit_results.json
# Exploratory, examined after initial results:
python -m benchmarks.layout_novelty_benchmark --seeds 17 23 41 --layout-alpha .04 --out benchmarks/layout_novelty_strict_results.json
python -m benchmarks.layout_novelty_benchmark --seeds 1009 1013 1031 --layout-alpha .04 --out benchmarks/layout_novelty_strict_audit_results.json
python -m benchmarks.transfer_benchmark
```

## Remaining limitations and next gates

1. False positives remain too high for automatic pausing, even with the stricter reference cutoff. The union of independently calibrated guard components does **not** inherit either component's nominal alpha. No control policy is changed.
2. The data generator injects an offset-3 arrangement on a known two-marker ring. A novel *number* of landmarks, arbitrary topology, unseen sensor vocabulary, changing observation reliability, and adversarial sensor failures remain untested.
3. Distinct model banks were originally constructed with a simulator harness; fitting is offline, the world model may be wrong, and the `goal` and initial position are supplied. Detection is not proof of latent understanding or a safe autonomous brain.
4. Freeze a future decision rule and test against **new genuinely uninspected world families** before considering rollout. Require low false positives under live closed-loop action policies, robust detection delay, restart consistency and validated resource budgets. Retain V2A and V2B after core v1.0 learning milestones.
