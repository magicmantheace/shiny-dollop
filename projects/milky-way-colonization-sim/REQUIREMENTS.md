# Requirements — milky-way-colonization-sim

## Toolchain

- **Rust** (stable; developed against rustc 1.99.0) — `pipeline/` has
  **zero third-party crate dependencies**: CSV parsing, gzip extraction
  (via the system `gzip`), and downloads (via the system `curl`) are
  deliberately dependency-free so the pipeline builds anywhere cargo
  does, offline once the catalog cache exists.
- **Godot 4.7.2** (pinned by version + SHA-256 per ADR practice; the
  binary is a local tool, not committed) for `viewer/`.
- System tools: `curl` (catalog downloads), `gzip` (HYG decompression).

## Runtime (target machine)

- Adam's PC: Windows 11, i5-10400F, RTX 3060 12 GB, 32 GB RAM
  (design §7.3 budgets against this).
- The S0 viewer runs anywhere Godot 4.7 runs; the star table is
  platform-independent (little-endian, explicitly laid out).

## Data inputs (fetched by the pipeline, never committed raw)

- HYG v4.4 `hyg_v44.csv.gz` — Codeberg `astronexus/hyg`, CC BY-SA 4.0.
- NASA Exoplanet Archive `pscomppars` via the TAP sync service.
- Optional (S0 measurement): AT-HYG v4.0 from Codeberg `astronexus/athyg`.
