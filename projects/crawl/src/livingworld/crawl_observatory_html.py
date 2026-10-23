from __future__ import annotations

import html
import json
from typing import Any


def render_observatory_html(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, separators=(",", ":")).replace("</", "<\\/")
    title = html.escape(f"Crawl Observatory — {snapshot.get('crawl', {}).get('id', 'unknown')}")
    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>{title}</title>
<style>
:root {{ color-scheme: dark; font-family: Inter, system-ui, sans-serif; background:#11151b; color:#e7edf5; }}
body {{ margin:0; padding:24px; }}
h1,h2,h3 {{ margin:0 0 12px; }}
small,.muted {{ color:#98a7b8; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:12px; margin:16px 0; }}
.card {{ background:#19212b; border:1px solid #2d3948; border-radius:10px; padding:14px; overflow:auto; }}
.kpi {{ font-size:1.55rem; font-weight:700; }}
table {{ width:100%; border-collapse:collapse; font-size:.88rem; }}
th,td {{ border-bottom:1px solid #2b3745; padding:7px; text-align:left; vertical-align:top; }}
th {{ position:sticky; top:0; background:#19212b; }}
.bar {{ height:8px; background:#2b3745; border-radius:5px; overflow:hidden; }}
.bar > span {{ display:block; height:100%; background:#89a7c7; }}
pre {{ white-space:pre-wrap; word-break:break-word; font-size:.8rem; }}
section {{ margin-top:24px; }}
.tag {{ display:inline-block; padding:2px 7px; border-radius:10px; background:#273445; margin:2px; font-size:.75rem; }}
</style>
</head>
<body>
<h1>Crawl Observatory</h1><div class=\"muted\" id=\"subtitle\"></div>
<div class=\"grid\" id=\"kpis\"></div>
<section><h2>Simulation detail tiers</h2><div class=\"grid\" id=\"tiers\"></div></section>
<section><h2>Selected crawler diagnostic</h2><div class=\"card\" id=\"selected\"></div></section>
<section><h2>Crawlers</h2><div class=\"card\"><table id=\"crawlers\"></table></div></section>
<section><h2>Floor occupancy</h2><div class=\"card\" id=\"occupancy\"></div></section>
<section><h2>Encounters & parties</h2><div class=\"grid\"><div class=\"card\"><h3>Encounters</h3><pre id=\"encounters\"></pre></div><div class=\"card\"><h3>Parties</h3><pre id=\"parties\"></pre></div></div></section>
<section><h2>Interesting events</h2><div class=\"card\"><table id=\"events\"></table></div></section>
<section><h2>Director interventions</h2><div class=\"card\"><pre id=\"director\"></pre></div></section>
<section><h2>Performance</h2><div class=\"card\"><pre id=\"performance\"></pre></div></section>
<script type=\"application/json\" id=\"data\">{payload}</script>
<script>
const d=JSON.parse(document.getElementById('data').textContent);
const c=d.crawl||{{}}; const p=d.population||{{}};
document.getElementById('subtitle').textContent=`${{c.status}} • tick ${{c.tick}} • floor ${{c.current_floor}}/${{c.configured_floors}} • seed ${{c.seed}}`;
const kpis=[['Survivors',c.survivors],['Eliminated',c.eliminated],['Crawlers',c.starting_crawlers],['Events',(d.recent_events||[]).length],['Notable',(d.interesting_events||[]).length],['Active parties',(d.active_parties||[]).length]];
document.getElementById('kpis').innerHTML=kpis.map(x=>`<div class=\"card\"><div class=\"muted\">${{x[0]}}</div><div class=\"kpi\">${{x[1]??0}}</div></div>`).join('');
const tiers=p.detail_tiers||{{}}; document.getElementById('tiers').innerHTML=Object.entries(tiers).map(([k,v])=>`<div class=\"card\"><b>Tier ${{k}}</b><div class=\"kpi\">${{v}}</div></div>`).join('');
const s=d.selected_crawler||{{}};
document.getElementById('selected').innerHTML=`<h3>${{s.npc_id||'none'}}</h3><div>Tier ${{s.detail_tier||'-'}} • ${{s.status||'-'}} • HP ${{Number(s.health||0).toFixed(3)}} • objective ${{s.objective||'-'}}</div><p><b>Decision trace</b></p><pre>${{JSON.stringify(s.decision_trace||{{}},null,2)}}</pre><p><b>Recent events</b></p><pre>${{JSON.stringify((s.recent_events||[]).slice(0,8),null,2)}}</pre>`;
const rows=d.crawlers||[]; const cols=['npc_id','status','tier','floor','location_id','health','stamina','level','specialization','party_id','objective','inventory_count','kills'];
document.getElementById('crawlers').innerHTML='<tr>'+cols.map(x=>`<th>${{x}}</th>`).join('')+'</tr>'+rows.map(r=>'<tr>'+cols.map(x=>`<td>${{r[x]??''}}</td>`).join('')+'</tr>').join('');
const occ=(d.floor||{{}}).occupancy||{{}}; document.getElementById('occupancy').innerHTML=Object.entries(occ).map(([loc,ids])=>`<p><b>${{loc}}</b> <span class=\"tag\">${{ids.length}} crawlers</span><br><small>${{ids.slice(0,20).join(', ')}}${{ids.length>20?' …':''}}</small></p>`).join('');
document.getElementById('encounters').textContent=JSON.stringify(d.active_encounters||[],null,2); document.getElementById('parties').textContent=JSON.stringify(d.active_parties||[],null,2);
const ev=d.interesting_events||[]; document.getElementById('events').innerHTML='<tr><th>score</th><th>tick</th><th>type</th><th>summary</th><th>actors</th></tr>'+ev.map(e=>`<tr><td>${{Number(e.semantic_score||0).toFixed(3)}}</td><td>${{e.tick}}</td><td>${{e.event_type}}</td><td>${{e.summary}}</td><td>${{(e.actor_ids||[]).join(', ')}}</td></tr>`).join('');
document.getElementById('director').textContent=JSON.stringify(d.director_interventions||[],null,2); document.getElementById('performance').textContent=JSON.stringify(d.performance||{{}},null,2);
</script>
</body></html>"""
