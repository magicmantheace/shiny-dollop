# Standalone learning priority — October 20, 2026

## Development instruction

Prioritize measurable **learning, generalization, memory retention, reusable
skills, safe continual updates, and bounded simulated goal development**.
Do not expand AthenZ, Synveil, or cross-project integration during this phase.
Keep the existing integration PR unmerged. Preserve Version 2A (computational
affect) before and overlapping Version 2B (virtual environment), but neither
takes priority over standalone learning.

The starting main commit is `188873da59ab2dba429c3ccb498840f5c786640c`.
The existing random-layout, hidden-prerequisite, plan repair, and plan
compaction findings are inspected development studies, **not blind evidence**
of general cognitive transfer. A score on the existing seed family cannot
close D3 generalization or D4 skill reuse.

## First implementation slice: safeguarded updates

`developmental_ai.policy_review.StagedPolicyUpdate` wraps the original
`TransferBrain` without changing its default learning algorithm. It:

- Copies a policy to a disposable SQLite database before training new episodes.
- Scores old and proposed policies on the **same** reserved train-namespace
  validation layouts, disjoint from ordinary sequential training and test.
- Measures success, steps, blocked moves and external reward.
- Gates eligibility using a configurable paired-cohort maximum success loss.
- Requires a separate explicit approval plus a matching review digest before
  installing and persisting weights.
- Rejects a changed base or tampered candidate; rejected updates never change
  the original persistent database.
- Preserves promoted policy persistence across process restarts.

This is a practical **update-integrity and regression gate** only.
It does not solve catastrophic forgetting, prove out-of-family transfer,
guarantee statistical non-inferiority, or provide authenticated approval.
The proposed candidate is temporary; after a crash, recreate and review it.
The digest is not a signature or evidence of the approving person's identity.

### Example (interactive, manual promotion)

```python
from pathlib import Path
from developmental_ai.transfer import TransferBrain
from developmental_ai.policy_review import StagedPolicyUpdate

brain = TransferBrain(Path("local_policy.sqlite3"), seed=17)
try:
    proposal = StagedPolicyUpdate(brain, 100, validation_episodes=64)
    reviewed = proposal.review()
    print(reviewed)
    # Inspect results and obtain explicit owner approval before proceeding.
    if reviewed["receipt"]["eligible_for_manual_approval"]:
        # Only invoke this after actual human approval; never automate it.
        # proposal.promote(approved=True, receipt_sha256=reviewed["sha256"])
        pass
    else:
        proposal.reject()
finally:
    brain.close()
```

Validation uses train indices starting at 3,000,000, not the historical
`test` namespace. Proposed training is refused if it could overlap the
validation index reservation. The default 2-percentage-point tolerance is a
simple deterministic gate; report binomial uncertainty before making
scientific claims. Do not tune it against the public test cohorts.

## Reproduction

```sh
python -m unittest tests.test_policy_review -v
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

The new CI workflow attempts full Linux validation, historical transfer, and
focused Windows tests. A GitHub workflow being committed does **not** itself
prove that it ran. Check actual run status and logs.

## Next research gates (not completed)

1. Benchmark genuinely distinct task families and unseen action/observation
   vocabularies, with strong heuristic and target-only baselines.
2. Quantify sequential A→B→C→A forgetting with matched replay and update
   ablations; retain negative results.
3. Extend the existing memory and skills, not duplicate them, using observed
   action-outcome relations; test restart and skill composition.
4. Add bounded simulated self-selected goals only after learned skills and
   retention show reliable improvements.

No AthenZ or Synveil integration work is authorized by this slice.
