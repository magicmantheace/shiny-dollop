# Evidence-opposition onset guard — evidence-count abstention gate on recent8

**29 October 2026. Status: optional, simulated, unpromoted. No default-controller
promotion, no PR merge, no D1–D10 or V2A/V2B roadmap change, no AthenZ/Synveil
integration.**

## Experiment identity

- **Name and purpose:** `evidence_opposition_onset_guard` — whether a change
  signal computed from the observed evidence itself (raw span-conditional
  outcome counts, with NO fitted probabilities anywhere) can separate switch
  onsets from stationary noise, drive a selective abstention gate that reduces
  harmful TEST actions at checkpoints 2 and 4 after an unannounced rule
  change, and release by checkpoint 32 — where both preceding abstention
  gates, derived from the acting model's own fitted probabilities, were
  structurally silent at onset. Build Order Priority 1 (Independent
  Learning), item 4, and Priority 2 (Generalization & Reasoning), item 8;
  handoff §8 first-contact overconfidence / weak uncertainty calibration.
- **Candidate:** `EvidenceOppositionGuardMemory`
  (`developmental_ai/evidence_opposition_onset_guard.py`) — acts through
  recent8 exactly (a `RelationOutcomeMemory` fitted on the last 8 events
  only; no archive, no model selection, no displacement margin) plus a gate
  computed from the observed evidence itself: for each of the newest 2
  events, a hard span-majority expectation is built from the 24 events
  immediately preceding the newest window (same engineered span statistic;
  strictly-highest reported class wins, tie/empty → no expectation); an
  event is opposed if it is matched (expectation and reported class both
  non-neutral) and its reported class differs from the expectation; the gate
  fires and abstains iff opposed_count == 2. Below 26 events the gate is not
  evaluable. Separate optional learner; the default controller and all
  existing learners are untouched.
- **Branch and commits:** `developmental-ai/evidence-opposition-onset-guard`
  (forked from `developmental-ai/first-contact-onset-guard` @ `8e0a686`,
  itself forked from `developmental-ai/early-post-switch-adaptation` @
  `edd371f`, itself forked from `developmental-ai/standalone-policy-review`
  @ `6e0cac5`). Protocol frozen at `a148ee3`; implementation at `6fb0ec5`;
  evaluation at `816b4e4`. This grading report is committed on top of the
  evaluation commit.
- **Frozen protocol:** `benchmarks/evidence_opposition_onset_guard_protocol.json`
  (schema `developmental-ai.evidence-opposition-onset-guard-protocol/v1`,
  frozen 2026-10-28, before any implementation, unit test, harness, or score
  inspection for this experiment).
- **Cohorts:** development 312003/312021/312039 and additional
  313001/313017/313041 — NEW at freeze, disjointness verified by
  project-wide search before the freeze commit. Both cohorts are now
  **INSPECTED** and must never be re-tuned against. Detailed results:
  `benchmarks/evidence_opposition_onset_guard_results.json` (development)
  and `benchmarks/evidence_opposition_onset_guard_additional_results.json`
  (additional).
- **Simulator:** `StochasticWorld` unchanged (authored span-to-effect bands,
  two public numeric features). Schedule per seed: A → B1 (inverted) →
  return-A → B2 (inverted), plus a stationary A→A control arm. True outcomes
  flip with probability 1/8; TRAIN reports flip with probability 1/20. The
  learner sees only the public reported stream — no phase label, rule
  identity, or true outcome. Checkpoints 0/2/4/8/16/32 for every stage; 48
  TEST episodes per cohort cell (16 per seed, same indices re-scored at
  every checkpoint, never trained on). Checkpoint 0 is a reported
  diagnostic, NOT graded: at k=0 the stream contains zero post-switch
  events.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover -s tests`:
  873 tests OK in the evaluation stage, and 873 tests OK again in this grading
  stage (run this pass; the grading-stage changes are documentation only,
  no code changed). Focused candidate tests: 22/22 PASS in the
  implementation stage.
- Historical regressions: **PASS** — `python -m benchmarks.transfer_benchmark`
  (unchanged) exited 0 with its standard three-seed output in the evaluation
  stage, and exited 0 again when re-run in this grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts were
  run with no change to any frozen parameter, threshold, seed, or
  checkpoint. Every checkpoint entry carries the candidate's recorded
  signal record (per newest-window event: span, reported class, reference
  count, reference majority, matched/opposed flags; plus opposed_count,
  matched_count, gate fired / abstained flag, gate-evaluable flag), a
  checkpoint SHA256, and restore-replay identity verified true at every
  checkpoint in both cohorts (script-verified in this grading stage; no
  criterion-6 field missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the evaluation
  or grading commit was checked; no CI is claimed for `816b4e4` or for this
  grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results in
this grading stage, not hand-copied. Denominators are exact episode counts
(48 per stage-checkpoint cell); signal-state denominators are
seed-checkpoint states (18 onset, 15 graded control, per cohort).

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 1 | Signal separation from signal records alone (onset mean opposed ≥0.9; control (k=2,4) ≤0.6; gap ≥0.5) | **PASS** | **PASS** |
| 2 | Gate firing non-vacuous/selective (≥4/18 onset states; ≤2/15 graded control states) | **PASS** | **PASS** |
| 3 | Onset harm reduction (pooled k=2,4 harm ≤75% of recent8; ≤1 cell worse) | **PASS** | **PASS** |
| 4 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8) | **PASS** | **PASS** |
| 5 | Stationary control selectivity (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **PASS** |
| 6 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 1 — evidence signal separation (PASS, both cohorts)

Development: pooled onset mean opposed_count **1.056** (18 onset states;
required ≥ 0.9), stationary control (k=2,4) mean **0.000** (6 states;
required ≤ 0.6), gap **1.056** (required ≥ 0.5). Additional: onset mean
**1.000**, control mean **0.167**, gap **0.833**. Both cohorts sit close to
the protocol's a priori design expectations (onset ≈ 1.1, control ≈ 0.4,
derived from the known 1/8 stochastic + 1/20 report flip rates, combined
disagreement 0.1625) — and the control means came in *below* the design
value. This is the primary scientific test of the experiment, graded from
the recorded signal records alone with no TEST outcomes involved, and it
passes: raw span-conditional outcome counts carry an onset signal that the
acting model's fitted probabilities did not (the preceding experiment's
contradiction count was 0 in 28 of 36 onset states; here opposed_count is
0 in only 4 of 18 (development) and 5 of 18 (additional) onset states).
Mean matched_count was 1.278 (development) / 1.333 (additional) at onset
states vs 0.500 / 0.833 at control (k=2,4) states — matching is not the
bottleneck the protocol's sparsity failure mode feared.

### Criterion 2 — gate firing non-vacuous and selective (PASS, both cohorts)

Development: the gate fired at **5 of 18** onset seed-checkpoint states
(required ≥ 4), for **80/288** pooled onset abstentions; it fired at **0 of
15** graded stationary control states (required ≤ 2). Additional: fired at
**5 of 18** onset states, **80/288** onset abstentions, **0 of 15** graded
control states. For comparison, the preceding probability-derived gate
fired at 1 of 36 onset states across its two cohorts and the
experiment before that at none. The firing rate is real but modest —
roughly one third of onset states, close to the protocol's design estimate
((0.57)² ≈ one third) — and 13 of 18 onset states in each cohort still act
through recent8 unprotected (see the honest limits under Scientific
conclusion).

### Criterion 3 — onset harm reduction (PASS, both cohorts — narrowly)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate harm **185**
vs recent8 **250** — 74.0% of recent8, against the required ceiling of
≤ 187.5 (75%). No individual onset cell is worse than recent8 (6 of 6
cells ≤; required ≥ 5): B1-2 45 = 45, B1-4 32 vs 41, return-A-2 16 vs 42,
return-A-4 38 = 38, B2-2 32 vs 48, B2-4 22 vs 36. Additional: candidate
**198** vs recent8 **270** — 73.3%, ceiling 202.5; 6 of 6 cells ≤ recent8
(B1-2 31 vs 45, B1-4 29 vs 45, return-A-2 44 = 44, return-A-4 16 vs 42,
B2-2 46 = 46, B2-4 32 vs 48). The pass is genuine but narrow: the margin
is 2.5 harm actions (development) and 4.5 (additional) under the ceiling,
and the reduction is produced entirely by the 80 abstentions in the 5
firing states per cohort — in the 3 onset cells where the gate did not
fire for any seed, candidate harm equals recent8 exactly. In absolute
terms onset harm remains high: 185 and 198 harmful actions across 288
onset episode-checkpoints.

### Criterion 4 — release and productivity by checkpoint 32 (PASS, both cohorts)

Development: k=32 abstentions **0/144**, successes **65** = recent8 65
(required ≥ 57). Additional: abstentions **0/144**, successes **59** =
recent8 59 (required ≥ 51). Release is complete at k=32 on both cohorts,
as designed (the 24-event reference window has slid past the switch).
This pass does not erase the pre-registered persistence cost at k=8/16,
reported in full in the learning-evaluation table: development B1-16
successes 5 vs recent8 26 (32 abstentions) and return-A-8 successes 23 vs
31 (16 abstentions); additional B1-8 successes 10 vs 27 (32 abstentions)
and return-A-8 successes 13 vs 21 (16 abstentions). The gate keeps firing
while its reference window still straddles the switch, and that costs
real successes mid-recovery — graded as a reported cost by the protocol,
not hidden.

### Criterion 5 — stationary control downstream selectivity (PASS, both cohorts)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32)
abstentions **0/240**, successes **125** = recent8 125, harm **115** =
recent8 115. Additional: abstentions **0/240**, successes **87** = recent8
87, harm **153** = recent8 153. The candidate is indistinguishable from
recent8 on stationary evidence at every graded control checkpoint in both
cohorts — zero false abstention, zero lost productivity, zero added harm.
Unlike the preceding experiment's criteria 3–4, these passes are not
vacuous in the damaging direction: the same gate demonstrably fires at
onsets (criterion 2) while never firing here.

### Criterion 6 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions, actual
harmful / productive / neutral outcomes, reported harmful, and label flips
for every stage; per-method successes / harmful TEST actions / abstentions
/ attempted tasks at every checkpoint; the candidate's recorded signal
record (per-event span, reported class, reference count, reference
majority, matched/opposed flags; opposed_count, matched_count, gate
fired / abstained flag, gate-evaluable flag) at every checkpoint;
checkpoint SHA256; and restore-replay identity (true at every checkpoint
in both cohorts, script-verified in this stage). Learner
information-acquisition actions = 0 and additional requested observations
= 0 throughout, as frozen.

## Learning evaluation

Candidate vs recent8 (successes / harmful TEST actions / abstentions, 48
episodes per cell). The candidate equals recent8 in every cell except
where its gate fired.

| Stage-ckpt | Dev candidate | Dev recent8 | Add candidate | Add recent8 |
| --- | --- | --- | --- | --- |
| B1-0 † | 2 / 46 / 0 | 2 / 46 | 1 / 47 / 0 | 1 / 47 |
| B1-2 | 3 / 45 / 0 | 3 / 45 | 1 / 31 / 16 | 3 / 45 |
| B1-4 | 0 / 32 / 16 | 7 / 41 | 3 / 29 / 16 | 3 / 45 |
| B1-8 | 28 / 20 / 0 | 28 / 20 | 10 / 6 / 32 | 27 / 21 |
| B1-16 | 5 / 11 / 32 | 26 / 22 | 20 / 28 / 0 | 20 / 28 |
| B1-32 | 14 / 34 / 0 | 14 / 34 | 17 / 31 / 0 | 17 / 31 |
| return-A-0 † | 0 / 48 / 0 | 0 / 48 | 0 / 48 / 0 | 0 / 48 |
| return-A-2 | 0 / 16 / 32 | 6 / 42 | 4 / 44 / 0 | 4 / 44 |
| return-A-4 | 10 / 38 / 0 | 10 / 38 | 0 / 16 / 32 | 6 / 42 |
| return-A-8 | 23 / 9 / 16 | 31 / 17 | 13 / 19 / 16 | 21 / 27 |
| return-A-16 | 32 / 16 / 0 | 32 / 16 | 21 / 27 / 0 | 21 / 27 |
| return-A-32 | 20 / 28 / 0 | 20 / 28 | 16 / 32 / 0 | 16 / 32 |
| B2-0 † | 1 / 47 / 0 | 1 / 47 | 0 / 48 / 0 | 0 / 48 |
| B2-2 | 0 / 32 / 16 | 0 / 48 | 2 / 46 / 0 | 2 / 46 |
| B2-4 | 10 / 22 / 16 | 12 / 36 | 0 / 32 / 16 | 0 / 48 |
| B2-8 | 25 / 23 / 0 | 25 / 23 | 20 / 28 / 0 | 20 / 28 |
| B2-16 | 19 / 13 / 16 | 29 / 19 | 19 / 29 / 0 | 19 / 29 |
| B2-32 | 31 / 17 / 0 | 31 / 17 | 26 / 22 / 0 | 26 / 22 |
| control-0 † | 20 / 28 / 0 | 20 / 28 | 19 / 29 / 0 | 19 / 29 |
| control-2 | 27 / 21 / 0 | 27 / 21 | 18 / 30 / 0 | 18 / 30 |
| control-4 | 29 / 19 / 0 | 29 / 19 | 17 / 31 / 0 | 17 / 31 |
| control-8 | 24 / 24 / 0 | 24 / 24 | 20 / 28 / 0 | 20 / 28 |
| control-16 | 20 / 28 / 0 | 20 / 28 | 18 / 30 / 0 | 18 / 30 |
| control-32 | 25 / 23 / 0 | 25 / 23 | 14 / 34 / 0 | 14 / 34 |


† Checkpoint 0 is a reported diagnostic, not graded (zero post-switch
events in the stream at k=0 for the switch stages). k=0 harm is 46–48 of
48 per switch stage in both cohorts for candidate and recent8 alike — at
k=0 the signal correctly sees no opposition, exactly as the protocol's
expected failure modes registered.

Reference points on the same cohorts: the preceding experiment's
candidate (`first_contact_onset_guard`, run here as a baseline) pooled
onset successes/harm/abstentions were 22/234/32 (development) and
18/270/0 (additional) — on these cohorts its probability-derived gate
again produced essentially no onset protection (additional: harm
identical to recent8's 270, zero abstentions). The earlier
`gated_archive_prequential` baseline pooled onset harm was 243
(development) and 275 (additional — worse than recent8's 270). The
privileged expected oracle (knows the expected hidden rule, not the
realized stochastic flip; a reference only, never a baseline) pooled
onset successes/harm were 182/106 (development) and 190/98 (additional):
onset tasks are largely solvable, and the candidate (23/185 development,
10/198 additional) remains far from that — its gain over recent8 is harm
avoided by abstention, not tasks newly solved. Pooled onset successes
actually *fall* vs recent8 (development 23 vs 38; additional 10 vs 18):
abstaining states forfeit the few successes recent8's obsolete model
still lands. That trade was pre-registered (harm is the graded onset
currency; successes are graded at release, criterion 4), and it is
reported here rather than smoothed over.

**Retention note (feeds the next limitation):** at return-A onset the
retained pre-switch model is immediately productive — `frozen_A` scores
34/48 successes at both return-A-2 and return-A-4 (development) and 35/48
at both (additional), 68 and 70 pooled. The candidate scores 10
(development) and 4 (additional) pooled at those cells: when its gate
fires it abstains (forfeiting those successes), and when it does not it
acts through stale recent8. Detection exists; recovery of retained
knowledge does not.

**Generalization level:** at most handoff level 2–3 (choosing among /
applying already-supplied representations under a rule change, plus a
designer-supplied abstention rule). The A/B rules, span statistic,
windows, and gate rule are all designer-supplied. No level-6 or
novel-representation claim is made. A PASS here demonstrates
evidence-count onset detection and selective abstention in this
simulator only, not calibrated uncertainty in general.

## Safety and evidence costs

- **Harmful TEST actions:** reported per checkpoint above; pooled onset
  harm 185 (development) and 198 (additional) vs recent8 250 / 270 —
  reduced by roughly a quarter, not eliminated; k=0 diagnostic harm
  46–48/48 at every switch stage in both cohorts.
- **Actual harmful TRAIN-acquisition actions** (external actor, counted
  once per seed, never netted against TEST results): development — A
  242, B1 87, return-A 47, B2 78 harmful of 1,248 main-schedule actions
  (plus control continuation 67 of 192); additional — A 251, B1 81,
  return-A 42, B2 73 of 1,248 (plus control 68 of 192). Label flips in
  the reported stream: development 48 (main) + 4 (control); additional
  56 (main) + 5 (control).
- **Failed-by-abstention:** candidate onset abstentions 80/288 in each
  cohort (5 firing states × 16 episodes), plus the persistence
  abstentions at k=8/16 detailed under criterion 4; 0 at every graded
  stationary control checkpoint and 0 at k=32 in both cohorts. The
  always-abstain baseline is 48/48 abstentions with 0 successes and 0
  harm at every checkpoint, as registered — the candidate is not that:
  it completes 65/59 successes at k=32 pooled stages, identical to
  recent8.
- **Additional requested observations / learner acquisition actions:**
  0 / 0, exactly as frozen.
- **False confidence and unnecessary abstention:** false confidence is
  reduced but remains the larger term — the candidate still acts on the
  obsolete recent8 model at 13 of 18 onset states per cohort
  (opposed_count 1 in 9/18 development and 8/18 additional onset states:
  signal present at sub-threshold level, below the both-events bar the
  protocol set for selectivity). Unnecessary abstention at graded
  checkpoints is zero on stationary evidence in both cohorts.
- **Report integrity / provenance:** checkpoint SHA256 replay identity
  held at every checkpoint in both cohorts; hashes validate record
  integrity only, not the truth of the (deliberately corrupted) public
  reports.

## Scientific conclusion

**Demonstrated** — within this simulator, and at handoff generalization
level 2–3 only.

Per the protocol's own grading definitions: the conclusion is
**Demonstrated** because all six criteria PASS on BOTH cohorts, the full
unit suite passes, and the historical transfer benchmark still passes.
It is not a Regression under any clause of the protocol's definition
(onset harm below recent8 on both cohorts; stationary-control successes
identical to recent8; suite and transfer pass).

What the experiment genuinely establishes: the two preceding failures
were signal-source failures, not abstention-response failures. A change
signal computed from the observed evidence itself — hard span-majority
expectations from the 24 preceding events compared against the newest 2
reported outcomes as raw counts, with no fitted probability anywhere —
separates switch onsets from stationary noise (criterion 1, graded from
signal records alone), fires selectively (5/18 onset states, 0/15
control states, both cohorts), removes just over the pre-registered
quarter of recent8's onset harm, and releases fully by checkpoint 32
with no stationary-evidence cost. Every element of that sentence is
bounded by the honest limits: the harm margin over the 75% ceiling is
2.5 / 4.5 actions; absolute onset harm remains high; the gate covers
only about a third of onset states while opposed_count sits at 1 in
roughly half of them; mid-recovery persistence at k=8/16 costs real
successes; and onset successes fall vs recent8 because abstention, not
adaptation, is the response. This is the campaign's first graded
Demonstrated result, and it demonstrates a *detection* capability —
recognizing that current knowledge is contradicted — not yet any ability
to act well on that recognition.

No frozen parameter, threshold, seed, or checkpoint is changed in
response to these results. Any revised hypothesis gets a NEW protocol
and NEW seeds.

## Next limitation (selected for the next cycle)

**P1 — detection without recovery: at a detected (or detectable) return
to a previously learned rule, the learner's only protective response is
abstention, which forfeits the retained knowledge that is immediately
usable — frozen_A scores 68 (development) / 70 (additional) successes at
return-A checkpoints 2 and 4 pooled, while the candidate scores 10 / 4
there (abstaining when its gate fires, acting through stale recent8 when
it does not).** Measurable form for the next protocol: at return-A
checkpoints 2 and 4 on NEW seed cohorts, whether a learner that pairs an
evidence-based onset signal with retained-knowledge recovery can
approach frozen_A's successes while keeping onset harm at or below the
evidence-opposition guard's level — against recent8, frozen_A, and the
evidence-opposition guard itself as baselines. This stays inside
Priority 1 items 2 and 3 (long-term retention; preventing new learning
from overwriting established knowledge) joined to item 4, and does not
re-tune any parameter of the three graded onset experiments against
their inspected cohorts. (Secondary, recorded but not selected:
sub-threshold signal coverage — opposed_count 1 in roughly half of
onset states — and k=8/16 gate persistence cost.)

## Reproduction

```bash
python -m unittest discover -s tests
python -m benchmarks.transfer_benchmark
python -m benchmarks.evidence_opposition_onset_guard_benchmark --cohort development
python -m benchmarks.evidence_opposition_onset_guard_benchmark --cohort additional
```

Re-running the benchmark cohorts reproduces the inspected results above;
it does not make the seeds un-inspected.
