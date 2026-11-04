# Project instructions — drabbit-pet

These rules apply inside `projects/drabbit-pet/`. The repository-root
`AGENTS.md` wins on any conflict.

## Scope

1. Work only inside this folder. Do not modify other projects or the
   repository root beyond registering this project in the root README
   index.
2. Use project-prefixed branches, commits, and PR titles
   (`drabbit-pet: …`). Do not auto-merge or force-push. The PR stays a
   draft until the owner directs otherwise.

## The core is sacred

3. `core/` is the one pet brain both apps share. It must stay
   **framework-free and UI-agnostic**: no Electron, DOM, HTTP, Android,
   filesystem, or sprite references — plain TypeScript over plain-JSON
   state, zero runtime dependencies.
4. **Deterministic time is a hard invariant.** Pet state is a pure
   function of the save plus timestamps. The sim advances in fixed
   1-minute steps; randomness is hashed from pet id + step index.
   Never call `Date.now()` (or any clock) inside the sim, never keep a
   hidden tick counter in a host, and never add a random source that
   would make offline catch-up differ from live ticking.
5. `docs/PET_DESIGN.md` is the simulation spec and `core/src/constants.ts`
   is its implementation. They must agree; change both together.
6. Art is data: sprite/art assets are replaceable files under
   `assets/` (or the desktop app), referenced by name. Nothing about
   the art is hard-coded into `core/`.

## One pet, one owner of state

7. The desktop app is the only writer of the save file. The Android
   app holds no simulation and no authoritative state; it talks to the
   desktop's companion server (docs/DESIGN.md).
8. The companion token is a secret: never commit it, print it in logs,
   or put it in test fixtures. Tests use obvious dummy tokens only.

## Verification honesty

9. Never claim Windows or Android verification from VM runs. VM tests
   prove core logic and headless builds only; Electron window
   behaviour is owner-PC evidence and Android behaviour is
   owner-device evidence. Record the split in
   `docs/MUSE_HANDOFF.md` after every slice.
10. After substantive changes, run the affected test suites and update
    README / MUSE_HANDOFF / TEST_PLAN with real results (counts and
    platform), separating verified, unverified, and planned work.
