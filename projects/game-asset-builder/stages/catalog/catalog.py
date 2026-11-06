"""Catalog stage: metadata + sha256 for a finished asset (stdlib only).

A catalog entry lives at ``catalog/<slug>/metadata.json`` and is the
committed record of the asset. The .glb itself stays in the local
``outputs/<slug>/`` area (generated outputs never enter git); the entry
pins it by filename + sha256 so any copy can be verified against the
record.
"""

import hashlib
import json
import os

ENTRY_VERSION = 1


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def slugify(name: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in name.lower())
    return "-".join(part for part in slug.split("-") if part)


def build_entry(name: str, source_concept: str, glb_path: str,
                counts: dict, bones: list[str], actions: list[str],
                provenance: dict) -> dict:
    return {
        "entry_version": ENTRY_VERSION,
        "name": name,
        "slug": slugify(name),
        "source_concept": source_concept,
        "asset_file": os.path.basename(glb_path),
        "asset_location": "outputs/<slug>/ (local; not in git)",
        "sha256": sha256_file(glb_path),
        "bytes": os.path.getsize(glb_path),
        "counts": counts,
        "bones": bones,
        "actions": actions,
        "provenance": provenance,
    }


def write_entry(catalog_dir: str, entry: dict) -> str:
    folder = os.path.join(catalog_dir, entry["slug"])
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "metadata.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(entry, fh, indent=1)
        fh.write("\n")
    return path


def read_entry(catalog_dir: str, slug: str) -> dict:
    with open(os.path.join(catalog_dir, slug, "metadata.json"),
              encoding="utf-8") as fh:
        return json.load(fh)


def verify_entry(entry: dict, glb_path: str) -> bool:
    return os.path.exists(glb_path) \
        and sha256_file(glb_path) == entry["sha256"] \
        and os.path.getsize(glb_path) == entry["bytes"]
