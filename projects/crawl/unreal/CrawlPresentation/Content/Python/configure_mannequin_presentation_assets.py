import json
from pathlib import Path

import unreal

PROTOCOL = "crawl.presentation-assets.v1"


def _project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _log(message):
    unreal.log(f"[CrawlAssetConfig] {message}")


def _asset_class_name(asset_data):
    value = asset_data.asset_class_path.asset_name if hasattr(asset_data, "asset_class_path") else asset_data.asset_class
    return str(value)


def _object_path(asset_data):
    return f"{asset_data.package_name}.{asset_data.asset_name}"


def _index_assets():
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    assets = registry.get_assets_by_path("/Game", recursive=True)
    by_name = {}
    for asset in assets:
        by_name.setdefault(str(asset.asset_name), []).append(asset)
    return by_name


def _find(by_name, name, allowed_classes=None, required=True):
    candidates = by_name.get(name, [])
    if allowed_classes:
        allowed = set(allowed_classes)
        candidates = [asset for asset in candidates if _asset_class_name(asset) in allowed]
    if not candidates:
        if required:
            raise RuntimeError(f"Required mannequin presentation asset not found: {name}")
        return None
    candidates.sort(key=lambda asset: str(asset.package_name))
    return _object_path(candidates[0])


def _first_available(by_name, names, allowed_classes=None, required=True):
    for name in names:
        path = _find(by_name, name, allowed_classes=allowed_classes, required=False)
        if path:
            return path
    if required:
        raise RuntimeError(f"None of the required mannequin presentation assets were found: {', '.join(names)}")
    return None


def main():
    by_name = _index_assets()

    mesh_classes = {"SkeletalMesh"}
    animation_classes = {"AnimSequence", "AnimMontage"}

    manny = _find(by_name, "SKM_Manny_Simple", mesh_classes)
    quinn = _find(by_name, "SKM_Quinn_Simple", mesh_classes)
    idle = _first_available(by_name, ["MM_Idle", "MF_Idle"], animation_classes)
    walk = _first_available(
        by_name,
        ["MF_Unarmed_Walk_Fwd", "MM_Unarmed_Walk_Fwd", "MM_Walk_Fwd", "MF_Walk_Fwd"],
        animation_classes,
    )
    run = _first_available(
        by_name,
        ["MF_Unarmed_Run_Fwd", "MM_Unarmed_Run_Fwd", "MM_Run_Fwd", "MF_Run_Fwd", "MF_Unarmed_Walk_Fwd"],
        animation_classes,
    )
    attack = _first_available(by_name, ["MM_Attack_01", "MM_Attack_02", "MM_Attack_03"], animation_classes)
    hit_light = _first_available(
        by_name,
        ["MM_HitReact_Front_Lgt_01", "MM_HitReact_Front_Med_01", "MM_HitReact_Back_Med_01"],
        animation_classes,
    )
    hit_heavy = _first_available(
        by_name,
        ["MM_HitReact_Front_Hvy_01", "MM_HitReact_Front_Med_01", "MM_HitReact_Front_Lgt_01"],
        animation_classes,
    )
    death = _first_available(
        by_name,
        ["MM_Death_Back_01", "MM_Death_Front_01", "MM_Death_Front_02", "MM_Death_Front_03"],
        animation_classes,
    )

    slots = {
        "rig.humanoid.crawler": manny,
        "rig.enemy.biped": quinn,
        "locomotion.humanoid.standard": walk,
        "locomotion.enemy.biped": walk,
        "idle.humanoid.combat_ready": idle,
        "idle.enemy.biped": idle,
        "humanoid.combat.attack.default": attack,
        "enemy.biped.combat.attack.default": attack,
        "humanoid.reaction.hit.default": hit_light,
        "enemy.biped.reaction.hit.default": hit_light,
        "humanoid.reaction.injury": hit_heavy,
        "enemy.biped.reaction.injury": hit_heavy,
        "humanoid.reaction.near_death": hit_heavy,
        "enemy.biped.reaction.near_death": hit_heavy,
        "humanoid.reaction.death": death,
        "enemy.biped.reaction.death": death,
        "humanoid.reaction.defeat": death,
        "enemy.biped.reaction.defeat": death,
        "humanoid.locomotion.move": walk,
        "enemy.biped.locomotion.move": walk,
        "humanoid.locomotion.run": run,
        "enemy.biped.locomotion.run": run,
        "humanoid.combat.ready": idle,
        "enemy.biped.combat.ready": idle,
        "humanoid.combat.disengage": idle,
        "enemy.biped.combat.disengage": idle,
        "humanoid.idle.observe": idle,
        "enemy.biped.idle.observe": idle,
        "environment.dungeon.floor.standard": "/Engine/BasicShapes/Cube.Cube",
        "environment.dungeon.wall.standard": "/Engine/BasicShapes/Cube.Cube",
        "environment.dungeon.wall.corner": "/Engine/BasicShapes/Cube.Cube",
        "environment.dungeon.wall.doorway": "/Engine/BasicShapes/Cube.Cube",
        "environment.dungeon.pillar": "/Engine/BasicShapes/Cylinder.Cylinder",
        "environment.dungeon.ceiling": "/Engine/BasicShapes/Cube.Cube",
        "environment.dungeon.arch": "/Engine/BasicShapes/Cube.Cube",
        "environment.dungeon.rubble": "/Engine/BasicShapes/Sphere.Sphere",
        "environment.dungeon.crate": "/Engine/BasicShapes/Cube.Cube",
        "environment.dungeon.barrel": "/Engine/BasicShapes/Cylinder.Cylinder",
        "environment.dungeon.torch": "/Engine/BasicShapes/Cylinder.Cylinder",
    }

    output = _project_dir() / "presentation_assets.json"
    payload = {
        "protocol": PROTOCOL,
        "authoritative": False,
        "profile": "ue58-third-person-mannequins-v1",
        "notes": [
            "Generated from locally migrated Epic UE5 Third Person mannequin assets.",
            "All bindings are presentation-only and do not alter Crawl simulation truth.",
            "Manny is the temporary crawler visual; Quinn is the temporary enemy visual.",
            "Missing specialized rescue assets intentionally remain unbound and use presentation fallback behavior."
        ],
        "slots": slots,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    _log(f"Wrote {output}")
    _log(f"Crawler mesh: {manny}")
    _log(f"Enemy mesh: {quinn}")
    _log(f"Idle: {idle}")
    _log(f"Walk: {walk}")
    _log(f"Run: {run}")
    _log(f"Attack: {attack}")
    _log(f"Hit: {hit_light}")
    _log(f"Injury: {hit_heavy}")
    _log(f"Death: {death}")
    _log("Mannequin presentation profile configured. Simulation authority unchanged.")
    return output


main()
