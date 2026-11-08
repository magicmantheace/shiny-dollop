"""Game Asset Builder — engine hand-offs (P3).

Exporters that take a catalogued asset and produce a ready-to-use
package for a target the owner actually uses:

  godot    a folder for a Godot 4 project (res://): the .glb, a
           wrapper .tscn that instances it, the catalog record, and
           a README. Playback verification harness: handoff/godot/.
  threejs  the .glb plus an asset manifest, a GLTFLoader/AnimationMixer
           loader snippet, and a README. Verification harness:
           handoff/threejs/.
  studio   the AI Animation Studio's library intake format: the .glb
           under the asset root's assets/ tree and an entry in a
           schema-1.0.0 catalog JSON, status "candidate" — promotion
           to approved is the studio's own gated process and is never
           done from here.

Every export first verifies the local .glb against the catalog
record (sha256 + size) and again after copying: a hand-off that
does not match the catalogued bytes is refused, never shipped.
"""

import hashlib
import json
import os
import shutil

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_DIR = os.path.join(PROJECT_DIR, "catalog")
OUTPUTS_DIR = os.path.join(PROJECT_DIR, "outputs")
STUDIO_CATALOG_NAME = "game-asset-builder-catalog.json"


def _load_catalog_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gab_catalog_for_handoff",
        os.path.join(PROJECT_DIR, "stages", "catalog", "catalog.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_verified_entry(slug: str, catalog_dir: str = CATALOG_DIR,
                        outputs_dir: str = OUTPUTS_DIR):
    """Return (entry, glb_path) with the on-disk GLB verified
    against the catalog record; raise ValueError otherwise."""
    catalog_mod = _load_catalog_module()
    try:
        entry = catalog_mod.read_entry(catalog_dir, slug)
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError(f"no catalog entry for {slug!r}: {exc}") from exc
    glb_path = os.path.join(outputs_dir, slug, entry["asset_file"])
    if not catalog_mod.verify_entry(entry, glb_path):
        raise ValueError(
            f"{slug}: local GLB missing or does not match the catalog "
            f"record (sha256/size) — refusing to export unverified bytes")
    return entry, glb_path


def _is_rigged(entry: dict) -> bool:
    provenance = entry.get("provenance") or {}
    if "rigged" in provenance:
        return bool(provenance["rigged"])
    return bool(entry.get("bones"))


def _copy_verified(entry: dict, glb_path: str, dest: str) -> str:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copyfile(glb_path, dest)
    digest = hashlib.sha256()
    with open(dest, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != entry["sha256"] \
            or os.path.getsize(dest) != entry["bytes"]:
        raise ValueError(f"copied GLB at {dest} does not match the "
                         f"catalog record — export aborted")
    return dest


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _manifest(target: str, entry: dict, files: list[str]) -> dict:
    return {
        "handoff_version": 1,
        "target": target,
        "slug": entry["slug"],
        "name": entry["name"],
        "rigged": _is_rigged(entry),
        "bones": entry.get("bones", []),
        "actions": entry.get("actions", []),
        "asset_file": entry["asset_file"],
        "sha256": entry["sha256"],
        "bytes": entry["bytes"],
        "files": files,
        "generated_by": "game-asset-builder handoff export (P3)",
    }


def _godot_tscn(entry: dict) -> str:
    """A Godot 4 wrapper scene: instance it, and the imported GLB
    scene (with its AnimationPlayer) comes along."""
    slug = entry["slug"]
    node_name = "".join(c if c.isalnum() else "_"
                        for c in entry["name"]).strip("_") or "Asset"
    return (
        '[gd_scene load_steps=2 format=3]\n\n'
        f'[ext_resource type="PackedScene" path="res://assets/{slug}/'
        f'{slug}.glb" id="1"]\n\n'
        f'[node name="{node_name}" type="Node3D"]\n\n'
        f'[node name="Model" parent="." instance=ExtResource("1")]\n')


def export_godot(entry: dict, glb_path: str, dest_dir: str) -> dict:
    slug = entry["slug"]
    folder = os.path.join(dest_dir, slug)
    os.makedirs(folder, exist_ok=True)
    _copy_verified(entry, glb_path, os.path.join(folder, f"{slug}.glb"))
    _write(os.path.join(folder, f"{slug}.json"),
           json.dumps(entry, indent=1) + "\n")
    _write(os.path.join(folder, f"{slug}.tscn"), _godot_tscn(entry))
    clips = ", ".join(entry.get("actions", [])) or "none (static prop)"
    _write(os.path.join(folder, "README.md"), f"""# {entry['name']} — Godot hand-off

Generated by the Game Asset Builder (catalogue slug `{slug}`,
sha256 `{entry['sha256'][:16]}…`, verified against the catalog
record at export time).

## Use

Copy this folder into a Godot 4 project as `res://assets/{slug}/`
(the wrapper scene references the .glb at that path), let the editor
import it once, then instance `{slug}.tscn` — or instance the .glb
scene directly. Animation clips baked into the GLB: {clips}. They
live on the AnimationPlayer inside the imported scene; play them by
name from a script (`$Model/AnimationPlayer.play("idle")` — the
player's node path can vary with the import, find it with
`find_child("AnimationPlayer")` if unsure).

Rigged: {_is_rigged(entry)} · bones: {len(entry.get('bones', []))} ·
verts: {entry.get('counts', {}).get('verts')} ·
faces: {entry.get('counts', {}).get('faces')}
""")
    manifest = _manifest("godot", entry,
                         [f"{slug}.glb", f"{slug}.tscn", f"{slug}.json",
                          "README.md", "handoff-manifest.json"])
    _write(os.path.join(folder, "handoff-manifest.json"),
           json.dumps(manifest, indent=1) + "\n")
    return manifest


_THREEJS_SNIPPET = """// Game Asset Builder asset — three.js loader snippet.
// Requires three >= 0.150 with the addons path mapped
// ("three/addons/" -> examples/jsm/). The .glb is self-contained.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export async function loadAsset(url) {
  const gltf = await new GLTFLoader().loadAsync(url);
  const mixer = new THREE.AnimationMixer(gltf.scene);
  const actions = {};
  for (const clip of gltf.animations) {
    actions[clip.name] = mixer.clipAction(clip);
  }
  return { scene: gltf.scene, mixer, actions };
}

// Usage:
//   const { scene, mixer, actions } = await loadAsset('ASSET_FILE');
//   sceneRoot.add(scene);
//   actions['CLIP_NAME']?.play();
//   // per frame: mixer.update(deltaSeconds);
"""


def export_threejs(entry: dict, glb_path: str, dest_dir: str) -> dict:
    slug = entry["slug"]
    folder = os.path.join(dest_dir, slug)
    os.makedirs(folder, exist_ok=True)
    _copy_verified(entry, glb_path, os.path.join(folder, f"{slug}.glb"))
    asset_json = {
        "slug": slug,
        "name": entry["name"],
        "file": f"{slug}.glb",
        "sha256": entry["sha256"],
        "bytes": entry["bytes"],
        "rigged": _is_rigged(entry),
        "bones": entry.get("bones", []),
        "clips": entry.get("actions", []),
        "counts": entry.get("counts", {}),
    }
    _write(os.path.join(folder, "asset.json"),
           json.dumps(asset_json, indent=1) + "\n")
    snippet = _THREEJS_SNIPPET.replace("ASSET_FILE", f"{slug}.glb")
    if entry.get("actions"):
        snippet = snippet.replace("CLIP_NAME", entry["actions"][0])
    _write(os.path.join(folder, "loader-snippet.js"), snippet)
    clips = ", ".join(entry.get("actions", [])) or "none (static prop)"
    _write(os.path.join(folder, "README.md"), f"""# {entry['name']} — three.js hand-off

Generated by the Game Asset Builder (catalogue slug `{slug}`,
sha256 `{entry['sha256'][:16]}…`, verified against the catalog
record at export time).

The .glb is the whole asset (geometry, texture, skeleton, baked
clips: {clips}). `loader-snippet.js` shows the GLTFLoader +
AnimationMixer wiring; `asset.json` carries the machine-readable
facts. Any three.js version that loads glTF 2.0 works — the
Drabbit Pet desktop app renders this project's GLBs with three
0.180.
""")
    manifest = _manifest("threejs", entry,
                         [f"{slug}.glb", "asset.json", "loader-snippet.js",
                          "README.md", "handoff-manifest.json"])
    _write(os.path.join(folder, "handoff-manifest.json"),
           json.dumps(manifest, indent=1) + "\n")
    return manifest


def studio_record(entry: dict) -> dict:
    """One asset record in the AI Animation Studio's intake format
    (its schemas/asset.schema.json, schema_version 1.0.0).

    Honesty rules: status is always "candidate" (promotion is the
    studio's gated process); rig_id is the GAB template name, never
    the studio's studio_humanoid_v1 — these rigs are not that rig.
    """
    rigged = _is_rigged(entry)
    slug = entry["slug"]
    provenance = entry.get("provenance") or {}
    tags = ["game-asset-builder"]
    if rigged:
        tags.append("creature")
        if provenance.get("rig_template"):
            tags.append(provenance["rig_template"])
    else:
        tags.append("prop")
    for action in entry.get("actions", []):
        if action not in tags:
            tags.append(action)
    return {
        "schema_version": "1.0.0",
        "asset_id": slug,
        "kind": "body" if rigged else "prop",
        "uri": (f"assets/characters/{slug}.glb" if rigged
                else f"assets/props/{slug}.glb"),
        "rig_id": provenance.get("rig_template") if rigged else None,
        "status": "candidate",
        "source": "Game Asset Builder (local pipeline)",
        "license": "proprietary",
        "tags": tags,
        "metadata": {
            "generator": "game-asset-builder",
            "catalog_slug": slug,
            "source_concept": entry.get("source_concept"),
            "sha256": entry["sha256"],
            "bytes": entry["bytes"],
            "joints": len(entry.get("bones", [])),
            "bones": entry.get("bones", []),
            "clips": entry.get("actions", []),
            "verts": entry.get("counts", {}).get("verts"),
            "faces": entry.get("counts", {}).get("faces"),
            "weight_method": provenance.get("weight_method"),
            "mesh_model": provenance.get("mesh_model"),
            "texture_model": provenance.get("texture_model"),
        },
    }


def export_studio(entry: dict, glb_path: str, asset_root: str) -> dict:
    """Write the GLB into the studio asset-root layout and merge the
    record into the root's game-asset-builder catalog JSON (created
    if absent; an existing record for the same asset_id is replaced,
    never duplicated)."""
    record = studio_record(entry)
    dest = os.path.join(asset_root, *record["uri"].split("/"))
    _copy_verified(entry, glb_path, dest)
    catalog_path = os.path.join(asset_root, STUDIO_CATALOG_NAME)
    catalog = {"schema_version": "1.0.0", "assets": []}
    if os.path.exists(catalog_path):
        with open(catalog_path, encoding="utf-8") as fh:
            catalog = json.load(fh)
    assets = [a for a in catalog.get("assets", [])
              if a.get("asset_id") != record["asset_id"]]
    assets.append(record)
    catalog["assets"] = sorted(assets, key=lambda a: a["asset_id"])
    _write(catalog_path, json.dumps(catalog, indent=1) + "\n")
    return {"record": record, "glb_path": dest,
            "catalog_path": catalog_path}
