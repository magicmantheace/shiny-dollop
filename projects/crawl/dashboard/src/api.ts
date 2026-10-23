import type { HistoricalEvent, Kingdom, MapData, NPC, RefugeeCamp, War, WorldSummary } from './types'

const json = async <T>(response: Response): Promise<T> => {
  if (!response.ok) {
    const body = await response.text()
    throw new Error(body || `${response.status} ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export const getWorld = () => fetch('/api/world').then(json<WorldSummary>)
export const getMap = () => fetch('/api/map').then(json<MapData>)
export const getEvents = (limit = 100) => fetch(`/api/events?limit=${limit}`).then(json<HistoricalEvent[]>)
export const getMigrations = (limit = 60) => fetch(`/api/migrations?limit=${limit}`).then(json<HistoricalEvent[]>)
export const getRefugeeCamps = () => fetch('/api/refugee-camps').then(json<RefugeeCamp[]>)
export const getWars = () => fetch('/api/wars').then(json<War[]>)
export const getKingdom = (id: string) => fetch(`/api/kingdoms/${id}`).then(json<Kingdom>)
export const getNpc = (id: string) => fetch(`/api/npcs/${id}`).then(json<NPC>)

export const adminRequest = async <T>(path: string, key: string, body?: unknown, method = 'POST'): Promise<T> => {
  return fetch(path, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Admin-Key': key,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  }).then(json<T>)
}

export const runCommand = (key: string, type: string, target_id?: string, parameters: Record<string, unknown> = {}) =>
  adminRequest('/api/commands', key, { type, target_id, parameters, issuer: 'admin-dashboard' })

export const runNaturalCommand = (key: string, text: string) =>
  adminRequest('/api/commands/natural', key, { text, issuer: 'admin-dashboard', allow_ai_fallback: true })
