"""Recipe composition (F2 slice 2): per-part compatibility rules.

`studio.schema.validate_character` checks the *shape* of a character recipe
(identifier forms, outfit list, colors, status). This module checks the
recipe against the library it names: every part must exist, must be the
asset kind its slot requires, and must agree with the recipe's rig. A part
with a null `rig_id` is rig-agnostic and fits any rig.

Approval is a separate axis (ADR-008: playback resolves approved assets
only). With `require_approved=True` assembly refuses any part that is not
approved; otherwise candidate/retired parts assemble fine and are reported
by `unapproved_parts`. The assembled recipe keeps the existing wire shape —
`schemas/character.schema.json` forbids additional properties, so no
computed field is stored on it; approval state is reported, not persisted.
"""
from __future__ import annotations

from .schema import ValidationError, validate_character

# Slot name -> the asset kind that slot accepts.
SLOT_KINDS = {
    "body_base": "body",
    "head": "head",
    "hair": "hair",
    "outfit": "outfit",
}


class RecipeError(ValueError):
    """A character spec cannot be assembled; the message names the reason."""


def _slots(spec: dict) -> list[tuple[str, str]]:
    """(slot, part_id) pairs in check order: fixed slots, then outfit order."""
    pairs = [(slot, spec[slot]) for slot in ("body_base", "head", "hair")]
    pairs += [("outfit", part_id) for part_id in spec["outfit"]]
    return pairs


def _check_part(library, spec: dict, slot: str, part_id: str,
                require_approved: bool) -> dict:
    asset = library.get_asset(part_id)
    if asset is None:
        raise RecipeError(
            f"recipe part {slot} '{part_id}': no such asset in the library")
    expected_kind = SLOT_KINDS[slot]
    if asset["kind"] != expected_kind:
        raise RecipeError(
            f"recipe part {slot} '{part_id}': asset kind is '{asset['kind']}', "
            f"slot requires '{expected_kind}'")
    part_rig = asset.get("rig_id")
    if part_rig is not None and part_rig != spec["rig_id"]:
        raise RecipeError(
            f"recipe part {slot} '{part_id}': asset rig is '{part_rig}', "
            f"recipe rig is '{spec['rig_id']}'")
    if require_approved and asset["status"] != "approved":
        raise RecipeError(
            f"recipe part {slot} '{part_id}': asset status is "
            f"'{asset['status']}', 'approved' required")
    return asset


def assemble_character(library, spec: dict, *,
                       require_approved: bool = False) -> dict:
    """Validate a character spec against the library and return the recipe.

    Raises RecipeError with a named reason for the first failure: malformed
    spec (shape errors from validate_character are re-raised as RecipeError),
    unknown part, wrong asset kind for a slot, rig disagreement, or — with
    require_approved=True — an unapproved part. On success the spec is
    returned unchanged, in the existing recipe shape, ready for
    `Library.put_character`.
    """
    try:
        validate_character(spec)
    except ValidationError as err:
        raise RecipeError(f"invalid character spec: {err}") from err
    for slot, part_id in _slots(spec):
        _check_part(library, spec, slot, part_id, require_approved)
    return spec


def unapproved_parts(library, spec: dict) -> list[str]:
    """Part ids in the recipe whose library status is not 'approved'.

    Reporting companion to assemble_character for callers that assembled
    without require_approved (e.g. the CLI). Assumes the parts exist —
    run it on a spec that assembled successfully.
    """
    pending = []
    for _slot, part_id in _slots(spec):
        asset = library.get_asset(part_id)
        if asset is not None and asset["status"] != "approved":
            pending.append(part_id)
    return pending
