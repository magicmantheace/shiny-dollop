# Drabbit Pet

**Status:** IN DEVELOPMENT — P0 (foundation + design), P1 (pet-brain
core), and P2 (Electron desktop pet) built on a review branch; the
companion server (P3) and Android app (P4) are still planned. See
[the handoff](docs/MUSE_HANDOFF.md) for the honest
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

## Start point for agents

Read the repository-root `AGENTS.md`, then [this project's
instructions](AGENTS.md), [PET_DESIGN.md](docs/PET_DESIGN.md) (the
simulation spec), and [MUSE_HANDOFF.md](docs/MUSE_HANDOFF.md)
(current state, what's verified, what's next).
