// ABOUTME: Wire-shape fixtures for the M3 account APIs — saved searches, watchlist items, notifications.
// ABOUTME: Overrides let specs vary a field without inventing new wire shapes (mirrors fixtures/auth.ts + contracts.ts).

export interface WireSavedSearch {
  id: number
  name: string
  search_parameters: Record<string, unknown>
  created_at: string
  updated_at: string
}

export function makeSavedSearch(overrides: Partial<WireSavedSearch> = {}): WireSavedSearch {
  return {
    id: 1,
    name: 'Cheap frigates',
    search_parameters: { ships_only: true, min_price: 0, max_price: 5_000_000, size: 50, sort_by: 'price', sort_direction: 'asc' },
    created_at: '2026-07-17T00:00:00Z',
    updated_at: '2026-07-17T00:00:00Z',
    ...overrides,
  }
}

export interface WireWatchlistItem {
  id: number
  type_id: number
  type_name: string
  max_price: number | null
  notes: string | null
  created_at: string
  updated_at: string
}

export function makeWatchlistItem(overrides: Partial<WireWatchlistItem> = {}): WireWatchlistItem {
  return {
    id: 1,
    type_id: 587,
    type_name: 'Rifter',
    max_price: null,
    notes: null,
    created_at: '2026-07-17T00:00:00Z',
    updated_at: '2026-07-17T00:00:00Z',
    ...overrides,
  }
}

export interface WireNotification {
  id: number
  type: string
  message: string
  contract_id: number | null
  watch_type_id: number | null
  price: number | null
  is_read: boolean
  created_at: string
}

export function makeNotification(overrides: Partial<WireNotification> = {}): WireNotification {
  return {
    id: 1,
    type: 'watchlist_match',
    message: 'Rifter available in an auction priced 900,000 ISK in Jita IV - Moon 4',
    contract_id: 232_100_001,
    watch_type_id: 587,
    price: 900_000,
    is_read: false,
    created_at: '2026-07-17T11:00:00Z',
    ...overrides,
  }
}
