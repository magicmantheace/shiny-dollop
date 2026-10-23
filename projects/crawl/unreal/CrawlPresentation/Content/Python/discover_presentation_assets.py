import json
from pathlib import Path

import unreal


def _project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _asset_class_name(asset_data):
    value = asset_data.asset_class_path.asset_name if hasattr(asset_data, "asset_class_path") else asset_data.asset_class
    return str(value)


def _is_candidate_name(name):
    lowered = name.lower()
    terms = (
        "manny",
        "quinn",
        "mannequin",
        "human",
        "humanoid",
        "character",
        "crawler",
        "enemy",
        "walk",
        "run",
        "idle",
        "attack",
        "hit",
        "react",
        "death",
        "die",
        "combat",
    )
    return any(term in lowered for term in terms)


def main():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    all_assets = registry.get_assets_by_path("/Game", recursive=True)

    meshes = []
    animations = []
    for asset_data in all_assets:
        class_name = _asset_class_name(asset_data)
        asset_name = str(asset_data.asset_name)
        package_name = str(asset_data.package_name)
        object_path = f"{package_name}.{asset_name}"

        if class_name == "SkeletalMesh":
            meshes.append(
                {
                    "name": asset_name,
                    "asset": object_path,
                    "likely_presentation_candidate": _is_candidate_name(asset_name),
                }
            )
        elif class_name in {"AnimSequence", "AnimMontage", "BlendSpace", "BlendSpace1D"}:
            animations.append(
                {
                    "name": asset_name,
                    "asset": object_path,
                    "class": class_name,
                    "likely_presentation_candidate": _is_candidate_name(asset_name),
                }
            )

    meshes.sort(key=lambda item: (not item["likely_presentation_candidate"], item["name"].lower(), item["asset"]))
    animations.sort(key=lambda item: (not item["likely_presentation_candidate"], item["name"].lower(), item["asset"]))

    output = _project_dir() / "Generated" / "presentation_asset_inventory.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "protocol": "crawl.presentation-asset-inventory.v1",
        "authoritative": False,
        "skeletal_mesh_count": len(meshes),
        "animation_asset_count": len(animations),
        "skeletal_meshes": meshes,
        "animation_assets": animations,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    unreal.log(f"[CrawlAssetInventory] Wrote {output}")
    unreal.log(f"[CrawlAssetInventory] Skeletal meshes: {len(meshes)}; animation assets: {len(animations)}")
    return output


main()
