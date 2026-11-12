"""Data layer for the local UI: catalog summaries, stage registry,
doctor facts, and preview-render paths. Pure stdlib; no HTTP here so
every function is unit-testable without a server.

The catalogued .glb files live outside git in ``outputs/<slug>/``;
a summary therefore reports presence by directory + size only. The
full sha256 check runs on demand (``verify_slug``) because hashing a
20 MB file per card per page load is wasteful.
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_DIR = os.path.join(PROJECT_DIR, "catalog")
OUTPUTS_DIR = os.path.join(PROJECT_DIR, "outputs")

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.match(slug or ""))


def _is_rigged(entry: dict) -> bool:
    """Provenance carries ``rigged`` on P1+ entries; the P0 entry
    predates the flag, so fall back to the bone list (a prop has
    none, a rigged asset always has some)."""
    provenance = entry.get("provenance") or {}
    if "rigged" in provenance:
        return bool(provenance["rigged"])
    return bool(entry.get("bones"))


def entry_summary(entry: dict, outputs_dir: str) -> dict:
    slug = entry["slug"]
    glb_path = os.path.join(outputs_dir, slug, entry["asset_file"])
    present = os.path.exists(glb_path)
    size_ok = present and os.path.getsize(glb_path) == entry["bytes"]
    renders_dir = os.path.join(outputs_dir, slug, "renders")
    previews = []
    if os.path.isdir(renders_dir):
        previews = sorted(f for f in os.listdir(renders_dir)
                          if f.lower().endswith(".png"))
    provenance = entry.get("provenance") or {}
    return {
        "slug": slug,
        "name": entry["name"],
        "asset_file": entry["asset_file"],
        "bytes": entry["bytes"],
        "sha256_short": entry["sha256"][:16],
        "counts": entry.get("counts", {}),
        "bone_count": len(entry.get("bones", [])),
        "actions": entry.get("actions", []),
        "rigged": _is_rigged(entry),
        "rig_template": provenance.get("rig_template"),
        "weight_method": provenance.get("weight_method"),
        "mesh_model": provenance.get("mesh_model"),
        "texture_model": provenance.get("texture_model"),
        "glb_present": present,
        "glb_size_ok": size_ok,
        "previews": previews,
    }


def list_catalog(catalog_dir: str = CATALOG_DIR,
                 outputs_dir: str = OUTPUTS_DIR) -> list[dict]:
    """Summaries for every catalogued asset, sorted by slug."""
    summaries = []
    if not os.path.isdir(catalog_dir):
        return summaries
    for slug in sorted(os.listdir(catalog_dir)):
        meta = os.path.join(catalog_dir, slug, "metadata.json")
        if not os.path.isfile(meta):
            continue
        with open(meta, encoding="utf-8") as fh:
            entry = json.load(fh)
        summaries.append(entry_summary(entry, outputs_dir))
    return summaries


def entry_detail(slug: str, catalog_dir: str = CATALOG_DIR,
                 outputs_dir: str = OUTPUTS_DIR) -> dict | None:
    """Full metadata for one asset plus a live sha256 verification.

    Returns None for an unknown slug. The verification result is
    ``{"present": bool, "sha256_match": bool}`` — the same check the
    CLI's ``catalog-verify`` runs.
    """
    if not valid_slug(slug):
        return None
    meta = os.path.join(catalog_dir, slug, "metadata.json")
    if not os.path.isfile(meta):
        return None
    with open(meta, encoding="utf-8") as fh:
        entry = json.load(fh)
    # Loaded by path, like pipeline.py loads the stage modules: the
    # catalog module lives one package deeper than the project root.
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gab_catalog_for_ui",
        os.path.join(PROJECT_DIR, "stages", "catalog", "catalog.py"))
    catalog_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(catalog_mod)
    glb_path = os.path.join(outputs_dir, slug, entry["asset_file"])
    return {
        "entry": entry,
        "summary": entry_summary(entry, outputs_dir),
        "verification": {
            "present": os.path.exists(glb_path),
            "sha256_match": catalog_mod.verify_entry(entry, glb_path),
        },
    }


def stage_table() -> list[dict]:
    from stages import STAGES
    return [{
        "index": i,
        "name": stage.name,
        "kind": stage.kind,
        "device": stage.device,
        "isolated_process": stage.isolated_process,
        "summary": stage.summary,
    } for i, stage in enumerate(STAGES)]


def doctor_info() -> dict:
    """The CLI ``doctor`` report as data (same probes, JSON shape)."""
    smi = shutil.which("nvidia-smi")
    gpu = None
    if smi:
        out = subprocess.run(
            [smi, "--query-gpu=name,memory.total,memory.free",
             "--format=csv,noheader"],
            capture_output=True, text=True, check=False)
        gpu = out.stdout.strip() or None
    blender = shutil.which("blender")
    if not blender:
        known = os.path.expanduser("~/workspace/tools/blender/blender")
        if os.path.exists(known):
            blender = known
    from stages import STAGES
    return {
        "python": sys.version.split()[0],
        "platform": f"{platform.system()} {platform.machine()}",
        "gpu": gpu,
        "blender": blender,
        "stages": [{
            "name": stage.name,
            "needs": stage.device,
            "can_run": stage.device != "gpu" or gpu is not None,
        } for stage in STAGES],
    }


def preview_path(outputs_dir: str, slug: str,
                 filename: str) -> str | None:
    """Resolve a preview render for serving, or None.

    Guards: slug must be a plain catalog slug, filename must be a
    bare ``*.png`` basename, and the resolved path must stay inside
    that slug's ``renders/`` directory.
    """
    if not valid_slug(slug):
        return None
    if not filename or os.path.basename(filename) != filename:
        return None
    if not filename.lower().endswith(".png"):
        return None
    renders_dir = os.path.join(outputs_dir, slug, "renders")
    candidate = os.path.realpath(os.path.join(renders_dir, filename))
    if os.path.commonpath([candidate, os.path.realpath(renders_dir)]) \
            != os.path.realpath(renders_dir):
        return None
    return candidate if os.path.isfile(candidate) else None
