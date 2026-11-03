"""Small offline CLI. The Godot preview is optional."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from .library import Library, ROOT, DEFAULT_DB
from .schema import validate_scene, validate_asset, validate_character, validate_catalog, ValidationError

EXAMPLES = ROOT / "examples"

def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Animation Studio foundation")
    parser.add_argument("command", choices=["validate", "init-db", "seed", "register", "list-assets", "demo"])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--catalog", default="quaternius_f1_catalog.json",
                        help="catalog fixture in examples/ (register command)")
    parser.add_argument("--scene", default="scene_demo.json",
                        help="scene fixture in examples/ (demo command)")
    parser.add_argument("--out", type=Path, default=ROOT / "godot" / "data" / "scene_runtime.json")
    args = parser.parse_args(argv)
    if args.command == "validate":
        validate_scene(load("scene_demo.json"))
        validate_scene(load("scene_tavern_v2.json"))
        validate_asset(load("asset_mug.json"))
        validate_character(load("character_traveler.json"))
        catalog = validate_catalog(load("quaternius_f1_catalog.json"))
        print(f"Validated scene, asset, character examples and F1 catalog "
              f"({len(catalog['assets'])} assets, {len(catalog['characters'])} characters)")
        return 0
    if args.command == "demo":
        scene = validate_scene(load(args.scene))
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(scene, indent=2) + "\n", encoding="utf-8")
        print(f"Saved {len(scene['events'])} validated events to {args.out}")
        manifest = EXAMPLES / "asset_manifest.json"
        if manifest.exists():
            target = args.out.parent / "asset_manifest.json"
            shutil.copyfile(manifest, target)
            print(f"Saved asset manifest to {target}")
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
        elif args.command == "list-assets":
            for item in lib.list_assets():
                print(f"{item['asset_id']} [{item['status']}] {item['uri']}")
        return 0
    except (ValidationError, OSError, ValueError) as err:
        parser.error(str(err))
    finally:
        lib.close()
    return 2
