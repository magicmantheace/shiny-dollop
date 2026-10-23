import hashlib, json
from pathlib import Path
import unreal


def _project_dir(): return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))

def _sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    root=_project_dir()/"Generated"/"underreach-29d3"
    proof_path=root/"reaction-death-binding-proof.json"
    out=root/"reaction-death-binding-unreal-debug.json"
    before=_sha(proof_path)
    proof=json.loads(proof_path.read_text(encoding='utf-8'))
    binding=proof['reaction_death_binding']
    items=binding['bindings']
    target=[x for x in items if x['presentation_kind'] in {'hit_reaction','death'}]
    loaded=[]; missing=[]
    for item in target:
        asset=unreal.load_asset(item['asset_path']) if item.get('asset_path') else None
        if asset is None: missing.append(item.get('asset_path'))
        else: loaded.append(item['asset_path'])
    reactions=[x for x in target if x['presentation_kind']=='hit_reaction']
    deaths=[x for x in target if x['presentation_kind']=='death']
    max_sync=max([float(x.get('contact_sync_error_seconds') or 0.0) for x in reactions] or [0.0])
    after=_sha(proof_path)
    validation={
        'all_target_assets_loaded': not missing and len(loaded)==len(target),
        'all_reactions_real': bool(reactions) and all(x.get('binding_status')=='measured_real_asset' for x in reactions),
        'all_deaths_real': bool(deaths) and all(x.get('binding_status')=='measured_real_asset' for x in deaths),
        'reaction_contact_sync_exact': max_sync <= 0.001,
        'deaths_terminal_and_canonical': bool(deaths) and all(x.get('terminal_pose_required') is True and x.get('canonical_death') is True for x in deaths),
        'proof_file_unchanged': before==after,
        'presentation_non_authoritative': binding.get('authoritative') is False and binding.get('canonical_state_mutation_allowed') is False,
    }
    validation['all_pass']=all(validation.values())
    payload={
        'protocol':'underreach.reaction-death-unreal-debug.v1','authoritative':False,
        'engine_version':unreal.SystemLibrary.get_engine_version(),
        'reaction_count':len(reactions),'death_count':len(deaths),
        'unique_reaction_assets':len({x['asset_path'] for x in reactions}),
        'unique_death_assets':len({x['asset_path'] for x in deaths}),
        'max_contact_sync_error_seconds':max_sync,'missing_assets':missing,
        'proof_file_sha256_before':before,'proof_file_sha256_after':after,'validation':validation,
    }
    out.write_text(json.dumps(payload,indent=2,sort_keys=True),encoding='utf-8')
    if not validation['all_pass']: unreal.log_error('[29D.3] Unreal reaction/death proof FAILED')
    else: unreal.log('[29D.3] Unreal reaction/death proof PASS')
    return out

main()
