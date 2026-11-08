"""Pipeline orchestrator: concept image -> catalogued .glb.

Runs the stages from stages.py in order, with file-based hand-off in
``outputs/<slug>/``:

  prep     in-process (stages/prep/cutout.py)
  mesh     subprocess on the owner's PC via gpu_bridge (own process
           there; exits before texture is dispatched)
  texture  subprocess on the owner's PC via gpu_bridge
  segment  P3-SAM on the owner's PC via gpu_bridge (rigged runs
           only): proxy built on the VM, labels land in labels.npz
  rig      Blender headless subprocess (stages/rig/rig_blender.py) —
           template chosen per run (winged-creature / quadruped /
           biped)
  animate  Blender headless subprocess (stages/animate/animate_blender.py)
  catalog  in-process (stages/catalog/catalog.py)

Prop runs (``unrigged=True``) replace rig+animate with the prop stage
(stages/prop/prop_blender.py): a clean static GLB, catalogued with
empty bones/actions and ``rigged: false`` provenance.

Writes outputs/<slug>/run-manifest.json with per-stage timings and
stats, and the catalog entry under catalog/<slug>/metadata.json.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUTS_DIR = os.path.join(PROJECT_DIR, "outputs")
CATALOG_DIR = os.path.join(PROJECT_DIR, "catalog")
LAB_VENV_PYTHON = r"D:\asset-forge-lab\venvs\hunyuan\Scripts\python.exe"
LAB_REPO = r"D:\asset-forge-lab\repos\Hunyuan3D-2"
P3SAM_VENV_PYTHON = r"D:\asset-forge-lab\venvs\p3sam\Scripts\python.exe"
P3SAM_DEMO = r"D:\asset-forge-lab\repos\Hunyuan3D-Part\P3-SAM\demo"
P3SAM_CKPT = (r"D:\asset-forge-lab\seg\p3sam_weights\p3sam"
              r"\p3sam.safetensors")


def _load_module(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(PROJECT_DIR, relpath))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cutout_mod = _load_module("gab_cutout", "stages/prep/cutout.py")
preflight_mod = _load_module("gab_preflight", "stages/prep/preflight.py")
segment_mod = _load_module("gab_segment", "stages/segment/segment.py")
catalog_mod = _load_module("gab_catalog", "stages/catalog/catalog.py")
poses_mod = _load_module("gab_poses", "stages/animate/poses.py")

_TEMPLATE_BODY_PLAN = {"biped": "biped", "quadruped": "quadruped",
                       "winged-creature": "winged"}


def find_blender() -> str:
    env = os.environ.get("GAB_BLENDER")
    if env:
        return env
    on_path = shutil.which("blender")
    if on_path:
        return on_path
    known = os.path.expanduser("~/workspace/tools/blender/blender")
    if os.path.exists(known):
        return known
    raise RuntimeError("Blender not found (set GAB_BLENDER)")


def _run_blender(script_rel, args, marker):
    cmd = [find_blender(), "-b", "--python",
           os.path.join(PROJECT_DIR, script_rel), "--"] + args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or marker not in proc.stdout:
        tail = (proc.stdout + proc.stderr)[-3000:]
        raise RuntimeError(f"Blender stage {script_rel} failed:\n{tail}")
    for line in proc.stdout.splitlines():
        if " " in line and line.split(" ", 1)[0].endswith("_JSON"):
            return json.loads(line.split(" ", 1)[1])
    raise RuntimeError(f"Blender stage {script_rel} gave no JSON report")


def _stage_json_from_log(runner, lab_rel_log):
    local = os.path.join("/tmp", os.path.basename(lab_rel_log))
    runner.fetch_from_lab(lab_rel_log, local)
    with open(local, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("STAGE_JSON "):
                return json.loads(line[len("STAGE_JSON "):])
    return None


def _gpu_stage(runner, slug, stage_name, script_rel, script_args,
               timeout_s, workdir, python=LAB_VENV_PYTHON, cwd=LAB_REPO,
               extra_env=None):
    """Dispatch one GPU stage to the PC lab; return (result, stage_stats).

    Raises if the stage exits non-zero or if VRAM is not released back
    near the pre-stage baseline afterwards (the unload checkpoint).
    """
    script_local = os.path.join(PROJECT_DIR, script_rel)
    lab_script = f"scripts\\gab_{stage_name}.py"
    runner.stage_to_lab(script_local, lab_script)
    env = {"HF_HOME": runner.lab_dir + r"\hf"}
    if extra_env:
        env.update(extra_env)
    spec = {
        "name": f"{slug}_{stage_name}",
        "cmd": [python,
                runner.lab_dir + "\\" + lab_script] + script_args,
        "cwd": cwd,
        "env": env,
        "log": runner.lab_dir + f"\\logs\\gab_{slug}_{stage_name}.log",
        "result": runner.lab_dir + f"\\out\\gab_{slug}_{stage_name}"
                                   "_result.json",
    }
    result = runner.run_lab_stage(spec, timeout_s=timeout_s)
    if result["exit_code"] != 0:
        raise RuntimeError(
            f"GPU stage {stage_name} exited {result['exit_code']}: "
            f"{result.get('job_stdout_tail', '')}")
    released = result["vram_after_exit_mib"] - result["baseline_vram_mib"]
    if released > 1024:
        raise RuntimeError(
            f"unload checkpoint failed after {stage_name}: VRAM after "
            f"exit is {released} MiB above the pre-stage baseline")
    stats = _stage_json_from_log(
        runner, f"logs\\gab_{slug}_{stage_name}.log")
    return result, stats


def _segment_stage(runner, slug, textured_glb, workdir, rotate_z):
    """Layer 3 segmentation: proxy (VM Blender) -> P3-SAM (PC, own
    venv/process) -> labels.npz in the rig frame. Returns the
    labels path; per-stage detail is recorded by the caller from
    the returned info dict."""
    proxy_glb = os.path.join(workdir, "proxy.glb")
    proxy = _run_blender("stages/segment/make_proxy.py", [
        "--input", textured_glb, "--output", proxy_glb,
        "--rotate-z", str(rotate_z)], "PROXY_OK")
    lab_proxy = f"inputs\\{slug}-proxy.glb"
    runner.stage_to_lab(proxy_glb, lab_proxy)
    lab_out = f"out\\gab\\{slug}\\segment"
    result, stats = _gpu_stage(
        runner, slug, "segment", "stages/segment/p3sam_driver.py",
        [runner.lab_dir + "\\" + lab_proxy,
         runner.lab_dir + "\\" + lab_out,
         P3SAM_CKPT, P3SAM_DEMO],
        timeout_s=1800, workdir=workdir,
        python=P3SAM_VENV_PYTHON, cwd=P3SAM_DEMO,
        extra_env={"PYTHONUTF8": "1",
                   "PYTORCH_CUDA_ALLOC_CONF":
                       "expandable_segments:True"})
    runner.fetch_from_lab(
        lab_out + "\\auto_mask_mesh_final_face_ids.npy",
        os.path.join(workdir, "face_ids.npy"))
    runner.fetch_from_lab(
        lab_out + "\\auto_mask_mesh_final.glb",
        os.path.join(workdir, "segmented.glb"))
    labels_npz = os.path.join(workdir, "labels.npz")
    npz_stats = segment_mod.write_labels_npz(
        proxy_glb, os.path.join(workdir, "face_ids.npy"), labels_npz,
        transform=proxy.get("transform"))
    info = {"runner": result, "stats": stats, "proxy": proxy,
            "labels": npz_stats}
    return labels_npz, info


def run_pipeline(concept_path: str, name: str, ears: bool = False,
                 arms: bool = True, target_verts: int = 50000,
                 resume: bool = False, template: str = "winged-creature",
                 unrigged: bool = False, rotate_z: int = 0,
                 prop_target_verts: int = 30000,
                 segment: bool = True) -> dict:
    """Run the pipeline on one concept image.

    ``template`` selects the rig template (winged-creature, quadruped,
    biped). ``unrigged=True`` runs the prop path instead: prep -> mesh
    -> texture -> prop (clean static GLB) -> catalog, with no rig or
    animate stage and a catalog entry that says so. ``rotate_z`` is
    the recorded per-run facing correction for the rig stage (see
    rig_blender.py); it is ignored for props.
    """
    from gpu_bridge import BridgeRunner

    slug = catalog_mod.slugify(name)
    workdir = os.path.join(OUTPUTS_DIR, slug)
    os.makedirs(workdir, exist_ok=True)
    manifest = {"name": name, "slug": slug, "concept": concept_path,
                "template": None if unrigged else template,
                "unrigged": unrigged, "rotate_z": rotate_z,
                "stages": {}}
    started = time.time()

    def record(stage, info):
        manifest["stages"][stage] = info
        with open(os.path.join(workdir, "run-manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=1)

    # 1. prep -------------------------------------------------------------
    cutout_png = os.path.join(workdir, "cutout.png")
    t0 = time.time()
    if not (resume and os.path.exists(cutout_png)):
        stats = cutout_mod.make_cutout(concept_path, cutout_png)
    else:
        stats = {"resumed": True}
    record("prep", {"seconds": round(time.time() - t0, 2), **stats})

    # 1b. pre-flight separation check (rigged runs only) ----------------
    # Advisory, never fatal: a "warn" verdict means the concept fuses
    # limbs the rig will struggle to separate (docs/DESIGN.md, concept
    # pose & separation spec); it is recorded in the manifest so the
    # decision to proceed is visible, not silent. Props have no rig
    # to protect, so they skip it.
    if not unrigged:
        body_plan = _TEMPLATE_BODY_PLAN.get(template, "biped")
        manifest["preflight"] = preflight_mod.analyze_concept(
            concept_path, body_plan)
        with open(os.path.join(workdir, "run-manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=1)

    # 2+3. mesh + texture on the PC --------------------------------------
    runner = BridgeRunner()
    status = runner.status()
    manifest["gpu_host"] = {
        "hostname": status["hostname"], "agent": status["version"]}
    lab_in = f"inputs\\{slug}.png"
    runner.stage_to_lab(cutout_png, lab_in)
    lab_cutout = runner.lab_dir + "\\" + lab_in
    lab_shape = f"out\\gab\\{slug}\\shape.glb"
    lab_textured = f"out\\gab\\{slug}\\textured.glb"

    shape_glb = os.path.join(workdir, "shape.glb")
    if not (resume and os.path.exists(shape_glb)):
        result, stats = _gpu_stage(
            runner, slug, "shape", "stages/mesh/hunyuan_shape.py",
            [lab_cutout, runner.lab_dir + "\\" + lab_shape],
            timeout_s=1800, workdir=workdir)
        record("mesh", {"runner": result, "stats": stats})
        runner.fetch_from_lab(lab_shape, shape_glb)
    else:
        record("mesh", {"resumed": True})

    textured_glb = os.path.join(workdir, "textured.glb")
    if not (resume and os.path.exists(textured_glb)):
        result, stats = _gpu_stage(
            runner, slug, "texture", "stages/texture/hunyuan_paint.py",
            [runner.lab_dir + "\\" + lab_shape, lab_cutout,
             runner.lab_dir + "\\" + lab_textured],
            timeout_s=3600, workdir=workdir)
        record("texture", {"runner": result, "stats": stats})
        runner.fetch_from_lab(lab_textured, textured_glb)
    else:
        record("texture", {"resumed": True})

    final_glb = os.path.join(workdir, f"{slug}.glb")
    renders_dir = os.path.join(workdir, "renders")
    os.makedirs(renders_dir, exist_ok=True)

    if unrigged:
        # 4-prop. clean static GLB — no rig, no animate ------------------
        prop = _run_blender("stages/prop/prop_blender.py", [
            "--input", textured_glb, "--output", final_glb,
            "--report", os.path.join(workdir, "prop-report.json"),
            "--target-verts", str(prop_target_verts)], "PROP_OK")
        record("prop", prop)

        # 5-prop. catalog: bones/actions honestly empty -----------------
        entry = catalog_mod.build_entry(
            name=name,
            source_concept=os.path.basename(concept_path),
            glb_path=final_glb,
            counts={"verts": prop["prop_verts"],
                    "faces": prop["prop_faces"],
                    "raw_mesh_verts": prop["raw_verts"],
                    "raw_mesh_faces": prop["raw_faces"]},
            bones=[],
            actions=[],
            provenance={
                "mesh_model": "tencent/Hunyuan3D-2 hunyuan3d-dit-v2-0",
                "texture_model": "tencent/Hunyuan3D-2 hunyuan3d-paint-v2-0",
                "rigged": False,
                "rig_template": None,
                "weight_method": None,
                "gpu_host": manifest["gpu_host"],
                "mesh_stage": manifest["stages"].get("mesh", {}),
                "texture_stage": manifest["stages"].get("texture", {}),
            })
        entry_path = catalog_mod.write_entry(CATALOG_DIR, entry)
        record("catalog", {"entry": entry_path,
                           "sha256": entry["sha256"]})

        # 6-prop. verify: cold re-import proves the GLB is static -------
        verify = _run_blender("stages/catalog/render_verify.py", [
            "--input", final_glb,
            "--rest-png", os.path.join(renders_dir, "beauty.png"),
            "--action-png", os.path.join(renders_dir, "front.png"),
            "--report", os.path.join(workdir, "verify-report.json"),
            "--static"], "VERIFY_OK")
        record("verify", verify)
        manifest["seconds_total"] = round(time.time() - started, 2)
        manifest["final_glb"] = final_glb
        manifest["catalog_entry"] = entry_path
        with open(os.path.join(workdir, "run-manifest.json"), "w") as fh:
            json.dump(manifest, fh, indent=1)
        return manifest

    # 3b. segment: P3-SAM part labels (rigged runs only) ------------------
    labels_npz = None
    if segment:
        labels_npz, seg_info = _segment_stage(
            runner, slug, textured_glb, workdir, rotate_z)
        record("segment", seg_info)

    # 4. rig ---------------------------------------------------------------
    rigged_glb = os.path.join(workdir, "rigged.glb")
    rig_report_path = os.path.join(workdir, "rig-report.json")
    rig_args = [
        "--input", textured_glb, "--output", rigged_glb,
        "--blend", os.path.join(workdir, "rigged.blend"),
        "--report", rig_report_path,
        "--template", template,
        "--rotate-z", str(rotate_z),
        "--ears", "1" if ears else "0",
        "--arms", "1" if arms else "0",
        "--target-verts", str(target_verts)]
    if labels_npz:
        rig_args += ["--labels", labels_npz]
    rig = _run_blender("stages/rig/rig_blender.py", rig_args, "RIG_OK")
    record("rig", rig)

    # 5. animate -----------------------------------------------------------
    animate_report_path = os.path.join(workdir, "animate-report.json")
    anim = _run_blender("stages/animate/animate_blender.py", [
        "--input", rigged_glb, "--output", final_glb,
        "--report", animate_report_path,
        "--template", template], "ANIMATE_OK")
    record("animate", anim)

    # 6. catalog -----------------------------------------------------------
    entry = catalog_mod.build_entry(
        name=name,
        source_concept=os.path.basename(concept_path),
        glb_path=final_glb,
        counts={"verts": rig["rigged_verts"],
                "faces": rig["rigged_faces"],
                "raw_mesh_verts": rig["raw_verts"],
                "raw_mesh_faces": rig["raw_faces"]},
        bones=rig["bones"],
        actions=sorted(anim["actions"].keys()),
        provenance={
            "mesh_model": "tencent/Hunyuan3D-2 hunyuan3d-dit-v2-0",
            "texture_model": "tencent/Hunyuan3D-2 hunyuan3d-paint-v2-0",
            "rigged": True,
            "rig_template": rig["template"],
            "weight_method": rig["weight_method"],
            "segmentation": rig.get("segmentation"),
            "label_map": (rig.get("weight_veto") or {}).get("label_map"),
            "gpu_host": manifest["gpu_host"],
            "mesh_stage": manifest["stages"].get("mesh", {}),
            "texture_stage": manifest["stages"].get("texture", {}),
        })
    entry_path = catalog_mod.write_entry(CATALOG_DIR, entry)
    record("catalog", {"entry": entry_path, "sha256": entry["sha256"]})

    # 7. verify: cold re-import + preview renders (catalog stage output)
    showcase = poses_mod.showcase_clip(template)
    verify = _run_blender("stages/catalog/render_verify.py", [
        "--input", final_glb,
        "--rest-png", os.path.join(renders_dir, "rest.png"),
        "--action-png", os.path.join(renders_dir, f"{showcase}.png"),
        "--report", os.path.join(workdir, "verify-report.json"),
        "--template", template], "VERIFY_OK")
    record("verify", verify)

    manifest["seconds_total"] = round(time.time() - started, 2)
    manifest["final_glb"] = final_glb
    manifest["catalog_entry"] = entry_path
    with open(os.path.join(workdir, "run-manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    return manifest
