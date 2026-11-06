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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="asset_builder")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    sub.add_parser("stages").set_defaults(fn=cmd_stages)
    sub.add_parser("benchmark-plan").set_defaults(fn=cmd_benchmark_plan)
    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
