import { FormEvent, useEffect, useMemo, useState } from 'react'
import { getEvents, getKingdom, getMap, getMigrations, getNpc, getWars, getWorld, runCommand, runNaturalCommand } from './api'
import type { HistoricalEvent, Kingdom, MapData, NPC, War, WorldSummary } from './types'
import './styles.css'
import './continent.css'

const pct = (value: number) => `${Math.round(value * 100)}%`
const num = (value: number | undefined) => Math.round(value ?? 0).toLocaleString()

export default function App() {
  const [world, setWorld] = useState<WorldSummary | null>(null)
  const [map, setMap] = useState<MapData | null>(null)
  const [events, setEvents] = useState<HistoricalEvent[]>([])
  const [migrations, setMigrations] = useState<HistoricalEvent[]>([])
  const [wars, setWars] = useState<War[]>([])
  const [adminKey, setAdminKey] = useState(() => localStorage.getItem('livingworld-admin-key') ?? 'change-me')
  const [command, setCommand] = useState('advance 1 day')
  const [commandResult, setCommandResult] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [selectedKingdom, setSelectedKingdom] = useState<Kingdom | null>(null)
  const [selectedNpc, setSelectedNpc] = useState<NPC | null>(null)
  const [npcId, setNpcId] = useState('')

  const refresh = async () => {
    try {
      const [w, m, e, migrationData, warsData] = await Promise.all([
        getWorld(),
        getMap(),
        getEvents(80),
        getMigrations(60),
        getWars(),
      ])
      setWorld(w)
      setMap(m)
      setEvents(e)
      setMigrations(migrationData)
      setWars(warsData)
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  useEffect(() => {
    refresh()
    const timer = window.setInterval(refresh, 5000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    localStorage.setItem('livingworld-admin-key', adminKey)
  }, [adminKey])

  const settlementsById = useMemo(
    () => new Map(map?.settlements.map((s) => [s.id, s] as const) ?? []),
    [map],
  )
  const kingdomIndex = useMemo(
    () => new Map(map?.kingdoms.map((k, i) => [k.id, i] as const) ?? []),
    [map],
  )

  const selectKingdom = async (id: string) => {
    try {
      setSelectedNpc(null)
      setSelectedKingdom(await getKingdom(id))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const inspectNpc = async (event?: FormEvent) => {
    event?.preventDefault()
    if (!npcId.trim()) return
    try {
      setSelectedKingdom(null)
      setSelectedNpc(await getNpc(npcId.trim()))
      setError('')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const adminAction = async (type: string, parameters: Record<string, unknown> = {}) => {
    setBusy(true)
    try {
      const result = await runCommand(adminKey, type, undefined, parameters)
      setCommandResult(JSON.stringify(result, null, 2))
      await refresh()
    } catch (err) {
      setCommandResult(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const submitCommand = async (event: FormEvent) => {
    event.preventDefault()
    if (!command.trim()) return
    setBusy(true)
    try {
      const result = await runNaturalCommand(adminKey, command)
      setCommandResult(JSON.stringify(result, null, 2))
      await refresh()
    } catch (err) {
      setCommandResult(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  if (!world || !map) {
    return <main className="loading"><h1>LivingWorld Control Center</h1><p>{error || 'Connecting to world service…'}</p></main>
  }

  const minX = map.bounds.min_x ?? 0
  const maxX = map.bounds.max_x ?? 100
  const minY = map.bounds.min_y ?? 0
  const maxY = map.bounds.max_y ?? 100
  const mapWidth = Math.max(1, maxX - minX)
  const mapHeight = Math.max(1, maxY - minY)
  const mapY = (y: number) => maxY - y + minY
  const worldLabel = map.continent?.name ?? world.region.name

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Authoritative simulation</p>
          <h1>{world.name}</h1>
          <p>{worldLabel} · {world.date_label} · {world.paused ? 'PAUSED' : `${world.speed_multiplier}×`}</p>
        </div>
        <div className="connection"><span className="status-dot" />LIVE</div>
      </header>

      {error && <div className="error-banner">{error}</div>}

      <section className="metric-grid">
        <Metric label="Population" value={num(world.metrics.population)} />
        <Metric label="Regions" value={num(world.metrics.regions ?? world.regions)} />
        <Metric label="Kingdoms" value={num(world.metrics.kingdoms)} />
        <Metric label="Settlements" value={num(world.metrics.settlements)} />
        <Metric label="Persistent NPCs" value={num(world.metrics.persistent_npcs)} />
        <Metric label="Active Wars" value={num(world.metrics.active_wars)} />
        <Metric label="Refugees admitted" value={num(world.metrics.refugees_accepted_last_month)} />
        <Metric label="Refugees camped" value={num(world.metrics.refugees_rejected_last_month)} />
        <Metric label="Active camps" value={num(world.metrics.active_refugee_camps)} />
        <Metric label="Camp population" value={num(world.metrics.refugee_camp_population)} />
      </section>

      <main className="dashboard-grid">
        <section className="panel map-panel continent-map-panel">
          <div className="panel-heading">
            <div><p className="eyebrow">Strategic continent view</p><h2>{worldLabel}</h2></div>
            <span>{map.regions.length} regions · {map.refugee_camps.length} camps</span>
          </div>
          <svg className="world-map continent-map" viewBox={`${minX} ${minY} ${mapWidth} ${mapHeight}`} role="img" aria-label="Strategic continent map">
            <defs>
              <pattern id="grid" width={Math.max(5, mapWidth / 20)} height={Math.max(5, mapHeight / 20)} patternUnits="userSpaceOnUse">
                <path d={`M ${Math.max(5, mapWidth / 20)} 0 L 0 0 0 ${Math.max(5, mapHeight / 20)}`} className="map-gridline" fill="none" />
              </pattern>
            </defs>
            <rect x={minX} y={minY} width={mapWidth} height={mapHeight} className="map-ground" />
            <rect x={minX} y={minY} width={mapWidth} height={mapHeight} fill="url(#grid)" />
            {map.regions.map((region) => {
              const left = region.bounds.min_x ?? 0
              const right = region.bounds.max_x ?? left
              const bottom = region.bounds.min_y ?? 0
              const top = region.bounds.max_y ?? bottom
              return (
                <g key={region.id} className="region-boundary">
                  <rect x={left} y={mapY(top)} width={Math.max(0, right - left)} height={Math.max(0, top - bottom)} />
                  <text x={(left + right) / 2} y={mapY((bottom + top) / 2)}>{region.name}</text>
                </g>
              )
            })}
            {map.trade_routes.map((route) => {
              const a = settlementsById.get(route.origin_settlement_id)
              const b = settlementsById.get(route.destination_settlement_id)
              if (!a || !b) return null
              return <line key={route.id} x1={a.position.x} y1={mapY(a.position.y)} x2={b.position.x} y2={mapY(b.position.y)} className="route-line" />
            })}
            {map.landmarks.map((landmark) => (
              <g key={landmark.id} className="landmark">
                <circle cx={landmark.position.x} cy={mapY(landmark.position.y)} r="1.4" />
                <title>{landmark.name}: {landmark.description}</title>
              </g>
            ))}
            {map.settlements.map((s) => {
              const colorIndex = kingdomIndex.get(s.kingdom_id) ?? 0
              return (
                <g key={s.id} className={`settlement kingdom-${colorIndex % 4}`} onClick={() => selectKingdom(s.kingdom_id)}>
                  <circle cx={s.position.x} cy={mapY(s.position.y)} r={s.type === 'town' ? 2.1 : 1.25} />
                  <title>{s.name} · {s.type} · {s.region_id} · pop {s.population.toLocaleString()}</title>
                </g>
              )
            })}
            {map.refugee_camps.map((camp) => {
              const host = settlementsById.get(camp.host_settlement_id)
              if (!host) return null
              return (
                <g key={camp.id} className="refugee-camp-marker">
                  <path d={`M ${host.position.x - 2.2} ${mapY(host.position.y) + 4.5} L ${host.position.x + 2.2} ${mapY(host.position.y) + 4.5} L ${host.position.x} ${mapY(host.position.y) + 0.5} Z`} />
                  <title>{camp.id} · {camp.people.toLocaleString()} people · health {pct(camp.health)}</title>
                </g>
              )
            })}
            {map.armies.map((army) => {
              const s = settlementsById.get(army.location_settlement_id)
              return s ? <rect key={army.id} x={s.position.x - 1} y={mapY(s.position.y) - 5} width="2" height="2" className="army" /> : null
            })}
          </svg>
          <div className="legend">
            {map.kingdoms.map((k, i) => <button key={k.id} onClick={() => selectKingdom(k.id)}><span className={`legend-dot kingdom-${i % 4}`} />{k.name}</button>)}
          </div>
        </section>

        <section className="panel kingdom-panel">
          <div className="panel-heading"><div><p className="eyebrow">Political state</p><h2>Kingdoms</h2></div></div>
          <div className="stack-list">
            {map.kingdoms.map((k) => (
              <button className="list-card" key={k.id} onClick={() => selectKingdom(k.id)}>
                <strong>{k.name}</strong><span>{k.dominant_ancestry}</span>
                <small>{k.settlement_ids.length} settlements · {k.border_policy} border · refugees {k.refugee_policy}</small>
              </button>
            ))}
          </div>
          <h3>Wars</h3>
          {wars.filter((w) => w.state === 'active').length === 0 ? <p className="muted">No active wars.</p> : wars.filter((w) => w.state === 'active').map((war) => (
            <div className="war-card" key={war.id}><strong>{war.id}</strong><span>{war.attacker_kingdom_id} → {war.defender_kingdom_id}</span><small>{war.goal} · score {war.attacker_score.toFixed(1)}</small></div>
          ))}
        </section>

        <section className="panel migration-panel">
          <div className="panel-heading"><div><p className="eyebrow">Population movement</p><h2>Borders, Camps & Migration</h2></div><span>{migrations.length} flows loaded</span></div>
          <div className="region-grid">
            {map.regions.map((region) => (
              <article className="region-card" key={region.id}>
                <strong>{region.name}</strong>
                <span>{region.climate.replaceAll('_', ' ')}</span>
                <small>{region.population.toLocaleString()} people · {region.settlement_count} settlements</small>
              </article>
            ))}
          </div>
          <h3>Active refugee camps</h3>
          <div className="migration-feed">
            {map.refugee_camps.length === 0 ? <p className="muted">No active refugee camps.</p> : map.refugee_camps.slice(0, 10).map((camp) => (
              <article key={camp.id} className="refugee-flow camp-card">
                <strong>{camp.id}</strong>
                <p>{camp.people.toLocaleString()} people outside {settlementsById.get(camp.host_settlement_id)?.name ?? camp.host_settlement_id}</p>
                <small>food {pct(camp.food_security)} · health {pct(camp.health)} · {camp.status}</small>
              </article>
            ))}
          </div>
          <h3>Recent movement</h3>
          <div className="migration-feed">
            {migrations.length === 0 ? <p className="muted">No recorded migration yet. Advance at least one month.</p> : migrations.slice(0, 12).map((event) => (
              <article key={event.id} className={event.type === 'REFUGEE_MOVEMENT' ? 'refugee-flow' : ''}>
                <strong>{event.type === 'REFUGEE_MOVEMENT' ? 'Refugees' : 'Migration'}</strong>
                <p>{event.summary}</p>
                <small>{num(Number(event.data.people ?? 0))} people · Y{event.occurred_at.year} M{event.occurred_at.month}</small>
              </article>
            ))}
          </div>
        </section>

        <section className="panel control-panel">
          <div className="panel-heading"><div><p className="eyebrow">God-mode administration</p><h2>World Control</h2></div></div>
          <label>Admin key<input type="password" value={adminKey} onChange={(e) => setAdminKey(e.target.value)} /></label>
          <div className="button-row">
            <button disabled={busy} onClick={() => adminAction(world.paused ? 'world.resume' : 'world.pause')}>{world.paused ? 'Resume' : 'Pause'}</button>
            <button disabled={busy} onClick={() => adminAction('world.advance', { amount: 1, unit: 'day' })}>+1 day</button>
            <button disabled={busy} onClick={() => adminAction('world.advance', { amount: 1, unit: 'month' })}>+1 month</button>
            <button disabled={busy} onClick={() => adminAction('world.advance', { amount: 1, unit: 'year' })}>+1 year</button>
          </div>
          <p className="hint">Simulation speed</p>
          <div className="button-row">
            {[1, 10, 100, 1000, 10000].map((speed) => (
              <button key={speed} disabled={busy} onClick={() => adminAction('world.set_speed', { speed })}>
                {speed === 10000 ? 'MAX' : `${speed}×`}
              </button>
            ))}
          </div>
          <form onSubmit={submitCommand} className="command-form">
            <label>Natural command<textarea value={command} onChange={(e) => setCommand(e.target.value)} rows={3} /></label>
            <button type="submit" disabled={busy}>Issue command</button>
          </form>
          <p className="hint">Policy examples: “set kingdom_0001 border closed” or “set kingdom_0001 refugees welcome”.</p>
          {commandResult && <pre className="command-result">{commandResult}</pre>}
        </section>

        <section className="panel inspector-panel">
          <div className="panel-heading"><div><p className="eyebrow">Entity inspection</p><h2>Inspector</h2></div></div>
          <form className="npc-form" onSubmit={inspectNpc}>
            <input placeholder="npc_0000001" value={npcId} onChange={(e) => setNpcId(e.target.value)} />
            <button>Inspect NPC</button>
          </form>
          {selectedKingdom && <KingdomInspector kingdom={selectedKingdom} />}
          {selectedNpc && <NpcInspector npc={selectedNpc} />}
          {!selectedKingdom && !selectedNpc && <p className="muted">Select a kingdom on the map or enter an NPC ID.</p>}
        </section>

        <section className="panel events-panel">
          <div className="panel-heading"><div><p className="eyebrow">Immutable history</p><h2>Recent Events</h2></div><span>{events.length} loaded</span></div>
          <div className="event-feed">
            {events.map((event) => (
              <article key={event.id} className={event.importance >= 0.8 ? 'important' : ''}>
                <div><strong>{event.type.replaceAll('_', ' ')}</strong><span>Y{event.occurred_at.year} M{event.occurred_at.month} D{event.occurred_at.day}</span></div>
                <p>{event.summary}</p><small>{event.source}</small>
              </article>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong></div>
}

function KingdomInspector({ kingdom }: { kingdom: Kingdom }) {
  return <div className="inspector">
    <h3>{kingdom.name}</h3>
    <dl>
      <dt>Government</dt><dd>{kingdom.government}</dd>
      <dt>Population</dt><dd>{kingdom.population.toLocaleString()}</dd>
      <dt>Border policy</dt><dd>{kingdom.border_policy}</dd>
      <dt>Refugee policy</dt><dd>{kingdom.refugee_policy}</dd>
      <dt>Refugee camps</dt><dd>{kingdom.refugee_camps}</dd>
      <dt>Camp population</dt><dd>{kingdom.camp_population.toLocaleString()}</dd>
      <dt>Treasury</dt><dd>{Math.round(kingdom.treasury).toLocaleString()}</dd>
      <dt>Food reserve</dt><dd>{pct(kingdom.food_reserve)}</dd>
      <dt>Readiness</dt><dd>{pct(kingdom.military_readiness)}</dd>
      <dt>Ruler</dt><dd>{kingdom.ruler?.name ?? 'Vacant'}</dd>
    </dl>
    {kingdom.last_decision && <div className="decision"><strong>Last decision: {kingdom.last_decision.action}</strong><span>score {kingdom.last_decision.score.toFixed(1)}</span><pre>{JSON.stringify(kingdom.last_decision.reasons, null, 2)}</pre></div>}
  </div>
}

function NpcInspector({ npc }: { npc: NPC }) {
  return <div className="inspector">
    <h3>{npc.title ? `${npc.title} ` : ''}{npc.name}</h3>
    <dl>
      <dt>Ancestry</dt><dd>{npc.ancestry}</dd>
      <dt>Age</dt><dd>{npc.age}</dd>
      <dt>Status</dt><dd>{npc.alive ? npc.social_status : 'deceased'}</dd>
      <dt>Occupation</dt><dd>{npc.occupation}</dd>
      <dt>Health</dt><dd>{pct(npc.health)}</dd>
      <dt>Wealth</dt><dd>{npc.wealth.toFixed(1)}</dd>
    </dl>
    <h4>Goals</h4><p>{npc.goals.join(', ') || 'None'}</p>
    <h4>Recent memories</h4>
    {npc.memories.slice(-5).reverse().map((m) => <p className="memory" key={m.event_id}>{m.summary}</p>)}
  </div>
}
