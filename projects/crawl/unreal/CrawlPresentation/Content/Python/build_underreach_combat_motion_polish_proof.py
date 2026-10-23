import hashlib, json, math
from pathlib import Path
import unreal


def _project_dir(): return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root=_project_dir()/"Generated"/"underreach-29d4"
    proof_path=root/"combat-motion-polish-proof.json"
    out=root/"combat-motion-polish-unreal-debug.json"
    before=_sha(proof_path)
    proof=json.loads(proof_path.read_text(encoding="utf-8"))
    polish=proof["motion_polish"]
    directives=polish["directives"]
    attacks=[d for d in directives if d["presentation_kind"]=="attack"]
    reactions=[d for d in directives if d["presentation_kind"]=="hit_reaction"]
    deaths=[d for d in directives if d["presentation_kind"]=="death"]
    missing=[]
    for d in directives:
        path=d.get("asset_path")
        if not path or unreal.load_asset(path) is None:
            missing.append(path)
    max_alignment=max([float(d.get("contact_alignment_cm",0.0)) for d in attacks] or [0.0])
    max_slide=max([float(d.get("foot_slide_budget_cm",0.0)) for d in attacks] or [0.0])
    max_reaction=max([float(d.get("reaction_displacement_cm",0.0)) for d in reactions] or [0.0])
    max_sync=max([float(d.get("contact_sync_error_seconds",0.0)) for d in reactions] or [0.0])
    max_blend=max([max(float(d["blend_in_seconds"]),float(d["blend_out_seconds"])) for d in directives] or [0.0])
    camera_holds=sum(1 for d in attacks if float(d.get("camera_contact_hold_seconds",0.0))>0.0)
    corpse_locks=sum(1 for d in deaths if d.get("corpse_root_lock") is True)
    after=_sha(proof_path)
    validation={
        "all_real_assets_load": not missing,
        "attack_alignment_bounded": bool(attacks) and max_alignment <= float(polish["max_pair_alignment_cm"])+1e-9,
        "foot_slide_budget_bounded": bool(attacks) and max_slide <= 3.0+1e-9,
        "reaction_motion_bounded": bool(reactions) and max_reaction <= float(polish["max_knockback_cm"])+1e-9,
        "reaction_contact_sync": bool(reactions) and max_sync <= 0.001+1e-9,
        "transition_blends_bounded": bool(directives) and max_blend <= 0.18+1e-9,
        "camera_contact_holds_present": camera_holds == len(attacks),
        "death_corpse_locks_present": bool(deaths) and corpse_locks == len(deaths),
        "presentation_non_authoritative": polish.get("authoritative") is False and polish.get("canonical_state_mutation_allowed") is False,
        "proof_file_unchanged": before==after,
    }
    validation["all_pass"]=all(validation.values())
    payload={
        "protocol":"underreach.combat-motion-polish-unreal-debug.v1",
        "authoritative":False,
        "engine_version":unreal.SystemLibrary.get_engine_version(),
        "directive_count":len(directives),"attack_count":len(attacks),"reaction_count":len(reactions),"death_count":len(deaths),
        "unique_asset_count":len({d.get("asset_path") for d in directives if d.get("asset_path")}),
        "max_pair_alignment_cm":max_alignment,"max_foot_slide_budget_cm":max_slide,"max_reaction_displacement_cm":max_reaction,
        "max_contact_sync_error_seconds":max_sync,"max_transition_blend_seconds":max_blend,
        "camera_contact_hold_count":camera_holds,"corpse_root_lock_count":corpse_locks,"missing_assets":missing,
        "proof_file_sha256_before":before,"proof_file_sha256_after":after,"validation":validation,
    }
    out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding="utf-8")
    if not validation["all_pass"]: unreal.log_error("[29D.4] Unreal combat motion polish proof FAILED")
    else: unreal.log("[29D.4] Unreal combat motion polish proof PASS")
    return out

main()
