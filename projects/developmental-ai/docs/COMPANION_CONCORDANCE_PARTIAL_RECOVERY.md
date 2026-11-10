# Companion concordance partial recovery — a companion-concordance corroboration leg (leg C) for partial abstention triggers

**10 November 2026 protocol frozen; 10 November 2026
implementation; 10 November 2026 evaluation; graded 10 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `companion_concordance_partial_recovery`
  — whether ONE changed element, leg C, a COMPANION-CONCORDANCE
  CORROBORATION LEG for PARTIAL abstention triggers (a partial
  trigger fires behind leg P when leg R OR leg C is armed; leg C
  is armed iff the partial pair's non-opposed companion event is
  NOT reference-concordant — unmatched, i.e. matched false), can
  hold criterion 9's frozen first-switch (B1) engagement form on
  BOTH cohorts — the pre-acting cycle's selected limitation
  (criterion 9 FAILed there on BOTH cohorts on complementary
  halves of sub-condition (a): development's count met at 3/6
  with zero non-full firings, additional's non-full credit met
  with two retained partials but its count 2/6, harm passing
  both comparisons on both) — while holding stationary
  selectivity (criterion 6), B2 protection with the inverted
  minority model carried (criterion 1), checkpoint-32 release
  (criterion 5), and return-A harm (criterion 4) as co-graded
  guards. Leg C is binary; it has no numeric threshold. Leg P,
  leg R, and leg T were explicitly NOT re-tuned. Build Order
  Priority 1 (Independent Learning), items 2 + 3 + 4; handoff §8
  excessive abstention / harmful decisions caused by
  overconfidence. This protocol's PRIMARY criterion is
  criterion 15, the conjunction of (a) criterion 9's B1 form
  (non-full credit a retained partial only, the widened class's
  removal carried, now reachable through leg R OR leg C), (b)
  criterion 6's stationary form, (c) criterion 1's B2 form with
  the inverted minority model carried, and (d) criterion 5's
  checkpoint-32 release form; criteria 9, 6, 1, 5, 11, 4, 2, 3,
  and 7 are its co-graded guards. The protocol also froze a
  grading cap: a Demonstrated verdict additionally requires at
  least one B1 onset state in at least one cohort at which the
  decisive baseline disarmed a partial by leg R and the
  candidate took that retained-partial abstention through
  leg C.
- **Candidate:** `CompanionConcordancePartialRecoveryMemory`
  (`developmental_ai/companion_concordance_partial_recovery.py`)
  — IDENTICAL to the graded `PreActingJointReleaseRecoveryMemory`
  in every element (acting model recent8 exactly, extended
  signal, retained archive, archive concordance, joint test
  joint_count >= 1, recovery model, the full three-leg authority
  condition, the minority branch in full INCLUDING the inverted
  minority model, leg T on both recovery branches, leg P >= 0.70,
  and the full / retained-partial abstention classes with the
  widened class removed records-only, support threshold null) —
  verified by a diff against the graded pre-acting candidate at
  implementation: the ONLY code differences are leg C (the
  companion computation over the newest pair's signal records —
  companion = the non-opposed event when opposed_count == 1,
  concordant iff matched AND not opposed, armed iff NOT
  concordant; fallback matched/concordant/armed false outside a
  partial trigger and below the minimum — the one added gate
  condition for partial triggers, leg P AND (leg R OR leg C)),
  the corroboration-failure flags
  abstention_disarmed_by_preceding_pair /
  abstention_disarmed_by_companion, the five decision-record
  fields companion_matched / companion_concordant /
  companion_armed / companion_threshold null /
  abstention_disarmed_by_companion, its docstring, and
  names/schema. Separate optional learner; the default
  controller and all existing learners are untouched; the
  graded pre-acting candidate appears only as the decisive
  baseline.
- **Branch and commits:**
  `developmental-ai/companion-concordance-partial-recovery`
  (forked from `b670272`, the pre-acting grading commit).
  Protocol frozen at `af1fc1b` (BEFORE implementation);
  implementation at `3e69fe6`; evaluation at `3da6458`. This
  grading report is committed on top of the evaluation commit.
- **Frozen protocol:**
  `benchmarks/companion_concordance_partial_recovery_protocol.json`
  (frozen 2026-11-10, before any implementation, unit test,
  harness, or score inspection for this experiment).
- **Cohorts:** development 492003/492021/492039 and additional
  493001/493017/493041 — NEW at freeze, disjoint from every
  earlier cohort. Both cohorts are now **INSPECTED** and must
  never be re-tuned against.
- **Decisive baseline:** `pre_acting_joint_release_recovery`
  (identical but for leg C; branch selection identical except
  at partial-trigger states where leg R fails, leg C passes,
  leg P and the carried authority hold, and neither recovery
  branch fired). `recent8` is the simplest credible baseline
  and the candidate's own acting model.

## Verification

- Unit tests: PASS — 77/77 new candidate tests at
  implementation; full suite 1554 tests OK in the
  implementation and evaluation stages, and re-run in this
  grading stage: 1554 tests OK (`python3 -m unittest discover
  -s tests`, run 2026-11-10 this pass). The new tests include
  the discriminating states: the unmatched-companion rows
  (preceding 0, companion NEUTRAL — unmatched — decisive
  baseline acts on recent8 disarmed by leg R, candidate
  ABSTAINS as kind partial through leg C) and the
  unmatched-span rows (companion on a majority-less span,
  reference_count 0 — same leg-C firing), against the
  concordant-companion state where both act identically.
- Historical regressions: PASS — historical transfer benchmark
  (`python3 -m benchmarks.transfer_benchmark`) exit 0 in the
  evaluation stage and re-run in this grading stage, standard
  three-seed output (success gains 0.5567 / 0.50 / 0.51 on
  seeds 17 / 23 / 41).
- Frozen cohorts: PASS (run exactly as registered) — both
  cohorts evaluated at `3da6458`; every checkpoint entry
  carries per-method successes / harmful TEST actions /
  abstentions / attempted tasks, the candidate's full decision
  record (including the full companion and stale records),
  checkpoint SHA256, and restore-replay identity
  (script-verified in this grading stage: true at every
  checkpoint in both cohorts, 72/72 entries per cohort).
- Linux validation: UNVERIFIED (no GitHub Actions run on the
  grading commit was checked; no CI is claimed).
- Windows validation: UNVERIFIED (same).

## Per-criterion grading (precommitted, graded individually, per cohort)

Graded script-computed from the saved detailed results at
`3da6458` (grading script and output kept with the campaign
records). PRIMARY criterion 15 first, then co-graded guards 9,
6, 1, 5, 11, 4, 2, 3, 7. Development / additional throughout.

**Criterion 15 — PRIMARY (B1 + stationary + B2 + release
conjunction): FAIL / FAIL.** Development: B1 side FAIL,
stationary side PASS, B2 side PASS, release side FAIL.
Additional: B1 side PASS, stationary side FAIL, B2 side PASS,
release side PASS. The conjunction therefore fails on both
cohorts, each failure attributable to its exact side below —
and the two cohorts again fail the same frozen conjunction in
mirror image.

**Criterion 9 — first-switch (B1) engagement: FAIL / PASS.**
Development FAILs on sub-condition (a)'s count alone:
abstention TAKEN at only 2/6 pooled B1 onset states (seed
492003 k=2, FULL, purity 0.914; seed 492021 k=4, retained
partial, purity 0.857, armed through leg R AND leg C both) —
the non-full sub-condition IS met by that one partial, and
harm PASSes both comparisons (63 <= guard 70 (b); 63 <
recent8 86 (c)). B1 successes 1 vs recent8 10 / guard 10,
stated in full. **Leg C changed NO graded state on this
cohort**: the candidate is score-identical and branch-identical
to the decisive baseline at every checkpoint (score differences
0/72). Both untaken B1 partials (seed 492021 k=2, purity 0.857;
seed 492039 k=4, purity 0.892; both preceding_pair_opposed_count
0) had CONCORDANT companions (matched true), so leg C was not
armed and BOTH corroboration legs failed — development's B1
count failure is a both-legs failure, not an R-only one. One
further development B1 state (seed 492003 k=4) was taken by the
retained recovery branch, and one (seed 492039 k=2) carried no
trigger at all. Additional PASSes in full: TAKEN 5/6 (2 full +
3 retained partial; partial corroboration paths R+C, R+C, and
C-only), harm 13 <= guard 45 and 13 < recent8 76. B1 successes
3 vs recent8 20 / guard 19, stated in full. **The C-only firing
is the experiment's one exercised leg-C state at a graded
population**: seed 493041, k=2, partial trigger, preceding 0,
companion unmatched (matched false, concordant false, armed
true), purity 0.929 — the decisive baseline acted on recent8
(0/16) and the candidate took the retained-partial abstention
(0/0). That single firing is the whole candidate-vs-decisive
difference on the additional cohort's graded populations (B1
TAKEN 4/6 → 5/6; pooled onset harm 85 → 69) at zero success
cost at that state, because recent8 scored 0/16 there. Two
further leg-C firings occurred at UNGRADED checkpoint 0 on the
same seed (B1 k=0 and control k=0, both abstained vs decisive
recent8), making the whole additional score difference 3/72
checkpoints, all on seed 493041.

**Criterion 6 — stationary control selectivity: PASS / FAIL.**
Development PASSes in full with NO control firing at all:
abstentions 0/240, successes 143 vs recent8 140, harm 97 vs
100 — the candidate's control line is identical to the
decisive baseline's (branch differences 0/15 graded control
states), and leg C's stationary price on graded control states
was ZERO on this cohort (its only control firing anywhere is
at ungraded checkpoint 0, on the additional cohort).
Additional FAILs on (b) alone: abstentions 16/240 PASS and
harm 136 vs 145 PASS, but successes 88 vs recent8 95,
required >= 89 — short by exactly 1. The entire deficit is ONE
carried FULL firing (seed 493001, k=2, purity 0.806, 0/0 vs
recent8 7/9), identical in the decisive baseline; leg C added
no graded control firing on this cohort either.

**Criterion 1 — second-switch (B2) protection: PASS / PASS.**
Both cohorts PASS in full — the carried inverted minority
model's profile holds at full engagement on both. Minority
TAKEN 6/6 on both (a); selectivity 0/6 at B1 and 0/6 at
return-A on both (b); harm 36 vs guard 38 and ceiling
0.60 × recent8 73 = 43.8 development, 26 vs guard 60 and
ceiling 0.60 × recent8 80 = 48.0 additional (c); successes 60
vs guard 10 + 16 = 26 development, 70 vs guard 4 + 16 = 20
additional (d). No abstention fired at B2 onset on either
cohort; the minority-model cross-check PASSes at every
minority-fired state (13 development / 9 additional applicable)
with first-frame choices differing from the widened-window
method at 6/6 minority-fired B2 onset states on EACH cohort.
Candidate identical to the decisive baseline at every B2 state
on both cohorts.

**Criterion 5 — release and productivity by checkpoint 32:
FAIL / PASS.** Development FAILs on TWO sub-conditions.
(a) abstentions 0/144 PASS; (d) abstained branch 0/9 PASS.
(b) successes 47 vs recent8 60 — below the recent8 − 8 line
of 52. (c) non-recent8 branch in 2/9 switch-stage k=32 states
against the allowance of 1. Both routings are regular retained
routings at seed 492003, stale counts 0/0, and BOTH are harmful
on this draw: B1 retained (purity 0.737) scoring 0/16 vs
recent8 1/15, and B2 retained (purity 0.711) scoring 0/16 vs
recent8 12/4 — together they are the cohort's entire −13 k=32
success deficit and more. Leg C and leg T touch neither
routing (leg T disarmed ZERO states on either cohort this
cycle; the one leg-C-pattern state at checkpoint 32 anywhere —
additional seed 493001 B1, partial, preceding 0, companion
armed — was BLOCKED by leg P at purity 0.625, candidate recent8
0/16 identical to the decisive baseline). Additional PASSes in
full: abstentions 0/144, successes 84 = recent8 84,
non-recent8 0/9, abstained 0/9. All nine k=32 states per cohort:
development — 492003 B1 retained above, 492003 B2 retained
above, 492003 return-A recent8 (purity 0.759, 9/7 =); 492021
all recent8 (B1 0.688 stale 1/0, 9/7 =; B2 0.769, 10/6 =;
return-A 0.703, 3/13 =); 492039 all recent8 (B1 partial 0.720,
11/5 =; B2 partial 0.618, 0/16 =; return-A 0.765, 5/11 =).
Additional — all nine recent8 (493001 B1 partial 0.625
leg-P-blocked above, 0/16 =; 493001 B2 0.680, 8/8 =; 493001
return-A 0.703, 10/6 =; 493017 B1 0.621, 10/6 =; B2 0.800,
11/5 =; return-A 0.686, 14/2 =; 493041 B1 0.815, 8/8 =; B2
0.677, 12/4 =; return-A 0.677, 11/5 =).

**Criterion 11 — B1/stationary conjunction (carried): FAIL /
FAIL.** Development fails on its B1 side only (criterion 9;
its stationary side PASSes with no firing at all); additional
fails on its stationary side only (criterion 6; its B1 side
PASSes in full, carried there by the leg-C firing).

**Criterion 4 — return-A onset harm: FAIL / PASS.**
Development: harm 54 vs guard 61 PASS on (a) but ceiling
0.60 × recent8 83 = 49.8 FAIL on (b); regular recovery TAKEN
6/6. The candidate is identical to the decisive baseline at
every return-A state on both cohorts — the ceiling failure is
a carried outcome at fully engaged states, not a leg-C effect
(companion-armed partial records occur at return-A states on
both cohorts, but every such state was taken by the retained
recovery branch above the abstention branch in the decision
order). Additional: harm 30 vs guard 46 and ceiling
0.60 × recent8 67 = 40.2, PASS in full; regular recovery
TAKEN 6/6.

**Criterion 2 — return-A recovery successes: PASS / PASS.**
Development: successes 42 vs frozen_A 58 (floor 23.2) and
guard 3 + 16 = 19, PASS. Additional: 66 vs frozen_A 76
(floor 30.4) and guard 18 + 16 = 34, PASS. Stated in full, as
registered: frozen_A beats the candidate on BOTH axes at
return-A on BOTH cohorts (58/38 vs 42/54 development; 76/20 vs
66/30 additional), and cumulative does the same on development
(58/38) and exactly ties the candidate on additional (66/30).

**Criterion 3 — pooled onset harm: PASS / PASS.** Pooled onset
harm 153 vs guard 169 development and 69 vs guard 151
additional, with all 6/6 individual onset cells <= recent8 on
both cohorts. Development's pooled figure is identical to the
decisive baseline's 153; additional's is BELOW the decisive
baseline's 85 by exactly the leg-C firing's −16 harm.

**Criterion 7 — full accounting: PASS / PASS.** Replay
identity true at every checkpoint in both cohorts (72/72
entries per cohort); no criterion-7 field missing anywhere;
support_threshold null everywhere; companion_threshold null
everywhere; abstention_disarmed_by_support false everywhere;
widened_threshold 3, staleness_pair_threshold 2, and
preceding_pair_threshold 1 everywhere; abstention gate
recomputable everywhere (incl. the leg-C composition for
partial triggers) with 0 mismatches; companion fields
recomputable from the signal records at every partial state
(25 development / 28 additional) and at their registered
fallback values at every non-partial state; companion-rule ==
candidate branch everywhere; pre-acting-release-rule ==
decisive baseline branch everywhere; preceding-pair-rule ==
widened-removal-rule everywhere; widened-rule == inverted
branch everywhere; newest4 / widened_armed recomputable
everywhere; abstention_trigger_kind in {full, partial, none}
everywhere — never widened, as the carried removal requires;
stale lists of 18 with both pair counts recomputable
everywhere with 0 mismatches;
minority_model_archive_count == archive_events_count
everywhere; minority_model_inverted true everywhere;
minority-model cross-check PASS at every minority-fired state
(13/13 development, 9/9 additional applicable); learner
acquisition actions 0 throughout.

## Learning evaluation

Candidate vs recent8 (simplest credible baseline), successes /
harmful TEST actions per stage-checkpoint cell (candidate
first; abstentions in parentheses where nonzero):

Development — B1: k=0 1/47 vs 1/47; k=2 0/32 (16 abst) vs
0/48; k=4 1/31 (16) vs 10/38; k=8 0/0 (48) vs 29/19; k=16
6/42 vs 6/42; k=32 20/28 vs 21/27. return-A: k=0 4/44 vs
4/44; k=2 20/28 vs 3/45; k=4 22/26 vs 10/38; k=8 19/29 vs
21/27; k=16 21/27 vs 24/24; k=32 17/31 vs 17/31. B2: k=0
13/35 vs 1/47; k=2 30/18 vs 6/42; k=4 30/18 vs 17/31; k=8
30/18 vs 38/10; k=16 33/15 vs 28/20; k=32 10/38 vs 22/26.
Control: k=0 28/20 vs 28/20; k=2 35/13 vs 32/16; k=4 32/16 vs
32/16; k=8 31/17 vs 31/17; k=16 19/29 vs 19/29; k=32 26/22
vs 26/22.

Additional — B1: k=0 2/30 (16) vs 2/46; k=2 0/0 (48) vs 1/47;
k=4 3/13 (32) vs 19/29; k=8 0/0 (48) vs 31/17; k=16 26/22 vs
26/22; k=32 18/30 vs 18/30. return-A: k=0 23/25 vs 0/48; k=2
33/15 vs 11/37; k=4 33/15 vs 18/30; k=8 33/15 vs 21/27; k=16
25/23 vs 25/23; k=32 35/13 vs 35/13. B2: k=0 0/48 vs 0/48;
k=2 35/13 vs 2/46; k=4 35/13 vs 14/34; k=8 25/23 vs 22/26;
k=16 25/23 vs 26/22; k=32 31/17 vs 31/17. Control: k=0 16/16
(16) vs 20/28; k=2 14/18 (16) vs 21/27; k=4 9/39 vs 9/39; k=8
20/28 vs 20/28; k=16 14/34 vs 14/34; k=32 31/17 vs 31/17.

Pooled onset (checkpoints 2 and 4): candidate 103 successes /
153 harm development and 139/69 additional, vs decisive
baseline 103/153 and 139/85, vs widened-window 115/141 and
129/95, vs guard 23/169 and 41/151, vs recent8 46/242 and
65/223. The candidate differs from the decisive baseline in
score at 0/72 development checkpoints and 3/72 additional
checkpoints (all three on seed 493041, all leg-C firings); it
differs from the inverted method at 0/72 development and 4/72
additional checkpoints. Past knowledge retention is graded by
checkpoint-32 and stationary behaviour above: development's
k=32 deficit is the two harmful retained routings; additional
is at exact recent8 parity at k=32. Generalization level: at
most handoff level 2–3, as registered — designer-supplied
rules throughout; no novel-representation claim.

## Safety and evidence costs

- Harmful TEST actions: pooled onset 153 development / 69
  additional (candidate), detailed per criterion above; B1
  pooled onset harm 63 / 13; B2 36 / 26; return-A 54 / 30;
  stationary control harm 97 / 136; checkpoint-32 harm is
  inside the per-state k=32 records above.
- Failed-by-abstention: candidate onset abstentions 32/288
  development and 80/288 additional; stationary 0/240 and
  16/240; checkpoint-32 0/144 on both. Every leg-C firing's
  productivity cost is stated per state: the one graded firing
  cost 0 successes (recent8 scored 0/16 at that state); the two
  ungraded checkpoint-0 firings cost 0 successes at B1 k=0
  (0/16 vs 0/16 decisive harm difference only) and 4 successes
  at control k=0 (candidate 0/0 vs decisive recent8 4/12) —
  recorded, not hidden.
- Learner information-acquisition actions: 0 throughout.
  Additional requested observations: 0.
- External TRAIN actor costs (shared evidence stream,
  identical for all methods, published in full, never netted
  against TEST results): development — stage A 720 actions,
  239 actually harmful (242 reported harmful, 17 label flips);
  B1 192 actions, 80 harmful; B2 192, 79; return-A subset 144,
  50; control continuation 192, 68. Additional — stage A 720
  actions, 257 actually harmful (258 reported, 25 flips); B1
  192, 84; B2 192, 91; return-A subset 144, 48; control
  continuation 192, 66.
- False confidence / unnecessary abstention: development's two
  k=32 retained routings (purity 0.737 / 0.711, each 0/16) are
  the cycle's false-confidence states; leg C produced no
  unnecessary graded abstention on either cohort (its sole
  graded firing abstained at a state where recent8 scored
  0/16).
- Report integrity: all figures script-computed from the saved
  detailed results at `3da6458` in this grading stage; the
  492003-family / 493001-family cohorts are INSPECTED and no
  parameter was re-tuned against them or any earlier cohort.

## Scientific conclusion

**Failed / Regression at checkpoint 32.** Failed under the
protocol's own definitions (PRIMARY criterion 15 FAILs on BOTH
cohorts — development on its B1 and release sides, additional
on its stationary side — and the Failed clause triggers on the
additional cohort several times over: criteria 15, 6, and 11
FAIL there, criterion 7 PASSes both). A Regression under the
protocol's checkpoint-32 clause: development k=32 successes 47
fall below the recent8 − 4 line of 56 — the deficit is exactly
the two carried retained routings at seed 492003 (purity
0.737 / 0.711, stale counts 0/0, each scoring 0/16), which
neither leg C nor leg T touches. The other Regression clauses
do not trigger: pooled onset harm 153/69 is well below
recent8's 242/223 on both cohorts; the control-successes
clause requires both cohorts and development is +3 against
additional's −7; the full unit suite and the historical
transfer benchmark pass.

What the experiment actually establishes, stated as prominently
as the failure: leg C, the single changed element, was
exercised at exactly ONE graded state across both cohorts, and
at that state it did exactly its designed work — additional
seed 493041, B1 k=2: a retained-partial abstention the decisive
baseline could not take (leg R disarmed at preceding 0), worth
the whole pooled-onset harm gap vs the decisive baseline on
that cohort (69 vs 85) and the B1 count step 4/6 → 5/6, at zero
success cost. **The grading cap is therefore MET** (at least
one B1 onset state in at least one cohort where the decisive
baseline disarmed a partial by leg R and the candidate took it
through leg C), via that state, and does not bind beyond it.
But one exercised state on one cohort is not an
engagement-composition demonstration: on development the leg
was never the deciding leg at any graded state — the cohort's
two leg-R-blocked partials were blocked by leg C too
(concordant companions), so development's B1 failure is a
both-legs failure of the newest-pair corroboration family, and
every other development outcome, including the checkpoint-32
Regression, is a carried outcome identical to the decisive
baseline. Leg C's stationary price on graded control states
was zero on both cohorts. Partially demonstrated does not
apply (it requires criterion 15 PASS on both cohorts).

**Next limitation (selected for the next cycle, Priority 1):**
checkpoint-32 release — the non-recent8 recovery routings at
checkpoint 32. Criterion 5 FAILs development on TWO
sub-conditions this cycle ((b) successes 47 vs the line of 52
and (c) non-recent8 2/9), its failure carries this cycle's
Regression, and — the changed shape versus the pre-acting
cycle, whose development routings were both productive — both
of development's routings here are HARMFUL retained routings
(purity 0.737 / 0.711, each 0/16 vs recent8 1/15 and 12/4) at
stale counts 0/0, a population neither leg T (whose designed
population was again absent: it disarmed zero states on either
cohort) nor leg C touches. Measurable: on NEW cohorts under a
NEW protocol, whether an evidence-derived condition on the
recovery branches' late routings — a genuinely new structural
quantity, not a threshold variant of leg T — can hold
criterion 5's frozen form on BOTH cohorts while holding B1
engagement (criterion 9, with leg C carried), stationary
selectivity (criterion 6), B2 protection (criterion 1), and
return-A harm (criterion 4) as co-graded guards. Recorded but
not selected: development's B1 count failure is now a
both-legs failure — leg C demonstrated its designed work on
the additional cohort (cap met, count repaired there) and a
further B1 retry would need a corroboration quantity beyond
the newest pair's companion event, which no graded population
in this cycle identifies; additional's stationary failure is
1 success past the line on ONE carried full firing with
development passing at zero firings; development's criterion 4
failure is the return-A ceiling alone at fully engaged states
with additional passing in full; frozen_A beats the candidate
on both axes at return-A on both cohorts again, and cumulative
does so on development and ties on additional.

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration,
D1–D10/V2A/V2B unchanged.
