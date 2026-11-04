# MUSE_HANDOFF — Milky Way Colonization Simulator

State as of **2026-11-04**, end of slice S0. Branch
`milky-way-colonization-sim/foundation` (local commits only — not
pushed, no PR; Adam reviews first).

## What S0 delivered

1. **Project foundation** — README, AGENTS.md (binding data-integrity
   rules), REQUIREMENTS, `docs/DESIGN.md` (the spec: Adam's 5 founding
   decisions + 7 §11 rulings, incl. §11.7 default-to-Sol), root README
   registration row.
2. **Data pipeline** (`pipeline/`, Rust, **zero third-party crates**) —
   builds the game star table from HYG v4.4 + NASA Exoplanet Archive
   pscomppars:
   - 119,614 HYG rows → filter `0 ≤ dist < 100,000 pc` → 109,390
     usable; equatorial→galactic J2000 rotation; pc→ly (×3.26156);
     heliocentric frame, Sol at origin.
   - Names: proper → Bayer/Flamsteed → Gliese → HIP → HD → HR → HYG id.
   - Temperature/mass derived from spectral class / mass–luminosity,
     flagged `derived` per record (HYG has neither column).
   - Archive merge: 713 hosts matched by designation (HYG proper/bf/
     Gliese/HIP/HD/HR indexes + GL↔GJ alias), 104 by coordinates
     (uniform 2 pc grid, ≤1.0 pc), 4,003 inserted as real rows from
     archive coordinates (flagged `source: exoplanet-archive`), 27
     skipped (no usable position, counted in the report).
   - Output: **113,393 stars, 6,424 planets, `stars.bin` 6,882,528
     bytes**, deterministic (byte-identical rebuilds), read-back
     verified in the pipeline itself. `data/manifest.json` +
     `data/SOURCES.md` committed; the .bin and catalog caches are
     git-ignored regenerable artifacts.
   - Binary format contract: `pipeline/src/table.rs` (64-byte header,
     48-byte star records, 32-byte planet records, string table).
     The GDScript reader mirrors it exactly — change both together.
3. **Godot viewer** (`viewer/`, Godot 4.7.2, GDScript) — ArrayMesh
   `PRIMITIVE_POINTS` + shader (spectral colours; magnitude→point
   size via colour alpha; unknown magnitude gets a neutral size),
   orbit/fly camera (drag/wheel/WASD/QE), **Go to Sol** (button or F),
   click-pick via grid ray-walk with an info panel (name, class,
   distance, teff/mass with derived markers, planet list).
   Headless `--verify` passes all assertions (see TEST_PLAN.md §3);
   `--measure` mode loads any table and reports load time/memory.
4. **~1M-star measurement** — AT-HYG v4.0 resolved (Codeberg
   `astronexus/athyg`, `data/athyg_40.csv.gz`; LFS-backed; the
   README's `athyg_v40` name 404s). Nearest-1M table: 52,014,311
   bytes, viewer load 739 ms / 173.8 MB static. Numbers in
   TEST_PLAN.md §4. The shipping map stays HYG ~120k per ruling
   §11.6; the 1M option is measured and viable for a later decision.

## Test state

- `cargo test`: **22/22 pass** (unit + fixture integration, offline).
- Godot `--verify`: **all VERIFY_PASS, exit 0** (verbatim output in
  TEST_PLAN.md).
- Pipeline determinism: two builds → identical SHA-256.

## Gotchas found in S0 (don't rediscover these)

- GDScript `class_name` types are invisible in a bare headless run
  with no editor import pass — the viewer preloads `star_table.gd`
  instead. Keep it that way.
- HYG's "distance" for 10,224 rows is a ≥100,000 pc placeholder (not
  an error value of −1); filter on it or the galaxy gets a fake shell.
- Archive hostnames rarely match HYG designations directly (713 of
  4,847); coordinate matching and insertion carry the merge. Most
  real exoplanet hosts are simply not in HYG.
- TRAPPIST-1 is an inserted host, not an HYG star — if a future
  change drops inserted hosts, the verify catches it (7 planets).
- Inserted hosts have absmag 0 (= unknown). Any magnitude-driven
  logic must treat 0 as missing, never as "brightest".

## Unverified / owner-PC gates

- FPS and rendering feel on Adam's RTX 3060 (no FPS claims made).
- Interactive picking/orbit with a real mouse; Windows export.
- S1 design question parked by Adam: offline progression (galaxy
  advancing while the game is closed) — settle in the S1 design pass.

## Next slice

**S1 — Sim core (headless)**, only on Adam's go-ahead: Rust core with
galaxy state, daily tick + monthly settlement, one civilization
colonizing (survey/claim/found/grow), fuel-range movement, save/load,
scripted campaign tests. The viewer stays a viewer until S2 wires
the frontend to the core.
