export const POLL_INTERVAL_MS = 750
export const CLIENT_STALE_AFTER_MS = 3500
export const healthLabel = (health) => `${Math.round(Math.max(0, Math.min(1, health)) * 100)}%`
export const statusLabel = (row) => row.terminal || row.status === 'fallen' || row.status === 'eliminated' ? 'Fallen' : row.in_active_encounter ? 'Combat' : row.health < 0.5 ? 'Injured' : 'Alive'
export const connectionLabel = (state, lastReceiptMs, nowMs = Date.now()) => !state ? 'Connecting' : nowMs - lastReceiptMs > CLIENT_STALE_AFTER_MS ? 'Stale' : state.connection.state === 'live' ? 'Live' : state.connection.state === 'stale' ? 'Stale' : 'Offline'
export const requestBody = (viewerId, requestId, presentationTick, descenderId) => ({ viewer_id: viewerId, request_id: requestId, requested_at_presentation_tick: presentationTick, ...(descenderId ? { descender_id: descenderId } : {}) })
export const isConfirmedFocus = (state, descenderId) => Boolean(state?.focus?.mode === 'manual' && state.focus.active_descender_id === descenderId)
export const canFollow = (state, row, pendingId) => Boolean(state && row && row.camera_available && !pendingId && !isConfirmedFocus(state, row.descender_id))
export const eventMatchesSelection = (event, selectedId) => Boolean(selectedId && event.actor_ids.includes(selectedId))
export const panelState = (state, error, lastReceiptMs, nowMs = Date.now()) => !state && !error ? 'loading' : !state?.descent ? 'no-descent' : connectionLabel(state, lastReceiptMs, nowMs) === 'Stale' ? 'stale' : error ? 'reconnecting' : 'ready'
