# First-contact onset guard — contradiction-gated abstention on recent8

**28 October 2026. Status: optional, simulated, unpromoted. No default-controller
promotion, no PR merge, no D1–D10 or V2A/V2B roadmap change, no AthenZ/Synveil
integration.**

## Experiment identity

- **Name and purpose:** `first_contact_onset_guard` — whether abstaining on
  self-contradiction, instead of acting on an obsolete model or re-routing to
  another stale window, reduces harmful TEST actions at checkpoints 2 and 4
  after an unannounced rule change, without collapsing into always-abstain,
  false-firing on stationary noise, or needing any privileged switch signal.
  Build Order Priority 1 (Independent Learning), item 4; handoff §8
  first-contact overconfidence / weak uncertainty calibration.
- **Candidate:** `FirstContactGuardMemory`
  (`developmental_ai/first_contact_onset_guard.py`) — acts through recent8
  exactly (a `RelationOutcomeMemory` fitted on the last 8 events only; no
  archive, no model selection, no displacement margin) plus a count-based
  contradiction gate on the acting model's own strict prequential predictions
  over the newest 4 events (each scored by a fit on the 8 events strictly
  before it): if ≥2 of the 4 newest reported outcomes were assigned
  probability < 0.125, abstain instead of acting. Below 12 events the gate is
  not evaluable. Separate optional learner; the default controller and all
  existing learners are untouched.
- **Branch and commits:** `developmental-ai/first-contact-onset-guard`
  (forked from `developmental-ai/early-post-switch-adaptation` @ `edd371f`,
  itself forked from `developmental-ai/standalone-policy-review` @ `6e0cac5`).
  Protocol frozen at `625d4ab`; implementation at `fb2695f`; evaluation at
  `0cdd40d`. This grading report is committed on top of the evaluation commit.
- **Frozen protocol:** `benchmarks/first_contact_onset_guard_protocol.json`
  (schema `developmental-ai.first-contact-onset-guard-protocol/v1`, frozen
  2026-10-28, before any implementation, unit test, harness, or score
  inspection for this experiment).
- **Cohorts:** development 302003/302021/302039 and additional
  303001/303017/303041 — NEW at freeze, disjointness verified by project-wide
  search before the freeze commit. Both cohorts are now **INSPECTED** and must
  never be re-tuned against. Detailed results:
  `benchmarks/first_contact_onset_guard_results.json` (development) and
  `benchmarks/first_contact_onset_guard_additional_results.json` (additional).
- **Simulator:** `StochasticWorld` unchanged (authored span-to-effect bands,
  two public numeric features). Schedule per seed: A → B1 (inverted) →
  return-A → B2 (inverted), plus a stationary A→A control arm. True outcomes
  flip with probability 1/8; TRAIN reports flip with probability 1/20. The
  learner sees only the public reported stream — no phase label, rule
  identity, or true outcome. Checkpoints 0/2/4/8/16 for every stage; 48 TEST
  episodes per cohort cell (16 per seed, same indices re-scored at every
  checkpoint, never trained on). Checkpoint 0 is a reported diagnostic, NOT
  graded: at k=0 the stream contains zero post-switch events.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover -s tests`:
  851 tests OK in the evaluation stage, and 851 tests OK again in this grading
  stage (run this pass; the grading-stage changes are documentation only, no
  code changed). Focused candidate tests: 16/16 PASS in the implementation
  stage.
- Historical regressions: **PASS** — `python -m benchmarks.transfer_benchmark`
  (unchanged) exited 0 with its standard three-seed output in the evaluation
  stage, and exited 0 again when re-run in this grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts were run
  with no change to any frozen parameter, threshold, seed, or checkpoint.
  Every checkpoint entry carries the candidate's gate record (four prequential
  probabilities, contradiction count, abstained flag, gate-evaluable flag),
  a checkpoint SHA256, and restore-replay identity verified true at every
  checkpoint in both cohorts (script-verified in this grading stage; no
  criterion-5 field missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the evaluation
  or grading commit was checked; no CI is claimed for `0cdd40d` or for this
  grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results in
this grading stage, not hand-copied. Denominators are exact episode counts
(48 per stage-checkpoint cell).

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 1 | Onset harm reduction (pooled k=2,4 harm ≤75% of recent8; ≤1 cell worse) | **FAIL** | **FAIL** |
| 2 | Gate non-vacuous at onset (≥48/288 pooled onset abstentions) | **FAIL** | **FAIL** |
| 3 | Release/productivity by k=8 (abstentions ≤36/144; successes ≥ recent8 −8) | **PASS** | **PASS** |
| 4 | Stationary control selectivity (abstentions ≤16/192; successes ≥ recent8 −4; harm ≤ recent8) | **PASS** | **PASS** |
| 5 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 1 — onset harm reduction (FAIL, both cohorts)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate harm **260**
vs recent8 **260** — the required ceiling was ≤ 0.75 × 260 = **195**. The
candidate is identical to recent8 in every onset cell (B1-2 41, B1-4 47,
return-A-2 46, return-A-4 44, B2-2 42, B2-4 40). Part (b) passes (0 of 6 cells
worse than recent8) only because the candidate never differs from recent8 at
all; part (a) fails outright.
Additional: candidate **206** vs recent8 **222** (ratio 0.928) — the required
ceiling was ≤ **166.5**. The entire reduction comes from a single cell,
return-A-4 (23 vs 39), where the gate fired for one seed; the other five
onset cells are identical to recent8. Part (b) passes (0 of 6 cells worse);
part (a) fails on both cohorts.

### Criterion 2 — gate non-vacuous at onset (FAIL, both cohorts)

Development: candidate onset abstentions **0/288** — the gate fired at **0 of
18** onset seed-checkpoints. Additional: **16/288**, from exactly **one**
firing onset seed-checkpoint (seed 303017, return-A-4, contradiction count 2,
probabilities [0.333333, 0.090909, 0.818182, 0.066667]). The requirement was
≥48/288 (at least 3 of 18 onset states). This is the same failure shape as the
preceding experiment's adequacy gate, which also never fired at onset: a gate
that does not fire cannot claim onset protection, regardless of harm figures.

### Criterion 3 — release and productivity by checkpoint 8 (PASS, both cohorts)

Development: k=8 abstentions **0/144**, successes **63** vs recent8 63
(required ≥ 55). Additional: abstentions **0/144**, successes **82** vs
recent8 82 (required ≥ 74). The criterion passes on both cohorts — but
trivially: the gate never fired at k=8 either, so the candidate's k=8
productivity is recent8's own, not evidence of release *after* abstention.
There was essentially no abstention to release from.

### Criterion 4 — stationary control selectivity (PASS, both cohorts)

Development: graded control checkpoints (2, 4, 8, 16) abstentions **0/192**,
successes **132** = recent8 132, harm **60** = recent8 60. Additional:
abstentions **0/192**, successes **62** = recent8 62, harm **130** = recent8
130. The criterion passes as frozen on both cohorts — again largely
vacuously, because the gate fired 0 times at the graded control checkpoints.
One honest qualification: at the *ungraded* control checkpoint 0 in the
additional cohort the gate **did** fire (seed 303017; 16 abstentions, harm 12
vs recent8 23, successes 20 vs 25) — on a stream containing no rule change at
all. Checkpoint 0 is diagnostic-only under the protocol, so this does not
change the grade, but it is direct evidence the gate can fire on stationary
noise while not firing on genuine switch evidence (see diagnosis).

### Criterion 5 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions, actual
harmful / productive / neutral outcomes, reported harmful, and label flips
for every stage; per-method successes / harmful TEST actions / abstentions /
attempted tasks at every checkpoint; the candidate's recorded gate decision
(the four prequential probabilities, contradiction count, abstained flag,
gate-evaluable flag, acting source) at every checkpoint; checkpoint SHA256;
and restore-replay identity (true at every checkpoint in both cohorts,
script-verified in this stage). Learner information-acquisition actions = 0
and additional requested observations = 0 throughout, as frozen.

## Learning evaluation

Candidate vs recent8 (successes / harmful TEST actions / abstentions, 48
episodes per cell). The candidate equals recent8 in every cell except the two
additional-cohort cells noted.

| Stage-ckpt | Dev candidate | Dev recent8 | Add candidate | Add recent8 |
| --- | --- | --- | --- | --- |
| B1-0 † | 0 / 48 / 0 | 0 / 48 / 0 | 0 / 32 / 16 | 1 / 47 / 0 |
| B1-2 | 7 / 41 / 0 | 7 / 41 / 0 | 12 / 36 / 0 | 12 / 36 / 0 |
| B1-4 | 1 / 47 / 0 | 1 / 47 / 0 | 15 / 33 / 0 | 15 / 33 / 0 |
| B1-8 | 27 / 21 / 0 | 27 / 21 / 0 | 31 / 17 / 0 | 31 / 17 / 0 |
| B1-16 | 18 / 30 / 0 | 18 / 30 / 0 | 27 / 21 / 0 | 27 / 21 / 0 |
| return-A-0 † | 0 / 48 / 0 | 0 / 48 / 0 | 3 / 45 / 0 | 3 / 45 / 0 |
| return-A-2 | 2 / 46 / 0 | 2 / 46 / 0 | 9 / 39 / 0 | 9 / 39 / 0 |
| return-A-4 | 4 / 44 / 0 | 4 / 44 / 0 | 9 / 23 / 16 | 9 / 39 / 0 |
| return-A-8 | 12 / 36 / 0 | 12 / 36 / 0 | 16 / 32 / 0 | 16 / 32 / 0 |
| return-A-16 | 20 / 28 / 0 | 20 / 28 / 0 | 17 / 31 / 0 | 17 / 31 / 0 |
| B2-0 † | 0 / 48 / 0 | 0 / 48 / 0 | 3 / 45 / 0 | 3 / 45 / 0 |
| B2-2 | 6 / 42 / 0 | 6 / 42 / 0 | 2 / 46 / 0 | 2 / 46 / 0 |
| B2-4 | 8 / 40 / 0 | 8 / 40 / 0 | 19 / 29 / 0 | 19 / 29 / 0 |
| B2-8 | 24 / 24 / 0 | 24 / 24 / 0 | 35 / 13 / 0 | 35 / 13 / 0 |
| B2-16 | 31 / 17 / 0 | 31 / 17 / 0 | 38 / 10 / 0 | 38 / 10 / 0 |
| control-0 † | 28 / 20 / 0 | 28 / 20 / 0 | 20 / 12 / 16 | 25 / 23 / 0 |
| control-2 | 35 / 13 / 0 | 35 / 13 / 0 | 11 / 37 / 0 | 11 / 37 / 0 |
| control-4 | 28 / 20 / 0 | 28 / 20 / 0 | 19 / 29 / 0 | 19 / 29 / 0 |
| control-8 | 36 / 12 / 0 | 36 / 12 / 0 | 15 / 33 / 0 | 15 / 33 / 0 |
| control-16 | 33 / 15 / 0 | 33 / 15 / 0 | 17 / 31 / 0 | 17 / 31 / 0 |

† Checkpoint 0 is a reported diagnostic, not graded (zero post-switch events
in the stream at k=0 for the switch stages).

Reference points: the preceding experiment's candidate
(`gated_archive_prequential`) pooled onset harm was 259 (development) and 236
(additional) with 0 onset abstentions on development and 16 on additional —
the same near-silence. frozen_A scores 37 (development) / 36 (additional)
successes at both return-A-2 and return-A-4 — retained knowledge the
candidate's abstention policy does not recover (candidate return-A onset
successes: 2/4 development, 9/9 additional, identical to recent8 except the
one abstaining cell, which kept recent8's 9 successes while avoiding 16
harm actions). The privileged expected oracle (knows the expected hidden
rule, not the realized stochastic flip; a reference only, never a baseline)
pooled onset successes/harm were 190/98 (development) and 172/116
(additional) — onset tasks are largely solvable; the candidate is nowhere
near that, because it behaves as recent8.

**Mechanism diagnosis (from the recorded gate records, not new tuning):**
the signal itself is absent, not merely the threshold. Across both cohorts'
36 onset seed-checkpoints, the contradiction count was **0 in 28, 1 in 7, and
2 in 1**; only **9 of 144** onset prequential probabilities fell below the
0.125 floor (development 4/72, additional 5/72). A `RelationOutcomeMemory`
fitted on 8 sparse events assigns middling probabilities (≈0.33) even to
genuinely reversed outcomes, so the acting model's own predictions barely
register the switch in the first 2–4 events. The gate fired exactly 3 times
in the additional cohort and 0 times in development; all 3 firings were seed
303017, and 2 of the 3 (B1-0, control-0) occurred on streams with **no rule
change yet** — the gate's only non-onset firings were false-fires on
pre-switch noise, while 35 of 36 genuine onset states produced no response.
Two different abstention triggers (mean log-score in the preceding
experiment, contradiction count here) have now failed the same way: gating
on the sparse recent-window model's own predictive probabilities does not
yield a usable onset signal in this simulator.

**Generalization level:** at most handoff level 2–3 (choosing among /
applying already-supplied representations under a rule change, plus a
designer-supplied abstention rule). The A/B rules, span statistic, acting
window, and gate thresholds are all designer-supplied. No level-6 or
novel-representation claim is made.

## Safety and evidence costs

- **Harmful TEST actions:** reported per checkpoint above; the headline is
  that onset harm is unchanged from recent8 — pooled onset harm 260/288
  episode-checkpoints (development) and 206/288 (additional), with k=0
  diagnostic harm 48/48 at every switch stage in development and 32–45/48 in
  additional.
- **Actual harmful TRAIN-acquisition actions** (external actor, counted once
  per seed, never netted against TEST results): development — A 226, B1 79,
  return-A 54, B2 78 harmful of 1,248 main-schedule actions (plus control
  continuation 71 of 192); additional — A 240, B1 84, return-A 57, B2 76 of
  1,248 (plus control 59 of 192). Label flips in the reported stream:
  development 40 (main) + 10 (control); additional 42 (main) + 9 (control).
- **Failed-by-abstention:** candidate 0 at every graded checkpoint in
  development; in additional, 16 at return-A-4 (the one onset firing) plus 16
  at each of the ungraded B1-0 and control-0 diagnostics — all from seed
  303017. The always-abstain baseline is 48/48 abstentions with 0 successes
  and 0 harm at every checkpoint, as registered.
- **Additional requested observations / learner acquisition actions:** 0 / 0,
  exactly as frozen.
- **False confidence and unnecessary abstention:** false confidence remains
  the dominant failure — the candidate acted on the obsolete recent8 model at
  35 of 36 onset states. Unnecessary abstention is nearly absent at graded
  checkpoints, but the gate's only stationary-stream firing (control-0,
  additional) shows its rare firings are not selective for real changes.
- **Report integrity / provenance:** checkpoint SHA256 replay identity held
  at every checkpoint in both cohorts; hashes validate record integrity only,
  not the truth of the (deliberately corrupted) public reports.

## Scientific conclusion

**Failed.**

Per the protocol's own grading definitions: the conclusion is **Failed**
because criteria 1 and 2 FAIL on the additional cohort (they also fail on
development). It is **not** a Regression under the protocol's definition:
pooled onset harm does not exceed recent8 on both cohorts (equal on
development, lower on additional), stationary-control successes do not fall
below recent8 by more than 4 on either cohort (identical), and the full unit
suite and historical transfer benchmark pass. It is not Demonstrated or
Partially demonstrated under any reading of the frozen definitions
(Partially demonstrated requires criteria 1, 2, and 5 to PASS on both
cohorts).

What the experiment genuinely establishes, negatively: abstention as the
response was not the missing piece — the *detection signal* is. A
count-based contradiction gate on the acting model's own strict prequential
probabilities is silent at genuine onsets (1 firing in 36 onset states)
because sparse 8-event fits assign non-extreme probabilities to reversed
outcomes. Combined with the preceding experiment, both abstention triggers
tried so far — mean prequential log-score and contradiction count, both
derived from the same sparse model's probabilities — fail to fire when it
matters. The one firing that did occur at an onset (return-A-4, additional)
worked exactly as designed (harm 23 vs 39 at no success cost), which shows
the abstention *response* is sound when the signal exists; the signal is
what does not exist.

No frozen parameter, threshold, seed, or checkpoint is changed in response
to these results. Any revised hypothesis gets a NEW protocol and NEW seeds.

## Next limitation (selected for the next cycle)

**P1/P2 — the acting model's own predictive probabilities carry almost no
onset signal: at switch onsets the sparse recent-window model's prequential
probabilities for genuinely reversed outcomes fall below the 0.125 noise
floor in only 9 of 144 scoring events (contradiction count 0 in 28 of 36
onset states), so any gate derived from those probabilities — log-score or
count — is structurally silent at first contact.** Measurable form for the
next protocol: whether a change signal computed from the observed evidence
itself (not from the acting model's assigned probabilities) can separate
switch onsets from stationary noise — measured as onset-vs-stationary
signal separation and downstream harm/abstention behavior at checkpoints
2 and 4, against recent8 and an always-abstain control, on NEW seed
cohorts. This stays inside Priority 1 item 4 (adaptation to changing
environments) and Priority 2 item 8 (recognize when existing knowledge is
insufficient; handoff §8 weak uncertainty calibration), and does not
re-tune any parameter of this or the preceding experiment.

## Reproduction

```bash
python -m unittest discover -s tests
python -m benchmarks.transfer_benchmark
python -m benchmarks.first_contact_onset_guard_benchmark --cohort development
python -m benchmarks.first_contact_onset_guard_benchmark --cohort additional
```

Re-running the benchmark cohorts reproduces the inspected results above; it
does not make the seeds un-inspected.
