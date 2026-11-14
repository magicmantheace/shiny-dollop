# Partial-scoped support abstention recovery — leg S scoped to the partial trigger class

**13 November 2026 protocol frozen; 13 November 2026
implementation; 13 November 2026 evaluation; graded 14 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `partial_scoped_support_abstention_recovery`
  — whether ONE changed element, the SCOPING of leg S to the
  partial trigger class (the full gate becomes leg P alone,
  exactly the graded singleton candidate's full gate; the partial
  gate stays leg P AND (leg R OR leg C) AND leg S at
  support_threshold 1, carried unchanged;
  abstention_disarmed_by_support live for partial triggers only
  and false at full states by construction; no new numeric value
  and no new decision-record field), can hold criterion 9's frozen
  B1 form on BOTH cohorts — the stationary-support grading's
  selected limitation (criterion 9 FAILed development on
  sub-condition (a) alone in that cycle — TAKEN 2/6 against the
  decisive baseline's 5/6, harm passing both comparisons —
  entirely through leg S's three B1 disarmings, two of them FULL
  triggers the scoping restores by construction; additional
  passed only at the floor, 3/6, after two more disarmings, one
  of them full) — while holding stationary selectivity (criteria
  19/6, PASSing both in that cycle as a carried profile),
  checkpoint-32 release (criteria 18/5), B2 protection
  (criterion 1), and return-A profiles (criteria 17/4/2) as
  co-graded guards. Leg P, leg R, leg C, leg T, leg W, leg N,
  and leg D were explicitly NOT re-tuned. Build Order Priority
  1 (Independent Learning); handoff §8 excessive abstention /
  weak uncertainty calibration. This protocol's PRIMARY
  criterion is criterion 20, criterion 9's frozen B1 form
  promoted to PRIMARY; criteria 9, 19, 6, 18, 5, 1, 11, 17, 4,
  2, 3, and 7 are its co-graded guards. The protocol also froze
  TWO grading caps: a Demonstrated verdict requires (i) at
  least one graded B1 state in at least one cohort at which the
  decisive baseline took a recent8 action through leg S's
  disarming of a FULL trigger while the candidate took the
  abstention (a restored full zero-support taking), AND (ii)
  at least one graded control state in at least one cohort at
  which the decisive baseline took an abstention with
  supporting_opposed_count == 0 on a PARTIAL trigger while the
  candidate acted through leg S's disarming (the preserved
  stationary partial test).
- **Candidate:** `PartialScopedSupportAbstentionRecoveryMemory`
  (`developmental_ai/partial_scoped_support_abstention_recovery.py`)
  — IDENTICAL to the graded
  `StationarySupportAbstentionRecoveryMemory` in every element
  (acting model recent8 exactly, extended signal, retained
  archive, archive concordance, joint test joint_count >= 1,
  recovery model, the full three-leg authority condition, the
  minority branch in full INCLUDING the inverted minority model
  and leg W on the minority branch, leg T on both recovery
  branches, leg N and leg D on the regular branch, leg P >=
  0.70, leg R and leg C on partial abstention triggers, the
  full / retained-partial abstention classes with the widened
  class removed records-only, singleton_release_fired carried,
  support_threshold 1 carried) — verified by a diff against the
  graded stationary-support candidate at implementation: the
  ONLY code differences are the scoping (full gate leg P alone;
  partial gate unchanged; abstention_disarmed_by_support gained
  the explicit abstention_trigger_kind == "partial" condition),
  its docstring, and names/schema. Separate optional learner;
  the default controller and all existing learners are
  untouched; the graded stationary-support candidate appears
  only as the decisive baseline.
- **Branch and commits:**
  `developmental-ai/partial-scoped-support-abstention-recovery`
  (forked from `c12caeb`, the stationary-support grading
  commit). Protocol frozen at `ac14281` (BEFORE
  implementation); implementation at `6d65405`; evaluation at
  `b1f5c63`. This grading report is committed on top of the
  evaluation commit.
- **Frozen protocol:**
  `benchmarks/partial_scoped_support_abstention_recovery_protocol.json`
  (frozen 2026-11-13, before any implementation, unit test,
  harness, or score inspection for this experiment).
- **Cohorts:** development 542003/542021/542039 and additional
  543001/543017/543041 — NEW at freeze, verified disjoint from
  every earlier cohort. Both cohorts are now **INSPECTED** and
  must never be re-tuned against.
- **Decisive baseline:** `stationary_support_abstention_recovery`
  (identical but for the scoping; branch selection differs only
  at FULL abstention-trigger states with
  supporting_opposed_count == 0 and leg P passing, where the
  candidate abstains and the decisive baseline fell through to
  recent8). `recent8` is the simplest credible baseline and the
  candidate's own acting model.

## Verification

- Unit tests: PASS — 132/132 new candidate tests at
  implementation; full suite 2100 tests OK in the
  implementation and evaluation stages, and re-run in this
  grading stage: 2100 tests OK (`python3 -m unittest discover
  -s tests`, run 2026-11-14 this pass). The new tests include
  the discriminating states: a full trigger at supporting 0
  and purity 1.0 the decisive stationary baseline disarms
  through leg S to recent8 and the candidate TAKES as an
  abstention through leg P alone (abstention_disarmed_by_support
  false by construction), and the partial zero-support triggers
  through leg C on which candidate and decisive baseline are
  disarmed identically.
- Historical regressions: PASS — historical transfer benchmark
  (`python3 -m benchmarks.transfer_benchmark`) exit 0 in the
  evaluation stage and re-run in this grading stage, standard
  three-seed output (success gains 0.5567 / 0.50 / 0.51 on
  seeds 17 / 23 / 41).
- Frozen cohorts: PASS (run exactly as registered) — both
  cohorts evaluated at `b1f5c63`; every checkpoint entry
  carries per-method successes / harmful TEST actions /
  abstentions, the candidate's full decision record (including
  the full support, singleton, newest-breadth, acting-breadth,
  companion, and stale records), checkpoint SHA256, and
  restore-replay identity (script-verified in this grading
  stage: true at every checkpoint in both cohorts, 72/72
  entries per cohort).
- Linux validation: UNVERIFIED (no GitHub Actions run on the
  grading commit was checked; no CI is claimed).
- Windows validation: UNVERIFIED (same).

## Per-criterion grading (precommitted, graded individually, per cohort)

Graded script-computed from the saved detailed results at
`b1f5c63` (grading script and output kept with the campaign
records). PRIMARY criterion 20 first, then co-graded guards
9, 19, 6, 18, 5, 1, 11, 17, 4, 2, 3, 7. Development /
additional throughout.

The headline fact, stated before any criterion: **the
candidate is branch- and score-identical to the decisive
stationary-support baseline at ALL 72 checkpoints on BOTH
cohorts (0/72 score differences, zero branch differences).**
The scoping's designed population did not occur on these
draws: across both cohorts only TWO full zero-support states
occur at any checkpoint — development seed 542003 return-A
k=2 (a recovery branch fired, retained_archive, so no
abstention gate was reached) and additional seed 543041 B2
k=32 (abstention authority unarmed) — so no gated full
zero-support trigger was drawn and no full taking was
restored. Every per-criterion figure below is therefore the
decisive baseline's own figure on these cohorts, and every
PASS is a carried-profile pass. This is exactly the failure
mode the protocol pre-registered as possible.

**Criterion 20 — PRIMARY (first-switch B1 engagement,
criterion 9's frozen form): FAIL / FAIL.** Development FAILs
sub-condition (a) on both its halves: abstention TAKEN at
1/6 pooled B1 onset states against the >= 3 floor, and the
one taking is FULL (seed 542039 k=4, purity 0.854, supporting
1, 0/0 vs recent8 8/8), so the non-full credit is 0 against
>= 1. Harm passes both comparisons: 76 <= guard 76 (b) at
exact guard parity, and 76 < recent8 84 (c). Additional FAILs
(a) on the non-full half alone: TAKEN 3/6, at the count floor,
but ALL THREE takings are FULL (seed 543017 k=4, purity 0.921,
supporting 1; seed 543041 k=2, purity 0.865, supporting 1;
seed 543041 k=4, purity 0.816, supporting 3 — each 0/0), so
the non-full credit is again 0. Harm 47 <= guard 47 (b) at
exact guard parity and 47 < recent8 72 (c). The partial class
contributes ZERO taken B1 states on either cohort, and its
population is fully accounted: each cohort drew exactly three
partial B1 triggers — development: seed 542003 k=2 (purity
0.763, supporting 0, blocked by BOTH leg R and leg C —
preceding 0, companion concordant — recent8 0/16 under both
methods), seed 542021 k=2 (purity 0.824, supporting 0, through
leg C, disarmed by leg S, recent8 1/15 under both), seed
542039 k=2 (purity 0.829, supporting 0, through leg C,
disarmed by leg S, recent8 1/15 under both); additional: seed
543001 k=2 (purity 0.903, supporting 1, blocked by both
corroboration legs, recent8 0/16 under both), seed 543001 k=4
(purity 0.903, supporting 0, through leg C, disarmed by leg
S, recent8 0/16 under both), seed 543017 k=2 (purity 0.946,
supporting 0, through leg C, disarmed by leg S, recent8 1/15
under both). Every partial disarming is shared identically
with the decisive baseline — the scoping, by construction,
does not touch the partial gate — so on these draws the B1
failure is not the scoping's doing and not its repair: it is
the carried profile's B1 draw (one gated full trigger on
development, three on additional, all at supporting >= 1,
where leg S never applied even unscoped). B1 successes 4 vs
recent8 12 / guard 4 development; 1 vs recent8 24 / guard 1
additional, stated in full. **Grading cap (i) is NOT MET on
either cohort: zero restored full zero-support takings** —
the candidate took no B1 state the decisive baseline had
disarmed, because no such state was drawn.

**Criterion 9 — first-switch (B1) engagement (guard
position): FAIL / FAIL.** The same computation as PRIMARY
criterion 20, reported twice as registered, never two
thresholds.

**Criteria 19 / 6 — stationary control selectivity
(criterion 19 is the preceding cycle's PRIMARY form in guard
position; criterion 6 is the same computation in its carried
guard position): PASS / PASS — as a carried profile, at exact
recent8 parity, with NO stationary trigger drawn at all.**
All three sub-conditions pass on both cohorts at parity:
development (a) abstentions 0/240; (b) successes 128 =
recent8 128, required >= 122; (c) harm 112 = recent8 112.
Additional (a) 0/240; (b) successes 130 = recent8 130,
required >= 124; (c) harm 110 = recent8 110. All 15 graded
control states per cohort are recent8 under candidate,
decisive baseline, and recent8 alike; the candidate took ZERO
control abstentions on either cohort. The one partial
zero-support control disarming anywhere — development seed
542021 control k=4 (partial through leg C, purity 0.818,
supporting 0, candidate recent8 7/9) — is shared identically
with the decisive baseline (its branch there is also recent8
7/9): the decisive baseline did NOT abstain at that state, so
**grading cap (ii) is NOT MET either**: there is no graded
control state at which the decisive baseline abstained on a
partial zero-support trigger while the candidate acted. Any
stationary PASS here is the carried profile's — on these
draws the stationary arm drew no taken trigger of any kind,
so there is nothing for a support leg, scoped or unscoped,
to demonstrate.

**Criteria 18 / 5 — checkpoint-32 release: PASS / PASS.**
Both cohorts pass in full. Development: (a) abstentions
0/144; (b) successes 62 vs recent8 56, required >= 48; (c)
non-recent8 1/9 — the carried leg-N retained firing at seed
542003 return-A k=32 (newest 2 / acting 2, stale 1, purity
0.703, retained 12/4, identical under the decisive baseline);
(d) abstained 0/9. Additional: (a) 0/144; (b) successes 78 vs
recent8 75, required >= 67; (c) non-recent8 1/9 — the carried
leg-N retained firing at seed 543001 return-A k=32 (newest 2
/ acting 2, purity 0.706, retained 11/5, identical under the
decisive baseline); (d) abstained 0/9. No leg-D singleton
firing occurs at checkpoint 32 on either cohort (the cycle's
one singleton firing is at additional seed 543041 return-A
k=8, ungraded, identical under the decisive baseline).

**Criterion 1 — second-switch (B2) protection: FAIL /
FAIL.** Development FAILs on (a), (c), and (d): minority
TAKEN 1/6 against the >= 3 floor (the one firing: seed 542021
k=4, minority_fraction 0.323, purity 0.909, 13/3, cross-check
differing at that state as registered); selectivity (b)
passes (minority 0/6 at B1, 0/6 at return-A); harm 83 vs
guard 80 FAILs the guard comparison and 83 vs the ceiling
0.60 x recent8 87 = 52.2 FAILs the ceiling; successes 13 vs
guard 0 + 16 = 16 FAIL. Additional FAILs on (a), (c)-ceiling,
and (d): minority TAKEN 2/6; selectivity passes (0/6, 0/6);
harm 57 <= guard 81 passes the guard comparison but 57 vs
the ceiling 0.60 x recent8 81 = 48.6 FAILs; successes 23 vs
guard 15 + 16 = 31 FAIL. Both failures are carried identical
to the decisive baseline (minority 1/6 and 2/6, B2 successes /
harm 13/83 and 23/57 under both methods); the scoping touches
no B2 state on either cohort. The B2 harm figures include the
carried partial leg-S disarmings shared with the decisive
baseline (development seeds 542021 B2 k=2 and 542039 B2 k=4,
plus 542003 B2 k=8 ungraded; additional has none at B2).

**Criterion 11 — B1/stationary conjunction: FAIL / FAIL.**
The conjunction of criteria 6 and 9; it FAILs on its B1 side
on both cohorts, its stationary side passing both.

**Criteria 17 / 4 — return-A onset harm (criterion 17 is
the return-A PRIMARY form of an earlier cycle; criterion 4
is the same computation in its carried position): PASS /
FAIL.** Development passes both sub-conditions: harm 48 <=
guard 71 (a) and 48 <= ceiling 0.60 x recent8 87 = 52.2 (b);
recovery TAKEN 4/6. Additional passes (a) — harm 70 <= guard
79 — and FAILs the ceiling (b): 70 vs 0.60 x recent8 94 =
56.4; recovery TAKEN 3/6. Carried identical to the decisive
baseline on both cohorts (return-A successes / harm 48/48
and 26/70 under both methods).

**Criterion 2 — return-A recovery successes: PASS / FAIL.**
Development: successes 48 vs the frozen_A floor 0.40 x 62 =
24.8 (a) PASS and vs guard 9 + 16 = 25 (b) PASS. Additional
FAILs (a) alone: successes 26 vs the floor 0.40 x 74 = 29.6;
(b) passes, 26 >= guard 1 + 16 = 17. frozen_A / cumulative
beat the candidate on BOTH axes at return-A on both cohorts
again (development frozen_A 62/34 and cumulative 68/28 vs
candidate 48/48; additional frozen_A 74/22 and cumulative
56/40 vs candidate 26/70), carried identical to the decisive
baseline.

**Criterion 3 — pooled onset harm: PASS / PASS.**
Development: pooled onset harm 207 <= guard 227 (a), per-cell
harm <= recent8 in 6/6 onset cells (b). Additional: 174 <=
guard 207 (a), 6/6 cells (b). Pooled onset successes / harm
are identical to the decisive baseline on both cohorts
([65, 207] development, [50, 174] additional, vs recent8
[30, 258] / [41, 247] and singleton [63, 145] / [49, 143] —
the candidate-vs-singleton difference on these cohorts is
exactly leg S's carried partial disarmings, 6/72 checkpoints
development and 2/72 additional, all shared with the decisive
baseline).

**Criterion 7 — full accounting: PASS / PASS.** Replay
identity 72/72 per cohort; no criterion-7 field missing;
support_threshold 1 everywhere; supporting_opposed_count
recomputable as acting_opposed_count − opposed_count
everywhere; abstention_disarmed_by_support recomputed exactly
everywhere under its SCOPED formula (true ONLY at partial
triggers whose other gate legs all pass at supporting 0 —
exactly 6 states development and 2 additional across all
checkpoints, every one shared with the decisive baseline);
the abstention gate recomputable everywhere under the scoped
composition (full: leg P alone; partial: leg P AND (leg R OR
leg C) AND leg S; no-trigger record: leg P); partial-scoped-rule
== candidate branch and stationary-support-rule == decisive
branch everywhere; singleton_release_fired and the
recovery_fired leg-N-or-leg-D composition recomputed
everywhere with 0 mismatches; companion fields recomputable
at every partial state (25 development / 29 additional) and
at fallback elsewhere; kind never widened; stale lists of 18,
acting lists of 8, and newest lists of 4 with all counts
recomputable everywhere and newest records == acting tail;
thresholds as registered; minority_model_archive_count ==
archive_events_count and minority_model_inverted true
everywhere; cross-check PASS at every minority-fired state
(4/4 development, 6/6 additional applicable; B2 onset
differing choices 1 development, 2 additional); learner
training actions 0, learner information-acquisition actions
0, additional requested observations 0. External TRAIN actor
costs are published in the saved detailed results and the
grading output (shared stage stream: 720 actor actions per
cohort, of which 260 actually harmful on development and
236 on additional — the shared external stream's costs,
identical for every method, never the learner's).

## Learning evaluation

- What the candidate demonstrably did on these cohorts is
  NOTHING the decisive baseline did not do: branch- and
  score-identical at 72/72 checkpoints on both cohorts. The
  scoping is a real, unit-tested code difference (132 tests,
  including the restored-full-taking construction), but its
  designed population — a gated FULL trigger at supporting 0
  — was drawn zero times in 144 cohort-checkpoints. The two
  full zero-support states that did occur never reached the
  abstention gate (one pre-empted by a recovery firing, one
  with abstention authority unarmed).
- Task successes / harm at the graded aggregates are the
  decisive baseline's: pooled onset [65, 207] / [50, 174];
  B1 [4, 76] / [1, 47]; B2 [13, 83] / [23, 57]; return-A
  [48, 48] / [26, 70]; checkpoint-32 [62, 82, 0] / [78, 66,
  0] vs recent8 [56, 88, 0] / [75, 69, 0]; control [128, 112,
  0] / [130, 110, 0], identical to recent8 in full on both
  cohorts.
- Generalization level: at most handoff level 2–3 (choosing
  among / applying already-supplied representations under a
  designer-supplied support-scoping rule). No novel
  representation, no level-6 claim. The experiment's
  contribution is a clean null: it separates "the scoping is
  wrong" from "the scoping was never exercised," and the
  answer on these draws is the latter.

## Safety and evidence costs

- Harmful TEST actions: pooled onset 207 development / 174
  additional (identical to the decisive baseline; below
  recent8's 258 / 247 and below the guards' 227 / 207).
- Failed-by-abstention: onset abstained episodes 16
  development / 64 additional (identical to the decisive
  baseline); control abstentions 0/240 on both cohorts;
  checkpoint-32 abstentions 0/144 on both.
- Information acquisition: zero learner training actions,
  zero learner-issued acquisition actions, zero additional
  requested observations. All TRAIN evidence came from the
  shared external actor stream, whose actual harm is counted
  in full in the saved results (see criterion 7).
- False confidence / unnecessary abstention: the B1 profile
  is the honest cost centre — B1 successes 4 / 1 against
  recent8's 12 / 24, with B1 harm passing both comparisons
  only at exact guard parity (76 = 76, 47 = 47). The partial
  class's zero B1 contribution is an engagement failure, not
  a harm failure.

## Scientific conclusion

**Conclusion: FAILED, NOT a Regression.** The Failed clause
triggers on the additional cohort several times over:
PRIMARY criterion 20 FAILs there (non-full sub-condition),
and criteria 9, 1, 11, 17, 4, and 2 FAIL there; criterion 7
PASSes both cohorts, and criteria 19/6, 18/5, and 3 PASS
both. Partially demonstrated does not rescue the verdict:
its clause requires criterion 20 to pass on both cohorts.
No Regression clause triggers: pooled onset harm 207 / 174
is below recent8's 258 / 247 on both cohorts; stationary-
control successes are at exact recent8 parity on both (128 =
128, 130 = 130; diff 0 / 0 against the more-than-6
both-cohorts clause); checkpoint-32 successes 62 / 78 hold
above the recent8 − 4 lines of 52 / 71; the full unit suite
(2100 tests) and the historical transfer benchmark both pass
in this grading stage.

The honest summary of the scoping itself, stated plainly:
**the scoping demonstrated nothing on these draws, in either
direction.** Its designed population did not occur — zero
gated full zero-support triggers across both cohorts, against
the protocol's priced full-class exposure (kind mix given a
trigger: full 0.498 raw / 0.397 adjusted at onset) — so the
B1 cap cannot be met, the stationary cap cannot be met, and
the hypothesis is UNTESTED by these cohorts, neither
confirmed nor refuted, exactly as pre-registered as a
possible failure mode. What the cohorts DID draw is a B1
population the scoping never claimed to change: three partial
triggers per cohort contributing zero takings (four disarmed
by leg S through leg C at supporting 0 across both cohorts,
shared identically with the decisive baseline; two blocked by
both corroboration legs), and full triggers only at
supporting >= 1. B1 engagement on these draws is bounded by
the partial class's zero contribution and the full class's
draw rate — not by anything the scoping moved. Leg T's
staleness flag was recorded at exactly one state across both
cohorts (development seed 542021 return-A k=16, on an
abstained state taken identically by the decisive baseline);
it released no checkpoint-32 routing and changed no branch
or score anywhere.

Next limitation selected: **P1 first-switch (B1) onset
engagement — the partial (non-full) class's contribution
under the support-gated abstention classes** — criterion
20/9 FAILs on BOTH cohorts on sub-condition (a) with harm
passing both comparisons on both (development on count AND
non-full: TAKEN 1/6, non-full 0; additional on non-full
alone: TAKEN 3/6 all full, non-full 0), and the partial class
contributes zero taken B1 states on either cohort despite
three partial B1 triggers drawn per cohort (two per cohort
disarmed by leg S at supporting 0 through leg C; one per
cohort blocked by both leg R and leg C); whether an
evidence-derived condition on the partial abstention class —
one that gives the partial class a taken B1 population
without re-tuning leg S's threshold, leg P, leg R, or leg C,
and without reopening the full class the scoping just
restored — can hold criterion 9's frozen form on BOTH cohorts
while holding stationary selectivity (criteria 19/6),
checkpoint-32 release (criteria 18/5), B2 protection
(criterion 1), and return-A profiles (criteria 17/4/2) as
co-graded guards, on NEW cohorts under a NEW protocol.
Recorded but not selected: B2 protection FAILs on both
cohorts as well (minority 1/6 development, 2/6 additional;
development also on harm-vs-guard, the ceiling, and
successes; additional on the ceiling and successes) — a
carried draw identical to the decisive baseline, on a branch
the scoping does not touch, carried as a co-graded guard;
additional's return-A failures (criteria 17/4 ceiling, 2
floor) are carried identical with frozen_A / cumulative
both-axes dominance on both cohorts again; stationary
selectivity PASSes both at exact parity with zero control
abstentions drawn — no stationary population to retry;
checkpoint-32 release PASSes both on carried leg-N firings —
no release population to retry; the scoping hypothesis
itself is untested, not refuted — a retry would need a
cohort design that actually draws gated full zero-support
triggers, which no graded population this cycle sizes. Keep
the learner optional and unpromoted, the default controller
unchanged, no merge, no AthenZ/Synveil integration,
D1–D10/V2A/V2B unchanged.
