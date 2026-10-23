import json
from pathlib import Path

import unreal

FPS = 60
WIDTH = 1280
HEIGHT = 720


def _log(message):
    unreal.log(f"[CrawlRenderPreset] {message}")


def _project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _result_path():
    return _project_dir() / "Generated" / "unreal_build_result.json"


def _load_build_result():
    path = _result_path()
    if not path.exists():
        raise RuntimeError(f"Unreal build result not found: {path}. Run build_vertical_slice.py first.")
    return path, json.loads(path.read_text(encoding="utf-8"))


def _object_path(package_path):
    asset_name = package_path.rsplit("/", 1)[-1]
    return f"{package_path}.{asset_name}"


def build_render_preset():
    result_path, result = _load_build_result()
    digest = str(result["manifest_digest"])
    suffix = digest[:10]
    preset_name = f"MPC_CrawlVerticalSlice_v1_{suffix}"
    preset_package = f"/Game/CrawlGenerated/{preset_name}"

    if unreal.EditorAssetLibrary.does_asset_exist(preset_package):
        preset = unreal.load_asset(preset_package)
    else:
        preset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
            preset_name,
            "/Game/CrawlGenerated",
            unreal.MoviePipelinePrimaryConfig,
            unreal.MoviePipelinePrimaryConfigFactory(),
        )
        if preset is None:
            raise RuntimeError("Failed to create Movie Render Queue primary config asset")

    output = preset.find_or_add_setting_by_class(unreal.MoviePipelineOutputSetting)
    render_dir = _project_dir() / "Generated" / "Renders" / suffix
    render_dir.mkdir(parents=True, exist_ok=True)
    output.set_editor_property("output_directory", unreal.DirectoryPath(path=str(render_dir)))
    output.set_editor_property("output_resolution", unreal.IntPoint(WIDTH, HEIGHT))
    output.set_editor_property("use_custom_frame_rate", True)
    output.set_editor_property("output_frame_rate", unreal.FrameRate(FPS, 1))
    output.set_editor_property("override_existing_output", True)
    output.set_editor_property("file_name_format", f"crawl_vertical_{suffix}")

    deferred = preset.find_or_add_setting_by_class(unreal.MoviePipelineDeferredPassBase)
    if deferred is None:
        raise RuntimeError("Failed to add Deferred Rendering pass to Movie Render Queue preset")
    deferred.set_is_enabled(True)

    mp4 = preset.find_or_add_setting_by_class(unreal.MoviePipelineMP4EncoderOutput)
    if mp4 is None:
        raise RuntimeError("Failed to add MP4 encoder output to Movie Render Queue preset")
    mp4.set_is_enabled(True)
    mp4.set_editor_property("include_audio", False)
    # CRF 18 is a high-quality baseline; later production profiles can trade size for speed.
    mp4.set_editor_property("constant_rate_factor", 18)

    unreal.EditorAssetLibrary.save_loaded_asset(preset, False)

    result.update(
        {
            "render_config_asset": preset_package,
            "render_config_object": _object_path(preset_package),
            "map_object": _object_path(result["level_asset"]),
            "sequence_object": _object_path(result["sequence_asset"]),
            "render_output_directory": str(render_dir),
            "render_width": WIDTH,
            "render_height": HEIGHT,
            "render_fps": FPS,
            "expected_video_path": str(render_dir / f"crawl_vertical_{suffix}.mp4"),
        }
    )
    result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    _log(f"Render config: {preset_package}")
    _log(f"Output directory: {render_dir}")
    _log("The preset uses Unreal Movie Render Queue deferred rendering with H.264 MP4 output.")
    return preset_package


build_render_preset()
