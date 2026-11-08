# Sources — game star table

Built 2026-11-04T18:11:27Z by mwcs-pipeline 0.1.0 (design §1.6 pipeline).

## HYG Database v4.4

- Source: https://codeberg.org/astronexus/hyg (`hyg_v44.csv.gz`)
- License: **CC BY-SA 4.0** — this derived star table is shared under
  the same license. Credit: HYG Database (astronexus), merging
  Hipparcos, Yale Bright Star, and Gliese-Jahreiss catalogs.
- Input rows: 119614; usable after the placeholder-distance filter: 109390.
- Decompressed CSV SHA-256: `ea0e1699a1e7d48daa197b5fe567fcf447420e367f37619862ee1d6f077599cd`

## NASA Exoplanet Archive — pscomppars

- Source: TAP sync service, https://exoplanetarchive.ipac.caltech.edu/TAP
  (live TAP pull (cached)). Planet rows: 6451; planetary systems: 4847.
- CSV SHA-256: `57c776009d8e66825cd5ba20ebffe864b589dee03e2c9e950a8970b957d911ea`
- Acknowledgement: This research has made use of the NASA Exoplanet
  Archive, which is operated by the California Institute of Technology,
  under contract with NASA under the Exoplanet Exploration Program.

## Output

- `stars.bin`: 113393 stars, 6424 planets attached, 6882528 bytes, SHA-256
  `03993d9951e2ad1d550ddddcbe3ded24435ffd4d06258b9b6487ce034cadecc3`. Format: see `pipeline/src/table.rs`.
- Temperature and mass values derived by the pipeline (spectral
  lookup / mass–luminosity relation) are flagged `derived` per record.
  Host stars inserted from the Exoplanet Archive are flagged
  `source: exoplanet-archive`.
