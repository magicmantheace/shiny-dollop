"""Small offline CLI. The Godot preview is optional."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
from pathlib import Path
from . import gltf
from .director import (AdapterError, HttpAdapter, PlannerError, StubAdapter,
                       plan_scene)
from .ipc import write_ipc
from .jobs import JobError, enqueue, list_jobs, run_worker
from .library import Library, ROOT, DEFAULT_DB
from .promotion import DEFAULT_ASSET_ROOT, PromotionError, promote_asset, promote_character
from .recipes import (RecipeError, assemble_character, edit_character,
                      require_character, unapproved_parts)
from .reports import clip_keys_from_manifest, missing_action_report
from .reviews import DECISIONS, ReviewError, list_candidates, record_review
from .schema import validate_scene, validate_asset, validate_character, validate_catalog, ValidationError
from .shows import (ShowError, apply_continuity, capture_scene_memory,
                    export_show_package, record_scene_memory, validate_show,
                    verify_show_package)
from .timing import resolve_timing
from .voice import (ExternalVoiceEngine, StubVoiceEngine, VoiceCache,
                    VoiceError, subprocess_runner)

EXAMPLES = ROOT / "examples"

def load(name: str) -> dict:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))

def _asset_state(asset: dict) -> dict:
    meta = asset.get("metadata") or {}
    return {"asset_id": asset["asset_id"], "kind": asset["kind"],
            "status": asset["status"], "version": meta.get("version", "1.0.0"),
            "sha256": meta.get("sha256")}

def enrich_manifest(manifest: dict, lib: Library, asset_root: Path | None,
                    scene_props: list | None = None) -> dict:
    """Attach DB approval state (status/version/sha256) to a manifest.

    The base fixture carries the curated clip/stage data; everything the
    Godot resolver enforces — per-asset status, pinned version and
    SHA-256 — is copied from the library database at export time, never
    re-typed by hand. Stage piece hashes come from the kit record's
    per-piece digests (verified against the store at promotion time).
    Scene-declared props (F4.2) get a pin per prop id, resolved from the
    prop's asset record; a prop whose asset is not registered gets no
    pin, and the preview names it unavailable.
    """
    manifest = json.loads(json.dumps(manifest))
    manifest["assets"] = {a["uri"]: _asset_state(a) for a in lib.list_assets_full()}
    if scene_props:
        pins = {}
        for prop in scene_props:
            asset = lib.get_asset(prop["asset_id"])
            if asset:
                pins[prop["id"]] = {"uri": asset["uri"], **_asset_state(asset)}
        manifest["props"] = pins
    for recipe in manifest.get("recipes", {}).values():
        files = []
        body = lib.get_asset_by_uri(recipe["body"])
        if body:
            files.append({"uri": recipe["body"], "role": "body", **_asset_state(body)})
        for uri in recipe.get("animations", []):
            motion = lib.get_asset_by_uri(uri)
            if motion:
                files.append({"uri": uri, "role": "animation", **_asset_state(motion)})
        recipe["files"] = files
    stage = manifest.get("stage")
    if stage:
        kit = lib.get_asset(stage["asset_id"])
        if kit:
            pieces_meta = (kit.get("metadata") or {}).get("pieces") or {}
            for piece in stage.get("pieces", []):
                piece["status"] = kit["status"]
                piece["version"] = (kit.get("metadata") or {}).get("version", "1.0.0")
                piece["sha256"] = pieces_meta.get(Path(piece["file"]).name)
    return manifest

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Animation Studio foundation")
    parser.add_argument("command", choices=["validate", "init-db", "seed", "register", "promote", "assemble", "show-character", "edit-character", "export-character", "list-assets", "demo", "sockets", "plan", "speak", "enqueue", "work", "jobs", "report-missing", "candidates", "review", "continuity", "export-show", "verify-show"])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--catalog", default="quaternius_f1_catalog.json",
                        help="catalog fixture in examples/ (register/promote commands)")
    parser.add_argument("--scene", default="scene_demo.json",
                        help="scene fixture in examples/ (demo command); "
                             "report-missing: a scene JSON file "
                             "(a bare name resolves under examples/)")
    parser.add_argument("--asset-root", type=Path, default=None,
                        help="local asset store root (promote/demo/sockets); "
                             "defaults to AI_ANIMATION_ASSET_ROOT or the VM store")
    parser.add_argument("--body", default="assets/characters/Superhero_Male_FullBody.gltf",
                        help="body glTF under the asset root (sockets command)")
    parser.add_argument("--spec", type=Path, default=None,
                        help="character spec JSON file (assemble command)")
    parser.add_argument("--require-approved", action="store_true",
                        help="assemble/edit-character: refuse recipes with unapproved parts")
    parser.add_argument("--character", default=None,
                        help="character id (show/edit/export-character commands)")
    parser.add_argument("--body-base", default=None,
                        help="edit-character: new body_base part id")
    parser.add_argument("--head", default=None,
                        help="edit-character: new head part id")
    parser.add_argument("--hair", default=None,
                        help="edit-character: new hair part id")
    parser.add_argument("--outfit", default=None,
                        help="edit-character: new outfit as comma-separated part ids "
                             "(empty string clears the outfit)")
    parser.add_argument("--colors", default=None,
                        help="edit-character: new colors as a JSON object, "
                             "e.g. '{\"hair\": \"#663e32\"}'")
    parser.add_argument("--context", type=Path, default=None,
                        help="plan: director context JSON file (cast + lines)")
    parser.add_argument("--adapter", choices=["stub", "http"], default="stub",
                        help="plan: scene proposer adapter (default stub)")
    parser.add_argument("--model", default=None,
                        help="plan (http adapter): local model name "
                             f"(default {HttpAdapter.DEFAULT_MODEL})")
    parser.add_argument("--endpoint", default=None,
                        help="plan (http adapter): local model endpoint, loopback only "
                             f"(default {HttpAdapter.DEFAULT_ENDPOINT})")
    parser.add_argument("--out", type=Path, default=None,
                        help="output file (demo: scene runtime JSON, default godot/data/scene_runtime.json; "
                             "export-character: recipe spec file, required; "
                             "plan: enveloped scene JSON, required)")
    parser.add_argument("--line", default=None,
                        help="speak: line of dialogue to synthesize")
    parser.add_argument("--voice", default="narrator",
                        help="speak: voice name passed to the engine and the "
                             "cache key (default narrator)")
    parser.add_argument("--engine", choices=["stub", "external"], default="stub",
                        help="speak: voice engine (default stub — deterministic "
                             "offline silence at the ADR-009 speak hold; external "
                             "runs a local CLI engine, never the network)")
    parser.add_argument("--voice-cmd", default=None,
                        help="speak (external engine): command template; {voice} "
                             "is substituted, the line is fed on stdin and the "
                             "WAV is read from stdout "
                             "(default: the espeak-ng shape; no engine ships "
                             "with the studio)")
    parser.add_argument("--voice-cache", type=Path, default=None,
                        help="speak: voice clip cache directory (default: "
                             "AI_ANIMATION_VOICE_CACHE or a system-temp cache; "
                             "always outside git)")
    parser.add_argument("--rate", type=float, default=None,
                        help="speak: speak rate in chars/sec — the ADR-009 "
                             "timing variable (default 15)")
    parser.add_argument("--kind", default=None,
                        help="enqueue: job kind (e.g. validate_scene, export_scene)")
    parser.add_argument("--payload", type=Path, default=None,
                        help="enqueue: JSON payload file for the job")
    parser.add_argument("--worker", default=None,
                        help="work: worker id recorded on claims "
                             "(default worker-<pid>)")
    parser.add_argument("--once", action="store_true",
                        help="work: drain the queue and exit (the only mode "
                             "in this slice; accepted for clarity)")
    parser.add_argument("--stale-after", type=float, default=None,
                        help="work: before claiming, requeue running jobs "
                             "whose claim is older than this many seconds "
                             "(jobs at max attempts are failed instead)")
    parser.add_argument("--state", choices=["queued", "running", "done", "failed"],
                        default=None,
                        help="jobs: list only jobs in this state")
    parser.add_argument("--manifest", type=Path, default=None,
                        help="report-missing: asset manifest JSON file whose "
                             "clips table is the provided clip map "
                             "(a bare name resolves under examples/)")
    parser.add_argument("--asset", default=None,
                        help="review: asset id to record a review for")
    parser.add_argument("--reviewer", default=None,
                        help="review: reviewer name recorded on the review")
    parser.add_argument("--decision", choices=list(DECISIONS), default=None,
                        help="review: decision to record (advisory only; "
                             "never changes the asset's status)")
    parser.add_argument("--note", default=None,
                        help="review: optional note recorded on the review")
    parser.add_argument("--show", type=Path, default=None,
                        help="continuity / export-show: show manifest JSON "
                             "file (a bare name resolves under examples/)")
    parser.add_argument("--scene-index", type=int, default=None,
                        help="continuity: 0-based index of the scene to "
                             "apply the previous scene's memory to")
    args = parser.parse_args(argv)
    asset_root = args.asset_root or DEFAULT_ASSET_ROOT
    if args.command == "validate":
        validate_scene(load("scene_demo.json"))
        validate_scene(load("scene_tavern_v2.json"))
        validate_asset(load("asset_mug.json"))
        validate_character(load("character_traveler.json"))
        catalog = validate_catalog(load("quaternius_f1_catalog.json"))
        print(f"Validated scene, asset, character examples and F1 catalog "
              f"({len(catalog['assets'])} assets, {len(catalog['characters'])} characters)")
        return 0
    if args.command == "sockets":
        doc = gltf.load_gltf_json(asset_root / args.body)
        positions = gltf.joint_world_positions(doc)
        print(f"Bind-pose joint world positions for {args.body} "
              f"({gltf.joint_count(doc)} joints, metres, character origin at floor):")
        for bone in ("hand_l", "hand_r", "Head", "neck_01", "pelvis"):
            print(f"  {bone}: {gltf.round3(positions[bone])}")
        return 0
    if args.command == "demo":
        scene = validate_scene(load(args.scene))
        out_path = args.out or (ROOT / "godot" / "data" / "scene_runtime.json")
        envelope = write_ipc(out_path, scene)
        print(f"Saved {len(scene['events'])} validated events to {out_path} "
              f"(IPC envelope, ipc_version {envelope['ipc_version']})")
        manifest = EXAMPLES / "asset_manifest.json"
        if manifest.exists():
            target = out_path.parent / "asset_manifest.json"
            base = json.loads(manifest.read_text(encoding="utf-8"))
            if args.db.exists():
                lib = Library(args.db)
                try:
                    # The demo export reads through get_asset, so the opened
                    # DB must be migrated first (idempotent; a pre-migration
                    # v1 database is upgraded in place, rows preserved).
                    lib.init()
                    enriched = enrich_manifest(base, lib, asset_root,
                                               scene.get("props"))
                finally:
                    lib.close()
                target.write_text(json.dumps(enriched, indent=2) + "\n", encoding="utf-8")
                print(f"Saved asset manifest with library approval state to {target}")
            else:
                shutil.copyfile(manifest, target)
                print(f"Saved asset manifest to {target} (no library DB at {args.db}; "
                      "no approval state attached, preview will fall back to capsules)")
        print("Open godot/project.godot in Godot 4 and run the main scene to preview.")
        return 0
    if args.command == "plan":
        if args.context is None:
            parser.error("plan requires --context <director context JSON file>")
        if args.out is None:
            parser.error("plan requires --out <enveloped scene JSON file>")
        try:
            context = json.loads(args.context.read_text(encoding="utf-8"))
            if not isinstance(context, dict):
                parser.error("plan context must be a JSON object")
            if args.adapter == "http":
                adapter = HttpAdapter(
                    endpoint=args.endpoint or HttpAdapter.DEFAULT_ENDPOINT,
                    model=args.model or HttpAdapter.DEFAULT_MODEL)
            else:
                adapter = StubAdapter()
            result = plan_scene(adapter, context)
        except (AdapterError, PlannerError, OSError, ValueError) as err:
            parser.error(str(err))
        envelope = write_ipc(args.out, result.scene)
        summary = (f"Planned scene {result.scene['scene_id']} via {result.adapter} "
                   f"(attempts {result.attempts}, "
                   f"{'fallback' if result.fallback else 'no fallback'}) "
                   f"-> {args.out} (IPC envelope, ipc_version {envelope['ipc_version']})")
        if result.rejections:
            summary += f"; rejections: {' | '.join(result.rejections)}"
        print(summary)
        return 0
    if args.command == "speak":
        if args.line is None:
            parser.error("speak requires --line <dialogue line>")
        try:
            timing = resolve_timing(
                {"speak_chars_per_second": args.rate}
                if args.rate is not None else None)
            if args.engine == "external":
                template = (shlex.split(args.voice_cmd)
                            if args.voice_cmd else None)
                engine = ExternalVoiceEngine(subprocess_runner,
                                             argv_template=template)
            else:
                engine = StubVoiceEngine()
            record = VoiceCache(args.voice_cache).get_or_synthesize(
                args.line, args.voice, engine=engine, timing=timing)
        except (VoiceError, ValueError) as err:
            parser.error(str(err))
        origin = "cache" if record.from_cache else "synthesized"
        print(f"Voice clip key {record.key} ({origin})")
        print(f"  engine {record.engine}, voice {record.voice}, "
              f"duration {record.duration_ms} ms, {record.wav_len} bytes, "
              f"sha256 {record.wav_sha256}")
        print(f"  phonemes: {len(record.phonemes)} word segments "
              f"(ESTIMATED alignment) -> {record.wav_path}")
        return 0
    if args.command == "report-missing":
        if args.manifest is None:
            parser.error("report-missing requires --manifest <manifest JSON file>")
        scene_path = Path(args.scene)
        if not scene_path.exists():
            scene_path = EXAMPLES / args.scene
        manifest_path = args.manifest
        if not manifest_path.exists():
            manifest_path = EXAMPLES / args.manifest
        try:
            scene = validate_scene(
                json.loads(scene_path.read_text(encoding="utf-8")))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            records = missing_action_report(
                scene, clip_keys_from_manifest(manifest))
        except (ValidationError, OSError, ValueError) as err:
            parser.error(str(err))
        print(f"Scene {scene['scene_id']}: {len(records)} missing action(s)")
        for record in records:
            print(f"  events[{record['event_index']}] {record['op']} "
                  f"(actor {record['actor_id']}) needs clip "
                  f"'{record['needed']}': {record['reason']}")
        return 0
    if args.command == "continuity":
        if args.show is None:
            parser.error("continuity requires --show <show manifest JSON file>")
        if args.scene_index is None:
            parser.error("continuity requires --scene-index "
                         "<0-based index into the show's scenes>")
        show_path = args.show
        if not show_path.exists():
            show_path = EXAMPLES / args.show
        try:
            show = validate_show(
                json.loads(show_path.read_text(encoding="utf-8")))
        except (ValidationError, OSError, ValueError) as err:
            parser.error(str(err))
        entries = show["scenes"]
        if not 0 <= args.scene_index < len(entries):
            parser.error(f"--scene-index {args.scene_index} out of range for "
                         f"show {show['show_id']} ({len(entries)} scene(s), "
                         "0-based)")
        # Capture the memory chain in play order, recording each memory
        # into the library DB when one exists at --db (the demo export's
        # convention; a missing DB is reported, never silently created).
        lib = None
        try:
            memories = []
            if args.db.exists():
                lib = Library(args.db)
                lib.init()
            for entry in entries:
                memory = capture_scene_memory(entry["scene"])
                memories.append(memory)
                if lib is not None:
                    record_scene_memory(lib, show["show_id"], memory)
                print(f"Memory {memory['scene_id']}: makespan "
                      f"{memory['makespan_ms']} ms, "
                      f"{len(memory['actors'])} actor(s), "
                      f"{len(memory['props'])} prop(s)")
            target = entries[args.scene_index]
            if args.scene_index == 0:
                print(f"Scene {target['scene_id']} is the show's first "
                      "scene; no prior memory to apply")
            else:
                _applied, notes = apply_continuity(
                    target["scene"], memories[args.scene_index - 1])
                print(f"Continuity into {target['scene_id']} (from "
                      f"{memories[args.scene_index - 1]['scene_id']}):")
                for note in notes:
                    print(f"  {note}")
            if lib is None:
                print(f"No library DB at {args.db}; memories were not recorded")
        except (ValidationError, ShowError, ValueError) as err:
            parser.error(str(err))
        finally:
            if lib is not None:
                lib.close()
        return 0
    if args.command == "export-show":
        if args.show is None:
            parser.error("export-show requires --show <show manifest JSON file>")
        if args.out is None:
            parser.error("export-show requires --out <package directory>")
        show_path = args.show
        if not show_path.exists():
            show_path = EXAMPLES / args.show
        try:
            show = validate_show(
                json.loads(show_path.read_text(encoding="utf-8")))
            package = export_show_package(show, args.out)
        except (ValidationError, OSError, ValueError) as err:
            parser.error(str(err))
        print(f"Exported show {package['show_id']} to {args.out}: "
              f"{len(package['exported_files'])} file(s) hashed, "
              f"ipc_version {package['ipc_version']}")
        return 0
    if args.command == "verify-show":
        if args.out is None:
            parser.error("verify-show requires --out <package directory>")
        try:
            summary = verify_show_package(args.out)
        except (ShowError, OSError, ValueError) as err:
            parser.error(str(err))
        print(f"Package OK: show {summary['show_id']}, "
              f"{summary['scene_count']} scene(s), "
              f"{summary['files_checked']} file hash(es) verified")
        return 0
    lib = Library(args.db)
    try:
        lib.init()
        if args.command == "init-db":
            print(f"Initialized {args.db}")
        elif args.command == "seed":
            lib.put_asset(load("asset_mug.json"))
            lib.put_character(load("character_traveler.json"))
            lib.put_scene(load("scene_demo.json"))
            print("Seeded candidate examples; no production media files supplied")
        elif args.command == "register":
            catalog = validate_catalog(load(args.catalog))
            for asset in catalog["assets"]:
                lib.put_asset(asset)
            for character in catalog["characters"]:
                lib.put_character(character)
            print(f"Registered {len(catalog['assets'])} assets and "
                  f"{len(catalog['characters'])} characters from {args.catalog} into {args.db}")
        elif args.command == "promote":
            catalog = validate_catalog(load(args.catalog))
            all_ok = True
            for asset in catalog["assets"]:
                result = promote_asset(lib, asset["asset_id"], asset_root)
                verdict = "PROMOTED" if result["promoted"] else "REFUSED"
                all_ok = all_ok and result["promoted"]
                print(f"{verdict} asset {result['asset_id']}")
                for gate in result["gates"]:
                    print(f"  gate {gate['gate']}: "
                          f"{'PASS' if gate['passed'] else 'FAIL'} — {gate['detail']}")
                print(f"  pending human gates (NOT passed): {', '.join(result['pending'])}")
            for character in catalog["characters"]:
                result = promote_character(lib, character["character_id"])
                verdict = "PROMOTED" if result["promoted"] else "REFUSED"
                all_ok = all_ok and result["promoted"]
                print(f"{verdict} character {result['character_id']}")
                for gate in result["gates"]:
                    print(f"  gate {gate['gate']}: "
                          f"{'PASS' if gate['passed'] else 'FAIL'} — {gate['detail']}")
                print(f"  pending human gates (NOT passed): {', '.join(result['pending'])}")
            return 0 if all_ok else 2
        elif args.command == "assemble":
            if args.spec is None:
                parser.error("assemble requires --spec <character spec JSON file>")
            spec = json.loads(args.spec.read_text(encoding="utf-8"))
            recipe = assemble_character(lib, spec,
                                        require_approved=args.require_approved)
            lib.put_character(recipe)
            print(f"Assembled character {recipe['character_id']} "
                  f"(rig {recipe['rig_id']}) into {args.db}")
            pending = unapproved_parts(lib, recipe)
            if pending:
                print(f"  unapproved parts (not playable until promoted): "
                      f"{', '.join(pending)}")
            else:
                print("  all parts approved")
        elif args.command == "show-character":
            if args.character is None:
                parser.error("show-character requires --character <id>")
            recipe = require_character(lib, args.character)
            print(json.dumps(recipe, indent=2))
        elif args.command == "edit-character":
            if args.character is None:
                parser.error("edit-character requires --character <id>")
            changes = {}
            if args.body_base is not None:
                changes["body_base"] = args.body_base
            if args.head is not None:
                changes["head"] = args.head
            if args.hair is not None:
                changes["hair"] = args.hair
            if args.outfit is not None:
                changes["outfit"] = [p for p in args.outfit.split(",") if p]
            if args.colors is not None:
                changes["colors"] = json.loads(args.colors)
            recipe = edit_character(lib, args.character, changes,
                                    require_approved=args.require_approved)
            print(f"Edited character {recipe['character_id']} "
                  f"(rig {recipe['rig_id']}) in {args.db}")
            pending = unapproved_parts(lib, recipe)
            if pending:
                print(f"  unapproved parts (not playable until promoted): "
                      f"{', '.join(pending)}")
            else:
                print("  all parts approved")
        elif args.command == "export-character":
            if args.character is None:
                parser.error("export-character requires --character <id>")
            if args.out is None:
                parser.error("export-character requires --out <spec JSON file>")
            recipe = require_character(lib, args.character)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(recipe, indent=2) + "\n",
                                encoding="utf-8")
            print(f"Exported character {recipe['character_id']} to {args.out}")
        elif args.command == "list-assets":
            for item in lib.list_assets():
                print(f"{item['asset_id']} [{item['status']}] {item['uri']}")
        elif args.command == "enqueue":
            if args.kind is None:
                parser.error("enqueue requires --kind <job kind>")
            if args.payload is None:
                parser.error("enqueue requires --payload <JSON payload file>")
            payload = json.loads(args.payload.read_text(encoding="utf-8"))
            job_id = enqueue(lib, args.kind, payload)
            print(f"Enqueued job {job_id} ({args.kind})")
        elif args.command == "work":
            worker_id = args.worker or f"worker-{os.getpid()}"
            summaries = run_worker(lib, worker_id,
                                   stale_after_s=args.stale_after)
            for summary in summaries:
                print(f"job {summary['job_id']} [{summary['kind']}] "
                      f"{summary['state']}")
            done = sum(1 for s in summaries if s["state"] == "done")
            print(f"Worker {worker_id} ran {len(summaries)} job(s): "
                  f"{done} done, {len(summaries) - done} failed")
        elif args.command == "jobs":
            for job in list_jobs(lib, state=args.state):
                line = (f"job {job['job_id']} [{job['state']}] {job['kind']} "
                        f"attempts={job['attempts']} "
                        f"worker={job['worker_id'] or '-'} "
                        f"created={job['created_at']}")
                if job["error"]:
                    line += f" error: {job['error']}"
                print(line)
        elif args.command == "candidates":
            for entry in list_candidates(lib):
                print(f"{entry['asset_id']} [candidate] {entry['uri']} "
                      f"source={entry['source'] or '-'} "
                      f"license={entry['license'] or '-'} "
                      f"review={entry['review']}")
        elif args.command == "review":
            if args.asset is None:
                parser.error("review requires --asset <asset id>")
            if args.reviewer is None:
                parser.error("review requires --reviewer <name>")
            if args.decision is None:
                parser.error("review requires --decision <decision>")
            record = record_review(lib, args.asset, args.reviewer,
                                   args.decision, note=args.note)
            print(f"Recorded review {record['review_id']} for "
                  f"{record['asset_id']}: {record['decision']} by "
                  f"{record['reviewer']} (advisory only; asset status "
                  f"unchanged)")
        return 0
    except (ValidationError, PromotionError, RecipeError, JobError,
            ReviewError, OSError, ValueError) as err:
        parser.error(str(err))
    finally:
        lib.close()
    return 2
