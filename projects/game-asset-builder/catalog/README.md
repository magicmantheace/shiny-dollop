# catalog/

One folder per finished asset, holding its committed `metadata.json`
(entry format: `stages/catalog/catalog.py`, `entry_version` 1). The
entry records the asset's name, source concept, rig counts, bone and
action lists, stage provenance (models, GPU host, per-stage runner
results), and the sha256 + byte size of the finished .glb.

The .glb itself is a generated output and never enters git: it lives
in the local `outputs/<slug>/` area next to the run manifest, stage
reports, and preview renders. Verify any copy against its entry with:

    python3 asset_builder.py catalog-verify --slug <slug>

First entry: `ember-dragon/` — the P0 pipeline's proof asset
(2026-11-06), built end-to-end from a concept image by the local
pipeline.
