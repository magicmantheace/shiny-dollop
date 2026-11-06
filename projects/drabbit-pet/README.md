# Drabbit Pet

**Status:** v1 SCOPE COMPLETE on a review branch — P0 (foundation +
design), P1 (pet-brain core), P2 (Electron desktop pet), P3
(companion server), and P4 (Android companion app) are all built.
The Android app is source-complete but was written on a VM with no
JDK/Android SDK: its first compile is the owner's Android Studio
build, and the desktop pet's first visual check on Windows is still
open. See [the handoff](docs/MUSE_HANDOFF.md) for the honest
verified/unverified split.

A Tamagotchi-style virtual pet whose creature is the **renfaire
drabbit** — the furry winged dragon-rabbit of the Imaginarium
Galleries shoulder puppets: bright fur, cloth wings, horns, a long
furred tail, and a professional perch habit.

**One pet, two apps:**

- A **desktop pet** that lives on the PC screen (Electron) — it hops
  around the screen bottom, perches on windows like the puppets perch
  on shoulders, and is cared for from a click-open panel.
- An **Android app** that connects to the desktop pet over the local
  network / Tailscale to check on it and care for it away from the
  desk. Same pet, same state — the phone is a window, not a copy.

Both are driven by one framework-free TypeScript **pet brain**
(`core/`): needs, lifecycle (egg → baby → child → teen → adult, with
the adult form shaped by how well it was raised), sickness, messes,
neglect, death, and the next generation's egg. Time is deterministic —
the pet ages from timestamps, so a week offline catches up in one
advance call, identically to having ticked live.

**Bridge link (2026-11-05):** the desktop pet also *observes* the
Muse PC Bridge's avatar window. The bridge's GUI supervisor
publishes its state (idle / working / session / …) to a local
`display-state.json`; the pet's main process polls that file and the
pet reacts in its window — a bubble ("Pip is watching Muse work",
"⚠ Muse needs attention on the PC") and a happy bounce when a
bridge update lands. Strictly one-way and read-only: the pet holds
no bridge credentials, opens no sockets, and the reactions are
presentation only — the deterministic sim never sees them. If the
bridge runs its console form (no state file), the pet simply never
reacts. Path override: `DRABBIT_BRIDGE_STATE_FILE`.

**Auto care (2026-11-05):** a care-panel switch (persisted in
`auto-care.json`, default off). While on, the app itself keeps the
drabbit out of trouble: it feeds a meal when hunger runs low,
cleans up messes and grime, plays when happiness dips, and gives
medicine when the pet is sick — through the same action dispatcher
the panel and phone use, so auto-care shows in the event log like
any other care. Sleep is never forced (the pet naps and wakes on
its own). Decisions are a pure function of the pet summary
(`desktop/src/shared/auto-care.ts`); the sim never knows.

## Layout

| Folder | Contents | Slice |
| --- | --- | --- |
| `core/` | The pet brain: simulation, actions, persistence, tests, headless demo | P1 |
| `desktop/` | Electron desktop pet (P2) + companion server host (P3) | P2/P3 |
| `android/` | Kotlin companion app | P4 |
| `assets/` | Replaceable sprite/art assets | P2 |
| `docs/` | [Pet design bible](docs/PET_DESIGN.md), [architecture](docs/DESIGN.md), [test plan](docs/TEST_PLAN.md), [handoff](docs/MUSE_HANDOFF.md) | P0 |

## Try it

```sh
npm --prefix core install   # dev dependencies only; the core itself has no runtime deps
npm --prefix core test      # brain vitest suite
npm --prefix core run demo  # scripted egg→adult lifecycle diary

npm --prefix desktop install
npm --prefix desktop test   # desktop headless suites
npm --prefix desktop run build   # build the Electron app into desktop/dist
npm --prefix desktop run smoke   # headless launch smoke (Xvfb on Linux)
```

The Android app builds in Android Studio on the owner's PC (no SDK
on the build VM) — see [android/README.md](android/README.md) for the
pairing walkthrough, build steps, and what was verified without one.

## Start point for agents

Read the repository-root `AGENTS.md`, then [this project's
instructions](AGENTS.md), [PET_DESIGN.md](docs/PET_DESIGN.md) (the
simulation spec), and [MUSE_HANDOFF.md](docs/MUSE_HANDOFF.md)
(current state, what's verified, what's next).
