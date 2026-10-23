import type { DescenderRow, LedgerItem, ViewerState } from './types'
export const POLL_INTERVAL_MS: number
export const CLIENT_STALE_AFTER_MS: number
export const healthLabel: (health: number) => string
export const statusLabel: (row: DescenderRow) => string
export const connectionLabel: (state: ViewerState | null, lastReceiptMs: number, nowMs?: number) => string
export const requestBody: (viewerId: string, requestId: string, presentationTick: number, descenderId?: string) => Record<string, unknown>
export const isConfirmedFocus: (state: ViewerState | null, descenderId: string) => boolean
export const canFollow: (state: ViewerState | null, row: DescenderRow, pendingId: string | null) => boolean
export const eventMatchesSelection: (event: LedgerItem, selectedId: string | null) => boolean
export const panelState: (state: ViewerState | null, error: string, lastReceiptMs: number, nowMs?: number) => string
