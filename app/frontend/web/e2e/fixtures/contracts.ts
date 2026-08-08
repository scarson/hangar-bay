/**
 * Wire-shape fixture builders for the contracts API.
 *
 * Shapes mirror real recorded responses from GET /contracts/ and
 * GET /contracts/{contract_id} (see also the stubbed shapes in
 * src/features/contracts/components/pages.test.tsx). Keep these as plain
 * wire JSON — the point of the E2E fixture lane is to feed the app exactly
 * what the backend would send.
 *
 * A list row and a detail response are different shapes: the row carries the
 * summaries the server derives (primary_label, the blueprint flag, the
 * composition breakdown) and NO item array; the detail response carries the
 * row plus every item, both offered and requested. The builders take item
 * inputs either way and derive the summaries the same way the service does
 * (contract_service._primary_label / _composition / _blueprint_summary), so a
 * fixture cannot claim a label its items do not support.
 *
 * Sort keys in canned datasets are strictly ordered — distinct prices,
 * names, and dates — so ordering assertions never rely on tiebreakers
 * (testing-pitfalls TEST-3).
 */

/**
 * An expiry offset from the current clock, as a wire-format UTC timestamp.
 *
 * date_expired MUST outlive the clock in every fixture. Two things read it: the
 * backend's contracts list excludes rows past date_expired, so a past value is a
 * response the real API cannot produce; and the "Time left" column calls
 * timeRemaining(), which reads the real Date.now() and repaints the cell
 * "Expired". A fixed literal satisfies both the day it is written and neither
 * one later, with nothing in the repo changing on the day it flips
 * (testing-pitfalls TEST-17).
 *
 * date_issued stays a literal by design: it is a sort key, and ordering
 * assertions need it stable and distinct. Callers keep expiry offsets distinct
 * for the same reason.
 */
export function expiryInDays(days: number): string {
  return new Date(Date.now() + days * 86_400_000).toISOString().replace(/\.\d{3}Z$/, 'Z')
}

/**
 * A freshness stamp `minutes` in the past. last_seen_at and coverage.as_of feed
 * relative renderings ("Last seen 4 minutes ago"), so they are clock-anchored
 * for the same reason date_expired is.
 */
export function stampMinutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString().replace(/\.\d{3}Z$/, 'Z')
}

/** Every contract type the backend's closed enum admits. */
export type WireContractType = 'item_exchange' | 'auction' | 'courier' | 'loan' | 'unknown'

const CONTRACT_TYPES: WireContractType[] = [
  'item_exchange',
  'auction',
  'courier',
  'loan',
  'unknown',
]

/**
 * Dogma category names as the server's taxonomy cache would have resolved
 * them. Composition entries whose category id is missing from this map serve a
 * NULL name, which is the real "not resolved yet" case.
 */
const CATEGORY_NAMES: Record<number, string> = {
  4: 'Material',
  6: 'Ship',
  7: 'Module',
  8: 'Charge',
  9: 'Blueprint',
}

export interface WireContractItem {
  record_id: number
  type_id: number
  quantity: number
  is_included: boolean
  is_blueprint_copy: boolean | null
  type_name: string | null
  category: 'ship' | null
  category_id: number | null
  group_id: number | null
  market_group_id: number | null
  runs: number | null
  material_efficiency: number | null
  time_efficiency: number | null
}

export interface WireBlueprintSummary {
  copy_count: number
  runs: number | null
  material_efficiency: number | null
  time_efficiency: number | null
}

export interface WireCompositionCategory {
  category_id: number | null
  name: string | null
  item_row_count: number
}

export interface WireComposition {
  categories: WireCompositionCategory[]
  total_item_rows: number
  total_volume: number | null
}

export interface WireContract {
  contract_id: number
  issuer_id: number
  issuer_corporation_id: number
  // Nullable to match ESI: the public-contracts schema does not mark
  // start_location_id required.
  start_location_id: number | null
  start_location_system_id: number | null
  end_location_id: number | null
  type: WireContractType
  title: string
  for_corporation: boolean
  date_issued: string
  date_expired: string
  price: number
  buyout: number | null
  collateral: number
  reward: number
  volume: number
  reward_per_volume: number | null
  days_to_complete: number | null
  start_location_name: string | null
  end_location_name: string | null
  issuer_name: string | null
  issuer_corporation_name: string | null
  last_seen_at: string | null
  is_ship_contract: boolean
  is_blueprint_copy_contract: boolean
  primary_label: string
  composition: WireComposition | null
  blueprint_summary: WireBlueprintSummary | null
}

/** A detail response: the row plus both sides of the trade. */
export interface WireContractDetail extends WireContract {
  items: WireContractItem[]
}

export interface WireCoverage {
  ingested_region_ids: number[]
  as_of: string | null
}

export interface WirePage {
  total: number
  page: number
  size: number
  items: WireContract[]
  segment_counts: Record<WireContractType, number>
  coverage: WireCoverage
}

export interface WireTaxonomyCategory {
  category_id: number
  name: string
}

export interface WireTaxonomyGroup {
  group_id: number
  category_id: number | null
  name: string
}

export interface WireTaxonomy {
  categories: WireTaxonomyCategory[]
  groups: WireTaxonomyGroup[]
  coverage: 'partial' | 'complete'
}

/**
 * The taxonomy the corpus behind these fixtures would report: the categories
 * and groups its items carry, flat so the client scopes groups locally.
 * `partial` is the default because it is the cold-cache state — a spec that
 * wants the item-level surface open has to say so, rather than inheriting it.
 */
export function taxonomy(overrides: Partial<WireTaxonomy> = {}): WireTaxonomy {
  return {
    categories: [
      { category_id: 6, name: 'Ship' },
      { category_id: 7, name: 'Module' },
      { category_id: 9, name: 'Blueprint' },
    ],
    groups: [
      { group_id: 27, category_id: 6, name: 'Battleship' },
      { group_id: 25, category_id: 6, name: 'Frigate' },
      { group_id: 105, category_id: 9, name: 'Ship Blueprint' },
      { group_id: 77, category_id: 7, name: 'Shield Booster' },
    ],
    coverage: 'partial',
    ...overrides,
  }
}

/** The Forge, the region the dev corpus ingests — matches what filter specs select. */
export const COVERED_REGION_ID = 10000002

let recordSeq = 5_000_000_000

export function makeItem(overrides: Partial<WireContractItem> = {}): WireContractItem {
  recordSeq += 1
  return {
    record_id: recordSeq,
    type_id: 24694,
    quantity: 1,
    is_included: true,
    is_blueprint_copy: null,
    type_name: 'Maelstrom',
    category: 'ship',
    category_id: 6,
    group_id: 27,
    market_group_id: 78,
    runs: null,
    material_efficiency: null,
    time_efficiency: null,
    ...overrides,
  }
}

export function makeShipItem(typeName: string, overrides: Partial<WireContractItem> = {}): WireContractItem {
  return makeItem({ type_name: typeName, category: 'ship', category_id: 6, ...overrides })
}

export function makeBpcItem(typeName: string, overrides: Partial<WireContractItem> = {}): WireContractItem {
  return makeItem({
    type_name: typeName,
    category: null,
    category_id: 9,
    group_id: 105,
    is_blueprint_copy: true,
    market_group_id: null,
    runs: 10,
    material_efficiency: 4,
    time_efficiency: 8,
    ...overrides,
  })
}

/** Builder input: contract fields plus the items the derived summaries come from. */
export type ContractInput = Partial<WireContract> & { items?: WireContractItem[] }

/** Reward per m³. A zero volume gives nothing to divide by, so it serves NULL. */
function deriveRewardPerVolume(contract: { reward: number; volume: number }): number | null {
  if (!contract.volume) return null
  return contract.reward / contract.volume
}

/**
 * The row's headline: an offered ship outranks whatever module comes first in a
 * fitted hull, then the first named offered item, then the seller's own title
 * (blank counts as absent), then a courier's destination, then the id.
 */
function derivePrimaryLabel(
  contract: Pick<WireContract, 'contract_id' | 'title' | 'type' | 'end_location_name'>,
  offered: WireContractItem[],
): string {
  const named = offered.filter((item) => item.type_name)
  const headline = named.find((item) => item.category === 'ship') ?? named[0]
  if (headline?.type_name) return headline.type_name
  if (contract.title.trim()) return contract.title.trim()
  if (contract.type === 'courier') {
    return contract.end_location_name ? `Courier to ${contract.end_location_name}` : 'Courier'
  }
  return `Contract ${contract.contract_id}`
}

/**
 * What a multi-item contract is made of. One offered row is not a breakdown, so
 * composition is NULL below two. Counts are item ROWS, not summed quantities.
 * Every entry sorts by share — the unknown-category bucket included — then by
 * name, with unnamed entries after named ones at equal counts (§17.2).
 */
function deriveComposition(volume: number, offered: WireContractItem[]): WireComposition | null {
  if (offered.length < 2) return null

  const rowCounts = new Map<number | null, number>()
  for (const item of offered) {
    rowCounts.set(item.category_id, (rowCounts.get(item.category_id) ?? 0) + 1)
  }
  const categories: WireCompositionCategory[] = [...rowCounts].map(([category_id, count]) => ({
    category_id,
    name: category_id === null ? null : (CATEGORY_NAMES[category_id] ?? null),
    item_row_count: count,
  }))
  categories.sort(
    (a, b) =>
      b.item_row_count - a.item_row_count ||
      Number(a.name === null) - Number(b.name === null) ||
      (a.name ?? '').localeCompare(b.name ?? ''),
  )

  return { categories, total_item_rows: offered.length, total_volume: volume }
}

/**
 * The blueprint terms. With more than one copy the terms belong to individual
 * copies, so the count goes out alone and the values stay NULL.
 */
function deriveBlueprintSummary(offered: WireContractItem[]): WireBlueprintSummary | null {
  const copies = offered.filter((item) => item.is_blueprint_copy === true)
  if (copies.length === 0) return null
  if (copies.length > 1) {
    return { copy_count: copies.length, runs: null, material_efficiency: null, time_efficiency: null }
  }
  const copy = copies[0]
  return {
    copy_count: 1,
    runs: copy.runs,
    material_efficiency: copy.material_efficiency,
    time_efficiency: copy.time_efficiency,
  }
}

/**
 * A list row. `items` is an INPUT, not a field: the row the API serves carries
 * none, so the builder derives the summaries from them and drops them. Pass any
 * derived field explicitly to override the derivation (e.g. a composition whose
 * categories the taxonomy cache has not named).
 */
export function makeContract(input: ContractInput = {}): WireContract {
  const { items, ...overrides } = input
  const contractId = overrides.contract_id ?? 232_000_001
  const rows = items ?? [makeShipItem('Maelstrom')]
  const base = {
    contract_id: contractId,
    issuer_id: 95_208_740,
    issuer_corporation_id: 98_414_237,
    start_location_id: 60_003_760,
    start_location_system_id: 30_000_142,
    end_location_id: 60_003_760,
    type: 'item_exchange' as WireContractType,
    title: '',
    for_corporation: false,
    date_issued: '2026-06-14T23:36:29Z',
    date_expired: expiryInDays(30),
    price: 250_000_000,
    buyout: null,
    collateral: 0,
    reward: 0,
    volume: 470_000,
    days_to_complete: null,
    start_location_name: 'Jita IV - Moon 4 - Caldari Navy Assembly Plant',
    end_location_name: null,
    issuer_name: 'Sesta Hound',
    issuer_corporation_name: 'Cantankerous Old Bastards',
    last_seen_at: stampMinutesAgo(11),
    is_ship_contract: true,
    ...overrides,
  }
  const offered = rows.filter((item) => item.is_included)
  return {
    ...base,
    reward_per_volume: overrides.reward_per_volume ?? deriveRewardPerVolume(base),
    is_blueprint_copy_contract:
      overrides.is_blueprint_copy_contract ??
      offered.some((item) => item.is_blueprint_copy === true),
    primary_label: overrides.primary_label ?? derivePrimaryLabel(base, offered),
    composition:
      overrides.composition !== undefined
        ? overrides.composition
        : deriveComposition(base.volume, offered),
    blueprint_summary:
      overrides.blueprint_summary !== undefined
        ? overrides.blueprint_summary
        : deriveBlueprintSummary(offered),
  }
}

/** The same contract as the detail endpoint serves it: the row plus its items. */
export function makeContractDetail(input: ContractInput = {}): WireContractDetail {
  const items = input.items ?? [makeShipItem('Maelstrom')]
  return { ...makeContract({ ...input, items }), items }
}

/**
 * Per-type counts for a set of rows, every enum member present. The real
 * endpoint computes these with the contract_type filter lifted and every other
 * filter applied; for a responder serving one unfiltered population, that is
 * exactly a tally of the rows it holds.
 */
export function countByType(contracts: WireContract[]): Record<WireContractType, number> {
  const counts = Object.fromEntries(CONTRACT_TYPES.map((type) => [type, 0])) as Record<
    WireContractType,
    number
  >
  for (const contract of contracts) counts[contract.type] += 1
  return counts
}

/** Coverage as a corpus holding one freshly-ingested region reports it. */
export function coverage(overrides: Partial<WireCoverage> = {}): WireCoverage {
  return { ingested_region_ids: [COVERED_REGION_ID], as_of: stampMinutesAgo(6), ...overrides }
}

export function pageOf(
  contracts: WireContract[],
  overrides: Partial<Omit<WirePage, 'items'>> = {},
): WirePage {
  return {
    total: contracts.length,
    page: 1,
    size: 50,
    items: contracts,
    segment_counts: countByType(contracts),
    coverage: coverage(),
    ...overrides,
  }
}

/**
 * Seven ship contracts with strictly-ordered, all-distinct sort keys
 * (price, hull name, issued/expired dates). Mirrors the shape of the first
 * real ship-bearing dev dataset (2026-07-12).
 */
export const SEVEN_SHIPS: WireContract[] = [
  ['Revelation', 2_400_000_000],
  ['Raven', 330_000_000],
  ['Maelstrom', 250_000_000],
  ['Purifier', 70_000_000],
  ['Hound', 65_000_000],
  ['Breacher', 4_000_000],
  ['Minmatar Shuttle', 50_000],
].map(([name, price], i) =>
  makeContract({
    contract_id: 232_100_001 + i,
    price: price as number,
    // Later entries issued earlier: default sort (issued desc) matches array order.
    date_issued: `2026-06-2${8 - i}T0${i}:00:00Z`,
    date_expired: expiryInDays(30 - i),
    items: [makeShipItem(name as string)],
  }),
)

/** Contracts whose items are blueprint copies (BPC badge fixtures). */
export const BPC_CONTRACTS: WireContract[] = [
  ['Draugur Blueprint', 20_000_000],
  ['Phoenix Blueprint', 15_000_000],
  ['Breacher Blueprint', 2_400_000],
].map(([name, price], i) =>
  makeContract({
    contract_id: 232_200_001 + i,
    price: price as number,
    is_ship_contract: false,
    date_issued: `2026-06-1${5 - i}T0${i}:30:00Z`,
    date_expired: expiryInDays(19 - i),
    items: [makeBpcItem(name as string)],
  }),
)

/**
 * Auctions with distinct starting bids and buyouts, one of them without a
 * buyout at all — the case the row has to say in words rather than leave blank.
 */
export const AUCTION_CONTRACTS: WireContract[] = [
  { name: 'Vargur', price: 1_900_000_000, buyout: 2_600_000_000 },
  { name: 'Sleipnir', price: 780_000_000, buyout: 1_100_000_000 },
  { name: 'Cynabal', price: 240_000_000, buyout: null },
].map((auction, i) =>
  makeContract({
    contract_id: 232_400_001 + i,
    type: 'auction',
    price: auction.price,
    buyout: auction.buyout,
    date_issued: `2026-06-2${4 - i}T1${i}:15:00Z`,
    date_expired: expiryInDays(12 - i),
    items: [makeShipItem(auction.name)],
  }),
)

/**
 * Couriers: no items, money in the reward and the collateral, distinct
 * reward/collateral/volume/reward-per-m³/deadline so every sortable courier
 * column has an unambiguous order (TEST-3).
 *
 * reward ÷ volume is 2000, 1500 and 1800 ISK/m³, which orders the rows
 * differently from every other key here — an ordering assertion on Reward/m³
 * therefore fails if the sort falls back to reward. Keep the third row's
 * volume off the reward's own ratio: 12,000 m³ would put it at 1500 ISK/m³,
 * tying the second row and making that assertion decide on a tiebreaker.
 *
 * The last one's destination is a player structure nothing could resolve — the
 * row must say so rather than go blank.
 */
export const COURIER_CONTRACTS: WireContract[] = [
  {
    destination: 'Amarr VIII (Oris) - Emperor Family Academy',
    reward: 120_000_000,
    collateral: 3_000_000_000,
    volume: 60_000,
    days: 7,
  },
  {
    destination: 'Dodixie IX - Moon 20 - Federation Navy Assembly Plant',
    reward: 45_000_000,
    collateral: 800_000_000,
    volume: 30_000,
    days: 5,
  },
  {
    destination: null,
    reward: 18_000_000,
    collateral: 250_000_000,
    volume: 10_000,
    days: 3,
  },
].map((courier, i) =>
  makeContract({
    contract_id: 232_600_001 + i,
    type: 'courier',
    title: '',
    price: 0,
    reward: courier.reward,
    collateral: courier.collateral,
    volume: courier.volume,
    days_to_complete: courier.days,
    end_location_id: 1_038_000_000_001 + i,
    end_location_name: courier.destination,
    is_ship_contract: false,
    date_issued: `2026-06-1${8 - i}T0${i}:45:00Z`,
    date_expired: expiryInDays(16 - i),
    items: [],
  }),
)

/**
 * A dataset big enough to cross page boundaries (testing-pitfalls TEST-4).
 * Every contract has a unique hull label "Hull #NNN" and a unique price so
 * pages can be compared for duplicates/gaps by label alone.
 */
export function bigDataset(count: number): WireContract[] {
  return Array.from({ length: count }, (_, i) =>
    makeContract({
      contract_id: 232_300_001 + i,
      price: 1_000_000 + i * 10_000,
      date_issued: `2026-06-0${(i % 9) + 1}T${String(i % 24).padStart(2, '0')}:${String(i % 60).padStart(2, '0')}:00Z`,
      items: [makeShipItem(`Hull #${String(i + 1).padStart(3, '0')}`)],
    }),
  )
}

/** Slice a dataset the way the backend pages it. */
export function paginate(all: WireContract[], page: number, size: number): WirePage {
  return {
    total: all.length,
    page,
    size,
    items: all.slice((page - 1) * size, page * size),
    // Counted over the whole matching population, not the page: the segment
    // figures describe what selecting a segment would show.
    segment_counts: countByType(all),
    coverage: coverage(),
  }
}
