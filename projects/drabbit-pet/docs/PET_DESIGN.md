# Drabbit Pet — Pet Design Bible

This document is the **specification** for the pet simulation. The numbers
here are the numbers `core/src/constants.ts` implements; if the two ever
disagree, that is a bug. Behavioural/visual notes for the desktop and
Android slices (perching, sprite states) are marked as presentation —
they never affect the simulation.

## 1. The creature: the renfaire drabbit

The pet is a **drabbit** in the style of the Imaginarium Galleries
renaissance-faire shoulder puppets (Albert Alfaro's "Drabbits"): a small
**furry** dragon–rabbit. Not scaly, not monstrous — a plush, bright,
slightly ridiculous companion animal.

Defining features:

- Rabbit body, long upright **floppy-tipped ears**
- A pair of small curved **dragon horns**
- **Cloth wings** on the back — big enough to flap and glide-hop, too
  small for true flight
- A **long furred tail**, expressive, usually curled
- Bright, saturated **fur** (never natural rabbit colours)
- Big eyes, tiny fangs, permanent look of mild mischief

Presentation behaviour (desktop slice): the drabbit idles at the bottom
of the screen, hop-walks around, and **perches** — on the taskbar and on
top of window title bars — the way the puppets perch on a shoulder. It
sleeps curled up with its tail over its nose.

### Fur colour variants

Chosen when an egg is created; purely cosmetic, fixed for life.

| Variant id | Display name | Notes |
| --- | --- | --- |
| `ember` | Ember Red | Deep red fur, gold horns |
| `meadow` | Meadow Green | Green fur, cream belly |
| `royal` | Royal Purple | The classic faire colour |
| `sky` | Sky Blue | Pale blue, white wing cloth |
| `sunset` | Sunset Gold | Golden-yellow, orange tail tip |
| `rainbow` | Rainbow | Multicolour patches, rare and proud of it |

## 2. Lifecycle

| Stage | Duration (simulated) | Notes |
| --- | --- | --- |
| `egg` | 10 minutes incubation | No needs decay. After incubation the egg wiggles (`readyToHatch`) and waits for the `hatch` action. |
| `baby` | 60 minutes | Fastest decay. Helpless and dramatic about it. |
| `child` | 6 hours | Stage durations are cumulative from hatch: child begins at 60 min of age. |
| `teen` | 12 hours | Teen begins at 7 h of age. |
| `adult` | Indefinite | Adult begins at 19 h of age. Adult form is fixed at this transition by care score (§7). |
| `dead` | — | Reached when health hits 0 (§6). The save keeps the record; `startNewEgg` begins the next generation. |

Stage is a function of age since hatch (`ageMs`): baby < 1 h ≤ child <
7 h ≤ teen < 19 h ≤ adult.

## 3. Needs model

Four needs, each 0–100, plus health (0–100, §6). At hatch:
hunger 80, happiness 80, energy 100, cleanliness 100, health 100.

### Decay per minute while awake

| Need | Baby | Child | Teen | Adult |
| --- | --- | --- | --- | --- |
| Hunger | −0.30 | −0.22 | −0.20 | −0.16 |
| Happiness | −0.22 | −0.16 | −0.14 | −0.11 |
| Energy | −0.25 | −0.18 | −0.16 | −0.13 |
| Cleanliness | −0.10 | −0.08 | −0.07 | −0.06 |

### While asleep

- Energy **+1.50 / min** until full.
- Hunger, happiness, cleanliness decay at **30%** of the awake rate.
- A pet whose energy reaches **≤ 2** while awake falls asleep on the
  spot (exhaustion, event `fell_asleep`). It wakes on its own at
  energy 100 (event `woke`), or early via the `wake` action.

### While sick

- Happiness decays an extra **−0.10 / min**.
- Health decays (§6). Medicine is the only cure.

## 4. Messes

- While awake (post-hatch), each minute carries a **0.4%** chance of a
  mess; a very full belly (hunger ≥ 95) triples it to 1.2%.
- A mess: `messes` +1, cleanliness −8 immediately, event `mess`.
- `messes` also raise sickness risk (§5). The `clean` action clears all
  messes.

## 5. Sickness

- A pet is at risk each minute while **any** of: hunger = 0,
  cleanliness < 25, or messes ≥ 3. Risk is **0.2% per minute** while a
  condition holds.
- Onset: `sick = true`, event `sick`. There is no spontaneous cure;
  `giveMedicine` cures (event `cured`).
- Sickness is the fastest route to death if ignored (§6).

## 6. Health and death

Health is integrated per minute from conditions (not a pure average of
needs — a pet can be hungry and healthy, briefly):

| Condition (per minute) | Health Δ |
| --- | --- |
| Hunger = 0 (starving) | −0.12 |
| Cleanliness = 0 (filthy) | −0.04 |
| Sick | −0.08 |
| Recovery: not sick, hunger > 25, cleanliness > 25 | +0.06 |

Total neglect therefore kills in roughly a day: hunger empties in
~6 h, after which starvation (and usually sickness) drain health in
~8–14 h. There is no separate "neglect timer" — prolonged zero-need
neglect kills through health, and the death event records the cause:
`sickness` if sick at death, else `neglect` if any need was 0, else
`failing health`.

Death: stage becomes `dead`, `diedAt` and `deathCause` are recorded,
event `died`. The dead pet's record moves into the save's lineage when
`startNewEgg` is called; generation increments per egg.

## 7. Care score and adult forms

`careScore` (0–100) is the rolling measure of care quality. It starts at
**70** at hatch and moves:

| Cause | Δ |
| --- | --- |
| Per minute with any need at 0 | −0.04 |
| Per minute with any need < 20 (and none at 0) | −0.015 |
| Per minute with all needs ≥ 50 | +0.01 |
| Feeding a meal while hunger < 60 | +1.5 |
| Feeding a snack while hunger < 60 | +0.5 |
| Playing while happiness < 60 | +1.5 |
| Cleaning while messes > 0 | +2 |
| Cleaning while cleanliness < 50 (no messes) | +0.5 |
| Giving medicine while sick | +3 |
| Putting to sleep while energy < 30 | +1 |
| Overfeeding (§8) | −1 |
| Snack while hunger ≥ 90 | −1 |

At the teen → adult transition, the score fixes the adult form:

| careScore | Adult form | Look |
| --- | --- | --- |
| ≥ 70 | **Radiant Drabbit** (`radiant`) | Gleaming brushed fur, polished horns, wings held high. Care pays visibly. |
| 40 – 69 | **Content Drabbit** (`content`) | The standard happy faire drabbit. |
| < 40 | **Scruffy Drabbit** (`scruffy`) | Matted patches, droopy ears, one wing always slightly crumpled. Alive, loved-ish, judging you. |

## 8. Care actions

All actions are validated: they fail with a typed error on an egg
(except `hatch`), on a dead pet, while asleep (`feed`, `play`), or when
their precondition isn't met (`giveMedicine` on a healthy pet).

| Action | Effect |
| --- | --- |
| `hatch` | Egg only, after incubation. Stage → baby, `hatchedAt` set, needs at hatch values. Event `hatched`. |
| `feed` meal | Hunger +35, happiness +2, cleanliness −2. If hunger was > 90: **overfed** — health −3, careScore −1, event `overfed`. |
| `feed` snack | Hunger +8, happiness +5. If hunger was ≥ 90: careScore −1 (treats on a full belly teach bad habits). |
| `play` | Happiness +18, energy −7, hunger −3, cleanliness −2. Requires energy ≥ 10. |
| `clean` | Messes → 0, cleanliness → 100, happiness +1. |
| `putToSleep` | `asleep = true`. Event `fell_asleep`. |
| `wake` | `asleep = false`. Event `woke`. |
| `giveMedicine` | Requires sick. Sick → false, health +6, happiness −2 (it tastes awful), event `cured`. |
| `startNewEgg` | Dead pet only. Archives the pet into lineage, returns a fresh egg envelope, generation +1. |

All numeric results clamp to 0–100 (messes and counters excepted).

## 9. Mood (derived, never stored as truth)

Mood is computed from state after every advance/action, in this order:

1. Dead → `gone`
2. Egg → `waiting`
3. Sick → `sick`
4. Asleep → `asleep`
5. Health < 25 → `frail`
6. Lowest need < 15 → `miserable`
7. Mean of needs ≥ 78 → `joyful`
8. Mean ≥ 58 → `content`
9. Mean ≥ 38 → `okay`
10. Otherwise → `unhappy`

## 10. Time and determinism

- The simulation advances in **fixed 1-minute steps**. All randomness
  (mess and sickness rolls) is derived from a hash of
  `pet id + step index + roll salt`, so the same pet advanced through
  the same steps always gets the same rolls — whether the host ticks
  every minute, or catches up a week of offline time in one call.
- **Offline catch-up is exactly live ticking**: `advance(a→c)` equals
  `advance(a→b)` then `advance(b→c)`, bit for bit, including the event
  stream. Hosts never keep their own tick counters.
- The sim never reads a clock: the current time is always an input.
