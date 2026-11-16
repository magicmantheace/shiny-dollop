# The Underreach — Lantern Town, live desktop wallpaper

A delving colony town in a great cavern, rendered live in your
desktop background. The cavern is big enough for a small
settlement: at its north end the **Surface Gate** stands in the
rock, and below it the founding town — the **Deep Ledger** at its
civic heart, a converter forge, chandlery, charcoal kiln, tailor
and herbalist benches, the sealed food store, cots and a hauler's
cart — all of it threaded by the **lantern network**, the colony's
streets of light. Beyond the town's core lie named districts of
open ground — Workshop Row, the Residential Edge, the South
Meadow, the Deep-Ward — surveyed and empty, waiting for the
settlement to grow.

Gloam Rats scurry the network, Frontier Bearers amble it with
their loads, delvers walk between the lantern pools, and a Gloam
Lurker keeps to the dim rim. Creatures travel node to node along
the network like the game's nav graph, dwell in the light, and
leave through the gate or into the dark. Beyond the lantern
pools: cave dark, dust motes, spore shimmer over the fungal
terraces.

Built with three.js (vendored, no build step, no network calls)
and packaged for [Lively Wallpaper](https://www.rocksdanister.com/wallpaper/)
on Windows. Sibling to
[`projects/campfire-wallpaper/`](../campfire-wallpaper/); every
model is a Game Asset Builder catalogue asset, copied
byte-for-byte (see `docs/MUSE_HANDOFF.md` for sha256s).

## The roster rule (owner, 2026-11-16)

**This wallpaper must eventually include at least one copy of
every Game Asset Builder asset as it is created and passes its
gates.** v1 carries the full completed initial set — the
Underreach queue #1–#28 and #30, the Cart extra, and the four
pre-queue Underreach catalogue assets (39 models). Parked assets
(#29 ore face, #31 crystal cluster) join only when they complete
and pass their gates; future queue assets (#32 onward) are added
as they complete. The roster is data-driven — `js/roster.js`
(what exists) + `js/layout.js` (named plots in named zones,
where it stands) — so adding an asset is a row in each file plus
its GLB in `assets/`. Never silently drop an asset for
performance: if the roster breaks the perf budget, report it
with numbers (see `docs/TEST_PLAN.md`).

## Town layout & the future living world

The layout is a **town state**, not scattered coordinates:
zones, plots keyed by id, and the lantern network graph live in
`js/layout.js`, shaped so a future living-world simulation
(phase 2 — discussed with the owner, **not commissioned**)
could drive settlement growth plot by plot by supplying new
plot → asset assignments. This build renders the founding state
and talks to nothing.

## Install in Lively (Windows) — LATER, needs the owner's go

Deployment has **not** happened: v1 was built and verified on
the build VM only, and the owner's PC is busy. When the owner
says go:

1. Sync this folder to the PC (e.g. pull the
   `underreach-wallpaper/v1` branch in the PC checkout) —
   `projects/underreach-wallpaper/`, self-contained, ~475 MB
   (39 catalogue GLBs).
2. Open Lively → **Add Wallpaper** → drag the
   `underreach-wallpaper` folder onto the Lively window (or
   Browse to the folder containing `LivelyInfo.json`).
3. "The Underreach — Lantern Town" appears in the library with
   a preview; click it to apply.
4. To remove: right-click the wallpaper in Lively → Delete, or
   pick a different background.

## Preview without Lively

Serve the folder over HTTP (ES modules don't load from
`file://`) and open `index.html` in Chrome/Edge:

```
python3 -m http.server 8945 --directory projects/underreach-wallpaper
# → http://127.0.0.1:8945/
```

Add `?harness=1` for the verification seams used by
`docs/TEST_PLAN.md`.
