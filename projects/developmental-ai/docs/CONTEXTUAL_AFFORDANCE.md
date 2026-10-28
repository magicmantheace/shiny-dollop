# Context-indexed action-risk memory and descriptor drift (2026-10-21)

**Status: optional simulation-only research; NOT independent latent
regime discovery, causal safety, D3/D4 completion, or default promotion.**

## Motivation

The previous stable numeric-descriptor experiment trained `RiskMemory`
on one fixed cargo task. It correctly avoided an irreversible spoilage
operation on six inspected seeds (360/360 cargo successes versus
136/360 unfiltered). Its numeric descriptor was an engineered,
seed/family-specific alias for the simulator's hidden action name.
A stationary action-to-descriptor relationship was assumed.

The next problem is a *change in the meaning of that descriptor*:
a once-harmless descriptor becomes harmful, and the previous risky
descriptor becomes harmless. Can a memory-equipped agent learn the
new association and still retrieve its old association upon returning
to the original context?

## Protocol and simulator

See [the immutable prior protocol](../benchmarks/contextual_affordance_protocol.json),
committed as `0b38c64cc22a4b074d1d333dd2e2e9c5638afdff` **before**
creating the new candidate module and benchmark.

Two variants of the **existing** cargo simulator:

- **A:** Standard two-byte descriptors, rotating per-episode handles,
  scrambled numeric sensor channels and fixed hidden cargo rules.
- **B:** The numeric descriptors corresponding to the simulator's private
  `wash` (harmless) and `spoil` (irreversibly harmful) operations are
  swapped. **The physical transition rules remain unchanged.** This is
  *descriptor-meaning drift*, not changed physics or independently
  learned raw perceptions.

The simulator additionally supplies a public two-integer beacon:
A gives `[0,2]`; B gives `[2,0]`. The policy receives these
numbers, **not** their A/B meaning. It uses an explicitly engineered
Euclidean-nearest-memory mechanism. These beacons perfectly separate
the two regimes; this is a substantial source of information, not an
independently inferred cause or a general concept of environmental
context. There is no hidden access to an action-name dictionary in the
learner. For the ambiguous-cue control, the public beacon is `[1,1]`
and the distance tie is broken deterministically.

- **Source training A:** 80 cargo episodes, split `train`,
  indices 0..79, unfiltered novel-first behavior.
- **Changed training B:** 80 fresh unfiltered cargo episodes, split
  `train`, indices 300..379, in the descriptor-remapped context.
- Memory derives failed/successful episode correlations from public
  action descriptor + sensor-change evidence, *never* privileged
  sabotage/true action-name labels.
- **Evaluation:** A, B, then A again, each 60 `test` episodes
  per seed (A and B indices 8400..8459; return A 8500..8559).
  No policy or memory updates during this phase.
- Seeds: development 51001/51013/51031 and initially reserved
  61001/61013/61031. Once both cohorts have been run, all seeds must
  be called **inspected**.
- **Pre-evaluation implementation issue, preserved:** Frozen seed 51013
  produces a two-byte descriptor collision between `load` and `spoil`
  in the old generator. The initial development benchmark stopped with
  `ValueError: descriptor hash collision` before producing scores.
  Instead of selecting convenient new seeds, the new optional simulator
  now resolves duplicates **deterministically** by incrementing the
  second descriptor byte until it is unique, in the same action
  declaration order. The precommitted seeds, two-byte feature size,
  underlying cargo rules, and all original benchmarks remain untouched.
  The privileged oracle is updated to read the corrected simulator
  descriptor rather than assuming that every raw hash is unique.
  This post-protocol code correction is disclosed; it is not
  independent prospective validation.
- Controls: contextual retrieval, frozen A-only policy, B-only/latest
  policy, untrained novel-first, ambiguous-beacon ablation, simulator-
  privileged hazard-code oracle and fully privileged action-order oracle.
- Outcomes: task completion, spoilage actions, blocked action attempts,
  stalls, mean attempts, exact learned-memory restart/digest replay.

The `ContextMemory` stores two independent `RiskMemory` histories
behind observed cue vectors. It fully rebuilds both risk summaries
during restore, rejects inconsistent/tampered checkpoints and can
save/load private local JSON through atomic fsynced replacement with
a 4 MiB size limit. It has no external network or OS-action interface.
`ContextNovel` picks a memory once at episode start, disallows a
mid-episode public context switch, and uses unchanged
`FilteredNovel` to make simulated decisions.

**No automatic detection:** Training is explicitly segmented by the
experiment's A/B schedule. Source and changed-regime labels are used
by the *training harness to choose where to put experiences*. The
online agent merely matches a supplied beacon to an existing memory.
This is *retention and recall under a known context cue*, not automatic
self-directed discovery that the world changed.

## Verified development + reserved results

The fixed cohorts are **now both inspected**. The study was designed
after the original static hazard learning result, and the original new
run initially failed on frozen seed 51013's descriptor collision. After
a deterministic input-collision correction (see above), the model and
both benchmark cohorts executed successfully in GitHub Actions.

Each cohort contains **three seeds × 60 independent test episodes**
per stage; totals below are **out of 360** across both cohorts.
The B variant still uses the original cargo *physics*, but swaps the
codes for two actions. Training uses 80 *unfiltered* episodes in each
phase **per seed**; across the six seeds, phase A source training
succeeded in 164/480 and changed-phase B training in 171/480.

| Strategy | Initial A | Changed B | Return A |
| --- | ---: | ---: | ---: |
| **Public-cue-selected memory** | **360/360** | **360/360** | **360/360** |
| Frozen **A-only** risk memory | 360/360 | 128/360 | 360/360 |
| Latest **B-only** risk memory | 128/360 | 360/360 | 133/360 |
| Untrained novel-first | 130/360 | 130/360 | 131/360 |
| Context memory with **ambiguous cue** | 360/360 | 128/360 | 360/360 |
| Privileged hazard-identity veto | 360/360 | 360/360 | 360/360 |
| Privileged full action-order oracle | 360/360 | 360/360 | 360/360 |

The cue-selected agent performed **zero successful spoilage actions**
across all 1,080 A/B/A test episodes. On changed B, frozen A-only
memory performed **232** successful spoilage actions across 360
episodes, matching its 232 failures. On return A, B-only memory
performed **227**, matching its failures in that stage.
The ambiguous-cue negative control exactly matched old-only memory
on B (**128/360**), confirming the model's dependency on the
externally supplied context signal.

Every one of the six inspected seeds scored **60/60** separately on
each of the three context-selected evaluation stages. The known
two-component beacon allows trivial regime separation. The learner
does not discover the beacon, choose when to explore new dynamics,
infer the hidden descriptor remapping, nor autonomously allocate
training episodes into contexts.

A single learner with distinct stored histories **can recover its
prior behavior after a known context change** in this small
deterministic simulation. This is retained *retrieval*, **not** proof
of independently learned action semantics, causal risk, safe online
adaptation, unseen-world generalization or a self-developing mind.

### Verified execution

[First passing complete code run](https://github.com/magicmantheace/Developmental-AI/actions/runs/39599591270):
Linux full suite **550/550 tests** and both changed-context
benchmark cohorts passed, alongside the historical transfer and
all previous optional benchmarks; Windows focused suite passed.
The later documentation update does not change simulator behavior.
See the draft PR for latest-HEAD CI before declaring all checks
on the final documentation commit.

## Interpretation requirements

An A→B→A result should always include the following caveats:

1. The agent already received 80 episodes **from each context**.
   Successful B testing is not zero-shot environmental adaptation.
2. Both contexts use one manually written cargo simulator and share
   all sensor/action structure. There is no independent domain transfer.
3. The beacon provides an exact, engineered context distinction.
   Performance loss with `[1,1]` will show reliance on the beacon;
   it does not show learned change detection.
4. Models trained only on A or only on B use 80 episodes, while the
   context-indexed model uses 160; these controls do not match
   *total* experience, only experience available for each regime.
5. SHA-256 integrity/replay are not owner authentication or consent.
6. The risk filter learns failure correlations; in a different world,
   avoiding its learned token may prevent a necessary action.

Preserve the prior fixed-descriptor success and anonymous-action
failure reports as-is, including all unsuccessful and oracle controls.

## Reproduction

```sh
python -m unittest tests.test_contextual_affordance -v
python -m benchmarks.contextual_affordance_benchmark --cohort development
python -m benchmarks.contextual_affordance_benchmark --cohort reserved
python -m unittest discover -s tests -v
python -m benchmarks.transfer_benchmark --seeds 17 23 41 --train-episodes 5000 --test-episodes 300
```

No code from AthenZ/Synveil was changed. V2A computational affect
remains planned before and overlapping V2B virtual environment once
foundational learning is substantially more capable.

## Subsequent work, regardless of outcome

Replace the perfect beacon and simulator-provided identity with noisy
nonunique observable action features, requiring *actual change-point
inference* and active probing. Then test stochastic/nonstationary
dynamics, false-positive memory updates, old-task retention, and
matched-compute baseline policies. Keep the present draft unmerged
until full Windows + Linux verification and owner review.
