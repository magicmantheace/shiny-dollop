import type { ControlResult, ViewerState } from './types'
import { requestBody } from './viewer-model.mjs'
const json = async <T>(response: Response): Promise<T> => { const body = await response.json().catch(() => null); if (!response.ok) { const detail = body?.detail ?? body ?? `${response.status} ${response.statusText}`; throw new Error(typeof detail === 'string' ? detail : detail.reason ?? JSON.stringify(detail)) }; return body as T }
export const getViewerState = (viewerId: string) => fetch(`/api/feed/viewer/state?viewer_id=${encodeURIComponent(viewerId)}`, { cache: 'no-store' }).then(json<ViewerState>)
export const followDescender = (viewerId: string, requestId: string, tick: number, descenderId: string) => fetch('/api/feed/live/follow', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestBody(viewerId, requestId, tick, descenderId)) }).then(json<ControlResult>)
export const releaseToAuto = (viewerId: string, requestId: string, tick: number) => fetch('/api/feed/live/release', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(requestBody(viewerId, requestId, tick)) }).then(json<ControlResult>)
