/**
 * Wire-shape fixture builders for the contracts API.
 *
 * Shapes mirror real recorded responses from GET /contracts/ and
 * GET /contracts/{contract_id} (see also the stubbed shapes in
 * src/features/contracts/components/pages.test.tsx). Keep these as plain
 * wire JSON — the point of the E2E fixture lane is to feed the app exactly
 * what the backend would send.
 *
 * Sort keys in canned datasets are strictly ordered — distinct prices,
 * names, and dates — so ordering assertions never rely on tiebreakers
 * (testing-pitfalls TEST-3).
 */

export interface WireContractItem {
  record_id: number
  type_id: number
  quantity: number
  is_included: boolean
  is_singleton: boolean
  is_blueprint_copy: boolean | null
  raw_quantity: number | null
  type_name: string | null
  category: 'ship' | null
  market_group_id: number | null
}

export interface WireContract {
  contract_id: number
  issuer_id: number
  issuer_corporation_id: number
  start_location_id: number
  end_location_id: number
  type: 'item_exchange' | 'auction'
  status: string
  title: string
  for_corporation: boolean
  date_issued: string
  date_expired: string
  date_completed: string | null
  price: number
  reward: number
  volume: number
  start_location_name: string | null
  issuer_name: string | null
  issuer_corporation_name: string | null
  is_ship_contract: boolean
  items: WireContractItem[]
}

export interface WirePage {
  total: number
  page: number
  size: number
  items: WireContract[]
}

let recordSeq = 5_000_000_000

export function makeItem(overrides: Partial<WireContractItem> = {}): WireContractItem {
  recordSeq += 1
  return {
    record_id: recordSeq,
    type_id: 24694,
    quantity: 1,
    is_included: true,
    is_singleton: false,
    is_blueprint_copy: null,
    raw_quantity: null,
    type_name: 'Maelstrom',
    category: 'ship',
    market_group_id: 78,
    ...overrides,
  }
}

export function makeShipItem(typeName: string, overrides: Partial<WireContractItem> = {}): WireContractItem {
  return makeItem({ type_name: typeName, category: 'ship', ...overrides })
}

export function makeBpcItem(typeName: string, overrides: Partial<WireContractItem> = {}): WireContractItem {
  return makeItem({
    type_name: typeName,
    category: null,
    is_blueprint_copy: true,
    market_group_id: null,
    ...overrides,
  })
}

export function makeContract(overrides: Partial<WireContract> = {}): WireContract {
  const contractId = overrides.contract_id ?? 232_000_001
  return {
    contract_id: contractId,
    issuer_id: 95_208_740,
    issuer_corporation_id: 98_414_237,
    start_location_id: 60_003_760,
    end_location_id: 60_003_760,
    type: 'item_exchange',
    status: 'unknown',
    title: '',
    for_corporation: false,
    date_issued: '2026-06-14T23:36:29Z',
    date_expired: '2026-07-20T23:36:29Z',
    date_completed: null,
    price: 250_000_000,
    reward: 0,
    volume: 470_000,
    start_location_name: 'Jita IV - Moon 4 - Caldari Navy Assembly Plant',
    issuer_name: 'Sesta Hound',
    issuer_corporation_name: 'Cantankerous Old Bastards',
    is_ship_contract: true,
    items: overrides.items ?? [makeShipItem('Maelstrom')],
    ...overrides,
  }
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
    date_expired: `2026-07-2${8 - i}T0${i}:00:00Z`,
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
    date_expired: `2026-07-1${9 - i}T0${i}:30:00Z`,
    items: [makeBpcItem(name as string)],
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
  }
}
