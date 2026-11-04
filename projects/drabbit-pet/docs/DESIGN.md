# Drabbit Pet — Architecture Design

One pet, two apps, one brain. The simulation lives in a framework-free
TypeScript core that both hosts use identically; there is exactly one
pet state at any time, owned by the desktop app, and the Android app is
a remote window onto that same pet — never a second copy.

```
┌─────────────┐      ┌──────────────────────────────┐      ┌─────────────┐
│ Android app │ HTTP │ Desktop app (Electron)       │      │  core/      │
│ (Kotlin, P4)├─────►│  ├─ pet window (React, P2)   │ uses │  pet brain  │
│ status+care │token │  ├─ companion server (P3) ───┼─────►│  (TS, P1)   │
└─────────────┘      │  └─ save file on disk        │      └─────────────┘
                     └──────────────────────────────┘
```

## Components

### `core/` — the pet brain (P1, this build)

Framework-free TypeScript, zero runtime dependencies. Pure functions
over plain-JSON state:

- `createEgg(opts, nowMs)` → initial `PetState`
- `advance(state, nowMs)` → `{ state, events }` — deterministic
  fixed-step (1 min) simulation; see PET_DESIGN §10
- actions: `hatch`, `feed`, `play`, `clean`, `putToSleep`, `wake`,
  `giveMedicine` (each takes `(state, nowMs, …)`, advances first, then
  applies), `startNewEgg(envelope, opts, nowMs)`
- persistence: `createSave`, `serialize`, `parse`, `migrate`

The core never reads a clock, never touches the filesystem, and knows
nothing about Electron, HTTP, or Android. Any host that can call it
with a timestamp can run the pet.

### `desktop/` — Electron shell (P2, planned)

Electron + React + TypeScript, following the repo's app pattern.
Transparent always-on-top pet window rendering sprite states from core
state (idle/hop/sleep/eat/happy/sick/perch), a care panel wired to core
actions, a tray icon, and the save file. On launch it loads the save
and calls `advance` once with the current time — offline progression
falls out of the time model for free.

The desktop app **owns** the pet: it is the only writer of the save.

### Companion server (P3, implemented)

An HTTP server inside the desktop app exposing the one shared pet to
the phone (`desktop/src/main/server/`). Pure Node stdlib `http`,
Electron-free: it is constructed over the same PetService the care
panel drives, through the one shared action dispatcher, so a remote
action and a panel action are the same operation with the same error
codes. Settings live in `companion.json` beside the save (atomic
writes, corrupt-file recovery like the save's). The server is
**disabled by default**; enabling it in the care panel mints the
pairing token (32 random bytes, base64url) and starts it.
Configuration changes take effect by restarting the server; a bind
failure (e.g. port in use) surfaces as a panel-visible error state,
never a crash. Bind address is configurable (localhost / LAN /
Tailscale — the owner's network, the owner's choice); the token is
the gate.

### `android/` — Kotlin client (P4, implemented)

Kotlin + Jetpack Compose. A thin client: connection setup (address +
token), a status screen (Canvas-drawn drabbit, needs, stage, mood),
and care buttons that POST actions to the companion server. It holds
**no** simulation and **no** pet state of its own beyond what's on
screen. It polls status + cursor-delta events every 15 s while in
the foreground, keeps last-known state under an offline banner when
the PC is unreachable, and implements the protocol below exactly
(its unit-test fixtures are raw responses captured from the real P3
server). Built in Android Studio on the owner's PC — see
`android/README.md`.

### `assets/` — art (P2, planned)

Sprite PNGs and other replaceable art files. Assets are referenced by
name from the desktop app; the core contains no art paths at all.

## Save format

One JSON document, written by the desktop app (atomic replace):

```jsonc
{
  "schemaVersion": 1,
  "pet": { /* PetState — see core/src/types.ts */ },
  "lineage": {
    "generation": 1,
    "ancestors": [
      { "name": "…", "fur": "royal", "adultForm": "content",
        "bornAt": 0, "diedAt": 0, "deathCause": "neglect" }
    ]
  }
}
```

`serialize` is canonical (recursively key-sorted), so identical states
produce byte-identical saves — diffs and tests can rely on it.
`parse` validates the shape, checks `schemaVersion`, and routes older
versions through `migrate` (currently a stub: version 1 is the only
version; unknown *newer* versions are rejected, never guessed at).

`PetState` itself is plain JSON: identity (`id`, `name`, `fur`),
lifecycle (`stage`, `adultForm`, `bornAt`, `hatchedAt`, `ageMs`,
`diedAt`, `deathCause`), simulation bookkeeping (`lastTickAt`,
`stepCount`, `readyToHatch`), condition (`needs`, `health`,
`careScore`, `mood`, `asleep`, `sick`, `sickSince`, `messes`), and an
append-only `events` log capped at 500 entries (oldest dropped).

## Companion wire protocol (as implemented in P3)

Base: `http://<desktop>:<port>/v1` (default port **8931**), JSON
bodies, `Authorization: Bearer <pairing-token>` on every `/v1/*`
request (constant-time comparison; failures are 401 and counted in
the server stats the care panel shows). Errors:
`{ "ok": false, "error": { "code": "…", "message": "…" } }` with a
matching HTTP status — 401 unauthenticated, 400 bad request
(`bad_json`, `bad_payload`, `bad_query`), 403 desktop-only action,
409 invalid-for-state (the core's `PetError` code, unchanged), 413
body over 64 KB (`too_large`), 404 unknown route (`not_found`), 500
`internal`.

The server advances the pet to server-now before status and events
responses (actions advance inside the core, as everywhere), so
clients always see current state.

| Endpoint | Body / query | Response |
| --- | --- | --- |
| `GET /v1/status` | — | `{ ok, serverNow, pet: PetSummary }` |
| `POST /v1/actions` | `{ "kind": <ActionKind> }` — the same payload the care panel's IPC uses: hatch, feed-meal, feed-snack, play, clean, sleep, wake, medicine, new-egg | `{ ok, serverNow, pet: PetSummary, events: PetEvent[] }` |
| `GET /v1/events?since=<n>` | `since` = an event cursor (below); omit it to bootstrap | `{ ok, serverNow, events: PetEvent[], cursor }` |

**Event cursor.** The cursor is a *count*: the total number of
events produced in the current pet-line's log since the desktop
process started counting (anchored at the loaded log's length on
startup — cursors are per-desktop-run; a stale cursor at or beyond
the current total simply returns no events plus the fresh cursor, so
pollers resync). The event at log index `i` has sequence
`cursor - log.length + i`; `since = n` returns the retained events
with sequence ≥ n, oldest first, plus the new `cursor` to poll with
next time. `since = 0` returns the whole retained window (the core
caps the log at 500; events older than the window are gone, and a
`since` predating the window returns the whole window). Omitting
`since` returns no events and just the current cursor — the polling
bootstrap. P4 polls: bootstrap once, then `since = <last cursor>`.

`PetSummary` is the presentation subset of `PetState` (shared with
the IPC surface, `desktop/src/shared/summary.ts`):
`{ id, name, fur, stage, adultForm, mood, needs, health, careScore,
ageMs, asleep, sick, messes, readyToHatch, generation, deathCause }`.
The full `PetState` (step counters) stays server-side.

`startNewEgg` is deliberately **not** remotely performable —
starting the next generation is a desktop-side decision. Unlike the
draft, the wire format does recognize the `new-egg` kind (it is part
of the shared action vocabulary) and refuses it explicitly:
**403 `{ code: "desktop_only" }`**, so a client gets a precise,
testable answer instead of a generic bad-action error.

### Divergences from the P0 draft, and why

- **Action payload:** the draft used core-level names
  (`{ action: "feed", variant: "meal" }`); the implementation uses
  the care panel's `{ kind }` vocabulary (`feed-meal`, `sleep`, …).
  One payload shape means one validation function and one dispatch
  module shared by IPC and HTTP — no translation layer to drift.
- **Events addressing:** the draft filtered by timestamp
  (`since=<ms>`, `t > since`). Event timestamps are sim-minute
  granular, so several events share a `t` and a timestamp cursor can
  skip or repeat them; the count cursor above is exact.
- **`serverNow` on the events response** and the **403/413** statuses
  were added for the same reason: precise, testable answers.

## Time model

See PET_DESIGN §10. In one line: state is a pure function of the save
plus timestamps; the sim advances in fixed 1-minute steps with rolls
hashed from `pet id + step index`, so live ticking and offline
catch-up are the same computation.

## What is deliberately out of scope (v1)

- No cloud, no accounts, no sync: the pet lives on the owner's PC.
- No multiplayer / visiting pets.
- No in-app purchases, no ads, no telemetry.
- Android never simulates: if the desktop is off, the phone sees the
  last state the server reported (and the pet keeps aging on paper —
  it will be caught up the next time the desktop runs).
