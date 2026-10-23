export type ConnectionState = 'live' | 'stale' | 'offline' | 'reconnecting'
export type DescenderRow = { descender_id: string; display_name: string; channel_id: string; status: string; terminal: boolean; health: number; stratum_number: number; sector_id: string | null; activity: string; in_active_encounter: boolean; currently_followed: boolean; currently_auto_focused: boolean; camera_available: boolean; interest_score: number }
export type LedgerItem = { id: string; tick: number; event_type: string; label: string; actor_ids: string[]; sector_id: string | null; terminal: boolean }
export type ViewerState = {
  protocol: string; viewer_version: string; generated_at_unix_ms: number; viewer: { viewer_id: string; local_only: boolean }
  connection: { state: ConnectionState; connected_presenter: boolean; stale: boolean; stale_after_ms: number; stale_duration_ms: number; latest_authoritative_tick: number; latest_buffered_tick: number; latest_ledger_tick: number; latest_frame_id: string | null }
  descent: null | { id: string; status: string; current_tick: number; current_stratum: number; stratum_count: number }
  stratum: null | { number: number; theme: string; status: string; sector_count: number; refuge_sector_ids: string[] }
  summary: { living_descender_count: number; fallen_descender_count: number; logical_channel_count: number }
  focus: null | { mode: 'automatic' | 'manual'; active_channel_id: string | null; active_descender_id: string | null; active_descender_name: string; presentation_tick: number; presentation_seconds: number; last_seen_frame_id: string | null }
  camera: null | { status: string; mode: string; shot_id: string | null; target_actor_ids: string[]; focus_descender_id: string | null; focus_confirmed: boolean; presentation_tick: number; presentation_seconds: number }
  runtime: null | { protocol: string; runtime_id: string | null; overall_status: string; uptime_seconds: number; presentation_lag_ticks: number; unreal_connected: boolean; checkpoint_age_seconds: number | null; restart_count: number; recovery_count: number }
  descenders: DescenderRow[]; ledger: LedgerItem[]
}
export type ControlResult = { status: 'accepted' | 'rejected'; duplicate?: boolean; reason?: string; active_descender_id?: string | null; focus_mode?: string }
