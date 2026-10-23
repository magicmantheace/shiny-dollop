"""Deterministic, renderer-neutral identity records for Underreach Descenders."""

from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


CHARACTER_DNA_PROTOCOL = "underreach.character-dna.v1"
CHARACTER_DNA_SCHEMA_VERSION = 1
CHARACTER_DNA_IMPLEMENTATION_VERSION = "29a1.1"


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        # Preserve Python container types until the recursive normalizer sees
        # them.  ``mode="json"`` turns sets into lists using hash iteration
        # order, which made registry/population digests vary across processes.
        return _jsonable(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (set, frozenset)):
        return sorted((_jsonable(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def deterministic_digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _unit(seed: int, label: str) -> float:
    encoded = f"{seed}:{label}:{CHARACTER_DNA_IMPLEMENTATION_VERSION}".encode("utf-8")
    return int.from_bytes(sha256(encoded).digest()[:8], "big") / float(2**64 - 1)


def _normal(seed: int, label: str) -> float:
    # Deterministic Box-Muller sample. Clamp away from zero before log().
    u1 = max(1e-12, _unit(seed, f"{label}:u1"))
    u2 = _unit(seed, f"{label}:u2")
    return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _bounded(value: float, low: float, high: float) -> float:
    return round(min(high, max(low, value)), 6)


def _pick(seed: int, label: str, values: tuple[str, ...]) -> str:
    return values[min(len(values) - 1, int(_unit(seed, label) * len(values)))]


class PersistentAppearance(BaseModel):
    """Simulation-persistent appearance overlays, independent of render instances."""

    model_config = ConfigDict(extra="forbid")

    current_hair_asset: str
    facial_hair_asset: str | None = None
    clothing_asset_ids: list[str] = Field(default_factory=list)
    equipment_visual_ids: list[str] = Field(default_factory=list)
    persistent_marks: list[str] = Field(default_factory=list)
    injuries: list[str] = Field(default_factory=list)
    tattoos: list[str] = Field(default_factory=list)
    missing_features: list[str] = Field(default_factory=list)
    dirt_level: float = Field(default=0.0, ge=0.0, le=1.0)
    blood_level: float = Field(default=0.0, ge=0.0, le=1.0)
    magical_transformation_ids: list[str] = Field(default_factory=list)


class CharacterDNA(BaseModel):
    """Stable identity; never stores an Unreal actor, component, or object path."""

    model_config = ConfigDict(extra="forbid")

    protocol: Literal["underreach.character-dna.v1"] = CHARACTER_DNA_PROTOCOL
    schema_version: Literal[1] = CHARACTER_DNA_SCHEMA_VERSION
    implementation_version: str = CHARACTER_DNA_IMPLEMENTATION_VERSION
    descender_id: str = Field(min_length=1)
    master_seed: int = Field(ge=0, le=2**63 - 1)
    species: Literal["human", "dwarf"]
    species_profile: Literal["species.human", "species.dwarf"]
    style_profile: str = Field(min_length=1)
    age_years: int = Field(ge=18, le=100)
    height_cm: float
    mass_kg: float
    body_fat: float = Field(ge=0.0, le=1.0)
    muscularity: float = Field(ge=0.0, le=1.0)
    shoulder_width: float = Field(ge=0.0, le=1.0)
    hip_width: float = Field(ge=0.0, le=1.0)
    torso_length: float = Field(ge=0.0, le=1.0)
    leg_length: float = Field(ge=0.0, le=1.0)
    arm_length: float = Field(ge=0.0, le=1.0)
    head_scale: float = Field(ge=0.0, le=1.0)
    jaw_width: float = Field(ge=0.0, le=1.0)
    chin_prominence: float = Field(ge=0.0, le=1.0)
    cheek_prominence: float = Field(ge=0.0, le=1.0)
    nose_scale: float = Field(ge=0.0, le=1.0)
    brow_prominence: float = Field(ge=0.0, le=1.0)
    eye_scale: float = Field(ge=0.0, le=1.0)
    facial_fullness: float = Field(ge=0.0, le=1.0)
    face_seed: int = Field(ge=0, le=2**31 - 1)
    skin_variant: str
    eye_variant: str
    base_hair_asset: str
    base_facial_hair_asset: str | None = None
    appearance: PersistentAppearance

    @model_validator(mode="after")
    def validate_species_profile(self) -> "CharacterDNA":
        expected = f"species.{self.species}"
        if self.species_profile != expected:
            raise ValueError(f"species profile must be {expected}")
        if self.species == "human":
            if not 150.0 <= self.height_cm <= 205.0 or not 45.0 <= self.mass_kg <= 160.0:
                raise ValueError("Human body measurements are outside the v1 profile")
        else:
            if not 118.0 <= self.height_cm <= 158.0 or not 48.0 <= self.mass_kg <= 135.0:
                raise ValueError("Dwarf body measurements are outside the v1 profile")
            if self.shoulder_width < 0.5 or self.head_scale < 0.55:
                raise ValueError("Dwarf v1 requires a broad frame and corrected head proportion")
        transient_tokens = ("/Game/", "PersistentLevel.", "SkeletalMeshActor_", "0x")
        encoded = canonical_json(self)
        if any(token in encoded for token in transient_tokens):
            raise ValueError("Character DNA contains renderer-specific transient state")
        return self

    def digest(self) -> str:
        return deterministic_digest(self)


class CharacterDNAGenerator:
    """Generate constrained, correlated Human and Dwarf identity distributions."""

    HUMAN_HAIR = (
        "mpfb.system.hair.short01",
        "mpfb.system.hair.short02",
        "mpfb.system.hair.short03",
        "mpfb.system.hair.long01",
    )
    DWARF_HAIR = (
        "mpfb.system.hair.short02",
        "mpfb.system.hair.short04",
        "mpfb.system.hair.long01",
        "mpfb.system.hair.braid01",
    )
    DWARF_BEARD = (
        "underreach.generated.beard.short",
        "underreach.generated.beard.braided",
        "underreach.generated.beard.full",
    )

    def __init__(self, namespace_seed: str = "underreach-character-population-v1") -> None:
        self.namespace_seed = namespace_seed

    def seed_for(self, descender_id: str, species: str, ordinal: int = 0) -> int:
        value = f"{self.namespace_seed}:{species}:{descender_id}:{ordinal}"
        return int.from_bytes(sha256(value.encode("utf-8")).digest()[:8], "big") & (2**63 - 1)

    def generate(
        self,
        descender_id: str,
        species: Literal["human", "dwarf"],
        *,
        ordinal: int = 0,
        body_profile: str | None = None,
    ) -> CharacterDNA:
        seed = self.seed_for(descender_id, species, ordinal)
        frame = _bounded(0.5 + _normal(seed, "frame") * 0.14, 0.12, 0.9)
        muscle = _bounded(0.48 + _normal(seed, "muscle") * 0.16, 0.12, 0.9)
        adiposity = _bounded(0.24 + _normal(seed, "fat") * 0.095, 0.06, 0.48)
        if body_profile == "short_heavy":
            frame, muscle, adiposity = 0.72, 0.57, 0.39
        elif body_profile == "tall_thin":
            frame, muscle, adiposity = 0.34, 0.38, 0.11
        elif body_profile == "heavy":
            frame, muscle, adiposity = 0.79, 0.66, 0.38
        elif body_profile == "alternate":
            frame, muscle, adiposity = 0.52, 0.42, 0.18

        if species == "human":
            height = _bounded(177.0 + _normal(seed, "height") * 10.0, 150.0, 205.0)
            if body_profile == "short_heavy":
                height = 158.0
            elif body_profile == "tall_thin":
                height = 201.0
            shoulder = _bounded(0.34 + frame * 0.38 + muscle * 0.13, 0.2, 0.9)
            hip = _bounded(0.3 + frame * 0.25 + adiposity * 0.23, 0.2, 0.82)
            torso = _bounded(0.49 + _normal(seed, "torso") * 0.08, 0.28, 0.73)
            legs = _bounded(0.51 + (height - 177.0) / 180.0 + _normal(seed, "legs") * 0.045, 0.3, 0.78)
            arms = _bounded(0.5 + (height - 177.0) / 220.0 + _normal(seed, "arms") * 0.04, 0.32, 0.75)
            head = _bounded(0.48 - (height - 177.0) / 260.0, 0.35, 0.65)
            bmi = 20.0 + adiposity * 23.0 + muscle * 4.5 + frame * 2.0
            hair = _pick(seed, "hair", self.HUMAN_HAIR)
            beard = None if _unit(seed, "beard-chance") < 0.62 else "underreach.generated.beard.short"
            clothing = ["underreach.clothing.tunic.v1", "underreach.clothing.trousers.v1", "underreach.clothing.boots.v1"]
            equipment = ["underreach.armor.helmet.v1", "underreach.armor.breastplate.v1", "underreach.weapon.sword.v1"]
            style = "earth_survivor"
        else:
            height = _bounded(139.0 + _normal(seed, "height") * 7.0, 118.0, 158.0)
            if body_profile == "heavy":
                height = 132.0
            elif body_profile == "alternate":
                height = 149.0
            shoulder = _bounded(0.58 + frame * 0.3 + muscle * 0.1, 0.5, 0.96)
            hip = _bounded(0.5 + frame * 0.22 + adiposity * 0.15, 0.44, 0.9)
            torso = _bounded(0.58 + _normal(seed, "torso") * 0.055, 0.44, 0.79)
            legs = _bounded(0.27 + _normal(seed, "legs") * 0.04, 0.18, 0.39)
            arms = _bounded(0.36 + _normal(seed, "arms") * 0.045, 0.24, 0.49)
            head = _bounded(0.66 + _normal(seed, "head") * 0.045, 0.55, 0.79)
            bmi = 27.0 + adiposity * 20.0 + muscle * 5.5 + frame * 2.5
            hair = _pick(seed, "hair", self.DWARF_HAIR)
            beard = _pick(seed, "beard", self.DWARF_BEARD)
            clothing = ["underreach.clothing.tunic.v1", "underreach.clothing.trousers.v1", "underreach.clothing.boots.v1"]
            equipment = ["underreach.armor.helmet.v1", "underreach.armor.breastplate.v1", "underreach.weapon.sword.v1"]
            style = "underreach_delver"

        mass = _bounded(bmi * (height / 100.0) ** 2, 45.0 if species == "human" else 48.0, 160.0 if species == "human" else 135.0)
        face_fullness = _bounded(0.2 + adiposity * 0.72 + frame * 0.1, 0.12, 0.82)
        jaw = _bounded(0.35 + frame * 0.34 + (0.1 if species == "dwarf" else 0.0) + _normal(seed, "jaw") * 0.06, 0.15, 0.93)
        age = int(round(_bounded(34.0 + _normal(seed, "age") * 11.0, 18.0, 72.0)))
        face_seed = int(_unit(seed, "face-seed") * (2**31 - 1))
        skin = _pick(seed, "skin", ("skin_001", "skin_002", "skin_003", "skin_004", "skin_005"))
        eyes = _pick(seed, "eyes", ("eye_001", "eye_002", "eye_003", "eye_004"))
        appearance = PersistentAppearance(
            current_hair_asset=hair,
            facial_hair_asset=beard,
            clothing_asset_ids=clothing,
            equipment_visual_ids=equipment,
        )
        return CharacterDNA(
            descender_id=descender_id,
            master_seed=seed,
            species=species,
            species_profile=f"species.{species}",
            style_profile=style,
            age_years=age,
            height_cm=height,
            mass_kg=mass,
            body_fat=adiposity,
            muscularity=muscle,
            shoulder_width=shoulder,
            hip_width=hip,
            torso_length=torso,
            leg_length=legs,
            arm_length=arms,
            head_scale=head,
            jaw_width=jaw,
            chin_prominence=_bounded(0.48 + _normal(seed, "chin") * 0.13, 0.14, 0.86),
            cheek_prominence=_bounded(0.38 + face_fullness * 0.25 + _normal(seed, "cheek") * 0.09, 0.12, 0.9),
            nose_scale=_bounded(0.48 + _normal(seed, "nose") * 0.13 + (0.05 if species == "dwarf" else 0.0), 0.14, 0.9),
            brow_prominence=_bounded(0.43 + _normal(seed, "brow") * 0.12 + (0.08 if species == "dwarf" else 0.0), 0.12, 0.92),
            eye_scale=_bounded(0.5 + _normal(seed, "eye-scale") * 0.1, 0.18, 0.82),
            facial_fullness=face_fullness,
            face_seed=face_seed,
            skin_variant=skin,
            eye_variant=eyes,
            base_hair_asset=hair,
            base_facial_hair_asset=beard,
            appearance=appearance,
        )

    def population(self, species: Literal["human", "dwarf"], count: int) -> list[CharacterDNA]:
        if count < 1:
            raise ValueError("population count must be positive")
        return [self.generate(f"population_{species}_{index:03d}", species, ordinal=index) for index in range(count)]


Migration = Callable[[dict[str, Any]], dict[str, Any]]
MIGRATIONS: dict[int, Migration] = {}


def register_migration(source_version: int, migration: Migration) -> None:
    if source_version in MIGRATIONS:
        raise ValueError(f"migration from schema {source_version} is already registered")
    MIGRATIONS[source_version] = migration


def migrate_character_dna(payload: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(canonical_json(payload))
    version = int(value.get("schema_version", 0))
    while version < CHARACTER_DNA_SCHEMA_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise ValueError(f"no Character DNA migration from schema {version}")
        value = migration(value)
        version = int(value.get("schema_version", version))
    if version != CHARACTER_DNA_SCHEMA_VERSION:
        raise ValueError(f"unsupported Character DNA schema {version}")
    return value


class CharacterDNAStore:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def path_for(self, descender_id: str) -> Path:
        safe = "".join(character for character in descender_id if character.isalnum() or character in "-_")
        if not safe or safe != descender_id:
            raise ValueError("descender ID is not safe for a DNA filename")
        return self.directory / f"{safe}.character-dna.json"

    def save(self, dna: CharacterDNA) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(dna.descender_id)
        temporary = path.with_suffix(path.suffix + ".tmp")
        encoded = (json.dumps(dna.model_dump(mode="json"), indent=2, sort_keys=True) + "\n").encode("utf-8")
        with temporary.open("wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        reloaded = CharacterDNA.model_validate(migrate_character_dna(json.loads(temporary.read_text(encoding="utf-8"))))
        if reloaded.digest() != dna.digest():
            raise RuntimeError("Character DNA changed during persistence validation")
        os.replace(temporary, path)
        return path

    def load(self, descender_id: str) -> CharacterDNA:
        value = json.loads(self.path_for(descender_id).read_text(encoding="utf-8"))
        return CharacterDNA.model_validate(migrate_character_dna(value))
