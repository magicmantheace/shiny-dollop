"""Explicit candidate -> approved promotion with machine-checked gates.

Implements the ASSET_PIPELINE lifecycle step "Promote explicitly to
approved" for the local library. Every gate that can be checked from the
catalog record plus the asset-store files is checked here and recorded
in validation_runs. Gates that need a human (visual animation/thumbnail
review, owner-hardware visual/FPS check) are NEVER silently passed:
they are returned as pending, printed by the CLI, and recorded in the
promotion validation row's detail text.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import gltf
from .library import Library

PENDING_GATES = (
    ("visual_review", "visual animation/thumbnail review needs a human reviewer"),
    ("owner_hardware_visual", "visual/FPS check on owner hardware is outstanding"),
)

DEFAULT_ASSET_ROOT = Path(
    os.environ.get("AI_ANIMATION_ASSET_ROOT",
                   Path.home() / "workspace" / "ai-animation-studio-assets"))


class PromotionError(RuntimeError):
    pass


def _gate(results: list, name: str, passed: bool, detail: str) -> bool:
    results.append({"gate": name, "passed": passed, "detail": detail})
    return passed


def check_asset_gates(lib: Library, asset: dict, root: Path) -> list[dict]:
    """Machine-checkable promotion gates for one catalogued asset."""
    results: list[dict] = []
    meta = asset.get("metadata") or {}
    uri = asset["uri"]
    target = root / uri
    ok = _gate(results, "status_is_candidate", asset["status"] == "candidate",
               f"status is {asset['status']!r}")
    if uri.endswith("/"):
        present = target.is_dir() and any(target.glob("*.glb"))
        _gate(results, "source_present", bool(present),
              f"pack directory {uri} {'present with GLB pieces' if present else 'missing or empty'}")
        pieces = meta.get("pieces") or {}
        bad = [name for name, digest in pieces.items()
               if not (target / name).is_file() or gltf.sha256_file(target / name) != digest]
        _gate(results, "piece_hashes_match", bool(pieces) and not bad,
              f"{len(pieces) - len(bad)}/{len(pieces)} piece hashes match"
              + (f"; failing: {', '.join(sorted(bad))}" if bad else ""))
        return results
    present = target.is_file()
    _gate(results, "source_present", present, f"{uri} {'present' if present else 'MISSING'}")
    if not present:
        return results
    expected = meta.get("sha256")
    if expected:
        actual = gltf.sha256_file(target)
        _gate(results, "hash_match", actual == expected,
              "sha256 matches catalog" if actual == expected
              else f"sha256 mismatch: file {actual[:12]}… != catalog {expected[:12]}…")
    else:
        _gate(results, "hash_match", False, "catalog records no sha256 for this file")
    try:
        doc = gltf.load_gltf_json(target)
    except (ValueError, KeyError, OSError) as err:
        _gate(results, "gltf_parse", False, f"could not parse glTF document: {err}")
        return results
    if asset.get("rig_id"):
        joints = gltf.joint_count(doc)
        declared = meta.get("joints")
        if declared is not None:
            _gate(results, "skeleton_facts", joints == declared,
                  f"skin joints {joints} (catalog declares {declared})")
        else:
            _gate(results, "skeleton_facts", joints > 0,
                  f"skin present with {joints} joints (no catalog declaration)")
    if asset["kind"] == "motion":
        clips = gltf.clip_durations(doc)
        declared = meta.get("clips") or {}
        names_ok = set(clips) == set(declared)
        durations_ok = all(abs(clips[name] - float(declared[name])) <= 0.01
                           for name in declared if name in clips)
        _gate(results, "clip_inventory", names_ok and durations_ok
              and meta.get("clip_count") == len(clips),
              f"{len(clips)} clips in file vs {meta.get('clip_count')} catalogued"
              + ("" if names_ok and durations_ok else "; name/duration mismatch"))
    return results


def promote_asset(lib: Library, asset_id: str, root: Path) -> dict:
    asset = lib.get_asset(asset_id)
    if asset is None:
        raise PromotionError(f"asset {asset_id} is not registered in this database")
    results = check_asset_gates(lib, asset, root)
    for result in results:
        lib.record_validation(asset_id, "gate:" + result["gate"],
                              result["passed"], result["detail"])
    promoted = all(result["passed"] for result in results)
    pending = [name for name, _reason in PENDING_GATES]
    if promoted:
        lib.set_asset_status(asset_id, "approved")
        lib.record_validation(
            asset_id, "promotion", True,
            "promoted candidate -> approved; pending human gates: "
            + ", ".join(pending))
    else:
        lib.record_validation(asset_id, "promotion", False,
                              "promotion refused: a machine gate failed")
    return {"asset_id": asset_id, "promoted": promoted, "gates": results,
            "pending": pending}


def promote_character(lib: Library, character_id: str) -> dict:
    character = lib.get_character(character_id)
    if character is None:
        raise PromotionError(f"character {character_id} is not registered in this database")
    results: list[dict] = []
    _gate(results, "status_is_candidate", character["status"] == "candidate",
          f"status is {character['status']!r}")
    body = lib.get_asset(character["body_base"])
    _gate(results, "body_asset_approved", body is not None and body["status"] == "approved",
          f"body_base {character['body_base']} "
          + ("approved" if body and body["status"] == "approved" else "not approved/missing"))
    if body is not None:
        _gate(results, "rig_match", body.get("rig_id") == character["rig_id"],
              f"body rig {body.get('rig_id')!r} vs recipe rig {character['rig_id']!r}")
    hair = lib.get_asset(character["hair"])
    if hair is not None:
        _gate(results, "hair_asset_approved", hair["status"] == "approved",
              f"hair {character['hair']} "
              + ("approved" if hair["status"] == "approved" else "not approved"))
    promoted = all(result["passed"] for result in results)
    if promoted:
        lib.set_character_status(character_id, "approved")
    return {"character_id": character_id, "promoted": promoted, "gates": results,
            "pending": [name for name, _reason in PENDING_GATES]}
