"""Pipeline stage registry for the Game Asset Builder.

The registry is the single source of truth for stage order and for the
owner's unload discipline: every model stage declares ``isolated_process``
and the orchestrator runs it as a subprocess with file-based hand-off, so
no two heavy models are ever resident at once.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    name: str
    kind: str  # "tool" (no learned model) or "model"
    device: str  # "cpu" or "gpu"
    isolated_process: bool
    summary: str


STAGES = (
    Stage("prep", "tool", "cpu", False,
          "Concept image -> RGBA cutout (flood-fill/feather, optional rembg)."),
    Stage("mesh", "model", "gpu", True,
          "Cutout -> untextured mesh. Candidate models: see docs/DESIGN.md."),
    Stage("texture", "model", "gpu", True,
          "Mesh + cutout -> textured mesh. A different model from mesh."),
    Stage("rig", "tool", "cpu", True,
          "Blender headless: decimate, armature template, automatic weights."),
    Stage("animate", "tool", "cpu", True,
          "Blender headless: bake procedural pose recipes as clips."),
    Stage("catalog", "tool", "cpu", False,
          "Export .glb + preview renders + metadata + sha256 into the catalog."),
)


def stage_names() -> list[str]:
    return [s.name for s in STAGES]


def get_stage(name: str) -> Stage:
    for stage in STAGES:
        if stage.name == name:
            return stage
    raise KeyError(f"unknown stage: {name!r}")


def model_stages() -> list[Stage]:
    return [s for s in STAGES if s.kind == "model"]
