import { useEffect, useMemo, useRef, useState } from 'react'
import { followDescender, getViewerState, releaseToAuto } from './api'
import type { DescenderRow, ViewerState } from './types'
import { canFollow, connectionLabel, eventMatchesSelection, healthLabel, panelState, POLL_INTERVAL_MS, statusLabel } from './viewer-model.mjs'

const VIEWER_ID_KEY = 'underreach-viewer-id'
const REQUEST_SEQUENCE_KEY = 'underreach-request-sequence'
const viewerId = () => { const existing = localStorage.getItem(VIEWER_ID_KEY); if (existing) return existing; const created = 'viewer_local_alpha'; localStorage.setItem(VIEWER_ID_KEY, created); return created }
const nextRequestId = (action: string) => { const next = Number(localStorage.getItem(REQUEST_SEQUENCE_KEY) ?? '0') + 1; localStorage.setItem(REQUEST_SEQUENCE_KEY, String(next)); return `viewer_${action}_${String(next).padStart(4, '0')}` }

export default function App() {
  const sessionId = useMemo(viewerId, [])
  const [state, setState] = useState<ViewerState | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [pendingId, setPendingId] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [lastResult, setLastResult] = useState('')
  const [lastReceipt, setLastReceipt] = useState(0)
  const [clock, setClock] = useState(Date.now())
  const alive = useRef(true)

  const refresh = async () => {
    try {
      const next = await getViewerState(sessionId)
      if (!alive.current) return
      setState(next); setLastReceipt(Date.now()); setError('')
      setSelectedId((current) => current ?? next.focus?.active_descender_id ?? next.descenders[0]?.descender_id ?? null)
    } catch (reason) { if (alive.current) setError(reason instanceof Error ? reason.message : String(reason)) }
  }

  useEffect(() => {
    alive.current = true; refresh()
    const poll = window.setInterval(refresh, POLL_INTERVAL_MS)
    const clockTimer = window.setInterval(() => setClock(Date.now()), 500)
    return () => { alive.current = false; window.clearInterval(poll); window.clearInterval(clockTimer) }
  }, [])

  const selected = state?.descenders.find((item) => item.descender_id === selectedId) ?? null
  const view = panelState(state, error, lastReceipt, clock)
  const connection = connectionLabel(state, lastReceipt, clock)

  const control = async (kind: 'follow' | 'auto', row?: DescenderRow) => {
    if (!state?.focus || pendingId) return
    const target = row?.descender_id ?? 'auto'; setPendingId(target)
    setLastResult(kind === 'follow' ? `Switching to ${row?.display_name}…` : 'Returning to Auto…')
    try {
      // A live presentation tick can advance between the regular poll and a
      // human click. Refresh immediately before the command so the idempotent
      // control request carries the latest confirmed server cursor.
      const confirmed = await getViewerState(sessionId)
      setState(confirmed); setLastReceipt(Date.now())
      if (!confirmed.focus) throw new Error('Feed focus is not ready')
      const result = kind === 'follow'
        ? await followDescender(sessionId, nextRequestId('follow'), confirmed.focus.presentation_tick, row!.descender_id)
        : await releaseToAuto(sessionId, nextRequestId('auto'), confirmed.focus.presentation_tick)
      setLastResult(result.duplicate ? 'Already confirmed.' : 'Request acknowledged. Confirming Feed state…')
      await refresh()
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : String(reason); setError(message); setLastResult(`Control request rejected: ${message}`)
    } finally { setPendingId(null) }
  }

  if (view === 'loading') return <main className="center-state"><div className="sigil">U</div><h1>The Underreach</h1><p>Connecting to the live Feed…</p></main>
  if (view === 'no-descent') return <main className="center-state"><div className="sigil">U</div><h1>No active Descent</h1><p>The Feed is ready, but no Descent is currently running.</p></main>

  return <div className="viewer-shell">
    <header className="broadcast-header">
      <div className="brand"><span className="sigil small">U</span><div><p className="overline">Live spectator terminal</p><h1>The Underreach</h1><p>The Descent · Stratum {state?.stratum?.number ?? '—'} · {state?.stratum?.theme ?? 'Unknown sector network'}</p></div></div>
      <div className="header-health">
        <div className={`runtime-health ${state?.runtime?.overall_status ?? 'offline'}`}>
          <strong>{state?.runtime?.overall_status ?? 'Offline'}</strong>
          <small>{state?.runtime ? `${Math.floor(state.runtime.uptime_seconds / 60)}m uptime · lag ${state.runtime.presentation_lag_ticks} · Unreal ${state.runtime.unreal_connected ? 'connected' : 'offline'} · checkpoint ${state.runtime.checkpoint_age_seconds == null ? 'pending' : `${Math.floor(state.runtime.checkpoint_age_seconds)}s`}` : 'Runtime health unavailable'}</small>
        </div>
        <div className={`connection-pill ${connection.toLowerCase()}`}><span />{connection}</div>
      </div>
    </header>
    {error && <div className="notice error" role="alert">{view === 'reconnecting' ? 'Reconnecting: ' : ''}{error}</div>}
    {view === 'stale' && <div className="notice stale" role="status">The Feed has stopped advancing. Showing the last confirmed state.</div>}

    <section className="descent-strip" aria-label="Current Descent summary">
      <Metric label="Descent" value={state?.descent?.status ?? 'Unknown'} detail={state?.descent?.id ?? '—'} />
      <Metric label="Stratum" value={String(state?.stratum?.number ?? '—')} detail={`${state?.stratum?.sector_count ?? 0} Sectors`} />
      <Metric label="Living" value={String(state?.summary.living_descender_count ?? 0)} detail={`${state?.summary.fallen_descender_count ?? 0} Fallen`} />
      <Metric label="Ledger" value={`Tick ${state?.connection.latest_ledger_tick ?? 0}`} detail={`${state?.summary.logical_channel_count ?? 0} Feed channels`} />
    </section>

    <main className="viewer-grid">
      <section className="panel directory-panel">
        <div className="panel-heading"><div><p className="overline">Channel directory</p><h2>Descenders</h2></div><span>{state?.descenders.length ?? 0} tracked</span></div>
        <div className="descender-list">
          {state?.descenders.map((row) => {
            const active = state.focus?.active_descender_id === row.descender_id; const selectedRow = selectedId === row.descender_id
            return <button key={row.descender_id} className={`descender-row ${active ? 'active' : ''} ${selectedRow ? 'selected' : ''} ${row.terminal ? 'terminal' : ''}`} onClick={() => setSelectedId(row.descender_id)} aria-pressed={selectedRow}>
              <span className={`status-mark ${row.terminal ? 'terminal' : row.in_active_encounter ? 'combat' : 'alive'}`}>{row.terminal ? '†' : '●'}</span>
              <span className="descender-main"><strong>{row.display_name}</strong><small>{row.sector_id ?? 'Sector unknown'} · Health {healthLabel(row.health)}</small></span>
              <span className="row-state">{active ? (state.focus?.mode === 'manual' ? 'FOLLOWING' : 'AUTO') : statusLabel(row)}</span>
            </button>
          })}
          {state?.descenders.length === 0 && <p className="empty">No Descenders are currently registered.</p>}
        </div>
      </section>

      <section className="panel feed-panel">
        <div className="panel-heading"><div><p className="overline">Confirmed presentation state</p><h2>Current Feed</h2></div><span className={`mode-badge ${state?.focus?.mode}`}>{state?.focus?.mode === 'manual' ? 'MANUAL' : 'AUTO'}</span></div>
        <div className="feed-hero"><p>{state?.focus?.mode === 'manual' ? 'Following' : 'Automatic focus'}</p><h3>{state?.focus?.active_descender_name ?? 'No active Descender'}</h3><span>{state?.focus?.active_channel_id ?? 'Feed awaiting focus'}</span></div>
        <dl className="feed-details">
          <div><dt>Camera</dt><dd>{state?.camera?.mode.replaceAll('_', ' ') ?? 'waiting'}</dd></div>
          <div><dt>Targets</dt><dd>{state?.camera?.target_actor_ids.join(', ') || 'Awaiting shot'}</dd></div>
          <div><dt>Presentation</dt><dd>Tick {state?.focus?.presentation_tick ?? 0}</dd></div>
          <div><dt>Sector</dt><dd>{state?.descenders.find((item) => item.descender_id === state.focus?.active_descender_id)?.sector_id ?? 'Unknown'}</dd></div>
        </dl>
        <div className="preview-placeholder"><p>Current Feed</p><strong>Live in Unreal</strong><small>Shot {state?.camera?.shot_id ?? 'pending'}</small></div>
        <div className="controls">
          <button className="primary" disabled={!selected || !canFollow(state, selected, pendingId)} onClick={() => selected && control('follow', selected)}>{pendingId && pendingId !== 'auto' ? 'Switching…' : selected && !selected.camera_available ? 'Archive only' : selected ? `Follow ${selected.display_name}` : 'Select a Descender'}</button>
          <button className="auto-button" disabled={!state?.focus || state.focus.mode === 'automatic' || Boolean(pendingId)} onClick={() => control('auto')}>{pendingId === 'auto' ? 'Returning…' : 'Return to Auto'}</button>
        </div>
        <p className="acknowledgement" aria-live="polite">{lastResult || 'Controls update presentation focus only.'}</p>
        {selected?.terminal && <div className="terminal-callout"><strong>{selected.display_name} has Fallen.</strong><span>The channel remains available as a terminal record.</span></div>}
      </section>

      <section className="panel ledger-panel">
        <div className="panel-heading"><div><p className="overline">Canonical public record</p><h2>Recent Ledger</h2></div><span>Newest first</span></div>
        <div className="ledger-list">
          {state?.ledger.slice(0, 18).map((event) => <article key={event.id} className={`${event.terminal ? 'terminal' : ''} ${eventMatchesSelection(event, selectedId) ? 'highlight' : ''}`}><time>Tick {event.tick}</time><strong>{event.label}</strong><small>{event.sector_id ?? 'Sector not recorded'}</small></article>)}
          {state?.ledger.length === 0 && <p className="empty">Waiting for Ledger activity.</p>}
        </div>
      </section>
    </main>

    <details className="diagnostics"><summary>Viewer diagnostics</summary><div><span>Session</span><code>{sessionId}</code><span>API</span><code>{connection}</code><span>Runtime</span><code>{state?.runtime?.runtime_id ?? 'offline'}</code><span>Restarts</span><code>{state?.runtime?.restart_count ?? 0}</code><span>Frame</span><code>{state?.connection.latest_frame_id ?? 'waiting'}</code><span>Camera shot</span><code>{state?.camera?.shot_id ?? 'waiting'}</code><span>Last refresh</span><code>{lastReceipt ? new Date(lastReceipt).toLocaleTimeString() : 'never'}</code><span>Stale duration</span><code>{state?.connection.stale_duration_ms ?? 0} ms</code><span>Last control</span><code>{lastResult || 'none'}</code></div></details>
  </div>
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) { return <div><span>{label}</span><strong>{value}</strong><small>{detail}</small></div> }
