# desktop/ — Electron desktop pet (P2)

The drabbit's home. An Electron + React + TypeScript app that owns
the one pet: it loads the save, runs the clock for the clock-free
`core/` brain, renders the pet as a transparent always-on-top window
roaming the screen bottom, and provides the care panel, tray icon,
and (from P3) the companion server.

## Run it

```sh
npm --prefix ../core install   # once: core dev dependencies
npm install                    # in this folder
npm run build                  # core + typecheck + main/preload/renderer
npm test                       # headless unit tests (vitest)
npm run dev                    # vite dev server + Electron (developer loop)
npm run smoke                  # headless launch smoke (Xvfb on Linux)
```

To run the built app directly: `npx electron dist/main/main.js`
(or the electron binary in `node_modules/.bin`). Packaging into a
Windows installer (electron-builder) is **future work**, not part of
P2.

Environment knobs: `DRABBIT_USER_DATA=<dir>` overrides the save
location (default: Electron `userData`; the save is
`drabbit-save.json` there). `DRABBIT_SMOKE=1` is the smoke harness.

## What works (P2)

- **One pet, owned here.** On launch the save is loaded from
  `userData/drabbit-save.json`; a missing save starts a fresh egg,
  and a corrupt save is renamed aside (`drabbit-save.corrupt-*.json`,
  never silently destroyed) before a fresh egg starts — the recovery
  is logged to the console.
- **Ticking.** Every 5 s the pet advances to now via the core
  (offline catch-up is the same call on launch). The save is
  rewritten atomically (temp + rename) only when state changed, and
  once more on quit.
- **Pet window.** Frameless, transparent, always-on-top, 220×220,
  starting bottom-right. It roams the bottom of the primary display's
  work area — long idle sits, occasional short hops — pausing while
  the pet sleeps, while the care panel is open, or when paused from
  the tray. Clicking the pet opens the care panel.
- **The drabbit itself** is a hand-drawn inline SVG
  (`src/renderer/pet/DrabbitSvg.tsx`): furry body, floppy ears,
  horns, cloth wings, curled tail, all six fur variants from
  PET_DESIGN, radiant/scruffy adult-form flavour, and animation
  states — idle bob, hopping, sleeping (breathing + floating Z's),
  eating, playing, sick droop, egg wobble, ghost + gravestone for the
  departed. **This SVG is the v1 art: an honest placeholder**,
  structured so sprite assets can replace it later.
- **Care panel.** Name, stage, generation, age, adult form, mood;
  bars for hunger/happiness/energy/cleanliness/health plus care
  score; mess indicator; action buttons enabled/disabled by the
  core's rules (medicine only when sick, hatch only when the egg is
  ready, feed/play blocked while asleep, new egg only after death);
  invalid actions surface the core's error message in the panel; a
  live event feed (latest 30) updates as ticks and actions land.
- **Tray icon** with Show pet / Care panel / Pause roaming / Quit.
  Single-instance lock; closing windows never quits the app.
- **IPC** is a narrow typed surface (`pet:getSummary`, `pet:action`,
  `pet:events`, `pet:openPanel`, plus `pet:changed` / `pet:roamState`
  pushes) with contextIsolation on, nodeIntegration off, a sandboxed
  preload, and hand-rolled payload validation in main.

## Layout

| Path | Contents |
| --- | --- |
| `src/main/` | Main process: `main.ts` (windows/tray/roaming), `pet-service.ts` (owns state), `save-store.ts` (atomic save + corrupt recovery), `tick-service.ts`, `roaming.ts` (pure movement planner), `ipc.ts` |
| `src/preload/` | Sandboxed preload exposing `window.drabbit` |
| `src/shared/` | IPC channels, API types, summary projection, payload validation |
| `src/renderer/pet/` | The pet window (SVG drabbit + animation states) |
| `src/renderer/panel/` | The care panel |
| `tests/` | Headless vitest suites for the Electron-free modules |

## Verified vs owner-PC

Verified on the Linux VM (Node 24): typecheck, 29 unit tests, the
production build, and a headless Xvfb smoke in which the real
Electron binary launched, created a fresh save, and loaded both
windows. **Not** verified anywhere yet: the pet's actual look and
behaviour on a Windows desktop — transparency, always-on-top over
real windows, tray behaviour, roaming feel, multi-monitor. That is
owner-PC evidence, still to come. See `../docs/MUSE_HANDOFF.md`.
