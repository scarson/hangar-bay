import type { Contract } from '../../lib/api/client'

// Fixed locale: M1 is explicitly English-only (spec Non-goals), and tests
// assert formatted values (pitfall TEST-3).
const ISK = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
// Pinned to UTC: EVE is a UTC-native market, and the detail view's DATETIME
// formatter is likewise UTC — without this the list's "Issued" column renders
// date_issued in the viewer's local zone (a UTC-midnight timestamp reads as the
// previous day for anyone west of UTC), an off-by-a-day the audience must trust.
const DATE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })
// A hauling rate is a comparison figure, and the comparison is often decided
// inside the ISK: two jobs at 88.89 and 88.12 ISK/m³ are a real difference that
// the whole-ISK formatter above would render as one number twice.
const RATE = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

export function formatIsk(value: number | null | undefined): string {
  return value == null ? '—' : ISK.format(value)
}

/** Reward per m³. NULL arrives whenever there was no volume to divide by (§9). */
export function formatRewardPerVolume(value: number | null | undefined): string {
  return value == null ? '—' : RATE.format(value)
}

/** A courier's delivery window, in whole days. Absent is not zero (ESI-3). */
export function formatDeadline(days: number | null | undefined): string {
  return days == null ? '—' : `${days}d`
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
 * What an endpoint of a courier route is called. Player structures need an
 * ACL-scoped token to resolve, so some of them have no name at all — and the
 * cell has to say that rather than go blank, print the id, or invent a station
 * that reads like a real one.
 */
function endpointLabel(name: string | null | undefined): string {
  return name ?? 'Unknown structure'
}

/**
 * A courier's route, origin to destination. Deliberately NOT locationLabel's
 * id fallback: an id in a route reads as somewhere the reader could look up,
 * and the honest reading of an unresolvable endpoint is that it is unknown.
 */
export function routeLabel(contract: Contract): string {
  return `${endpointLabel(contract.start_location_name)} → ${endpointLabel(contract.end_location_name)}`
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
