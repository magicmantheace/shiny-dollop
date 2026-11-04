# TEST_PLAN — Milky Way Colonization Simulator

What was actually run for S0, with results. Last updated 2026-11-04.
Nothing in this file is aspirational: every claim below was executed
on this VM during the S0 build.

## 1. Pipeline unit + integration tests (Rust)

```
cd pipeline
cargo test
```

Environment: rustup toolchain `1.99.0-x86_64-unknown-linux-gnu`
(`RUSTUP_HOME`/`CARGO_HOME` under `~/workspace/synveil-tools`).

Result: **22 passed, 0 failed** (20 unit + 2 integration).

Coverage:
- `csv` — RFC 4180 quoted fields, doubled quotes, CRLF, no trailing
  newline.
- `astro` — pc→ly, J2000 rotation preserves distance, galactic-centre
  direction maps to +X, RA/Dec round trip.
- `derive` — spectral parsing (`G2V`, `M5Ve`, `K0III`, `sdM3`, `B9.5V`),
  temperature anchors/ordering/floor, luminosity round trip, Sun-like
  mass/temperature.
- `hyg` — placeholder-distance filter keeps Sol (dist 0), name
  fallback chain (proper → bf → Gliese → HIP → HD → HR → HYG id).
- `exo` — archive row parse incl. quoted fields.
- `merge` — host match by designation, by coordinates (≤1.0 pc),
  insert-missing-host (position from archive RA/Dec/dist, archive
  flag), skip-host-without-position.
- `table` — binary write→read round trip identical, byte-identical
  repeated writes, header/record sizes match the format contract.
- `tests/pipeline_integration.rs` (fixtures in
  `pipeline/tests/fixtures/`, no network) — full parse→merge→write→
  read path over hand-made HYG/archive slices: 5 HYG rows → 4 usable,
  hosts matched 1 by name + 1 by coordinates, 1 inserted with 3
  planets, 1 skipped, 6 planets attached, lossless round trip.

## 2. Live pipeline build

```
cd pipeline
cargo run --release -- build --out ../data --offline   # uses pipeline/cache/
```

(First build downloads into `pipeline/cache/`; `--offline` proves the
cache path.) Build report from 2026-11-04:

```
HYG v4.4 input rows:            119614
  dropped (placeholder distance):  10224
  usable stars:                    109390
  with proper names:               541
Exoplanet Archive planet rows:     6451
  planetary systems:               4847
  hosts matched by designation:    713
  hosts matched by coordinates:    104
  hosts inserted (not in HYG):     4003
  hosts skipped (no position):     27
  planets attached:                6424
Final table: 113393 stars, 6882528 bytes (stars.bin)
Distance from Sol: median 645.9 ly, max 27723.3 ly
Spot-check: Proxima Centauri at 4.226 ly (HYG v4.4 distance; modern value 4.246 ly)
Spot-check: TRAPPIST-1 present with 7 planets (expected 7)
Read-back verification: OK (113393 records round-tripped)
```

Reconciliation against the design doc (§1, verified by hand during
planning): HYG rows 119,614 ✓; placeholders 10,224 ✓; usable 109,390
✓; HYG max usable distance 990.099 pc ✓ (≈3,229 ly). Archive snapshot
(2026-11-04 pull): 6,451 planets / 4,847 systems ✓ — matches the
doc's snapshot exactly; counts drift upward over time.

Notes on the numbers:
- Proper names: 541 of the doc's 549 survive the filter — 8 named
  stars sit on placeholder-distance rows and are dropped by design.
- Final-table max distance 27,723.3 ly is **SWEEPS-4**, an
  archive-inserted host at the archive's own stated 8,500 pc (a
  SWEEPS bulge field estimate) — archive data, flagged with its
  source, not a pipeline error.
- Proxima at 4.226 ly is HYG v4.4's own distance; the catalog value
  is kept, the modern 4.246 ly difference is recorded, not "fixed".
- 6,424 of 6,451 planets attached: the 27 unattached belong to the
  27 skipped hosts (no usable archive position).
- `stars.bin` SHA-256
  `03993d9951e2ad1d550ddddcbe3ded24435ffd4d06258b9b6487ce034cadecc3`;
  a second build produced a byte-identical file (determinism ✓).
  Full provenance: `data/manifest.json`, `data/SOURCES.md`.

## 3. Godot viewer — headless verification

Godot 4.7.2 stable (Linux x86_64), already on this VM from the
ai-animation-studio project (`~/workspace/godot-bin/`).

```
godot --headless --path viewer -- --verify
```

Output (verbatim, 2026-11-04; whole run ~1.4 s):

```
VERIFY_PASS star_count=113393 matches manifest
VERIFY_PASS sol_at_origin dist_ly=0.0000
VERIFY_PASS trappist1_planets=7 names=TRAPPIST-1 b, TRAPPIST-1 c, TRAPPIST-1 d, TRAPPIST-1 e, TRAPPIST-1 f, TRAPPIST-1 g, TRAPPIST-1 h
VERIFY_PASS pick_sol index=0
MEASURE load_ms=96 stars=113393 planets=6424 mem_static_mb=67.5
VERIFY_PASS all
```

Exit code 0. The pick assertion drives the real camera: the camera is
aimed at Sol, Sol is projected to screen coordinates, and the
click-pick code path (`nearest_to_ray`) must return Sol's record.

Measurements (this VM, dummy renderer — load/memory only):
- Shipping table (113,393 stars): load **96 ms**, static memory
  **67.5 MB**.

## 4. ~1M-star extended measurement (Adam's ruling: measure)

Source resolution: the design phase's guessed AT-HYG URL 404'd. The
current location is the Codeberg repo `astronexus/athyg`, file
`data/athyg_40.csv.gz` (note: `athyg_40`, not the `athyg_v40` the
repo README text mentions — that name 404s). The file is Git-LFS
backed; the Codeberg media endpoint serves the real content.

- Download: 199,688,001 bytes gz (~488 MB CSV), 2,558,654 rows,
  2,533,096 with usable distances.
- Harness `pipeline/measure_extended.py` (Python stdlib, measurement
  only — not the shipping pipeline) selected the **1,000,000 nearest**
  usable stars (distance cutoff 468.85 pc) and wrote the same v1
  binary format to `data/extended/stars.bin` (git-ignored):
  **52,014,311 bytes**, build time **81.9 s** (two passes over the
  CSV; a Rust builder would be faster — the number is the harness's).
- Viewer measurement:
  ```
  godot --headless --path viewer -- --measure --data=<abs path>/data/extended/stars.bin
  MEASURE load_ms=739 stars=1000000 planets=0 mem_static_mb=173.8
  MEASURE_DONE
  ```
  So at 1M stars: ~52 MB on disk, **739 ms** load, **173.8 MB**
  static memory in the viewer process — comfortably inside the
  target PC's budget. The extended table is a scale proxy (AT-HYG
  only, no exoplanet merge), not a candidate shipping table; that
  decision belongs to a later slice.

## 5. NOT verified (owner-PC / later gates)

- **FPS / frame pacing on Adam's RTX 3060** — the VM's headless
  dummy renderer says nothing about rendering performance. No FPS
  claim is made anywhere in S0.
- Interactive feel: orbit/fly controls, click picking with a real
  mouse, point-size appearance under the Vulkan renderer.
- Windows build/export of the viewer.
- The pipeline's download path on a cold cache was exercised for the
  catalog fetches themselves (files in `pipeline/cache/` came from
  live downloads this session); `--offline` rebuilds from cache are
  what CI-style runs should use.
