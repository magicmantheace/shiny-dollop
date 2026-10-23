import argparse, json
from pathlib import Path
from livingworld.underreach_reaction_death_binding import build_reaction_death_binding_proof

p=argparse.ArgumentParser()
p.add_argument('--attack-profiles',required=True)
p.add_argument('--reaction-profiles',required=True)
p.add_argument('--output',required=True)
p.add_argument('--seed',default='underreach-29d3-reaction-death-proof')
a=p.parse_args()
att=json.loads(Path(a.attack_profiles).read_text(encoding='utf-8'))
rea=json.loads(Path(a.reaction_profiles).read_text(encoding='utf-8'))
proof=build_reaction_death_binding_proof(att,rea,a.seed)
out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(proof,indent=2,sort_keys=True),encoding='utf-8')
b=proof['reaction_death_binding']
items=b['bindings']
print(f"[29D.3] binding digest: {b['digest']}")
print(f"[29D.3] real reactions: {sum(x['presentation_kind']=='hit_reaction' for x in items)}")
print(f"[29D.3] real deaths: {sum(x['presentation_kind']=='death' for x in items)}")
print(f"[29D.3] output: {out}")
