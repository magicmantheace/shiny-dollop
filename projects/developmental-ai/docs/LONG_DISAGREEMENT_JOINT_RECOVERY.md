# Long disagreement joint recovery — disagreement-age recovery authority

**31 October 2026 (graded 1 November 2026). Status: optional, simulated,
unpromoted. No default-controller promotion, no PR merge, no D1–D10 or
V2A/V2B roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `long_disagreement_joint_recovery` — whether a
  third recovery-authority leg based on disagreement AGE (the preceding
  26-event window also disagreeing with the archive under the same
  strict-majority span machinery) can restore return-A recovery
  engagement starved by the graded bounded candidate's corroboration leg
  (recent_concordant_count >= 2 among the last 8), which is structurally
  weakest at checkpoint 2, while still expiring late. This tests the
  limitation selected after the bounded-authority experiment was graded
  Failed: return-onset authority starvation. Build Order Priority 1
  (Independent Learning), items 2 + 3 + 4; handoff §8 slow or incorrect
  recovery of old knowledge. The protocol's PRIMARY criterion is
  criterion 2 (recovery engagement restored and selective); criterion 5
  (release/productivity by k=32) is its co-graded guard. They are
  reported first and second below, as the protocol requires.
- **Candidate:** `LongDisagreementJointRecoveryMemory`
  (`developmental_ai/long_disagreement_joint_recovery.py`) — IDENTICAL
  to the graded `BoundedAuthorityJointRecoveryMemory` in acting model
  (recent8 exactly), immediate evidence-opposition signal (newest 2 vs
  24-event reference, opposed_count), retained archive
  (events[:N-26]), per-event archive concordance, joint recovery test
  (joint_count >= 1), archive-only recovery model, abstention trigger
  (opposed_count == 2), abstention authority (armed iff NOT
  stable_disagreement), and the first two recovery-authority legs
  (armed iff NOT stable_disagreement OR recent_concordant_count >= 2).
  The SINGLE changed element is a third recovery-authority leg: LONG
  DISAGREEMENT — the preceding window (the 26 events immediately before
  the local window, events[max(0,N-52):N-26]) is compared to the SAME
  archive with the SAME strict-majority span machinery;
  preceding_stable_disagreement iff C2 >= 1 AND D2 * 2 > C2;
  long_disagreement iff stable_disagreement AND
  preceding_stable_disagreement; RECOVERY is armed iff NOT
  stable_disagreement OR recent_concordant_count >= 2 OR
  long_disagreement. The decision record's recovery_arming_leg label
  reports `long` with precedence over `corroboration` (a label only;
  arming is the plain OR). Minimum 27 events, else an all-available
  fallback (never exercised in evaluation). Separate optional learner;
  the default controller and all existing learners are untouched; the
  graded guard, retained-recovery, joint, and bounded-authority
  candidates appear only as baselines.
- **Branch and commits:** `developmental-ai/long-disagreement-joint-recovery`
  (forked from `developmental-ai/bounded-authority-joint-recovery` @
  `e7fa5b6`). Protocol frozen at `b092f24`; implementation at `c005dbe`;
  evaluation at `1579e45`. This grading report is committed on top of
  the evaluation commit.
- **Frozen protocol:** `benchmarks/long_disagreement_joint_recovery_protocol.json`
  (schema `developmental-ai.long-disagreement-joint-recovery-protocol/v1`,
  frozen 2026-10-31, before any implementation, unit test, harness, or
  score inspection for this experiment).
- **Cohorts:** development 352003/352021/352039 and additional
  353001/353017/353041 — NEW at freeze, disjointness verified by
  project-wide search before the freeze commit. Both cohorts are now
  **INSPECTED** and must never be re-tuned against. Detailed results:
  `benchmarks/long_disagreement_joint_recovery_results.json`
  (development) and
  `benchmarks/long_disagreement_joint_recovery_additional_results.json`
  (additional).
- **Simulator:** `StochasticWorld` unchanged. Schedule per seed: A →
  B1 (inverted) → return-A → B2 (inverted), plus a stationary A→A
  control arm. True outcomes flip with probability 1/8; TRAIN reports
  flip with probability 1/20. The learner sees only the public reported
  stream — no phase label, rule identity, or true outcome. Checkpoints
  0/2/4/8/16/32 for every stage; 48 TEST episodes per cohort cell (16
  per seed, same indices re-scored at every checkpoint, never trained
  on). Checkpoint 0 is a reported diagnostic, NOT graded.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover -s
  tests`: 969 tests OK in the implementation stage, 969 tests OK in the
  evaluation stage, and 969 tests OK again in this grading stage (run
  this pass; the grading-stage changes are documentation only, no code
  changed). Focused candidate tests: 25/25 PASS in the implementation
  stage.
- Historical regressions: **PASS** — `python -m
  benchmarks.transfer_benchmark` (unchanged) exited 0 in the evaluation
  stage, and exited 0 again when re-run in this grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts
  were run with no change to any frozen parameter, threshold, seed, or
  checkpoint. Every checkpoint entry carries the candidate's full
  decision record (immediate signal records, archive concordance
  records, per-event joint flags/records, and the full authority record
  — expiry span records, comparable/disagreeing counts,
  stable_disagreement flag, preceding span records, preceding
  comparable/disagreeing counts, preceding stable flag,
  long_disagreement flag, recovery_arming_leg, per-event last-8
  archive-concordance records, recent_concordant_count, armed and
  would-fire flags — plus every count, branch, recovery-fired /
  abstained / gate-evaluable flags, acting source, and the records-only
  bounded-authority-rule and unexpired-joint-rule derivations), a
  checkpoint SHA256, and restore-replay identity verified true at every
  checkpoint in both cohorts (script-verified again in this grading
  stage; no criterion-7 field missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `1579e45` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results
in this grading stage, not hand-copied. Denominators are exact episode
counts (48 per stage-checkpoint cell; 96 per pooled return-A onset
figure; 288 per pooled all-stage onset figure); decision-record
denominators are seed-checkpoint states (6 per stage per cohort at
checkpoints 2 and 4; 9 switch-stage states per cohort at checkpoint
32). Criterion 2, this experiment's PRIMARY criterion, is reported
first and criterion 5 (release) second, as the protocol requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 2 | PRIMARY recovery engagement restored and selective, from decision records alone (recovery TAKEN ≥4/6 return-A states, split by arming leg; ≤1/6 B1 states) | **PASS** | **FAIL** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 switch-stage k=32 states, from records) | **FAIL** | **PASS** |
| 1 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4; cumulative/joint/bounded reported, not graded) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **FAIL** |
| 4 | Return-A onset harm (≤ guard AND ≤60% of recent8, pooled k=2,4) | **FAIL** | **FAIL** |
| 6 | Stationary control selectivity (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 2 (PRIMARY) — recovery engagement restored and selective (PASS development, FAIL additional)

Development: recovery was TAKEN at **4 of 6** return-A onset states —
exactly the required ≥ 4, the low edge of the design interval — and at
**0 of 6** B1 onset states (required ≤ 1). Additional: recovery was
TAKEN at only **3 of 6** return-A onset states — **FAIL** (required
≥ 4) — with B1 at **0 of 6** (passes). The records, however, overturn
the experiment's premise, and this report does not soften that:

- **The long leg changed no outcome on either cohort.** The
  candidate's scores are IDENTICAL to the
  `bounded_authority_joint_recovery` baseline at every checkpoint in
  both cohorts (**0 of 72** score diffs per cohort), its taken branch
  never differs from the records-only bounded-authority-rule derivation
  (**0** branch diffs), and would-fire-but-disarmed counts at return-A
  onset are **0 of 6** in both cohorts — the bounded rule never
  disarmed a joint state on these cohorts, so there was nothing for
  the long leg to restore.
- The long flag itself was set at **all 12** return-A onset states
  (6/6 per cohort), as designed. Every TAKEN state reports arming leg
  `long` (4 development, 3 additional) — but by the record's own
  reporting precedence that label masks the decisive fact: **every
  taken state was also armed by corroboration**
  (recent_concordant_count 2, 3, 2, 3 development; 2, 3, 2 additional —
  all ≥ 2). The long leg was never the sole arming leg at any taken
  state.
- Every NON-taken return-A state was **joint-silent**, not disarmed:
  joint_count == 0 in 2 of 6 development states and 3 of 6 additional
  states — in every case at k=2, with opposed_count == 0 in all five.
  Taken = 7 of 12 return-A states pooled; non-taken = 5 of 12, ALL at
  k=2 and ALL joint-silent. At k=2 recovery took in only 1 of 6 states
  across cohorts (seed 352039, development); at k=4 it took in 6 of 6.
  Engagement on these cohorts was therefore capped by the joint test's
  silence at the earliest checkpoint — not by authority. The graded
  bounded candidate's additional-cohort starvation (3 disarmed states
  at corroboration count exactly 1) did not recur on these cohorts at
  all.

So the PRIMARY criterion's development PASS is corroboration-leg luck
of exactly the kind the protocol warned against, and its additional
FAIL is a signal-absence failure, not an authority failure. The
disagreement-age hypothesis is **not supported as the binding
mechanism**: where the joint signal exists at a return, the existing
corroboration leg already arms recovery; where it does not exist
(k=2, opposed_count == 0), no authority condition of any age can engage
recovery, because the joint test itself is the gate.

### Criterion 5 — release and productivity by checkpoint 32 (FAIL development, PASS additional)

Development: k=32 abstentions **16/144** — (a) passes — successes
**33** vs recent8 **42** (required ≥ 34) — (b) **fails by 1** — and
from the decision records the candidate took a non-recent8 branch in
exactly **1 of 9** switch-stage k=32 states — (c) passes. The single
non-recent8 state is the whole story and it is an abstention, not a
recovery: at return-A k=32, seed 352003, the candidate abstained
(16 abstentions, 9 successes / 23 harm vs recent8's 18 / 30 in that
cell pooled — the state itself accounts for the pooled deficit).
Additional: abstentions **0/144**, successes **67** vs recent8 **73**
(required ≥ 65) — passes — non-recent8 branch in **1 of 9** states
(a retained_archive routing at B2 k=32, seed 353041). Against the
unexpired joint candidate on the same cohorts, k=32 pooled successes
are identical development (33 = 33) and better additional (67 vs 59).

### Criterion 1 — return-A recovery successes preserved (PASS, both cohorts)

Development: candidate pooled return-A (k=2,4) successes **38** against
frozen_A **54** — the 40% floor passes (38 × 5 = 190 ≥ 54 × 2 = 108) —
and against the guard-relative floor of guard + 16 = **19** (guard
scored 3) — passes. Additional: candidate **31** against frozen_A
**54** (floor passes: 155 ≥ 108) and guard + 16 = **16** (guard scored
0) — passes. Reported in full, as the protocol requires: plain
cumulative scored **65 / 62** return-A successes on the same cells —
nearly double the candidate's on both cohorts — and the joint and
bounded baselines scored exactly the candidate's **38 / 31** (identical
records, see criterion 2). Passing these floors does not soften the
gap to cumulative: at a return, cumulative needs no signal and no
authority to use retained knowledge, and on these cohorts it dominates
every gated variant at return-A on successes (65/62 vs 38/31) and harm
(31/34 vs 58/65).

### Criterion 3 — pooled onset harm not above the guard (PASS development, FAIL additional)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate harm
**198** vs guard **201** — (a) passes, by 3 — and candidate harm ≤
recent8 in **6 of 6** individual cells (required ≥ 5). Additional:
candidate **163** vs guard **162** — (a) **fails by 1 action** — with
**6 of 6** cells ≤ recent8 (vs recent8 pooled 239). A one-action
margin is a fail under the frozen rule and is recorded as such; no
threshold is adjusted after inspection.

### Criterion 4 — return-A onset harm (FAIL, both cohorts)

Development: pooled return-A harm candidate **58** vs guard **61** —
(a) passes — but vs recent8 **93** the 60% ceiling is 55.8 — (b)
**fails** by 2.2 actions. Additional: candidate **65** vs guard **64**
— (a) **fails by 1** — and vs recent8 **95** the ceiling is 57.0 —
(b) **fails** by 8. The mechanism is the criterion-2 finding: the
non-taken return-A states are all at k=2, joint-silent with
opposed_count == 0, so neither recovery NOR the guard's abstention
trigger (opposed_count == 2) can fire there; those states act through
stale recent8 at near-maximal harm (return-A k=2 cell harm 40
development / 48 additional, per 48-episode cell — additional k=2 is
0 successes / 48 harm across all three seeds). The
harm is concentrated exactly where the signal is absent.

### Criterion 6 — stationary control downstream selectivity (PASS, both cohorts)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32)
abstentions **0/240**, successes **134** vs recent8 129 (required
≥ 123), harm **106** vs recent8 111. Recovery engaged at 2 of 15
graded control states (both armed by the no-stable-disagreement leg;
long flag 0/15, as designed on stationary evidence) without downstream
cost. Additional: abstentions **0/240**, successes **121** = recent8
121, harm **119** = recent8 119; recovery engaged at 0 of 15 graded
control states — downstream-identical to recent8 on the stationary
arm.

### Criterion 7 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions, actual
harmful / productive / neutral outcomes, reported harmful, and label
flips for every stage; per-method successes / harmful TEST actions /
abstentions / attempted tasks at every checkpoint; the candidate's full
decision record (per-event immediate signal records, archive
concordance records, per-event joint flags/records, and the full
authority record — expiry span records with comparable/disagreeing
counts and stable_disagreement flag, preceding span records with
preceding comparable/disagreeing counts and preceding stable flag,
long_disagreement flag, recovery_arming_leg, per-event last-8
archive-concordance records, recent_concordant_count, recovery /
abstention armed and would-fire flags — plus every count, branch,
recovery-fired / abstained / gate-evaluable flags, acting source, and
the records-only bounded-authority-rule and unexpired-joint-rule
derivations) at every checkpoint; checkpoint SHA256; and
restore-replay identity (true at every checkpoint in both cohorts,
script-verified in this stage — no field missing anywhere). Learner
information-acquisition actions = 0, additional requested observations
= 0, and learner training actions = 0 throughout, as frozen.

## Learning evaluation

Candidate vs recent8 (successes / harmful TEST actions / abstentions,
48 episodes per cell).

| Stage-ckpt | Dev candidate | Dev recent8 | Add candidate | Add recent8 |
| --- | --- | --- | --- | --- |
| B1-0 † | 1 / 47 / 0 | 1 / 47 | 0 / 48 / 0 | 0 / 48 |
| B1-2 | 4 / 44 / 0 | 4 / 44 | 8 / 24 / 16 | 10 / 38 |
| B1-4 | 5 / 43 / 0 | 5 / 43 | 8 / 24 / 16 | 15 / 33 |
| B1-8 | 17 / 15 / 16 | 19 / 29 | 23 / 25 / 0 | 31 / 17 |
| B1-16 | 35 / 13 / 0 | 35 / 13 | 27 / 21 / 0 | 27 / 21 |
| B1-32 | 20 / 28 / 0 | 20 / 28 | 29 / 19 / 0 | 29 / 19 |
| return-A-0 † | 1 / 47 / 0 | 1 / 47 | 0 / 48 / 0 | 0 / 48 |
| return-A-2 | 8 / 40 / 0 | 0 / 48 | 0 / 48 / 0 | 0 / 48 |
| return-A-4 | 30 / 18 / 0 | 3 / 45 | 31 / 17 / 0 | 1 / 47 |
| return-A-8 | 26 / 22 / 0 | 13 / 35 | 25 / 23 / 0 | 26 / 22 |
| return-A-16 | 26 / 22 / 0 | 17 / 31 | 23 / 25 / 0 | 21 / 27 |
| return-A-32 | 9 / 23 / 16 | 18 / 30 | 18 / 30 / 0 | 18 / 30 |
| B2-0 † | 1 / 47 / 0 | 1 / 47 | 0 / 48 / 0 | 0 / 48 |
| B2-2 | 0 / 32 / 16 | 0 / 48 | 1 / 15 / 32 | 10 / 38 |
| B2-4 | 11 / 21 / 16 | 15 / 33 | 13 / 35 / 0 | 13 / 35 |
| B2-8 | 22 / 26 / 0 | 22 / 26 | 31 / 17 / 0 | 31 / 17 |
| B2-16 | 18 / 30 / 0 | 18 / 30 | 12 / 36 / 0 | 12 / 36 |
| B2-32 | 4 / 44 / 0 | 4 / 44 | 20 / 28 / 0 | 26 / 22 |
| control-0 † | 29 / 19 / 0 | 29 / 19 | 22 / 26 / 0 | 22 / 26 |
| control-2 | 29 / 19 / 0 | 29 / 19 | 23 / 25 / 0 | 23 / 25 |
| control-4 | 32 / 16 / 0 | 27 / 21 | 28 / 20 / 0 | 28 / 20 |
| control-8 | 24 / 24 / 0 | 24 / 24 | 25 / 23 / 0 | 25 / 23 |
| control-16 | 27 / 21 / 0 | 27 / 21 | 22 / 26 / 0 | 22 / 26 |
| control-32 | 22 / 26 / 0 | 22 / 26 | 23 / 25 / 0 | 23 / 25 |

† Checkpoint 0 is a reported diagnostic, not graded. k=0 harm is
47–48 of 48 per switch stage across cohorts and methods.

Reference points on the same cohorts (pooled onset, k=2,4, all stages;
successes / harm / abstentions): the decisive authority comparison
`bounded_authority_joint_recovery` (identical but for the long leg)
scored **58/198/32** (development) and **61/163/64** (additional) —
numerically identical to the candidate at every checkpoint, as
established under criterion 2. The unexpired
`joint_concordance_recovery` baseline scored the same pooled onset
totals and the same return-A totals (38/58 and 31/65) on these cohorts.
The harm comparator `evidence_opposition_guard` scored 23/201/64
(development) and 30/162/96 (additional) pooled onset. `cumulative`
scored return-A pooled successes **65 / 62** at return-A harm
**31 / 34** — dominating every gated variant at return-A on both axes
on both cohorts. `frozen_A` scored return-A **54 / 54** successes at
**42 / 42** harm. The privileged expected oracle pooled onset
successes/harm were 200/88 (development) and 184/104 (additional):
onset tasks remain largely solvable, and every realizable learner here
remains far from that.

**Retention note:** three successive authority designs (unexpired,
bounded, long-disagreement) now produce identical return-A behavior on
these cohorts, because the binding constraint has moved upstream of
authority entirely: at k=2 after a return, the newest-2 window carries
a joint event in only 1 of 6 states across cohorts, and opposed_count
is 0 in the other 5 — there is no signal for any authority condition
to act on. By k=4 the signal is present in 6 of 6 states and recovery
takes in 6 of 6. The recovery problem at the earliest checkpoint is
now a *signal-presence* problem, not an authority problem.

**Generalization level:** at most handoff level 2–3 (choosing among /
applying already-supplied representations under a rule change, plus
designer-supplied signal, concordance, routing, expiry, and
disagreement-age rules). No level-6 or novel-representation claim is
made. Nothing in this experiment speaks to general regime
identification: the archive is global and unsegmented, B2 recovery was
pre-registered as not expected (and did not occur at onset in either
cohort), and returns after intervening segments shorter than 52 events
are outside the long leg's scope.

## Safety and evidence costs

- **Harmful TEST actions:** reported per checkpoint above; pooled
  onset harm 198 (development) and 163 (additional) vs recent8
  261 / 239 and vs the guard 201 / 162. The pooled figures conceal the
  return-A k=2 concentration: 40 / 48 harm there, where the signal is
  absent and no branch can fire.
- **Actual harmful TRAIN-acquisition actions** (external actor, counted
  once per seed, never netted against TEST results): development — A
  249, B1 73, return-A 45, B2 74 harmful of 1,248 main-schedule actions
  (plus control continuation 70 of 192); additional — A 260, B1 85,
  return-A 41, B2 85 of 1,248 (plus control 64 of 192). Label flips in
  the reported stream: development 45 (main) + 7 (control); additional
  50 (main) + 7 (control).
- **Failed-by-abstention:** candidate onset abstentions 32/288
  (development) and 64/288 (additional); k=32 abstentions 16/144
  (development, the single return-A state under criterion 5) and 0/144
  (additional); graded stationary control abstentions 0/240 on both
  cohorts. The always-abstain baseline is 48/48 abstentions with 0
  successes and 0 harm at every checkpoint, as registered.
- **Additional requested observations / learner acquisition actions:**
  0 / 0, exactly as frozen.
- **False confidence and unnecessary abstention:** false recovery at
  B1 — the pre-registered dangerous direction — occurred at 0 of 6
  states on both cohorts, and B2 recovery never engaged at onset. The
  dominant error is neither false confidence nor false expiry but
  *signal absence*: at return-A k=2 the joint and opposition signals
  are both zero in 5 of 6 states across cohorts, so the learner acts
  through stale recent8 by default at near-maximal harm, with no
  recorded basis on which any gate of this family could have done
  otherwise.
- **Report integrity / provenance:** checkpoint SHA256 replay identity
  held at every checkpoint in both cohorts; hashes validate record
  integrity only, not the truth of the (deliberately corrupted) public
  reports.

## Scientific conclusion

**Failed** — per the protocol's own grading definitions: the PRIMARY
criterion 2 FAILs on the additional cohort (3/6 taken vs ≥4 required),
and criteria 3 and 4 also FAIL on the additional cohort (criterion 4
FAILs on both), which is the protocol's Failed condition. It is **not**
a Regression under any clause of the protocol's definition: pooled
onset harm does not exceed recent8's on either cohort (198 < 261;
163 < 239), stationary-control successes do not fall below recent8's
(134 > 129; 121 = 121), checkpoint-32 successes stay above the graded
bounded candidate's worse-cohort deficit line (33 ≥ 42 − 13 = 29;
67 ≥ 73 − 13 = 60), and the full unit suite and historical transfer
benchmark pass.

The experiment's decisive finding is a null result about its own
mechanism, recorded as prominently as any success: **the long
disagreement leg never changed a single outcome.** On these cohorts
the bounded candidate's starvation failure did not recur — there were
zero would-fire-but-disarmed return-A states — the long flag was set
at all 12 return-A onset states, and every taken state was already
armed by corroboration. The disagreement-age hypothesis therefore
receives no support as the binding mechanism, and the development
cohort's PRIMARY-criterion PASS is explicitly NOT credited to it.
What actually capped engagement — and return-A harm — on both cohorts
is upstream: at k=2 after a return, the newest-2 evidence window is
joint-silent with opposed_count == 0 in 5 of 6 states, so neither
recovery, nor abstention, nor any authority variant of this gate
family can fire. Three authority designs in a row have now converged
to identical behavior because authority is no longer the constraint.

No frozen parameter, threshold, seed, or checkpoint is changed in
response to these results. Any revised hypothesis gets a NEW protocol
and NEW seeds.

## Next limitation (selected for the next cycle)

**P1 — return-onset signal absence at the earliest checkpoint: at
return-A checkpoint 2, the newest-2 evidence window carries no usable
onset signal in 5 of 6 states across both graded cohorts
(joint_count == 0 AND opposed_count == 0 in every non-taken state), so
recovery engagement is capped at 4/6 and 3/6 pooled regardless of the
authority condition, return-A k=2 harm runs at 40/48 (development) and
48/48 (additional) through stale recent8, and return-A harm fails its
ceiling on both cohorts — while at k=4 the same signals are present in
6 of 6 states and recovery engages.** Measurable form for the next
protocol: on NEW seed cohorts, whether an onset signal computed over a
window or evidence summary that is actually populated at k=2 (rather
than the newest-2 joint/opposition counts, which are structurally
empty there) can engage recovery or abstention at return-A checkpoint
2 without false engagement at B1/B2 onset or on stationary evidence —
vs recent8, cumulative, frozen_A, the evidence-opposition guard, and
the joint / bounded / long-disagreement candidates as baselines. This
stays inside Priority 1 items 2, 3, and 4 (joined to handoff §8 weak
uncertainty calibration / first-contact overconfidence) and does not
re-tune any parameter of the eight graded onset experiments against
their inspected cohorts; the revised hypothesis gets its own frozen
protocol and NEW seeds. (Secondary, recorded but not selected: the
development k=32 criterion-5 failure by a single success, caused by
one late abstention state at return-A k=32 seed 352003; the additional
B2 k=32 retained_archive routing in 1/9 states; and cumulative's
continued dominance of every gated variant at return-A — 65/62
successes at 31/34 harm — which remains the standing challenge any
gated recovery must eventually answer.)

## Reproduction

```bash
python -m unittest discover -s tests
python -m benchmarks.transfer_benchmark
python -m benchmarks.long_disagreement_joint_recovery_benchmark --cohort development
python -m benchmarks.long_disagreement_joint_recovery_benchmark --cohort additional
```

Re-running the benchmark cohorts reproduces the inspected results
above; it does not make the seeds un-inspected.
