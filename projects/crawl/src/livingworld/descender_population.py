"""Deterministic population identity and clone-avoidance services for Underreach."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
import math
from time import perf_counter
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .character_dna import (
    CHARACTER_DNA_SCHEMA_VERSION,
    CharacterDNA,
    CharacterDNAGenerator,
    PersistentAppearance,
    deterministic_digest,
)
from .character_factory import CharacterFactory, CharacterRendererManifest


POPULATION_PROTOCOL = "underreach.descender-population.v1"
POPULATION_VERSION = "29a2.1"
DEFAULT_POPULATION_SEED = "underreach-29a2-population-proof"
DEFAULT_SPECIES_WEIGHTS = {"human": 0.60, "dwarf": 0.40}
STYLE_PROFILES = ("earth_survivor", "rugged", "practical", "armored", "lightweight")
OUTFIT_ASSETS = (
    "underreach.clothing.outfit.casual01.v1",
    "underreach.clothing.outfit.casual02.v1",
    "underreach.clothing.outfit.casual03.v1",
    "underreach.clothing.outfit.casual04.v1",
    "underreach.clothing.outfit.casual05.v1",
    "underreach.clothing.outfit.worksuit01.v1",
)
VISUAL_VARIANTS = {
    "human": ("human_average", "human_short_heavy", "human_tall_thin"),
    "dwarf": ("dwarf_average", "dwarf_heavy", "dwarf_alt"),
}


def _unit(seed: str, descender_id: str, label: str) -> float:
    digest = sha256(f"{POPULATION_VERSION}:{seed}:{descender_id}:{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64 - 1)


def _pick(seed: str, descender_id: str, label: str, values: tuple[str, ...]) -> str:
    return values[min(len(values) - 1, int(_unit(seed, descender_id, label) * len(values)))]


class PresentationPersonality(BaseModel):
    """Future-facing presentation metadata; it has no simulation authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sociability: float = Field(ge=0.0, le=1.0)
    risk_tolerance: float = Field(ge=0.0, le=1.0)
    patience: float = Field(ge=0.0, le=1.0)
    assertiveness: float = Field(ge=0.0, le=1.0)
    humor_style: Literal["dry", "warm", "wry", "none"]
    trust_rate: float = Field(ge=0.0, le=1.0)
    stress_response: Literal["focus", "withdraw", "deflect", "confront"]


class PopulationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descender_id: str
    dna: CharacterDNA
    renderer_manifest: CharacterRendererManifest
    visual_identity_digest: str
    visual_variant: str
    style_profile: str
    personality: PresentationPersonality
    detail_tier: Literal["focused", "nearby", "background", "not_presented"] = "background"
    loadout_authority: Literal["presentation_fixture", "canonical_inventory"] = "presentation_fixture"

    @model_validator(mode="after")
    def identity_is_consistent(self) -> "PopulationEntry":
        if self.descender_id != self.dna.descender_id or self.descender_id != self.renderer_manifest.descender_id:
            raise ValueError("population identity is not bound to one Descender ID")
        if self.visual_variant != self.renderer_manifest.visual_variant:
            raise ValueError("visual variant disagrees with renderer manifest")
        return self


class DescenderPopulation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Literal["underreach.descender-population.v1"] = POPULATION_PROTOCOL
    implementation_version: Literal["29a2.1"] = POPULATION_VERSION
    population_seed: str
    species_weights: dict[str, float]
    character_dna_schema_version: int = CHARACTER_DNA_SCHEMA_VERSION
    asset_registry_digest: str
    ordered_descender_ids: list[str]
    entries: list[PopulationEntry]
    population_digest: str

    @model_validator(mode="after")
    def population_is_complete(self) -> "DescenderPopulation":
        ids = [item.descender_id for item in self.entries]
        if ids != self.ordered_descender_ids or len(ids) != len(set(ids)):
            raise ValueError("population entries must match unique ordered Descender IDs")
        return self


class CharacterManifestCache:
    """Small identity cache keyed only by persistent render inputs."""

    def __init__(self, factory: CharacterFactory | None = None) -> None:
        self.factory = factory or CharacterFactory()
        self._values: dict[str, CharacterRendererManifest] = {}
        self.hits = 0
        self.misses = 0
        self.cold_generation_seconds = 0.0
        self.warm_reconstruction_seconds = 0.0

    def key_for(self, dna: CharacterDNA) -> str:
        return deterministic_digest({
            "dna_digest": dna.digest(),
            "factory_version": self.factory.version,
            "asset_registry_digest": self.factory.registry.digest(),
        })

    def get(self, dna: CharacterDNA) -> CharacterRendererManifest:
        key = self.key_for(dna)
        started = perf_counter()
        if key in self._values:
            self.hits += 1
            value = self._values[key].model_copy(deep=True)
            self.warm_reconstruction_seconds += perf_counter() - started
            return value
        self.misses += 1
        value = self.factory.map(dna)
        self._values[key] = value.model_copy(deep=True)
        self.cold_generation_seconds += perf_counter() - started
        return value

    def diagnostics(self) -> dict[str, Any]:
        return {
            "cache_entries": len(self._values),
            "cache_hits": self.hits,
            "cache_misses": self.misses,
            "cold_generation_seconds": round(self.cold_generation_seconds, 6),
            "warm_reconstruction_seconds": round(self.warm_reconstruction_seconds, 6),
        }


class DescenderPopulationGenerator:
    def __init__(
        self,
        population_seed: str = DEFAULT_POPULATION_SEED,
        *,
        species_weights: dict[str, float] | None = None,
        factory: CharacterFactory | None = None,
        cache: CharacterManifestCache | None = None,
    ) -> None:
        self.population_seed = population_seed
        self.species_weights = dict(species_weights or DEFAULT_SPECIES_WEIGHTS)
        if set(self.species_weights) != {"human", "dwarf"}:
            raise ValueError("population weights must define Human and Dwarf")
        total = sum(float(value) for value in self.species_weights.values())
        if total <= 0 or any(float(value) < 0 for value in self.species_weights.values()):
            raise ValueError("population weights must be non-negative and non-zero")
        self.species_weights = {key: float(value) / total for key, value in self.species_weights.items()}
        self.factory = factory or CharacterFactory()
        self.cache = cache or CharacterManifestCache(self.factory)
        self.dna_generator = CharacterDNAGenerator(f"{population_seed}:{POPULATION_VERSION}")

    def species_for(self, descender_id: str) -> Literal["human", "dwarf"]:
        return "human" if _unit(self.population_seed, descender_id, "species") < self.species_weights["human"] else "dwarf"

    def _appearance(self, dna: CharacterDNA) -> PersistentAppearance:
        outfit = _pick(self.population_seed, dna.descender_id, "outfit", OUTFIT_ASSETS)
        equipment = ["underreach.weapon.sword.v1"]
        if _unit(self.population_seed, dna.descender_id, "helmet") < 0.55:
            equipment.append("underreach.armor.helmet.v1")
        if _unit(self.population_seed, dna.descender_id, "breastplate") < 0.68:
            equipment.append("underreach.armor.breastplate.v1")
        return dna.appearance.model_copy(update={
            "clothing_asset_ids": [outfit],
            "equipment_visual_ids": sorted(equipment),
        }, deep=True)

    def _personality(self, descender_id: str) -> PresentationPersonality:
        return PresentationPersonality(
            sociability=_unit(self.population_seed, descender_id, "sociability"),
            risk_tolerance=_unit(self.population_seed, descender_id, "risk"),
            patience=_unit(self.population_seed, descender_id, "patience"),
            assertiveness=_unit(self.population_seed, descender_id, "assertiveness"),
            humor_style=_pick(self.population_seed, descender_id, "humor", ("dry", "warm", "wry", "none")),
            trust_rate=_unit(self.population_seed, descender_id, "trust"),
            stress_response=_pick(self.population_seed, descender_id, "stress", ("focus", "withdraw", "deflect", "confront")),
        )

    def generate_entry(
        self,
        descender_id: str,
        *,
        species: Literal["human", "dwarf"] | None = None,
        detail_tier: Literal["focused", "nearby", "background", "not_presented"] = "background",
        visual_variant: str | None = None,
    ) -> PopulationEntry:
        resolved_species = species or self.species_for(descender_id)
        base = self.dna_generator.generate(descender_id, resolved_species)
        style = _pick(self.population_seed, descender_id, "style", STYLE_PROFILES)
        dna = base.model_copy(update={"style_profile": style, "appearance": self._appearance(base)}, deep=True)
        manifest = self.cache.get(dna)
        if visual_variant is not None:
            allowed = VISUAL_VARIANTS[resolved_species]
            if visual_variant not in allowed:
                raise ValueError(f"{visual_variant} is not a valid {resolved_species} visual variant")
            manifest = manifest.model_copy(update={"visual_variant": visual_variant}, deep=True)
        identity_digest = deterministic_digest({
            "descender_id": descender_id,
            "dna_digest": dna.digest(),
            "renderer_manifest_digest": manifest.digest(),
        })
        return PopulationEntry(
            descender_id=descender_id,
            dna=dna,
            renderer_manifest=manifest,
            visual_identity_digest=identity_digest,
            visual_variant=manifest.visual_variant,
            style_profile=style,
            personality=self._personality(descender_id),
            detail_tier=detail_tier,
        )

    def generate(
        self,
        descender_ids: Iterable[str],
        *,
        forced_species: dict[str, Literal["human", "dwarf"]] | None = None,
        forced_variants: dict[str, str] | None = None,
    ) -> DescenderPopulation:
        ordered = list(descender_ids)
        if not ordered or len(ordered) != len(set(ordered)):
            raise ValueError("population requires unique ordered Descender IDs")
        forced_species = forced_species or {}
        forced_variants = forced_variants or {}
        entries = [self.generate_entry(
            item, species=forced_species.get(item), visual_variant=forced_variants.get(item)
        ) for item in ordered]
        body = {
            "protocol": POPULATION_PROTOCOL,
            "implementation_version": POPULATION_VERSION,
            "population_seed": self.population_seed,
            "species_weights": self.species_weights,
            "character_dna_schema_version": CHARACTER_DNA_SCHEMA_VERSION,
            "asset_registry_digest": self.factory.registry.digest(),
            "ordered_descender_ids": ordered,
            "dna_digests": [item.dna.digest() for item in entries],
            "renderer_manifest_digests": [item.renderer_manifest.digest() for item in entries],
        }
        return DescenderPopulation(
            population_seed=self.population_seed,
            species_weights=self.species_weights,
            asset_registry_digest=self.factory.registry.digest(),
            ordered_descender_ids=ordered,
            entries=entries,
            population_digest=deterministic_digest(body),
        )


def _vector(dna: CharacterDNA, names: tuple[str, ...]) -> tuple[float, ...]:
    return tuple(float(getattr(dna, name)) for name in names)


def _nearest_distance(vectors: list[tuple[float, ...]], index: int) -> float:
    return min(
        math.sqrt(sum((left - right) ** 2 for left, right in zip(vectors[index], value)))
        for other, value in enumerate(vectors) if other != index
    ) if len(vectors) > 1 else 0.0


def population_diversity(population: DescenderPopulation) -> dict[str, Any]:
    entries = population.entries
    body_names = ("height_cm", "mass_kg", "body_fat", "muscularity", "shoulder_width", "hip_width")
    face_names = ("jaw_width", "chin_prominence", "cheek_prominence", "nose_scale", "brow_prominence", "eye_scale", "facial_fullness")
    body_vectors = [_vector(item.dna, body_names) for item in entries]
    face_vectors = [_vector(item.dna, face_names) for item in entries]
    dna_digests = [item.dna.digest() for item in entries]
    manifests = [item.renderer_manifest.digest() for item in entries]
    clothing = [tuple(item.dna.appearance.clothing_asset_ids) for item in entries]
    equipment = [tuple(item.dna.appearance.equipment_visual_ids) for item in entries]
    return {
        "protocol": "underreach.population-diversity.v1",
        "population_digest": population.population_digest,
        "population_count": len(entries),
        "species_counts": dict(sorted(Counter(item.dna.species for item in entries).items())),
        "exact_dna_duplicate_count": len(dna_digests) - len(set(dna_digests)),
        "exact_renderer_manifest_duplicate_count": len(manifests) - len(set(manifests)),
        "clothing_combination_count": len(set(clothing)),
        "equipment_visual_combination_count": len(set(equipment)),
        "hair_distribution": dict(sorted(Counter(item.dna.appearance.current_hair_asset for item in entries).items())),
        "skin_distribution": dict(sorted(Counter(item.dna.skin_variant for item in entries).items())),
        "style_distribution": dict(sorted(Counter(item.style_profile for item in entries).items())),
        "visual_variant_distribution": dict(sorted(Counter(item.visual_variant for item in entries).items())),
        "minimum_body_nearest_neighbor_distance": round(min(_nearest_distance(body_vectors, i) for i in range(len(entries))), 6),
        "average_body_nearest_neighbor_distance": round(sum(_nearest_distance(body_vectors, i) for i in range(len(entries))) / len(entries), 6),
        "minimum_face_nearest_neighbor_distance": round(min(_nearest_distance(face_vectors, i) for i in range(len(entries))), 6),
        "average_face_nearest_neighbor_distance": round(sum(_nearest_distance(face_vectors, i) for i in range(len(entries))) / len(entries), 6),
        "body_ranges": {
            name: {"minimum": min(float(getattr(item.dna, name)) for item in entries), "maximum": max(float(getattr(item.dna, name)) for item in entries)}
            for name in body_names
        },
    }
