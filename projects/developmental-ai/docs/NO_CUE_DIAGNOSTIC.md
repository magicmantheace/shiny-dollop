# One-step public-feedback regime diagnostic (2026-10-21)

**Optional simulation-only experiment. No default learner changes, no
AthenZ/Synveil integration, no real-world actuation.**

## Purpose

The prior [contextual affordance study](CONTEXTUAL_AFFORDANCE.md) retained
risk memories across A→B→A by receiving a perfect simulator-supplied public
two-number regime cue. The next test removes the cue **entirely from the
runtime policy inputs** and attempts to infer which of two *already
trained* risk memories applies using public action feedback.

The model does NOT independently discover new environments, general
physics, or stable action meanings. It learns a **diagnostic intervention**
from first-action training outcomes. It is tested only on the earlier
inspected deterministic cargo simulator, with engineered stable numeric
action descriptors and two known action-identity remappings. Both
candidate histories were separated by a phase-aware training harness:
80 training episodes in each of two known regimes.

## Frozen protocol and mechanism

See [benchmarks/no_cue_probe_protocol.json](../benchmarks/no_cue_probe_protocol.json),
committed as `4ab405b78ba9b3b787814da91f4355a92d4b7509` before writing
the policy or benchmark.

- Train A: `train/0..79`, B: `train/300..379`, with the old
  unfiltered `FilteredNovel` and previous `RiskMemory` histories.
- Test A `test/8700..8759`, B `test/8700..8759`, and return A
  `test/8800..8859` per seed, 18 steps per episode.
- Seeds 51001/51013/51031 and 61001/61013/61031 were all
  **previously inspected**. This is a post-hoc mechanistic follow-up,
  not a new blind holdout.
- Runtime public frame is `ShiftedCargo.frame()["public"]` only.
  The agent never receives a context cue, phase name, true action name,
  hidden recipe, or simulator ontology.
- It scans the first attempted step in each training episode and
  estimates `P(accepted | two-byte descriptor, known training history)`,
  with add-one smoothing. Candidates must have at least two first-step
  attempts in **each** history, and at least a 0.30 difference between
  their smoothed acceptance rates. Select the strongest difference
  with deterministic tie-breaking, not a simulator-private name.
- When all public sensor values are zero at episode start, one such
  diagnostic action is attempted before normal planning. Observed
  accepted/blocked feedback updates the relative likelihood of the
  existing histories; the chosen history supplies the preexisting
  risk filter for the remainder of the episode.
- The diagnostic action is a **real simulated action**; it consumes
  one step and is included in continuing `FilteredNovel` history.
  It is safe to probe at the very beginning **only because these
  particular known cargo operations cannot consume absent raw material**.
  The implementation does NOT guarantee safe probing in any other
  context, and its preconditions are not inferred causally.
- If training contains no sufficiently discriminative probe or the
  initial sensor state differs, the agent uses a deterministic
  historical policy. This is abstention/fallback, not independent
  novelty learning.
- The per-episode evidence and selected history are SHA-256
  checksummed and reconstructed from raw public observations and
  actions; source `ContextMemory` remains unchanged, replay-verifiable
  and locally checkpointable. Digests detect accidental tampering
  but do not authenticate external origin.

## Required comparisons

The test records full A/B/A trajectories with **all** methods:
one-probe inferred memory, the same one-probe step then **always
using frozen A**, frozen A-only and B-only memories without probing,
untrained novel-first, the previous **perfect-beacon upper reference**,
and a privileged action-hazard oracle.

Metrics: successes, spoilage, attempts, blocked actions, stalls,
number of diagnostic actions, history-selection accuracy for
**benchmark scoring only**, abstentions and exact replay after
checkpoint restoration.

The intervention is expected to distinguish regimes only because
the training history contains a descriptor that is blocked at time
zero in one regime and accepted in the other. In noisier or
irreversible environments an active probe could produce harm.
A positive result here is narrower than learned causal inference
or authentic self-development; it is supervised-by-experience
selection between **two already known contexts** from a publicly
observed outcome, not discovery of a third regime.

## Commands

```sh
python -m unittest tests.test_no_cue_diagnostic -v
python -m benchmarks.no_cue_probe_benchmark --cohort development
python -m benchmarks.no_cue_probe_benchmark --cohort inspected-additional
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

**Status:** The full benchmark and cross-platform GitHub tests must be
run on the current commit before reporting results. Preserve every
failed or inconclusive step; do not silently change seeds or claims.

## Next, after this bounded experiment

Test consequences that change stochastically and require more than
one low-risk probe. Model uncertainty and explicitly abstain from a
dangerous experiment when its cost cannot be bounded. Move from
simulator-assigned descriptors to learned affordances obtained from
observable feature streams, with *independently generated* tasks,
matched training experiences, and A→B→C→A retention. Keep the
source-trained learner and all earlier scientific baselines intact.
