import type { Contract } from '../../lib/api/client'

// Fixed locale: M1 is explicitly English-only (spec Non-goals), and tests
// assert formatted values (pitfall TEST-3).
const ISK = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
// Pinned to UTC: EVE is a UTC-native market, and the detail view's DATETIME
// formatter is likewise UTC — without this the list's "Issued" column renders
// date_issued in the viewer's local zone (a UTC-midnight timestamp reads as the
// previous day for anyone west of UTC), an off-by-a-day the audience must trust.
const DATE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

export function formatIsk(value: number | null | undefined): string {
  return value == null ? '—' : ISK.format(value)
}

export function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '—' : DATE.format(date)
}

/**
 * Coarse countdown for the list view ("3d 4h", "5h 12m", "42m", "Expired").
 * `now` is injectable so tests stay deterministic (TEST-3).
 */
export function timeRemaining(dateExpired: string, now: number = Date.now()): string {
  const ms = new Date(dateExpired).getTime() - now
  if (Number.isNaN(ms)) return '—'
  if (ms <= 0) return 'Expired'
  const totalMinutes = Math.floor(ms / 60_000)
  const days = Math.floor(totalMinutes / 1_440)
  const hours = Math.floor((totalMinutes % 1_440) / 60)
  const minutes = totalMinutes % 60
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${Math.max(1, minutes)}m`
}

// ESI's public-contracts `type` is a closed enum, so every member gets a name.
// Anything unrecognised keeps the historical "Exchange" reading rather than
// surfacing a raw wire value.
const TYPE_LABELS: Record<string, string> = {
  item_exchange: 'Exchange',
  auction: 'Auction',
  courier: 'Courier',
  loan: 'Loan',
  unknown: 'Unknown',
}

/**
 * Badge text for a contract's type. A courier is a hauling job rather than a
 * sale — its price is 0 and its money lives in the reward and the collateral —
 * so labelling it "Exchange" describes the one thing it is not.
 */
export function contractTypeLabel(type: string): string {
  // A stored type outside the map is served under the unknown segment, so the
  // label must say so rather than masquerade as an exchange.
  return TYPE_LABELS[type] ?? 'Unknown'
}

/**
 * Human label for where a contract starts. ESI does not mark start_location_id
 * required, so the id fallback has to survive its absence rather than
 * interpolating a null into the page.
 */
export function locationLabel(contract: Contract): string {
  if (contract.start_location_name) return contract.start_location_name
  return contract.start_location_id != null
    ? `Location ${contract.start_location_id}`
    : 'Unknown location'
}
