export type WorldDate = { year: number; month: number; day: number; hour: number }

export type ContinentSummary = {
  id: string
  name: string
  seed: string
  bounds: Record<string, number>
  region_ids: string[]
  climate_bands: string[]
  ocean_fraction: number
  generation_version: string
}

export type WorldSummary = {
  id: string
  name: string
  seed: string
  date: WorldDate
  date_label: string
  paused: boolean
  speed_multiplier: number
  metrics: Record<string, number>
  region: { id: string; name: string; climate: string; magic_intensity: number }
  regions: number
  continent?: ContinentSummary | null
  ai_enabled: boolean
}

export type MapSettlement = {
  id: string
  name: string
  type: string
  kingdom_id: string
  region_id: string
  position: { x: number; y: number; elevation: number }
  population: number
  biome: string
  food_security: number
  stability: number
  magic_intensity: number
}

export type MapKingdom = {
  id: string
  name: string
  capital_settlement_id: string
  dominant_ancestry: string
  stability: number
  border_policy: 'open' | 'controlled' | 'closed'
  refugee_policy: 'welcome' | 'limited' | 'reject'
  settlement_ids: string[]
}

export type MapRegion = {
  id: string
  name: string
  climate: string
  magic_intensity: number
  bounds: Record<string, number>
  settlement_ids: string[]
  kingdom_ids: string[]
  population: number
  settlement_count: number
  kingdom_count: number
}

export type RefugeeCamp = {
  id: string
  host_settlement_id: string
  host_kingdom_id: string
  origin_kingdom_id: string
  people: number
  ancestry_population: Record<string, number>
  created_at: WorldDate
  last_arrival_at: WorldDate
  status: 'active' | 'resettling' | 'closed'
  food_security: number
  health: number
  months_active: number
}

export type TradeRoute = {
  id: string
  origin_settlement_id: string
  destination_settlement_id: string
  distance: number
  safety: number
  active: boolean
  volume_last_day: number
}

export type Army = {
  id: string
  kingdom_id: string
  name: string
  troop_count: number
  location_settlement_id: string
  destination_settlement_id?: string | null
  morale: number
  supply_days: number
  readiness: number
  active: boolean
  supply_efficiency: number
  supply_source_settlement_id?: string | null
}

export type MapData = {
  bounds: Record<string, number>
  continent?: ContinentSummary | null
  region: Record<string, unknown>
  regions: MapRegion[]
  kingdoms: MapKingdom[]
  settlements: MapSettlement[]
  trade_routes: TradeRoute[]
  armies: Army[]
  landmarks: Array<{ id: string; name: string; kind: string; position: { x: number; y: number }; description: string; magic_intensity: number }>
  refugee_camps: RefugeeCamp[]
}

export type HistoricalEvent = {
  id: string
  type: string
  occurred_at: WorldDate
  summary: string
  subject_ids: string[]
  location_id?: string | null
  data: Record<string, unknown>
  source: string
  importance: number
}

export type Kingdom = MapKingdom & {
  government: string
  culture_id: string
  religion_id?: string | null
  ruler_npc_id?: string | null
  treasury: number
  tax_rate: number
  legitimacy: number
  military_readiness: number
  food_reserve: number
  goals: Record<string, number>
  population: number
  refugee_camps: number
  camp_population: number
  overlord_kingdom_id?: string | null
  ruler?: NPC | null
  last_decision?: { action: string; score: number; reasons: Record<string, number>; target_id?: string | null } | null
}

export type NPC = {
  id: string
  name: string
  ancestry: string
  settlement_id: string
  kingdom_id: string
  age: number
  sex: string
  alive: boolean
  health: number
  wealth: number
  occupation: string
  social_status: string
  title?: string | null
  goals: string[]
  traits: Record<string, number>
  memories: Array<{ event_id: string; summary: string; emotion: string; importance: number }>
}

export type War = {
  id: string
  attacker_kingdom_id: string
  defender_kingdom_id: string
  goal: string
  state: string
  attacker_score: number
  defender_score: number
  casualties: Record<string, number>
  occupied_settlement_ids: string[]
  front_settlement_ids: string[]
  siege_progress: Record<string, number>
  occupation_by_settlement: Record<string, string>
  attacker_exhaustion: number
  defender_exhaustion: number
  months_active: number
  peace_terms: Record<string, unknown>
}
