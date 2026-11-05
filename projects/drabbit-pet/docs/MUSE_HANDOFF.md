# Drabbit Pet — Muse Handoff

## What this project is

A Tamagotchi-style virtual pet: the renfaire drabbit (furry winged
dragon-rabbit, Imaginarium Galleries shoulder-puppet style). One pet,
two apps — an Electron desktop pet that owns the pet and its save, and
a Kotlin Android companion that connects to it. Both are driven by one
framework-free TypeScript pet brain in `core/`. Full design:
[PET_DESIGN.md](PET_DESIGN.md) (simulation spec) and
[DESIGN.md](DESIGN.md) (architecture + companion protocol as built).

## Current state (2026-11-04)

**P0 — foundation + design: DONE on this branch.**
README, AGENTS.md, PET_DESIGN, DESIGN, TEST_PLAN, this handoff,
monorepo layout (`core/`, `desktop/`, `android/`, `assets/` with
placeholder READMEs for unbuilt slices), root README registration.

**P1 — pet brain (`core/`): DONE on this branch.**
TypeScript, strict, zero runtime dependencies (devDeps: typescript,
vitest, tsx, @types/node). Deterministic 1-minute-step simulation:
needs/health/care-score model, egg→adult lifecycle, care-shaped adult
forms (radiant/content/scruffy), messes, sickness, death + lineage,
canonical JSON persistence with schema versioning and a migration
stub, append-only capped event log, headless demo.

**P2 — desktop pet (`desktop/`): DONE on this branch** (verified by
Nyx firsthand per the queue log; the owner's first visual check on
Windows is still open).
Electron 45 + React 19 + TS strict + Vite, consuming `drabbit-core`
via a `file:` dependency — **the core is unchanged**; no core edits
were needed. Main process owns the one pet state: save in Electron
`userData` (`drabbit-save.json`, atomic temp+rename writes; a corrupt
save is renamed aside, never destroyed, and a fresh egg starts), a
5 s tick service that advances with `Date.now()` (the shell is the
only place clocks live) and persists only on change, plus a final
advance+persist on quit. Frameless transparent always-on-top pet
window (220×220, bottom-right start) roaming the work-area bottom via
a pure, tested planner — long sits, short hops, paused while the pet
sleeps / the care panel is open / tray pause is on. Care-panel
window (single instance, hide-on-close), tray icon (Show pet / Care
panel / Pause roaming / Quit), single-instance lock. Typed IPC
(`pet:getSummary` / `pet:action` / `pet:events` / `pet:openPanel` +
`pet:changed` / `pet:roamState` pushes), contextIsolation on,
nodeIntegration off, sandboxed preload, hand-rolled payload
validation; core `PetError`s return as IPC error results. The pet is
rendered as a hand-drawn inline SVG (all six fur variants, adult-form
flavour, idle/hop/sleep/eat/play/sick/egg/ghost animation states) —
**v1 placeholder art**, structured for later sprite replacement.
Packaging (electron-builder) is future work, out of P2 scope.

**P3 — companion server (`desktop/src/main/server/`): DONE on this
branch** (pending Nyx verification). Node stdlib `http` only, no new
dependencies, core unchanged. The server is a second front door to
the same pet: it is constructed over the PetService with the **one
shared action dispatcher** (`action-dispatch.ts`, now used by IPC
too — the P2 IPC handler was refactored onto it), so remote and
panel actions have identical validation and error codes. Settings
live in `userData/companion.json` (own store, SaveStore pattern;
defaults `enabled: false`, `0.0.0.0:8931`, token `''`). The token
(32 random bytes, base64url) is minted lazily on first enable and
compared in constant time; regenerating restarts the server so the
old token dies immediately. Config changes apply via stop+start
under a CompanionService; a bind failure lands in a panel-visible
`error` state, never a crash. The pet now tracks an event **cursor**
(a produced-event count maintained by PetService) that backs
`GET /v1/events?since=`; two deliberate divergences from the P0
protocol draft — the `{ kind }` action payload (shared with IPC
instead of core action names + variant) and the count cursor
(instead of timestamp filtering) — are recorded with reasons in
DESIGN.md, as is the one behaviour the draft implied but didn't
spell out: `new-egg` is recognized and refused remotely with
**403 `desktop_only`**. The care panel gained a Companion section
(status/address, enable toggle, masked token with Show/Copy/
Regenerate, live request/auth-failure stats) over three new typed
IPC channels (`companion:getState` / `setEnabled` /
`regenerateToken`). Default-disabled means the smoke profile never
opens a port.

**P4 — Android companion (`android/`): BUILT as complete sources on
this branch** (pending Nyx verification; the app itself has never
been compiled — see the verification split below). Kotlin + Jetpack
Compose, single `:app` module (`ca.wilkins.drabbit`, minSdk 26,
SDK 35), zero third-party runtime dependencies beyond
AndroidX/Compose BOM (networking is `HttpURLConnection`, JSON is
`org.json`). Layers: `net/` (transport interface + production impl,
`DrabbitClient` with the protocol's full error mapping — 401
BadToken, 403 DesktopOnly, 409 StateError carrying the core's code +
message, other HTTP ServerError, IOException Unreachable, bad body
MalformedResponse), `model/` (wire model matching
`desktop/src/shared/api-types.ts` field-for-field, org.json parsing,
`CareRules` mirroring the core's action guards including
clean-while-asleep and play's energy floor), `data/`
(ConnectionSettings normalization + SharedPreferences store), `ui/`
(PetViewModel — connect, 15 s foreground polling with the count
cursor, actions, offline last-known-state; Connect + Pet screens;
the drabbit drawn with Compose Canvas in the desktop's fur palette).
`new-egg` is never offered (desktop-only by design). Cleartext HTTP
is explicitly enabled in the manifest — the companion is a
token-gated LAN/Tailscale service, documented in android/README.md.
The Gradle wrapper ships as `gradle-wrapper.properties` only: the
wrapper JAR/scripts could not be generated here (no JDK/Gradle);
Android Studio creates it on first open.

**The v1 slice queue (P0–P4) is now complete.** What remains is
owner-side verification, listed below.

## Verified (this Linux VM, Node v24.22.1, 2026-11-04)

- `npm --prefix core test` → **46 tests, 46 passed** (vitest 3.2.7):
  decay math per stage, asleep modifiers, egg rules, stage thresholds,
  offline catch-up == live ticking **byte-identical** across 1-jump /
  hourly / minute chunking over 24 h, every action's effects and error
  paths, sickness onset/cure, messes, neglect death (~14.8 h, cause
  sickness — probed and pinned as a regression test), adult forms in
  all three care bands, save round-trip byte-identical, bad-save
  rejection.
- `npm --prefix core run typecheck` and `npm run build` → clean under
  `tsc` strict.
- `npm --prefix core run demo` → exit 0; a scripted caretaker raises
  "Pip" from egg to a **radiant** adult over ~19 simulated hours,
  printing a diary of hatches, stage changes, messes, sleeps, and
  status lines (35 events, 3,253-byte save).
- `npm --prefix desktop run typecheck` → clean (main, preload,
  renderer, tests — all `tsc` strict).
- `npm --prefix desktop test` → **29 tests, 29 passed** (vitest
  3.2.7): save-store round-trip / missing / corrupt-recovery (bytes
  preserved aside), tick persistence (writes only on change, never
  for a dead pet, scheduler wiring), roaming planner (bounds under
  adversarial randomness, blocked contexts never move, hop→arrive→
  sit), IPC action mapping (every UI kind → the right core action;
  wrong-stage actions raise the core's typed errors) + payload
  validation, and visual-state derivation.
- `npm --prefix desktop run build` → clean: core `tsc`, desktop
  `tsc` (main + preload), Vite production build of both windows.
- `npm --prefix desktop run smoke` → **SMOKE_OK**: the real Electron
  45 binary launched headlessly under Xvfb against a throwaway
  userData, created and persisted a fresh save (canonical JSON with
  the egg's `created` event), and loaded both production windows.
- P3 (same VM, after the companion build): `npm --prefix desktop run
  typecheck` → clean; `npm --prefix desktop test` → **50 tests, 50
  passed** (the 29 above + 21 companion: config store incl.
  corrupt-recovery and injected-fs, real-HTTP auth/status/action
  parity with IPC, `desktop_only` refusal, events-cursor polling
  semantics, protocol edges 400/404/413, token regeneration
  invalidating the old token, stop-frees-port, bind-failure error
  state); `npm --prefix core test` → still **46/46** (core
  untouched); `npm --prefix desktop run build` → clean;
  `npm --prefix desktop run smoke` → **SMOKE_OK** (companion
  disabled by default in the smoke profile).

- P4 wire contract (same VM, 2026-11-04): with **no JDK/Android SDK
  on this VM** (`java`/`sdkmanager`/`adb`/`kotlinc`/`gradle` all
  absent — checked first, per the queue rules), the Gradle build
  could not run. Instead the compiled P3 server (`desktop/dist`) was
  booted headlessly in Node over a temp-dir PetService with a dummy
  token and driven over real HTTP: **13 raw responses captured
  verbatim** as the Android unit tests' fixtures (egg-ready + baby +
  dead status, hatch + feed-meal actions, events bootstrap/delta/
  caught-up/full-window, 401/403/409/404 error bodies). An
  independent strict shape check (Python) passed on all 13: exact
  PetSummary key set (16 fields, matching `summary.ts`), needs key
  set, `{t, kind, detail}` events, count-cursor semantics
  (bootstrap 4 → delta 5 → caught-up empty, `since=0` = 5 events),
  and the four error codes. The Kotlin sources passed a
  delimiter-balance smoke check only.

## NOT verified (no evidence exists yet)

- The desktop pet **on Windows**: transparency, always-on-top over
  real windows, tray behaviour, roaming feel, multi-monitor,
  high-DPI. The Xvfb smoke proves launch + window load + save
  creation on Linux — not the Windows desktop experience. That is
  the owner's first-visual-check checkpoint.
- The Android app **compiled or run, anywhere**: no JDK/Android SDK
  exists on this VM, so there is no Gradle build, no green unit-test
  run, and no device run yet. The JVM tests (client parsing + error
  mapping over the captured fixtures, events cursor, CareRules
  matrix, settings normalization, age formatting) ship as sources;
  their first execution is `./gradlew :app:testDebugUnitTest` in the
  owner's Android Studio. Any compile fallout is P4 follow-up.
- The companion server **from a real phone**: pairing, LAN and
  Tailscale reachability, and Windows Firewall behaviour on first
  enable are owner-device evidence; the VM tests prove the protocol
  over loopback only.
- Sprite assets: the pet is inline SVG on desktop and Canvas shapes
  on Android (v1 placeholder art in both);
  `assets/` holds only the generated app/tray icon.

## Working rules for the next agent

- Repo root `AGENTS.md` + project `AGENTS.md` bind; the core's
  determinism invariant (no clocks, no hidden tick counters, hashed
  rolls) is a hard rule, not a style preference.
- PET_DESIGN.md and `core/src/constants.ts` must change together.
- Slices land in queue order (P2 desktop → P3 server → P4 Android),
  each verified before the next; keep this file's verified/unverified
  split honest after every slice.

## 2026-11-05 — bridge link (post-v1, owner's request)

The owner asked for his desktop pet to be able to interact with the
new Muse PC Bridge avatar window. Shipped as a one-way link:

- `desktop/src/shared/bridge-reaction.ts` — defensive parsing of
  the bridge's `display-state.json` + the pure change→reaction
  mapping. `desktop/src/main/bridge-link.ts` — a polling service
  (2 s, injected reader/scheduler) that broadcasts reactions over
  the new `pet:bridgeReaction` channel; the pet window shows a
  bubble (6 s) and plays the bounce transient on `celebrate`.
- The sim is untouched: no core changes, no save changes, no new
  inputs to the pet's world — reactions are main/renderer
  presentation, so determinism and offline catch-up are unaffected.
  The link holds no bridge credentials and opens no sockets; the
  bridge gains no new inputs from the pet. Path resolution:
  `DRABBIT_BRIDGE_STATE_FILE` → `D:\shiny-dollop\...` checkout →
  home-relative checkout.
- Verified: VM desktop suite **63/63** (was 50; +12 bridge-link,
  +1 visual-state), core **46/46**, full build clean. Owner-PC
  smoke with a throwaway profile + staged state file: bubbles for
  `working` and `alert` captured from the real pet window; idle
  first-sighting correctly quiet. The owner's real pet/save were
  never run or touched.
- Not yet live in production: the bridge still runs its console
  supervisor form, which does not publish `display-state.json`.
  The link activates by itself the day the bridge's GUI form runs
  (owner's separate call) — no pet-side change needed then.

## Next step

The v1 queue is complete; everything left is owner-side
verification, in any order: (1) first visual check of the P2 pet on
the owner's Windows PC (look, roaming feel, transparency);
(2) open `android/` in Android Studio — accept the wrapper creation,
run `./gradlew :app:testDebugUnitTest`, fix any compile fallout as
P4 follow-up; (3) install on the Pixel 9a and do the first real
pairing against the desktop companion over LAN or Tailscale.
Future-work candidates already recorded: electron-builder packaging
(P2), PNG sprite art replacing the v1 placeholder art, title-bar
perching.
