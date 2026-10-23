"""Replaceable presentation mapping from Character DNA to renderer manifests."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .character_dna import CharacterDNA, canonical_json, deterministic_digest
from .equipment_attachment import attachment_profile_payload


CHARACTER_FACTORY_PROTOCOL = "underreach.character-renderer-manifest.v1"
CHARACTER_FACTORY_VERSION = "29a2.1"
HUMANOID_SKELETON_CONTRACT = "underreach.humanoid.manny.v1"


class AssetProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    creator: str
    source_url: str
    license: str
    date_acquired: str
    local_source_path: str
    project_path: str
    modifications: list[str] = Field(default_factory=list)
    unreal_only: bool = False
    attribution_required: bool = False

    @model_validator(mode="after")
    def validate_provenance(self) -> "AssetProvenance":
        if not self.source_url or not self.license or not self.creator:
            raise ValueError("asset provenance requires source, creator, and license")
        return self


class AppearanceAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str
    kind: Literal["hair", "facial_hair", "soft_clothing", "rigid_armor", "rigid_weapon"]
    slot: str
    species_compatibility: set[Literal["human", "dwarf"]]
    body_classes: set[str] = Field(default_factory=lambda: {"all"})
    style_tags: set[str] = Field(default_factory=set)
    supported_morph_groups: set[str] = Field(default_factory=set)
    conflicts: set[str] = Field(default_factory=set)
    source_asset: str
    unreal_asset: str
    provenance: AssetProvenance


class CharacterAssetRegistry:
    def __init__(self, assets: list[AppearanceAsset]) -> None:
        self.assets = {asset.asset_id: asset for asset in assets}
        if len(self.assets) != len(assets):
            raise ValueError("appearance asset IDs must be unique")

    def validate_selection(self, dna: CharacterDNA) -> tuple[AppearanceAsset, ...]:
        selected_ids = [
            dna.appearance.current_hair_asset,
            *([dna.appearance.facial_hair_asset] if dna.appearance.facial_hair_asset else []),
            *dna.appearance.clothing_asset_ids,
            *dna.appearance.equipment_visual_ids,
        ]
        selected: list[AppearanceAsset] = []
        occupied: dict[str, str] = {}
        for asset_id in selected_ids:
            asset = self.assets.get(asset_id)
            if asset is None:
                raise KeyError(f"appearance asset is not registered: {asset_id}")
            if dna.species not in asset.species_compatibility:
                raise ValueError(f"{asset_id} is not compatible with {dna.species}")
            if asset.slot in occupied:
                raise ValueError(f"appearance slot conflict: {asset.slot}")
            if any(conflict in selected_ids for conflict in asset.conflicts):
                raise ValueError(f"appearance conflict for {asset_id}")
            occupied[asset.slot] = asset_id
            selected.append(asset)
        return tuple(selected)

    def digest(self) -> str:
        return deterministic_digest([self.assets[key] for key in sorted(self.assets)])


class CharacterRendererManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Literal["underreach.character-renderer-manifest.v1"] = CHARACTER_FACTORY_PROTOCOL
    factory_version: str = CHARACTER_FACTORY_VERSION
    descender_id: str
    dna_digest: str
    species: Literal["human", "dwarf"]
    skeleton_contract: str = HUMANOID_SKELETON_CONTRACT
    animation_family: str = "humanoid.standard"
    source_body_asset: str
    body_morphs: dict[str, float]
    face_morphs: dict[str, float]
    mutable_parameters: dict[str, str | float | bool]
    material_profile: str
    asset_ids: list[str]
    asset_registry_digest: str
    actor_scale: float
    stride_scale: float
    foot_ik_offset_cm: float
    facial_contract: list[str]
    equipment_attachments: list[dict[str, Any]]
    visual_variant: str = "species_average"
    material_variants: dict[str, str] = Field(default_factory=dict)

    def digest(self) -> str:
        return deterministic_digest(self)


class RenderInstance(BaseModel):
    """Disposable renderer state. It is deliberately not serializable as DNA."""

    model_config = ConfigDict(extra="forbid")

    descender_id: str
    manifest_digest: str
    terminal: bool = False
    unreal_object_path: str | None = None
    cache_key: str


FACE_CONTRACT = [
    "blink_left", "blink_right", "eye_look_left", "eye_look_right", "brow_up", "brow_down",
    "jaw_open", "lip_pucker", "lip_funnel", "lip_stretch", "smile", "frown",
    "viseme_aa", "viseme_ee", "viseme_ih", "viseme_oh", "viseme_ou", "viseme_fv", "viseme_mbp",
]


def _provenance(title: str, source: str, project_path: str, *, creator: str = "Underreach project") -> AssetProvenance:
    internal = source.startswith("internal://")
    return AssetProvenance(
        title=title,
        creator=creator,
        source_url=source,
        license="Project-authored proxy" if internal else "CC0 / MakeHuman System Assets",
        date_acquired="2026-08-24",
        local_source_path=source,
        project_path=project_path,
        modifications=["Deterministic fitting and Unreal export for Slice 29A.1"],
        attribution_required=False,
    )


def default_character_asset_registry() -> CharacterAssetRegistry:
    species = {"human", "dwarf"}
    assets: list[AppearanceAsset] = []
    for name in ("short01", "short02", "short03", "short04", "long01", "braid01"):
        asset_id = f"mpfb.system.hair.{name}"
        assets.append(AppearanceAsset(
            asset_id=asset_id, kind="hair", slot="hair", species_compatibility=species,
            style_tags={"hair"}, supported_morph_groups={"head", "body"},
            source_asset=f"mpfb://makehuman_system_assets/hair/{name}",
            unreal_asset=f"/Game/Underreach29A1/Hair/{name}",
            provenance=_provenance(name, "https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html", f"/Game/Underreach29A1/Hair/{name}", creator="MakeHuman Community"),
        ))
    for name in ("short", "braided", "full"):
        asset_id = f"underreach.generated.beard.{name}"
        assets.append(AppearanceAsset(
            asset_id=asset_id, kind="facial_hair", slot="facial_hair", species_compatibility=species,
            style_tags={"facial_hair"}, supported_morph_groups={"head"},
            source_asset=f"internal://29a1/beard/{name}", unreal_asset=f"/Game/Underreach29A1/Hair/Beard_{name}",
            provenance=_provenance(f"Procedural {name} beard", f"internal://29a1/beard/{name}", f"/Game/Underreach29A1/Hair/Beard_{name}"),
        ))
    for asset_id, slot, source_name in (
        ("underreach.clothing.tunic.v1", "upper_body", "male_casualsuit01"),
        ("underreach.clothing.trousers.v1", "lower_body", "male_casualsuit02"),
        ("underreach.clothing.boots.v1", "feet", "shoes01"),
    ):
        assets.append(AppearanceAsset(
            asset_id=asset_id, kind="soft_clothing", slot=slot, species_compatibility=species,
            body_classes={"average", "short_heavy", "tall_thin", "dwarf"},
            style_tags={"earth_survivor", "underreach_delver"},
            supported_morph_groups={"height", "mass", "muscle", "proportions"},
            source_asset=f"mpfb://makehuman_system_assets/clothes/{source_name}",
            unreal_asset=f"/Game/Underreach29A1/Clothing/{asset_id.rsplit('.', 2)[-2].title()}",
            provenance=_provenance(source_name, "https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html", f"/Game/Underreach29A1/Clothing/{source_name}", creator="MakeHuman Community"),
        ))
    for index in range(1, 6):
        source_name = f"male_casualsuit{index:02d}"
        asset_id = f"underreach.clothing.outfit.casual{index:02d}.v1"
        assets.append(AppearanceAsset(
            asset_id=asset_id, kind="soft_clothing", slot="full_body", species_compatibility=species,
            body_classes={"average", "short_heavy", "tall_thin", "dwarf"},
            style_tags={"earth_survivor", "rugged", "practical", "lightweight"},
            supported_morph_groups={"height", "mass", "muscle", "proportions"},
            source_asset=f"mpfb://makehuman_system_assets/clothes/{source_name}",
            unreal_asset=f"/Game/Underreach29A1/Clothing/Outfit_Casual{index:02d}",
            provenance=_provenance(source_name, "https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html", f"/Game/Underreach29A1/Clothing/{source_name}", creator="MakeHuman Community"),
        ))
    assets.append(AppearanceAsset(
        asset_id="underreach.clothing.outfit.worksuit01.v1", kind="soft_clothing", slot="full_body",
        species_compatibility=species, body_classes={"average", "short_heavy", "tall_thin", "dwarf"},
        style_tags={"rugged", "practical", "armored"},
        supported_morph_groups={"height", "mass", "muscle", "proportions"},
        source_asset="mpfb://makehuman_system_assets/clothes/male_worksuit01",
        unreal_asset="/Game/Underreach29A1/Clothing/Outfit_Worksuit01",
        provenance=_provenance("male_worksuit01", "https://static.makehumancommunity.org/assets/assetpacks/makehuman_system_assets.html", "/Game/Underreach29A1/Clothing/male_worksuit01", creator="MakeHuman Community"),
    ))
    for asset_id, kind, slot, name in (
        ("underreach.armor.helmet.v1", "rigid_armor", "head_armor", "Helmet_Proxy"),
        ("underreach.armor.breastplate.v1", "rigid_armor", "chest_armor", "Breastplate_Proxy"),
        ("underreach.weapon.sword.v1", "rigid_weapon", "right_hand", "Sword_Proxy"),
    ):
        assets.append(AppearanceAsset(
            asset_id=asset_id, kind=kind, slot=slot, species_compatibility=species,
            body_classes={"all"}, style_tags={"underreach", "proof"},
            supported_morph_groups=set(), source_asset=f"internal://29a1/{name}",
            unreal_asset=f"/Game/Underreach29A1/Equipment/SM_{name}",
            provenance=_provenance(name, f"internal://29a1/{name}", f"/Game/Underreach29A1/Equipment/SM_{name}"),
        ))
    return CharacterAssetRegistry(assets)


class CharacterFactory:
    def __init__(self, registry: CharacterAssetRegistry | None = None) -> None:
        self.registry = registry or default_character_asset_registry()

    @property
    def version(self) -> str:
        return CHARACTER_FACTORY_VERSION

    @staticmethod
    def visual_variant(dna: CharacterDNA) -> str:
        if dna.species == "human":
            if dna.height_cm >= 187.0 and dna.mass_kg <= 90.0:
                return "human_tall_thin"
            if dna.height_cm <= 168.0 or dna.mass_kg >= 100.0:
                return "human_short_heavy"
            return "human_average"
        if dna.mass_kg >= 90.0 or dna.body_fat >= 0.32:
            return "dwarf_heavy"
        if dna.height_cm >= 145.0 and dna.mass_kg < 90.0:
            return "dwarf_alt"
        return "dwarf_average"

    def map(self, dna: CharacterDNA) -> CharacterRendererManifest:
        selected = self.registry.validate_selection(dna)
        reference_height = 178.0 if dna.species == "human" else 142.0
        # Dwarf stature is carried partly by actor scale and partly by authored
        # geometry proportions; it is therefore visibly non-uniform.
        actor_scale = dna.height_cm / reference_height
        body = {
            "height": round((dna.height_cm - 118.0) / 87.0, 6),
            "mass": round(min(1.0, dna.mass_kg / 150.0), 6),
            "body_fat": dna.body_fat,
            "muscularity": dna.muscularity,
            "shoulder_width": dna.shoulder_width,
            "hip_width": dna.hip_width,
            "torso_length": dna.torso_length,
            "leg_length": dna.leg_length,
            "arm_length": dna.arm_length,
            "head_scale": dna.head_scale,
        }
        face = {
            "jaw_width": dna.jaw_width,
            "chin_prominence": dna.chin_prominence,
            "cheek_prominence": dna.cheek_prominence,
            "nose_scale": dna.nose_scale,
            "brow_prominence": dna.brow_prominence,
            "eye_scale": dna.eye_scale,
            "facial_fullness": dna.facial_fullness,
            "age": round((dna.age_years - 18) / 82.0, 6),
        }
        mutable: dict[str, str | float | bool] = {
            "Species": dna.species,
            "Body.Height": body["height"],
            "Body.Mass": body["mass"],
            "Body.Muscle": dna.muscularity,
            "Body.Fat": dna.body_fat,
            "Body.Shoulders": dna.shoulder_width,
            "Body.Hips": dna.hip_width,
            "Body.Torso": dna.torso_length,
            "Body.Legs": dna.leg_length,
            "Body.Arms": dna.arm_length,
            "Body.Head": dna.head_scale,
            "Face.Seed": float(dna.face_seed),
            "Skin": dna.skin_variant,
            "Eyes": dna.eye_variant,
            "Hair": dna.appearance.current_hair_asset,
            "Terminal": False,
        }
        selected_equipment = set(dna.appearance.equipment_visual_ids)
        return CharacterRendererManifest(
            descender_id=dna.descender_id,
            dna_digest=dna.digest(),
            species=dna.species,
            source_body_asset=f"mpfb.hm08.{dna.species}.29a1",
            body_morphs=body,
            face_morphs=face,
            mutable_parameters=mutable,
            material_profile=f"underreach.skin.{dna.skin_variant}",
            asset_ids=[asset.asset_id for asset in selected],
            asset_registry_digest=self.registry.digest(),
            actor_scale=round(actor_scale, 6),
            stride_scale=round(0.88 + dna.leg_length * 0.24, 6),
            foot_ik_offset_cm=round(-2.0 if dna.species == "dwarf" else 0.0, 6),
            facial_contract=list(FACE_CONTRACT),
            equipment_attachments=[
                item for item in attachment_profile_payload(dna.species)
                if item["item_visual_id"] in selected_equipment
            ],
            visual_variant=self.visual_variant(dna),
            material_variants={
                "skin": dna.skin_variant,
                "eyes": dna.eye_variant,
                "hair": dna.appearance.current_hair_asset,
                "cloth": dna.appearance.clothing_asset_ids[0] if dna.appearance.clothing_asset_ids else "none",
                "metal": f"iron_{int(dna.master_seed % 3) + 1:02d}",
            },
        )

    def instantiate(
        self,
        dna: CharacterDNA,
        *,
        terminal: bool = False,
        unreal_object_path: str | None = None,
    ) -> RenderInstance:
        manifest = self.map(dna)
        cache_key = sha256(f"{manifest.digest()}:{int(terminal)}".encode("utf-8")).hexdigest()
        return RenderInstance(
            descender_id=dna.descender_id,
            manifest_digest=manifest.digest(),
            terminal=terminal,
            unreal_object_path=unreal_object_path,
            cache_key=cache_key,
        )

    @staticmethod
    def gameplay_visual_binding(item: dict[str, Any], visual_asset_id: str) -> dict[str, Any]:
        """Bind art without allowing it to become the gameplay item definition."""
        if not item.get("id") or not item.get("category"):
            raise ValueError("gameplay item definition is incomplete")
        return {
            "item_id": item["id"],
            "item_category": item["category"],
            "visual_asset_id": visual_asset_id,
            "gameplay_digest": deterministic_digest(item),
            "authoritative": False,
        }
