import type { Contract } from '../../lib/api/client'
import type { components } from '../../lib/api/schema'
import { REGIONS } from './regions'

type CompositionSummary = components['schemas']['CompositionSummary']
type BlueprintSummary = components['schemas']['BlueprintSummary']

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
// Coverage reads as a sentence ("originating in The Forge only"), so the id
// list has to come out as prose rather than as a comma join.
const NAME_LIST = new Intl.ListFormat('en-US', { style: 'long', type: 'conjunction' })
// Built once: REGIONS is a flat generated array, and both coverage sentences
// look up several ids on every render.
// Widened to number: REGIONS is `as const`, so an inferred Map would key on the
// literal union of today's ids and refuse to be asked about an id the corpus
// reported and this build has no name for — exactly the lookup that must work.
const REGION_NAMES = new Map<number, string>(REGIONS.map((region) => [region.id, region.name]))

export function formatIsk(value: number | null | undefined): string {
  return value == null ? '—' : ISK.format(value)
}

// Cargo is measured across nine orders of magnitude — a blueprint copy is
// 0.01 m³ and a freighter load is hundreds of thousands — so one fixed
// precision cannot serve both. Two decimals below 100, none above.
const SMALL_VOLUME = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })
/** Below this the decimals carry the information; above it they are noise. */
const VOLUME_PRECISION_THRESHOLD = 100
/** The smallest volume two decimals can state. */
const SMALLEST_SHOWN_VOLUME = 0.005

/**
 * A cargo volume, unit-less so each caller says m³ where it fits.
 *
 * Not `formatIsk`: that formatter drops every fraction, which is right for ISK
 * and wrong here. Measured on the live dev corpus (2026-08-08), six of the ten
 * composition-bearing contracts held less than 1 m³ — blueprint lots, which are
 * exactly what the composition line most often describes — and every one of
 * them rendered as "0 m³": a lot claiming to have no volume at all. A volume
 * too small even for two decimals says so rather than rounding to that claim.
 */
export function formatVolume(value: number | null | undefined): string {
  if (value == null) return '—'
  if (value !== 0 && Math.abs(value) < SMALLEST_SHOWN_VOLUME) return '<0.01'
  const format = Math.abs(value) < VOLUME_PRECISION_THRESHOLD ? SMALL_VOLUME : ISK
  return format.format(value)
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
 * The regions in an id list, named for a sentence. Coverage crosses the wire as
 * ids so the client never embeds a region literal (Criterion 7.3), which leaves
 * the naming here — against the same static map the filter rail lists.
 *
 * An id this build has no name for keeps its id rather than dropping out: CCP
 * adds regions and `regions.ts` is regenerated by hand, and a sentence about
 * three uncovered regions that silently names two is the kind of confident
 * falsehood the coverage states exist to prevent.
 */
export function regionNames(ids: readonly number[]): string {
  return NAME_LIST.format(ids.map((id) => REGION_NAMES.get(id) ?? `Region ${id}`))
}

/** How many category names a cell has room for before the rest becomes "other". */
const NAMED_CATEGORIES = 2

/**
 * What a mixed lot is made of, in one line (Criterion 6.1). The server sends
 * the categories sorted by share and does NOT truncate — how many fit is the
 * client's question — so this names the two largest and buckets the remainder.
 *
 * Counts are item ROWS. A contract of 100 identical drones in one row reads as
 * "1 Drone": summing quantities would describe an ammunition stack as a fleet.
 *
 * Two shapes cannot be named and both fall into the bucket: rows whose category
 * could not be determined at all (`category_id` null), and a category the name
 * cache has not resolved yet (`name` null). "Other" is exactly what they are;
 * anything else would be an invented label.
 */
export function formatComposition(composition: CompositionSummary): string {
  const named = composition.categories.filter((category) => category.name)
  const parts = named
    .slice(0, NAMED_CATEGORIES)
    .map((category) => `${category.item_row_count} ${category.name}${category.item_row_count === 1 ? '' : 's'}`)
  const other = composition.categories
    .filter((category) => !named.slice(0, NAMED_CATEGORIES).includes(category))
    .reduce((rows, category) => rows + category.item_row_count, 0)
  if (other > 0) parts.push(`${other} other`)
  // A corpus that carries no volume for the contract gets no figure: "0 m³"
  // would be a measurement rather than the absence of one.
  if (composition.total_volume != null) parts.push(`${formatVolume(composition.total_volume)} m³`)
  return parts.join(' · ')
}

/**
 * The terms of ONE offered blueprint copy. Each figure is named because the
 * three are not interchangeable and a bare "10 · 4 · 8" would need a legend.
 *
 * An absent figure is omitted rather than shown as zero: ESI omits `runs`
 * entirely for an original instead of sending -1 (ESI-3), and "ME 0" is a real
 * blueprint that is meaningfully different from one whose ME is unknown.
 */
export function formatBlueprintTerms(summary: BlueprintSummary): string {
  const parts: string[] = []
  if (summary.runs != null) parts.push(`${summary.runs} run${summary.runs === 1 ? '' : 's'}`)
  if (summary.material_efficiency != null) parts.push(`ME ${summary.material_efficiency}`)
  if (summary.time_efficiency != null) parts.push(`TE ${summary.time_efficiency}`)
  return parts.join(' · ')
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
