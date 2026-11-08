# Hand-offs (P3)

Exports from the catalog into the tools the owner actually uses,
plus the harnesses that prove the exported assets play back in a
real engine. Every export verifies the local .glb against the
catalog record (sha256 + size) before and after copying — a
hand-off that does not match the catalogued bytes is refused.

## Commands

```
python3 asset_builder.py export-godot   --slug ember-dragon --dest <dir>
python3 asset_builder.py export-threejs --slug ember-dragon --dest <dir>
python3 asset_builder.py export-studio  --slug ember-dragon --asset-root <dir>
```

- **godot** → `<dest>/<slug>/`: `<slug>.glb`, `<slug>.tscn` (wrapper
  scene instancing the GLB), `<slug>.json` (the catalog record),
  README, `handoff-manifest.json`. Copy the folder into a Godot 4
  project as `res://assets/<slug>/` (the wrapper references that
  path), import once, instance the .tscn.
- **threejs** → `<dest>/<slug>/`: `<slug>.glb`, `asset.json`
  (machine-readable facts), `loader-snippet.js` (GLTFLoader +
  AnimationMixer wiring), README, `handoff-manifest.json`.
- **studio** → the AI Animation Studio's intake format: the GLB
  lands at `<asset-root>/assets/characters/<slug>.glb` (rigged) or
  `assets/props/<slug>.glb` (prop), and a record is merged into
  `<asset-root>/game-asset-builder-catalog.json` (schema_version
  1.0.0, matching the studio's `schemas/asset.schema.json`).
  Records are always `status: "candidate"` and `rig_id` is the GAB
  template name — promotion to approved, and any claim of
  `studio_humanoid_v1` compatibility, belong to the studio's own
  gated process.

## Playback verification

Blender re-import (the catalog stage) is not engine playback. The
harnesses here close that gap; both were run against the real
catalogued assets for the P3 proof (results in
`docs/TEST_PLAN.md`).

### Godot (harness: `godot/`)

Needs the Godot 4 console build on the machine doing the check
(the owner's PC has 4.7.2). Assemble a scratch project: copy
`godot/project.godot` + `godot/verify_handoff.gd` into it, copy the
exported folders under `assets/`, and write `verify-spec.json`
next to them:

```json
{"assets": [{"slug": "ember-dragon", "rigged": true,
             "bones": ["root", "..."], "actions": ["hop", "idle"]}]}
```

(The bones/actions arrays are the catalog entry's, verbatim.) Then:

```
godot --headless --path <scratch> --import
godot --headless --path <scratch> --script verify_handoff.gd
```

The script instances each wrapper scene, checks the skeleton
against the spec, and samples bone global poses at t=0 vs mid-clip
for every clip — a clip that exists but does not move the skeleton
fails. It prints `GODOT_VERIFY <json>` per asset and
`GODOT_VERIFY_DONE {"ok": ...}`; exit code follows the verdict.

### three.js (harness: `threejs/verify.html`)

Needs a local three.js (module build + the GLTFLoader addon) and a
Chromium/Chrome. Copy `three.module.js` **and `three.core.js`**
(three ≥ 0.170 splits the module build across both files — with
only the first present the import graph 404s and the check never
runs) plus `addons/` (loaders/GLTFLoader.js,
utils/BufferGeometryUtils.js) beside `verify.html`. Chrome blocks
file:// ES-module imports, so serve the folder over local HTTP
(e.g. `python -m http.server` on 127.0.0.1), then:

```
chrome --headless=new --use-angle=swiftshader-webgl \
  --enable-unsafe-swiftshader --timeout=60000 --dump-dom \
  "http://127.0.0.1:<port>/verify.html?glb=<slug>.glb&clips=idle,hop&bones=14"
```

The page loads the GLB with GLTFLoader, plays every clip through
an AnimationMixer, and reports per-clip duration plus the maximum
bone world-position delta between t=0 and mid-clip as JSON in the
dumped DOM (`<pre id="result">`). Software WebGL (SwiftShader) is
enough — the check exercises loading, skinning and animation, not
rendering quality. `threejs/run_verify.mjs` automates the four
catalogued assets end to end (localhost server + one Chrome run
per asset): `node run_verify.mjs <harness-dir>`.
