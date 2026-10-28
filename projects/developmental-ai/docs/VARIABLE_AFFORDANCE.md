# Variable observation-schema outcome learning — October 22, 2026

**Status: opt-in development experiment, draft/unmerged, simulation-only.**

## Hypothesis

A persistent experience-based outcome model that does not require one fixed
length and vocabulary of numeric action descriptors can encounter a *third*
synthetic rule family, learn a new schema from public effects, and retain
earlier family competence. It must be compared with a source-frozen model,
an independent target-only learner, recent-48 memory, random actions,
abstention, and a privileged simulation-only oracle.

**Frozen before new learner/benchmark:** [protocol](../benchmarks/variable_affordance_protocol.json),
commit `0cc4cf6`. Implementation on the same established
`developmental_ai/observable_affordances.py` numeric outcome architecture:
`VariableOutcomeMemory`, commit `eb82085`. The new worlds exist exclusively
inside the bounded benchmark; no new OS/network/controller authority.

## Environment setup

Three distinct, manually authored task families (not renamed versions of a
single rule) each expose new per-episode opaque action IDs and a list of
observed numeric features. The learner never receives the simulator's family
name, hidden action rule, true effect function, or stable action identifier.

- **Quarry**: `grade`, `moisture`, signed magnitude difference determines
  productive/damaging/neutral outcomes, goal 3 productive actions.
- **Coolant**: `flow`, `heat`, `seal`, three-way thresholds determine
  outcome, goal 4.
- **Relay**: `phase`, `pulse`, `shield`, `noise`; modulus relationship
  and protection distinguish productive from damaging actions, goal 2.
  This rule deliberately stresses ordinary Euclidean nearest neighbors.

Each independent episode has five productive, four harmful, and three neutral
possible actions (sampled without revealing which is which). One damage
ends the episode; fewer than the specified productive actions is failure.
The agent sees only the current public goal counter, damage counter, and
available actions/observations; action names are shuffled/new each episode.
Its pre-trained knowledge cannot match opaque identifiers by name.

### Experience and evaluation separation

The learner receives `features,progress,damage` from a **separate
random one-action simulator actor**, using public before/after observations;
it never initiates training exploration. Training:

1. 180 quarry and 180 coolant outcomes per seed.
2. At evaluation checkpoints, 0, 16, 48, or 160 new relay outcomes.
3. At each checkpoint, the unchanged learned state is tested on 40 separate
   TEST episodes per family per seed, while recording all task failures and
   simulated harmful actions. The same TEST episodes recur across checkpoints
   and are **not independent** across time.
4. Full history remains append-only and has a deterministic SHA-256 replay
   checkpoint, with old source observations retained for revisit.

Frozen development seeds: 142003/142021/142039. Separately frozen additional
seeds: 143001/143017/143041. All become **inspected** once results are read.
A real independent environment author/generator would be required for a
stronger D3 result.

### Explicit information constraints

The learner is not given a domain label or effect rule, but the set of
observed feature **keys** uniquely distinguishes these three worlds. It
partitions examples by exact observed key set: this is an **engineered**
schema-isolation inductive bias, not learned language meaning or semantic
alignment. Its nearest-neighbor classifier is the existing fixed Euclidean
algorithm generalized to varying-dimensional vectors.

Good target-family performance after feedback is **adaptation**, not
zero-shot transfer. Good old-family retention may result from schema
partitioning rather than an independently discovered memory-consolidation
mechanism. No model update is allowed on held-out TEST episodes.

The random actor incurs potentially harmful simulator actions; report its
harm separately from TEST-policy harm. Checkpoint hashes prove internal
replay only; they do not authenticate observational truth or prevent
colluding source forgeries. This does not resolve the earlier witness
poisoning findings or authorize real-world probing.

## Status / reproduction

Dedicated focused CI:
[Variable schema outcome learning](https://github.com/magicmantheace/Developmental-AI/actions/runs/39815731144).

Full historical validation is a **separate** exact-HEAD requirement; prior
successful CI does not prove that these new code changes are regression-free.

```bash
python -m unittest tests.test_variable_affordance tests.test_observable_affordances -v
python -m benchmarks.variable_affordance_benchmark --cohort development
python -m benchmarks.variable_affordance_benchmark --cohort additional
```

Do not promote to default controller, alter AthenZ/Synveil, or merge PR #2
without measured evidence and owner review. Preserve the established D1-D10
sequence and V2A preceding/overlapping V2B.

## Current open research questions

- Does performance on the genuinely new rule **increase** with feedback
  enough to beat random/frozen baselines?
- Does source-family success survive target adaptation when old source events
  remain in the same *checkpoint*?
- How often does the non-smooth modulus rule defeat nearest neighbors, and
  is a simple target-only learner just as good?
- Can the next pass learn useful *relations* despite completely different
  feature-key vocabularies, rather than partitioning them by designer names?


## October 22 measured outcome — focused validation PASSED

**Exact frozen focused run:**
[39815731144](https://github.com/magicmantheace/Developmental-AI/actions/runs/39815731144).
45 unit tests passed (variable-schema + relevant historical retrieval,
consistency and numeric-affordance checks). Both exact three-seed
cohorts completed, retaining complete JSON result artifacts.

All six seeds and all TEST indices have now been inspected. Scores below
are successful TEST episodes out of **240 per family per checkpoint**.
The same 240 TEST episodes recur at each checkpoint; those measurements
are NOT independent samples.

| Test family / policy | 0 new relay obs | 16 | 48 | 160 |
| --- | ---: | ---: | ---: | ---: |
| Relay — persistent variable-schema memory | **69** | **233** | **240** | **240** |
| Relay — target-only kNN | 69 | 233 | 240 | 240 |
| Relay — last-48 memory | 69 | 233 | 240 | 240 |
| Relay — frozen source memory | 69 | 69 | 69 | 69 |
| Relay — untrained random | 78 | 78 | 78 | 78 |
| Quarry — persistent memory | 240 | 240 | 240 | 240 |
| Quarry — target-only | 26 | 26 | 26 | 26 |
| Quarry — last-48 memory | 26 | 26 | 26 | 26 |
| Coolant — persistent memory | 240 | 240 | 240 | 240 |
| Coolant — target-only | 10 | 10 | 10 | 10 |
| Coolant — last-48 memory | 240 | 240 | 10 | 10 |

The privileged simulator oracle completed **240/240 in all three
families** at all checkpoints, and always-abstain completed **0/240**
(with zero test harm).

### Test harms and source collection cost

- Relay persistent-memory harmful TEST actions: **171/240** at zero
  target observations, **7/240** after 16, **0** after 48 and 160.
  Its outcome on an unseen schema is **not safe**: zero-observation
  performance (69/240) trails the untrained random baseline (78/240).
- Quarry/coolant persistent-memory harmful TEST actions: **0** at each
  inspected checkpoint. These worlds have deliberately separable
  engineered feature rules.
- Across six independently run seeds, **3,120** unique first-action
  actor-generated TRAIN observations: **1,054 harmful**, **1,242
  productive**, **824 neutral**, broken down as quarry 360 harmful
  of 1,080 actions; coolant 352 harmful of 1,080; relay 342 harmful
  of 960. Actor interventions are NOT counted separately for each
  checkpoint, baseline, or read-only replay evaluation.
- Learner-initiated TRAIN acquisition actions: **zero**. That does not
  imply consequence-free or authenticated observational data.

### Scientific interpretation

**Demonstrated:** After receiving only 16 distinct relay-family public
outcomes from an independent synthetic actor, the persistent agent
improved from 69/240 to 233/240, and to 240/240 after 48.
Importantly it still solved 240/240 on both previously learned
families, even after the full 160 new-family observations. Checkpoint
round-trips preserve the complete ordered memory.

**Not demonstrated:** The target-only learner matched every single
relay completion exactly; source-family training yielded **no
detectable target-family transfer benefit**. Its one benefit is keeping
different learned schemas accessible from one persistent checkpoint.
Partitioning by pre-engineered feature key sets is a simple
handwritten multi-task mechanism, not semantic abstraction. The
strong performance is confined to small deterministic worlds with
balanced candidate actions and an ideal public progress/damage sensor.

In particular, **D3 genuine novel-family generalization is STILL OPEN**:
the relay world is developer-authored, and the agent needed relay
training events. We have shown **online novel-schema acquisition and
retention**, not zero-shot generalization or a unified independent
intelligence. Earlier collusive observer poisoning remains wholly
unresolved; a falsified but internally consistent event corpus can
still be loaded and learned.

### Next falsifiable steps

1. Create fresh **independent rule-author** tasks with unanticipated
   observation modality and goals; freeze held-out families before
   design selection. Make the old/new schema boundary unavailable as
   a manual training shortcut.
2. Learn transferable *relational invariants* without explicit
   feature-key matching; require benefit versus a target-only agent at
   matched target feedback and carefully account for extra source cost.
3. Evaluate A→B→C→A→B with drifting/noisy outcomes and distorted
   evidence, especially before any new-schema feedback, preserving
   strict abstention/harm accounting and restart correctness.
