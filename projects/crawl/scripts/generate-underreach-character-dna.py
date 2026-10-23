"""Emit deterministic Slice 29A.1 DNA, renderer, and population QA manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from time import perf_counter

from livingworld.character_dna import CharacterDNAGenerator, CharacterDNAStore, deterministic_digest
from livingworld.character_factory import CharacterFactory


PROFILES = (
    ("human_average", "human", "average", "underreach.clothing.outfit.casual01.v1", ("helmet", "breastplate", "sword")),
    ("human_short_heavy", "human", "short_heavy", "underreach.clothing.outfit.casual03.v1", ("breastplate", "sword")),
    ("human_tall_thin", "human", "tall_thin", "underreach.clothing.outfit.casual05.v1", ("sword",)),
    ("dwarf_average", "dwarf", "average", "underreach.clothing.outfit.worksuit01.v1", ("helmet", "breastplate", "sword")),
    ("dwarf_heavy", "dwarf", "heavy", "underreach.clothing.outfit.casual02.v1", ("breastplate", "sword")),
    ("dwarf_alt", "dwarf", "alternate", "underreach.clothing.outfit.casual04.v1", ("helmet", "sword")),
)

EQUIPMENT_IDS = {
    "helmet": "underreach.armor.helmet.v1",
    "breastplate": "underreach.armor.breastplate.v1",
    "sword": "underreach.weapon.sword.v1",
}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", default="underreach-29a1-character-proof")
    args = parser.parse_args()
    output = args.output.resolve()
    generator = CharacterDNAGenerator(args.seed)
    factory = CharacterFactory()
    store = CharacterDNAStore(output / "dna")

    started = perf_counter()
    examples = []
    authoring = []
    reconstruction = []
    for descender_id, species, profile, outfit_id, equipment_names in PROFILES:
        dna = generator.generate(descender_id, species, body_profile=profile)
        dna = dna.model_copy(update={"appearance": dna.appearance.model_copy(update={
            "clothing_asset_ids": [outfit_id],
            "equipment_visual_ids": [EQUIPMENT_IDS[name] for name in equipment_names],
        }, deep=True)}, deep=True)
        manifest = factory.map(dna).model_copy(update={"visual_variant": descender_id}, deep=True)
        store.save(dna)
        loaded = store.load(descender_id)
        rebuilt = factory.map(loaded).model_copy(update={"visual_variant": descender_id}, deep=True)
        examples.append(dna.model_dump(mode="json"))
        authoring.append({
            "descender_id": descender_id,
            "body_profile": profile,
            "visual_variant": descender_id,
            "dna": dna.model_dump(mode="json"),
            "renderer_manifest": manifest.model_dump(mode="json"),
            "renderer_manifest_digest": manifest.digest(),
        })
        reconstruction.append({
            "descender_id": descender_id,
            "pre_restart_dna_digest": dna.digest(),
            "post_restart_dna_digest": loaded.digest(),
            "pre_restart_renderer_manifest_digest": manifest.digest(),
            "post_restart_renderer_manifest_digest": rebuilt.digest(),
            "equal": dna == loaded and manifest == rebuilt,
        })

    populations = {}
    for species in ("human", "dwarf"):
        population_started = perf_counter()
        records = generator.population(species, 100)
        populations[species] = {
            "count": len(records),
            "digest": deterministic_digest([record.model_dump(mode="json") for record in records]),
            "unique_dna_digests": len({record.digest() for record in records}),
            "generation_seconds": round(perf_counter() - population_started, 6),
            "minimum_height_cm": min(record.height_cm for record in records),
            "maximum_height_cm": max(record.height_cm for record in records),
            "minimum_mass_kg": min(record.mass_kg for record in records),
            "maximum_mass_kg": max(record.mass_kg for record in records),
        }

    combined_population_digest = deterministic_digest({key: populations[key]["digest"] for key in sorted(populations)})
    write_json(output / "character_dna_examples.json", {
        "protocol": "underreach.character-dna-examples.v1",
        "implementation_version": "29a1.1",
        "seed": args.seed,
        "records": examples,
    })
    write_json(output / "character_authoring_inputs.json", {
        "protocol": "underreach.character-authoring-inputs.v1",
        "implementation_version": "29a1.1",
        "seed": args.seed,
        "characters": authoring,
    })
    write_json(output / "character_population_digest.json", {
        "protocol": "underreach.character-population-validation.v1",
        "implementation_version": "29a1.1",
        "seed": args.seed,
        "species": populations,
        "combined_population_digest": combined_population_digest,
    })
    write_json(output / "character_reconstruction_report.json", {
        "protocol": "underreach.character-reconstruction-report.v1",
        "implementation_version": "29a1.1",
        "all_equal": all(item["equal"] for item in reconstruction),
        "records": reconstruction,
        "generation_and_reconstruction_seconds": round(perf_counter() - started, 6),
    })
    print(json.dumps({
        "output": str(output),
        "profiles": len(authoring),
        "population_count": sum(value["count"] for value in populations.values()),
        "population_digest": combined_population_digest,
        "reconstruction_equal": all(item["equal"] for item in reconstruction),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
