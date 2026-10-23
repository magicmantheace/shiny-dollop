"""Validate persisted 29A.1 presentation meshes in a fresh Unreal process."""

import json
import os
from pathlib import Path

import unreal


def main():
    generated = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())) / "Generated"
    result = json.loads((generated / "live_unreal_result.json").read_text(encoding="utf-8"))
    level = result["level_asset"]
    level_system = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    if not level_system.load_level(level):
        raise RuntimeError(f"Could not load 29A.1 presentation level: {level}")
    actors = []
    for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
        components = list(actor.get_components_by_class(unreal.SkeletalMeshComponent))
        if not components:
            continue
        meshes = []
        for component in components:
            mesh = component.get_editor_property("skeletal_mesh_asset")
            meshes.append(mesh.get_path_name() if mesh is not None else None)
        actors.append({
            "label": actor.get_actor_label(),
            "skeletal_mesh_component_count": len(components),
            "meshes": meshes,
        })
    meshes = {mesh for item in actors for mesh in item["meshes"]}
    required = {
        "/Game/Underreach29A1/Characters/SK_UnderreachHuman.SK_UnderreachHuman",
        "/Game/Underreach29A1/Characters/SK_UnderreachDwarf.SK_UnderreachDwarf",
    }
    procedural = [item for item in actors if item["label"].startswith("Underreach_")]
    expected_by_species = {
        "Human": "/Game/Underreach29A1/Characters/SK_UnderreachHuman.SK_UnderreachHuman",
        "Dwarf": "/Game/Underreach29A1/Characters/SK_UnderreachDwarf.SK_UnderreachDwarf",
    }
    species_records = {}
    for species, expected_mesh in expected_by_species.items():
        matching = [item for item in procedural if item["label"].startswith(f"Underreach_{species}_")]
        species_records[species.lower()] = {
            "actor_count": len(matching),
            "actors": matching,
            "exclusive": len(matching) == 1
            and matching[0]["skeletal_mesh_component_count"] == 1
            and matching[0]["meshes"] == [expected_mesh],
        }
    assembly_valid = all(item["exclusive"] for item in species_records.values())
    body = {
        "protocol": "underreach.character-level-persistence.v1",
        "level": level,
        "skeletal_actors": actors,
        "required_meshes_present": required.issubset(meshes),
        "species": species_records,
        "one_body_per_procedural_actor": assembly_valid,
        "species_switch_exclusive": assembly_valid,
    }
    output = generated / "29a1" / "level_persistence_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(body, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, output)
    if not body["required_meshes_present"] or not assembly_valid:
        raise RuntimeError(f"29A.1 saved level reverted procedural meshes: {actors}")
    unreal.log("UNDERREACH 29A.1 LEVEL PERSISTENCE PASS")


main()
