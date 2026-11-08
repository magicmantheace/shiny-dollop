# D3/D4: Outcome-guided event memory after reward changes (experimental)

**Status: research only; no default promotion, no real actions, no D3/D4 gate completion.** The [`nonstationary_event_value_protocol.json`](../benchmarks/nonstationary_event_value_protocol.json) was committed on `main` as `d33af645581466e8d6360ae0827b636d80116f26` before testing any new evaluation episodes. Seeds 14003/14009/14033 and 27007/27011/27017 were previously inspected in other experiments; the second group is **not independent blind**.

## Objective and scope

The previous `outcome_event_memory.py` keeps a cumulative reward estimate over a four-state, task-specific HMM segmentation. It chooses inferred event spans whose labels produced good terminal rewards in the past. That works for stationary preferences but cannot adapt quickly when the same public context starts rewarding a different hidden label.

This optional experiment uses a **simulator-only** A→B→A curriculum. The same seed-dependent context-to-label reward rule A is learned first (200 `source_bursts` train episodes). The simulator privately changes each target label to `(label+2) % 4` for B, and then restores the original mapping. The learner is never given A/B flags, hidden labels, the true span, or the phase schedule: it receives **only** a public 0/1 context, raw four-symbol observations, the span it selected, and a terminal success/failure bit. Training episodes continue in a monotonic internal index even though generator indices are distinct. The HMM remains fixed and is trained separately on 160 raw-only source-family episodes; new adaptation uses `shifted_bursts` observations.

Training: `train/2000..2199` for initial preference A, `train/6000..6119` for B, and `train/6200..6319` for the return to A. At each stage, read-only evaluation uses **different** `test` episodes (`95000..95039`, `95100..95139`, `95200..95239`) with no learner update from evaluation rewards. Each approach has an equal binary-feedback training budget but chooses its own actions, so observed feedback is on-policy, not matched counterfactual outcomes.

## Methods compared

- **Frozen A:** initial 200 rewarded memories remain the only scoring evidence. It cannot adapt, even though it experiences subsequent training episodes.
- **Cumulative:** reward statistics over the complete history; old successes remain influential.
- **Sliding 32:** only the 32 most recent rewarded selections determine preferences. No assumption that old rewards remain applicable.
- **Archive/recent:** immutable initial A evidence plus a recent-32 policy; switch between the two after ≥3 negative outcomes in 4 steps and wait eight actions before another switch. These triggers are pre-specified engineering heuristics, **not learned uncertainty or reliable regime identification**.
- **Raw-run sliding 32:** same reward selection from raw same-symbol runs rather than HMM segments.
- **Privileged available-target upper reference:** uses a simulator-only test of whether the hidden relevant label occurs in the episode. No learner sees this information.

All train methods explore one in five actions using reproducible hash-derived choices. The archive only retains experience in a full local event log; **not** a truly memory-limited agent. An intact state digest is not a signature or consent. Restore verifies the full ordered decision and reward log by deterministic replay, including archive switches, rejecting internally inconsistent forgery even when the attacker recomputes the checksum.

## Results, frozen six-seed evaluation

Each stage comprises **6 seeds × 40 episodes = 240 tests per method**. More is better.

| Method | Initial A | Changed B | Return to A |
| --- | ---: | ---: | ---: |
| Frozen A | 160/240 (66.7%) | 21/240 (8.8%) | 168/240 (70.0%) |
| Cumulative | 160/240 (66.7%) | 28/240 (11.7%) | 168/240 (70.0%) |
| **Sliding window, 32 outcomes** | **161/240 (67.1%)** | **155/240 (64.6%)** | **169/240 (70.4%)** |
| Archive/recent with failure-triggered switching | 160/240 (66.7%) | 146/240 (60.8%) | 168/240 (70.0%) |
| Reward-trained raw-run window | 86/240 (35.8%) | 84/240 (35.0%) | 93/240 (38.8%) |
| Privileged available-target upper reference | 223/240 (92.9%) | 221/240 (92.1%) | 214/240 (89.2%) |

The sliding-window approach **substantially outperforms** a frozen or whole-history memory after a reward change. The archive mechanism learns to abandon failing preferences and can reactivate its old A memory, but it **does not outperform the sliding window at any stage**, switches repeatedly, and supplies no proven retention advantage here. The reappearance of A does not justify claiming a learned regime model: a frozen-A reference also performs well when the original world returns. These are descriptive scores from a small, inspected synthetic benchmark, not significance or safety guarantees.

The underlying event segmentation has known errors, and some episodes contain no reachable event with the target label. The fixed four-state vocabulary, explicit context IDs, access to binary rewards and hand-set window/trigger lengths are strong engineered priors. The simulation tests **reward adaptation**, not general episodic memory, causal goal discovery, or real-world lifelong learning. It is a useful negative result for the archive idea and a positive baseline for nonstationary event value.

## Verification

```sh
python -m unittest tests.test_nonstationary_event_value tests.test_outcome_event_memory tests.test_event_segmentation tests.test_environment_api -q
python -m benchmarks.nonstationary_event_value_benchmark --cohort development --out benchmarks/nonstationary_event_value_results.json
python -m benchmarks.nonstationary_event_value_benchmark --cohort additional --out benchmarks/nonstationary_event_value_additional_results.json
python -m benchmarks.transfer_benchmark
```

Remote CI, real hardware and an independent blind holdout remain unverified. The historical transfer benchmark must stay at seed 17 76.0%, seed 23 69.0%, seed 41 66.67% on the unchanged 5,000-training/300-test setup. Other tests may be unavailable in a reconstructed local checkout; do not imply full green coverage without evidence.

## Next milestone

Learn a **contextual change detector using its own held-out forecasts**, compare against strong sliding, discounted and contextual-window baselines on a newly frozen task family with hidden reward changes, and measure recovery speed and forgetting separately. Do not promote the archive just because it can toggle. D1 independent evaluation, D3 generalization and D4 transferable skills stay open. The user-consented AthenZ identity and Synveil policy boundaries stay separate; Versions 2A (affective cognition) then overlapping 2B (virtual home) remain as planned.
