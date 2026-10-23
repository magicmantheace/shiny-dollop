import json
import os
from pathlib import Path

import unreal

SCRIPT_VERSION = "v1"


def _project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _manifest_path():
    override = os.environ.get("CRAWL_STAGE_MANIFEST")
    if override:
        return Path(override)
    return _project_dir() / "Generated" / "stage_manifest.json"


def main():
    manifest_path = _manifest_path()
    if not manifest_path.exists():
        raise RuntimeError(f"Crawl staging manifest not found: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = str(manifest["digest"])
    suffix = digest[:10]
    level_asset = f"/Game/CrawlGenerated/CrawlVerticalSlice_{SCRIPT_VERSION}_{suffix}"
    sequence_name = f"LS_CrawlVerticalSlice_{SCRIPT_VERSION}_{suffix}"
    sequence_asset = f"/Game/CrawlGenerated/{sequence_name}"

    level_exists = unreal.EditorAssetLibrary.does_asset_exist(level_asset)
    sequence_exists = unreal.EditorAssetLibrary.does_asset_exist(sequence_asset)

    diagnostic_path = _project_dir() / "Generated" / "unreal_recovery_result.json"
    diagnostic_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostic = {
        "manifest": str(manifest_path),
        "manifest_digest": digest,
        "level_asset": level_asset,
        "sequence_asset": sequence_asset,
        "level_exists": bool(level_exists),
        "sequence_exists": bool(sequence_exists),
    }
    diagnostic_path.write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")

    if not level_exists or not sequence_exists:
        missing = []
        if not level_exists:
            missing.append(level_asset)
        if not sequence_exists:
            missing.append(sequence_asset)
        raise RuntimeError("Generated Unreal assets are missing: " + ", ".join(missing))

    result_path = _project_dir() / "Generated" / "unreal_build_result.json"
    result = {
        "manifest": str(manifest_path),
        "manifest_digest": digest,
        "level_asset": level_asset,
        "sequence_asset": sequence_asset,
        "fps": 60,
        "duration_seconds": manifest["duration_seconds"],
        "actor_count": len(manifest.get("actors", [])),
        "beat_count": len(manifest.get("beats", [])),
        "recovered_metadata": True,
    }
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    unreal.log(f"[CrawlVerticalSliceRecovery] Recovered metadata for {level_asset} and {sequence_asset}")


main()
