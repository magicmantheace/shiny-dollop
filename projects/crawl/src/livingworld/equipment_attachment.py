"""Deterministic presentation-only equipment attachment profiles.

The profiles are renderer metadata. They never change canonical equipment or
Character DNA; Blender and Unreal consume the same resolved records so a
reconstructed Descender receives identical attachment geometry.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ATTACHMENT_PROFILE_PROTOCOL = "underreach.equipment-attachment.v1"


class EquipmentAttachmentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol: Literal["underreach.equipment-attachment.v1"] = ATTACHMENT_PROFILE_PROTOCOL
    item_visual_id: str
    slot: Literal["head_armor", "chest_armor", "right_hand"]
    socket_name: Literal["head", "spine_03", "hand_r"]
    attachment_mode: Literal["skeletal_skin"] = "skeletal_skin"
    handedness: Literal["none", "right"] = "none"
    anchor_fraction: float = Field(ge=0.0, le=1.0)
    relative_location_cm: tuple[float, float, float]
    relative_rotation_degrees: tuple[float, float, float]
    relative_scale: tuple[float, float, float]
    geometry: dict[str, float | str]
    species: Literal["human", "dwarf"]

    @model_validator(mode="after")
    def validate_profile(self) -> "EquipmentAttachmentProfile":
        if any(value <= 0 for value in self.relative_scale):
            raise ValueError("attachment scale must be positive")
        required = {"helmet": "depth_cm", "breastplate": "width_cm", "sword": "blade_length_cm"}
        kind = str(self.geometry.get("kind", ""))
        key = required.get(kind)
        if key is None or float(self.geometry.get(key, 0.0)) <= 0.0:
            raise ValueError(f"invalid attachment geometry for {kind}")
        return self


_BASE = {
    "underreach.armor.helmet.v1": {
        "slot": "head_armor", "socket_name": "head", "handedness": "none",
        "anchor_fraction": 0.64, "relative_location_cm": (0.0, 0.0, 0.0),
        "relative_rotation_degrees": (0.0, 0.0, 0.0), "relative_scale": (1.0, 1.0, 1.0),
    },
    "underreach.armor.breastplate.v1": {
        "slot": "chest_armor", "socket_name": "spine_03", "handedness": "none",
        "anchor_fraction": 0.48, "relative_location_cm": (0.0, -19.0, -1.5),
        "relative_rotation_degrees": (0.0, 0.0, 0.0), "relative_scale": (1.0, 1.0, 1.0),
    },
    "underreach.weapon.sword.v1": {
        "slot": "right_hand", "socket_name": "hand_r", "handedness": "right",
        "anchor_fraction": 0.0, "relative_location_cm": (0.0, 0.0, 0.0),
        "relative_rotation_degrees": (0.0, 0.0, 0.0), "relative_scale": (1.0, 1.0, 1.0),
    },
}

_SPECIES = {
    "human": {
        "underreach.armor.helmet.v1": {"geometry": {"kind": "helmet", "radius_cm": 10.8, "depth_cm": 18.0}},
        "underreach.armor.breastplate.v1": {"geometry": {"kind": "breastplate", "width_cm": 36.0, "depth_cm": 3.5, "height_cm": 24.0}},
        "underreach.weapon.sword.v1": {"geometry": {"kind": "sword", "blade_length_cm": 64.0, "blade_base_radius_cm": 3.2, "blade_tip_radius_cm": 0.8, "guard_width_cm": 18.0, "handle_length_cm": 13.0}},
    },
    "dwarf": {
        "underreach.armor.helmet.v1": {"geometry": {"kind": "helmet", "radius_cm": 11.8, "depth_cm": 17.0}},
        "underreach.armor.breastplate.v1": {
            "relative_location_cm": (0.0, -17.5, -1.0),
            "geometry": {"kind": "breastplate", "width_cm": 38.0, "depth_cm": 4.0, "height_cm": 22.0},
        },
        "underreach.weapon.sword.v1": {"geometry": {"kind": "sword", "blade_length_cm": 52.0, "blade_base_radius_cm": 3.0, "blade_tip_radius_cm": 0.8, "guard_width_cm": 16.0, "handle_length_cm": 11.0}},
    },
}


def attachment_profiles(species: str) -> tuple[EquipmentAttachmentProfile, ...]:
    if species not in _SPECIES:
        raise ValueError(f"unsupported attachment species: {species}")
    records = []
    for item_visual_id in sorted(_BASE):
        values = deepcopy(_BASE[item_visual_id])
        values.update(deepcopy(_SPECIES[species][item_visual_id]))
        records.append(EquipmentAttachmentProfile(
            item_visual_id=item_visual_id,
            species=species,
            **values,
        ))
    if len({item.slot for item in records}) != len(records):
        raise ValueError("equipment attachment slots must be exclusive")
    return tuple(records)


def attachment_profile_payload(species: str) -> list[dict]:
    return [item.model_dump(mode="json") for item in attachment_profiles(species)]
