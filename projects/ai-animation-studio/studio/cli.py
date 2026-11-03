"""Small offline CLI. The Godot preview is optional."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from . import gltf
from .library import Library, ROOT, DEFAULT_DB
from .promotion import DEFAULT_ASSET_ROOT, PromotionError, promote_asset, promote_character
from .schema import validate_scene, validate_asset, validate_character, validate_catalog, ValidationError

EXAMPLES = ROOT / "examples"

def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))

def _asset_state(asset: dict) -> dict:
    meta = asset.get("metadata") or {}
    return {"asset_id": asset["asset_id"], "kind": asset["kind"],
            "status": asset["status"], "version": meta.get("version", "1.0.0"),
            "sha256": meta.get("sha256")}

def enrich_manifest(manifest: dict, lib: Library, asset_root: Path | None) -> dict:
    """Attach DB approval state (status/version/sha256) to a manifest.

    The base fixture carries the curated clip/stage data; everything the
    Godot resolver enforces — per-asset status, pinned version and
    SHA-256 — is copied from the library database at export time, never
    re-typed by hand. Stage piece hashes come from the kit record's
    per-piece digests (verified against the store at promotion time).
    """
    manifest = json.loads(json.dumps(manifest))
    manifest["assets"] = {a["uri"]: _asset_state(a) for a in lib.list_assets_full()}
    for recipe in manifest.get("recipes", {}).values():
        files = []
        body = lib.get_asset_by_uri(recipe["body"])
        if body:
            files.append({"uri": recipe["body"], "role": "body", **_asset_state(body)})
        for uri in recipe.get("animations", []):
            motion = lib.get_asset_by_uri(uri)
            if motion:
                files.append({"uri": uri, "role": "animation", **_asset_state(motion)})
        recipe["files"] = files
    stage = manifest.get("stage")
    if stage:
        kit = lib.get_asset(stage["asset_id"])
        if kit:
            pieces_meta = (kit.get("metadata") or {}).get("pieces") or {}
            for piece in stage.get("pieces", []):
                piece["status"] = kit["status"]
                piece["version"] = (kit.get("metadata") or {}).get("version", "1.0.0")
                piece["sha256"] = pieces_meta.get(Path(piece["file"]).name)
    return manifest

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Animation Studio foundation")
    parser.add_argument("command", choices=["validate", "init-db", "seed", "register", "promote", "list-assets", "demo", "sockets"])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--catalog", default="quaternius_f1_catalog.json",
                        help="catalog fixture in examples/ (register/promote commands)")
    parser.add_argument("--scene", default="scene_demo.json",
                        help="scene fixture in examples/ (demo command)")
    parser.add_argument("--asset-root", type=Path, default=None,
                        help="local asset store root (promote/demo/sockets); "
                             "defaults to AI_ANIMATION_ASSET_ROOT or the VM store")
    parser.add_argument("--body", default="assets/characters/Superhero_Male_FullBody.gltf",
                        help="body glTF under the asset root (sockets command)")
    parser.add_argument("--out", type=Path, default=ROOT / "godot" / "data" / "scene_runtime.json")
    args = parser.parse_args(argv)
    asset_root = args.asset_root or DEFAULT_ASSET_ROOT
    if args.command == "validate":
        validate_scene(load("scene_demo.json"))
        validate_scene(load("scene_tavern_v2.json"))
        validate_asset(load("asset_mug.json"))
        validate_character(load("character_traveler.json"))
        catalog = validate_catalog(load("quaternius_f1_catalog.json"))
        print(f"Validated scene, asset, character examples and F1 catalog "
              f"({len(catalog['assets'])} assets, {len(catalog['characters'])} characters)")
        return 0
    if args.command == "sockets":
        doc = gltf.load_gltf_json(asset_root / args.body)
        positions = gltf.joint_world_positions(doc)
        print(f"Bind-pose joint world positions for {args.body} "
              f"({gltf.joint_count(doc)} joints, metres, character origin at floor):")
        for bone in ("hand_l", "hand_r", "Head", "neck_01", "pelvis"):
            print(f"  {bone}: {gltf.round3(positions[bone])}")
        return 0
    if args.command == "demo":
        scene = validate_scene(load(args.scene))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(scene, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {len(scene['events'])} validated events to {args.out}")
        manifest = EXAMPLES / "asset_manifest.json"
        if manifest.exists():
            target = args.out.parent / "asset_manifest.json"
            base = json.loads(manifest.read_text(encoding="utf-8"))
            if args.db.exists():
                lib = Library(args.db)
                try:
                    enriched = enrich_manifest(base, lib, asset_root)
                finally:
                    lib.close()
                target.write_text(json.dumps(enriched, indent=2) + "\n", encoding="utf-8")
                print(f"Saved asset manifest with library approval state to {target}")
            else:
                shutil.copyfile(manifest, target)
                print(f"Saved asset manifest to {target} (no library DB at {args.db}; "
                      "no approval state attached, preview will fall back to capsules)")
        print("Open godot/project.godot in Godot 4 and run the main scene to preview.")
        return 0
    lib = Library(args.db)
    try:
        lib.init()
        if args.command == "init-db":
            print(f"Initialized {args.db}")
        elif args.command == "seed":
            lib.put_asset(load("asset_mug.json"))
            lib.put_character(load("character_traveler.json"))
            lib.put_scene(load("scene_demo.json"))
            print("Seeded candidate examples; no production media files supplied")
        elif args.command == "register":
            catalog = validate_catalog(load(args.catalog))
            for asset in catalog["assets"]:
                lib.put_asset(asset)
            for character in catalog["characters"]:
                lib.put_character(character)
            print(f"Registered {len(catalog['assets'])} assets and "
                  f"{len(catalog['characters'])} characters from {args.catalog} into {args.db}")
        elif args.command == "promote":
            catalog = validate_catalog(load(args.catalog))
            all_ok = True
            for asset in catalog["assets"]:
                result = promote_asset(lib, asset["asset_id"], asset_root)
                verdict = "PROMOTED" if result["promoted"] else "REFUSED"
                all_ok = all_ok and result["promoted"]
                print(f"{verdict} asset {result['asset_id']}")
                for gate in result["gates"]:
                    print(f"  gate {gate['gate']}: "
                          f"{'PASS' if gate['passed'] else 'FAIL'} — {gate['detail']}")
                print(f"  pending human gates (NOT passed): {', '.join(result['pending'])}")
            for character in catalog["characters"]:
                result = promote_character(lib, character["character_id"])
                verdict = "PROMOTED" if result["promoted"] else "REFUSED"
                all_ok = all_ok and result["promoted"]
                print(f"{verdict} character {result['character_id']}")
                for gate in result["gates"]:
                    print(f"  gate {gate['gate']}: "
                          f"{'PASS' if gate['passed'] else 'FAIL'} — {gate['detail']}")
                print(f"  pending human gates (NOT passed): {', '.join(result['pending'])}")
            return 0 if all_ok else 2
        elif args.command == "list-assets":
            for item in lib.list_assets():
                print(f"{item['asset_id']} [{item['status']}] {item['uri']}")
        return 0
    except (ValidationError, PromotionError, OSError, ValueError) as err:
        parser.error(str(err))
    finally:
        lib.close()
    return 2
