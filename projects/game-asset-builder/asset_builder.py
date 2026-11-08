#!/usr/bin/env python3
"""Game Asset Builder — orchestrator CLI (stdlib only).

Commands:
  doctor         Report this machine's fitness for each stage.
  stages         List the pipeline stages in order.
  benchmark-plan Print the Pip benchmark protocol summary.

Heavy stages are subprocesses (see stages.py); this CLI never imports a
model framework.
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys

from stages import STAGES, model_stages


def cmd_doctor(_args: argparse.Namespace) -> int:
    print(f"python   : {sys.version.split()[0]} ({platform.system()} "
          f"{platform.machine()})")
    smi = shutil.which("nvidia-smi")
    if smi:
        out = subprocess.run(
            [smi, "--query-gpu=name,memory.total,memory.free",
             "--format=csv,noheader"],
            capture_output=True, text=True, check=False)
        gpu = out.stdout.strip() or "nvidia-smi returned nothing"
        print(f"gpu      : {gpu}")
    else:
        print("gpu      : NONE detected — GPU model stages cannot run here")
    blender = shutil.which("blender")
    print(f"blender  : {blender or 'not on PATH (rig/animate/scoring need it)'}")
    gpu_ok = smi is not None
    for stage in STAGES:
        need = "GPU" if stage.device == "gpu" else "CPU"
        ok = gpu_ok if stage.device == "gpu" else True
        print(f"  stage {stage.name:<8} needs {need:<3} -> "
              f"{'ok' if ok else 'CANNOT RUN on this machine'}")
    return 0


def cmd_stages(_args: argparse.Namespace) -> int:
    for i, stage in enumerate(STAGES):
        iso = "isolated process" if stage.isolated_process else "in-process"
        print(f"{i}. {stage.name:<8} [{stage.kind}/{stage.device}, {iso}] "
              f"{stage.summary}")
    models = model_stages()
    print(f"\n{len(models)} model stages, each unloaded before the next "
          "loads (separate processes, file hand-off).")
    return 0


def cmd_benchmark_plan(_args: argparse.Namespace) -> int:
    print("Pip benchmark (protocol: docs/DESIGN.md)")
    print("  input     : benchmarks/pip/input-idle.png (fixed RGBA cutout)")
    print("  reference : owner's Meshy Pip, rendered through the same scorer")
    print("  per model : normalize -> render front/side/back/three-quarter")
    print("              -> silhouette IoU per view, counts, time, peak VRAM")
    print("  verdicts  : RIGGABLE (front IoU >= 0.75) / ROUGH / MELTED")
    return 0


def cmd_cutout(args: argparse.Namespace) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    proc = subprocess.run([sys.executable,
                           os.path.join(here, "stages/prep/cutout.py"),
                           args.input, args.output])
    return proc.returncode


def cmd_run(args: argparse.Namespace) -> int:
    import json

    from pipeline import run_pipeline
    manifest = run_pipeline(
        args.concept, args.name, ears=args.ears, arms=not args.no_arms,
        target_verts=args.target_verts, resume=args.resume,
        template=args.template, unrigged=args.prop,
        rotate_z=args.rotate_z, prop_target_verts=args.prop_target_verts)
    print(json.dumps({k: manifest[k] for k in
                      ("name", "slug", "seconds_total", "final_glb",
                       "catalog_entry")}, indent=1))
    return 0


def cmd_catalog_verify(args: argparse.Namespace) -> int:
    import pipeline
    entry = pipeline.catalog_mod.read_entry(pipeline.CATALOG_DIR, args.slug)
    glb = os.path.join(pipeline.OUTPUTS_DIR, args.slug, entry["asset_file"])
    ok = pipeline.catalog_mod.verify_entry(entry, glb)
    print(f"{args.slug}: sha256 {'MATCH' if ok else 'MISMATCH'} "
          f"({entry['sha256'][:16]}...)")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="asset_builder")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    sub.add_parser("stages").set_defaults(fn=cmd_stages)
    sub.add_parser("benchmark-plan").set_defaults(fn=cmd_benchmark_plan)
    p_cut = sub.add_parser("cutout", help="prep stage: image -> RGBA cutout")
    p_cut.add_argument("input")
    p_cut.add_argument("output")
    p_cut.set_defaults(fn=cmd_cutout)
    p_run = sub.add_parser("run", help="run the full pipeline on a concept")
    p_run.add_argument("--concept", required=True)
    p_run.add_argument("--name", required=True)
    p_run.add_argument("--template", default="winged-creature",
                       choices=("winged-creature", "quadruped", "biped"),
                       help="rig template (ignored with --prop)")
    p_run.add_argument("--prop", action="store_true",
                       help="unrigged prop path: no rig/animate stages, "
                            "catalogued as a static asset")
    p_run.add_argument("--ears", action="store_true",
                       help="template option: include ear bones")
    p_run.add_argument("--no-arms", action="store_true",
                       help="template option: omit arm bones")
    p_run.add_argument("--rotate-z", type=int, default=0,
                       choices=(0, 90, 180, 270),
                       help="facing correction for the rig stage, "
                            "chosen from renders of the generated mesh")
    p_run.add_argument("--target-verts", type=int, default=50000)
    p_run.add_argument("--prop-target-verts", type=int, default=30000)
    p_run.add_argument("--resume", action="store_true",
                       help="skip prep/mesh/texture if artifacts exist")
    p_run.set_defaults(fn=cmd_run)
    p_cat = sub.add_parser("catalog-verify",
                           help="verify a catalogued asset's sha256")
    p_cat.add_argument("--slug", required=True)
    p_cat.set_defaults(fn=cmd_catalog_verify)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
