import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { anonymousMe, jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'
import { daysFromNow, minutesFromNow } from '../../../test/dates'

/**
 * A list row: the summaries the server derives (primary_label, the blueprint
 * flag, composition) and no item array — the shape GET /contracts/ returns.
 */
const ROW = {
  contract_id: 101,
  issuer_id: 1,
  issuer_corporation_id: 101,
  start_location_id: 60003760,
  collateral: 0,
  type: 'item_exchange',
  title: 'Tristan for Sale',
  for_corporation: false,
  date_issued: '2026-07-01T00:00:00Z',
  date_expired: daysFromNow(7),
  price: 1000000,
  start_location_name: 'Jita IV - Moon 4 - Caldari Navy Assembly Plant',
  is_ship_contract: true,
  is_blueprint_copy_contract: false,
  primary_label: 'Tristan',
  composition: null,
}

/** The same contract as GET /contracts/{id} returns it: the row plus its items. */
const CONTRACT = {
  ...ROW,
  items: [
    {
      record_id: 1011,
      type_id: 587,
      quantity: 1,
      is_included: true,
      type_name: 'Tristan',
    },
  ],
}

/**
 * The list envelope. Every response carries per-type segment counts (all five
 * keys, zero-filled) and the coverage block, so a fixture is never a response
 * the real API could not produce. Counts are derived from the rows served here
 * — the request in these tests never filters by type, which is the one case
 * where the page's own rows ARE the segment population.
 */
function listPage(rows: { type: string }[], overrides: Record<string, unknown> = {}) {
  const segment_counts: Record<string, number> = {
    item_exchange: 0,
    auction: 0,
    courier: 0,
    loan: 0,
    unknown: 0,
  }
  for (const row of rows) segment_counts[row.type] += 1
  return {
    total: rows.length,
    page: 1,
    size: 50,
    items: rows,
    segment_counts,
    coverage: { ingested_region_ids: [10000002], as_of: minutesFromNow(-5) },
    ...overrides,
  }
}

function stubFetch(handler: (url: string) => Response) {
  const calls: string[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    calls.push(url)
    return handler(url)
  })
  return calls
}

afterEach(() => vi.unstubAllGlobals())

describe('ContractsPage', () => {
  it('renders fetched contracts in the table', async () => {
    stubFetch(anonymousMe(() => jsonResponse(listPage([ROW]))))

    renderApp('/contracts')

    expect(await screen.findByText('Tristan')).toBeInTheDocument()
    expect(screen.getByText(/1,000,000/)).toBeInTheDocument()
    // Descriptive per-view title (WCAG 2.4.2), not the scaffold's "web".
    expect(document.title).toBe('Ship Contracts — Hangar Bay')
    // Column headers are sticky so the labels/sort toggles survive a 50-row
    // scroll (JSDOM can't lay out `position: sticky`; guard the intent instead).
    expect(screen.getAllByRole('columnheader')[0].className).toContain('sticky')
    // The Time left cell renders a live countdown, not "Expired". This is the only
    // assertion that reads timeRemaining's output at a production call site, and it
    // is what keeps CONTRACT.date_expired anchored to the clock: with a fixed literal
    // the cell silently flips to "Expired" once the date passes, and nothing else
    // here would notice (testing-pitfalls TEST-17).
    expect(screen.getByText(/^\d+d \d+h$/)).toBeInTheDocument()
    expect(screen.queryByText('Expired')).not.toBeInTheDocument()
  })

  it('renders each row its own countdown, across the day, hour, and minute buckets', async () => {
    // Every offset carries a half-minute of padding so the truncating formatter
    // lands on the same bucket however long the render takes — a bare
    // minutesFromNow(20) is 20 minutes exactly and floors to "19m" the instant
    // any time elapses. The offsets are clock-relative (TEST-17) and the
    // expected strings are literal, so nothing here re-implements the formatter.
    const rows = [
      { name: 'Rifter', minutes: 3 * 1440 + 5 * 60 + 30, expected: '3d 5h' },
      { name: 'Myrmidon', minutes: 6 * 60 + 12.5, expected: '6h 12m' },
      { name: 'Dominix', minutes: 20.5, expected: '20m' },
    ]
    const items = rows.map((row, index) => ({
      ...ROW,
      contract_id: 200 + index,
      date_expired: minutesFromNow(row.minutes),
      primary_label: row.name,
    }))
    stubFetch(anonymousMe(() => jsonResponse(listPage(items))))

    renderApp('/contracts')

    await screen.findByText('Rifter')
    for (const row of rows) {
      const cells = within(screen.getByRole('row', { name: new RegExp(row.name) }))
      expect(cells.getByText(row.expected)).toBeInTheDocument()
    }
  })

  it('announces the result count in a polite status region (WCAG 4.1.3)', async () => {
    stubFetch(anonymousMe(() => jsonResponse(listPage([ROW]))))

    renderApp('/contracts')

    // Wait for load so the skeleton's own role="status" has unmounted, leaving
    // only the count region — filter/sort/page outcomes reach assistive tech
    // without moving focus off a rail control.
    await screen.findByText('Tristan')
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('1 contract matches your filters')
    expect(status).toHaveAttribute('aria-live', 'polite')
  })

  it('renders the row link from the label the server derived, id fallback included', async () => {
    // Real ESI data: title is "" (not null) and non-ship contracts often have
    // no resolvable type_name, so the server's last resort is "Contract <id>".
    // The row renders that verbatim rather than deriving its own — an empty
    // link would be unclickable-looking (found live during M1 acceptance).
    const untitled = {
      ...ROW,
      contract_id: 555,
      title: '',
      primary_label: 'Contract 555',
    }
    stubFetch(anonymousMe(() => jsonResponse(listPage([untitled]))))

    renderApp('/contracts')

    expect(await screen.findByRole('link', { name: 'Contract 555' })).toBeInTheDocument()
  })

  it('counts the rest of a bundle from the composition, in item rows not quantities', async () => {
    // The row carries no items, so the "+N more" suffix reads the server's
    // composition. total_item_rows counts item ROWS: a bundle of three rows is
    // "+2 more" however many units each row stacks.
    const bundle = {
      ...ROW,
      contract_id: 606,
      primary_label: 'Myrmidon',
      composition: {
        categories: [
          { category_id: 7, name: 'Module', item_row_count: 2 },
          { category_id: 6, name: 'Ship', item_row_count: 1 },
        ],
        total_item_rows: 3,
        total_volume: 120_000,
      },
    }
    stubFetch(anonymousMe(() => jsonResponse(listPage([bundle, ROW]))))

    renderApp('/contracts')

    const bundled = within(await screen.findByRole('row', { name: /Myrmidon/ }))
    expect(bundled.getByText('+2 more')).toBeInTheDocument()
    // A single-item contract gets no composition at all, so nothing to add.
    const single = within(screen.getByRole('row', { name: /Tristan/ }))
    expect(single.queryByText(/more/)).not.toBeInTheDocument()
  })

  it('shows the empty state for zero results', async () => {
    stubFetch(anonymousMe(() => jsonResponse(listPage([]))))

    renderApp('/contracts')

    expect(await screen.findByText(/no contracts match/i)).toBeInTheDocument()
  })

  it('shows the error state with a retry control on failure', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ detail: 'boom' }, 500)))

    renderApp('/contracts')

    expect(await screen.findByRole('alert')).toHaveTextContent(/failed to load/i)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('reads filters from the URL and sends them to the API', async () => {
    const calls = stubFetch(
      anonymousMe(() => jsonResponse(listPage([]))),
    )

    renderApp('/contracts?region_ids=10000002&is_bpc=true&sort_by=price&sort_direction=asc')

    await screen.findByText(/no contracts match/i)
    // Order-independent: whether /me or the contracts query fires first is
    // scheduling, not contract (the header now issues its own /me request).
    const listCall = calls.find((u) => u.includes('/api/v1/contracts/'))!
    expect(listCall).toContain('region_ids=10000002')
    expect(listCall).toContain('is_bpc=true')
    expect(listCall).toContain('sort_by=price')
  })

  it('carries a repeated region_ids URL through to repeated API params (shareable-URL contract)', async () => {
    // Drives the full multi-value inbound seam end-to-end: TanStack Router's
    // qss decode of ?region_ids=…&region_ids=… -> parseContractSearch array
    // coercion -> toApiQuery -> openapi-fetch's repeated-array serializer.
    // Guards the two-repeat case that single-value URL tests can't (TEST-5).
    const calls = stubFetch(
      anonymousMe(() => jsonResponse(listPage([]))),
    )

    renderApp('/contracts?region_ids=10000002&region_ids=10000020')

    await screen.findByText(/no contracts match/i)
    // Order-independent: see the rationale above.
    const listCall = calls.find((u) => u.includes('/api/v1/contracts/'))!
    expect(listCall).toContain('region_ids=10000002&region_ids=10000020')
  })

  it('redirects an out-of-range page to the last page instead of a false empty state', async () => {
    // A shared ?page=9 URL past the last page: the backend echoes {total>0,
    // items:[]} without clamping. The app must navigate to the last valid page
    // and render the row — never the contradictory "no contracts match" card
    // (which the "30 matching" header would flatly contradict).
    stubFetch(
      anonymousMe((url) =>
        url.includes('page=9')
          ? jsonResponse(listPage([], { total: 30, page: 9 }))
          : jsonResponse(listPage([ROW], { total: 30 })),
      ),
    )

    const { router } = renderApp('/contracts?page=9')

    expect(await screen.findByText('Tristan')).toBeInTheDocument()
    await waitFor(() => expect(router.state.location.search).toMatchObject({ page: 1 }))
    expect(screen.queryByText(/no contracts match/i)).not.toBeInTheDocument()
  })

  it('resets to page 1 when a filter changes', async () => {
    const calls = stubFetch(
      anonymousMe(() => jsonResponse(listPage([ROW], { total: 200, page: 3 }))),
    )

    const { router } = renderApp('/contracts?page=3')
    await screen.findByText('Tristan')

    await userEvent.click(screen.getByLabelText(/blueprint copies only/i))

    await waitFor(() => expect(router.state.location.search).toMatchObject({ page: 1 }))
    // Router state updates before TanStack Query issues the refetch — the
    // request assertions must also wait (TEST-2: fix the sync, never weaken).
    await waitFor(() => {
      expect(calls.at(-1)).toContain('is_bpc=true')
      expect(calls.at(-1)).toContain('page=1')
    })
  })
})

describe('ContractDetailPage', () => {
  it('renders a contract with its items', async () => {
    stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))

    renderApp('/contracts/101')

    // Heading is hull-first; the seller's title renders as a quoted subtitle.
    expect(await screen.findByRole('heading', { name: 'Tristan' })).toBeInTheDocument()
    expect(screen.getByText(/Tristan for Sale/)).toBeInTheDocument()
    // The list item renders as "1× Tristan" across text nodes — match the
    // full normalized text, not the bare name (which also appears in the h1).
    expect(screen.getByText(/1× Tristan/)).toBeInTheDocument()
    expect(screen.getByText(/jita/i)).toBeInTheDocument()
    // Detail title carries the hull name (WCAG 2.4.2 / shareable-URL principle).
    expect(document.title).toBe('Tristan — Hangar Bay')
  })

  it('heads with the label the server derived, "Contract <id>" last resort included', async () => {
    // The heading is the server's primary_label verbatim, so the detail page and
    // the list row can never name the same contract differently. Both ends of the
    // server's fallback chain render: a hull name, and the bare id a contract with
    // a blank-"" ESI title and no resolvable item name falls through to.
    const untitled = { ...CONTRACT, contract_id: 777, title: '' }
    stubFetch(anonymousMe(() => jsonResponse(untitled)))
    const named = renderApp('/contracts/777')
    expect(await screen.findByRole('heading', { name: 'Tristan' })).toBeInTheDocument()
    named.unmount()
    vi.unstubAllGlobals()

    const bare = {
      ...CONTRACT,
      contract_id: 778,
      title: '',
      primary_label: 'Contract 778',
      items: [{ ...CONTRACT.items[0], type_name: null }],
    }
    stubFetch(anonymousMe(() => jsonResponse(bare)))
    renderApp('/contracts/778')
    expect(await screen.findByRole('heading', { name: 'Contract 778' })).toBeInTheDocument()
  })

  it('badges a contract past its expiry and drops the countdown, keeping both while it is live', async () => {
    // The detail endpoint deliberately keeps serving contracts past
    // date_expired even though the list endpoint filters them out, so a
    // past-dated detail response is one the real API still produces. Both the
    // badge and the parenthetical countdown hang off timeRemaining's 'Expired'
    // sentinel, and neither branch had an assertion.
    stubFetch(anonymousMe(() => jsonResponse({ ...CONTRACT, date_expired: daysFromNow(-1) })))
    const expired = renderApp('/contracts/101')

    expect(await screen.findByText('Expired')).toBeInTheDocument()
    expect(screen.queryByText(/^\(.+\)$/)).not.toBeInTheDocument()
    expired.unmount()
    vi.unstubAllGlobals()

    stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))
    renderApp('/contracts/101')

    await screen.findByRole('heading', { name: 'Tristan' })
    expect(screen.getByText(/^\(\d+d \d+h\)$/)).toBeInTheDocument()
    expect(screen.queryByText('Expired')).not.toBeInTheDocument()
  })

  it('shows not-found for a 404', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ detail: 'Contract not found' }, 404)))

    renderApp('/contracts/999')

    expect(await screen.findByText(/not found/i)).toBeInTheDocument()
    expect(document.title).toBe('Contract not found — Hangar Bay')
  })

  it('shows not-found for a non-numeric id without issuing a request', async () => {
    // /contracts/abc -> Number('abc') -> NaN. The component's NaN guard must
    // short-circuit to NotFound; useContract(NaN) is a disabled query, so no
    // request should ever leave. Locks both the NotFound rendering and the
    // no-wasted-request behavior — if the guard is reordered below the
    // isPending branch, the disabled query's isPending stays true forever and
    // this page would render an eternal "Loading contract…" instead.
    const calls = stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))

    renderApp('/contracts/abc')

    expect(await screen.findByText(/not found/i)).toBeInTheDocument()
    // The guarded behavior is "no CONTRACTS request" — the header's own /me
    // request is expected and unrelated to the NaN-guard this test pins.
    expect(calls.filter((u) => !u.includes('/api/v1/me'))).toHaveLength(0)
  })

  it('back link restores the exact list filter/sort state via history when navigated in-app', async () => {
    // Detail is reached from a FILTERED list, so the back link must return to
    // that list with every URL param intact (PRODUCT #2: the URL is the
    // interface). It uses router.history.back() when the list is behind us,
    // rather than a bare to="/contracts" that would reset to defaults.
    stubFetch(
      anonymousMe((url) =>
        /\/contracts\/\d+/.test(url)
          ? jsonResponse(CONTRACT)
          : jsonResponse(listPage([ROW])),
      ),
    )

    const { router } = renderApp(
      '/contracts?is_bpc=true&sort_by=price&sort_direction=asc&ships_only=false',
    )

    await userEvent.click(await screen.findByRole('link', { name: 'Tristan' }))
    await screen.findByRole('heading', { name: 'Tristan' })
    expect(router.state.location.pathname).toBe('/contracts/101')

    await userEvent.click(screen.getByRole('button', { name: /all contracts/i }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/contracts'))
    expect(router.state.location.search).toMatchObject({
      is_bpc: true,
      sort_by: 'price',
      sort_direction: 'asc',
      ships_only: false,
    })
  })

  it('back link falls back to the default list on a cold deep link (no in-app history)', async () => {
    // A shared /contracts/$id opened fresh has nothing behind it, so the back
    // control is a plain link to the list rather than a history button.
    stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))

    renderApp('/contracts/101')

    await screen.findByRole('heading', { name: 'Tristan' })
    const back = screen.getByRole('link', { name: /all contracts/i })
    expect(back).toHaveAttribute('href', '/contracts')
  })
})


// A courier carries no items, prices at 0, and puts its money in the reward and
// the collateral. It reaches the UI whenever the ships-only default is turned off.
// With no item to name it after, the server's label falls through to the seller's
// own title.
const COURIER_ROW = {
  contract_id: 505,
  issuer_id: 9,
  issuer_corporation_id: 99,
  start_location_id: 60013288,
  collateral: 8_000_000_000,
  type: 'courier',
  title: 'Jita to Amarr rush',
  for_corporation: false,
  date_issued: '2026-07-01T00:00:00Z',
  // Anchored to the clock like ROW: a fixed expiry is a response the real
  // API cannot produce (the list filters date_expired > now()) and silently
  // repaints "Time left" as Expired once it passes (testing-pitfalls TEST-17).
  date_expired: daysFromNow(7),
  price: 0,
  reward: 80_000_000,
  volume: 899_999,
  reward_per_volume: 80_000_000 / 899_999,
  start_location_name: 'Airaken V - Moon 6 - Impro Warehouse',
  end_location_name: 'Amarr VIII (Oris) - Emperor Family Academy',
  days_to_complete: 3,
  is_ship_contract: false,
  is_blueprint_copy_contract: false,
  primary_label: 'Jita to Amarr rush',
  composition: null,
}

const COURIER = { ...COURIER_ROW, items: [] }

describe('courier contracts', () => {
  it('labels a courier row "Courier", not "Exchange"', async () => {
    stubFetch(anonymousMe(() => jsonResponse(listPage([COURIER_ROW]))))

    renderApp('/contracts?ships_only=false')

    // Scoped to the row: the segment toolbar above the table carries a Courier
    // control of its own, and the assertion is about the row's type badge.
    const row = within(await screen.findByRole('row', { name: /Jita to Amarr rush/ }))
    expect(row.getByText('Courier')).toBeInTheDocument()
    expect(row.queryByText('Exchange')).not.toBeInTheDocument()
  })

  it('shows the courier badge and its collateral on the detail view', async () => {
    stubFetch(anonymousMe(() => jsonResponse(COURIER)))

    renderApp('/contracts/505')

    expect(await screen.findByText('Courier')).toBeInTheDocument()
    expect(screen.queryByText('Exchange')).not.toBeInTheDocument()
    // Collateral is filterable and sortable, so it has to be readable too.
    expect(screen.getByText('Collateral')).toBeInTheDocument()
    expect(screen.getByText(/8,000,000,000/)).toBeInTheDocument()
  })

  it('renders a contract ESI sent without a start location without printing "null"', async () => {
    // start_location_id is not required by ESI's schema; the id fallback must not
    // interpolate a missing value into the page.
    const nowhere = { ...COURIER, start_location_id: null, start_location_name: null }
    stubFetch(anonymousMe(() => jsonResponse(nowhere)))

    renderApp('/contracts/505')

    expect(await screen.findByText('Unknown location')).toBeInTheDocument()
    expect(screen.queryByText(/Location null/)).not.toBeInTheDocument()
  })
})

const AUCTION_ROW = {
  ...ROW,
  contract_id: 303,
  type: 'auction',
  title: 'Vargur, no reserve',
  primary_label: 'Vargur',
}

// Loans carry no items, exactly like couriers, so nothing in one can satisfy
// ships-only. They get no segment control (spec Criterion 1.1) but stay
// reachable by URL and counted.
const LOAN_ROW = {
  ...ROW,
  contract_id: 404,
  type: 'loan',
  title: 'Capital fleet float',
  is_ship_contract: false,
  primary_label: 'Capital fleet float',
}

/**
 * Per-type counts as the server computes them: over the whole matching
 * population with the contract_type predicate lifted, and — for the item-less
 * types — with ships-only lifted too, so the courier figure is its true total
 * rather than the zero a ships-only view would return (Criterion 1.8). Nothing
 * here is derived from the page's own rows.
 */
const SEGMENT_COUNTS = { item_exchange: 1240, auction: 60, courier: 115, loan: 2, unknown: 1 }

/** Rows keyed off the requested segment, so a render can't drift from the request. */
function segmentedPage(url: string) {
  const type = new URL(url, 'http://localhost').searchParams.get('contract_type')
  const rows =
    type === 'courier'
      ? [COURIER_ROW]
      : type === 'auction'
        ? [AUCTION_ROW]
        : type === 'loan'
          ? [LOAN_ROW]
          : [ROW]
  return jsonResponse(listPage(rows, { segment_counts: SEGMENT_COUNTS }))
}

describe('contract-type segments', () => {
  it('counts All over the item-bearing types only while ships-only is on', async () => {
    // The item-less counts beside it are deliberately lifted figures (Criterion
    // 1.8) describing a view ships-only cannot show, so summing all five would
    // overstate what All actually renders: 1240 + 60, not + 115 + 2 + 1.
    stubFetch(anonymousMe(segmentedPage))

    renderApp('/contracts')

    expect(await screen.findByRole('button', { name: /^All 1,300$/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(screen.getByRole('button', { name: /^Item exchange 1,240$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Auction 60$/ })).toBeInTheDocument()
    // The courier control advertises its true total rather than the 0 the
    // ships-only view would return — the label must not flip on click.
    expect(screen.getByRole('button', { name: /^Courier 115$/ })).toBeInTheDocument()
    // loan and unknown are counted but get no control of their own.
    expect(screen.queryByRole('button', { name: /Loan/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Unknown/ })).not.toBeInTheDocument()
  })

  it('counts All over every type once the view is already widened', async () => {
    // ships_only=false with no segment selected: the item-less types are part of
    // what All renders, so they are part of what it claims — 1240+60+115+2+1.
    stubFetch(anonymousMe(segmentedPage))

    renderApp('/contracts?ships_only=false')

    expect(await screen.findByRole('button', { name: /^All 1,418$/ })).toBeInTheDocument()
  })

  it('selecting Courier clears ships-only visibly and asks the API for couriers', async () => {
    const calls = stubFetch(anonymousMe(segmentedPage))

    const { router } = renderApp('/contracts')
    await screen.findByText('Tristan')

    await userEvent.click(screen.getByRole('button', { name: /^Courier 115$/ }))

    // One navigation carries both halves: the segment AND the cleared checkbox
    // (Criterion 1.7 — the combination must be unreachable, and visibly so).
    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({
        contract_type: ['courier'],
        ships_only: false,
      }),
    )
    expect(screen.getByLabelText(/ships only/i)).not.toBeChecked()
    expect(screen.getByRole('button', { name: /^Courier 115$/ })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    // The segment names the view, in the heading and the tab label alike.
    expect(screen.getByRole('heading', { level: 1, name: 'Courier Contracts' })).toBeInTheDocument()
    await waitFor(() => expect(document.title).toBe('Courier Contracts — Hangar Bay'))

    await waitFor(() => {
      const listCall = calls.filter((u) => u.includes('/api/v1/contracts/')).at(-1)!
      expect(listCall).toContain('contract_type=courier')
      expect(listCall).not.toContain('is_ship_contract')
    })
  })

  it('returning to All removes both parameters and restores the ships-only default', async () => {
    const calls = stubFetch(anonymousMe(segmentedPage))

    const { router } = renderApp('/contracts?contract_type=courier&ships_only=false')
    await screen.findByText('Jita to Amarr rush')

    await userEvent.click(screen.getByRole('button', { name: /^All 1,300$/ }))

    // Criterion 1.9: the patch REMOVES ships_only rather than setting it true,
    // so the restored state is whatever the default is rather than a value
    // frozen at the call site. The route's validateSearch then re-derives that
    // default and writes it back out, exactly as Clear filters already does —
    // what must not survive is the explicit false that "cleared" is stored as.
    await waitFor(() => expect(router.state.location.searchStr).not.toContain('contract_type'))
    expect(router.state.location.searchStr).not.toContain('ships_only=false')
    expect(router.state.location.search).toMatchObject({ ships_only: true })
    expect(screen.getByLabelText(/ships only/i)).toBeChecked()
    expect(screen.getByRole('heading', { level: 1, name: 'Ship Contracts' })).toBeInTheDocument()

    await waitFor(() => {
      const listCall = calls.filter((u) => u.includes('/api/v1/contracts/')).at(-1)!
      expect(listCall).toContain('is_ship_contract=true')
      expect(listCall).not.toContain('contract_type')
    })
  })

  it('reaches a loan segment by URL alone, without a control and without ships-only', async () => {
    // Criterion 1.1: a type with no control is still reachable and counted. The
    // parser's item-less normalization has to hold at the wire, not just in its
    // own unit test — a shared ?contract_type=loan URL that still sent
    // is_ship_contract would be a guaranteed-empty request.
    const calls = stubFetch(anonymousMe(segmentedPage))

    renderApp('/contracts?contract_type=loan')

    expect(await screen.findByText('Capital fleet float')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Loan Contracts' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Loan/ })).not.toBeInTheDocument()
    // No control claims the view: All is not selected either.
    expect(screen.getByRole('button', { name: /^All/ })).toHaveAttribute('aria-pressed', 'false')

    const listCall = calls.filter((u) => u.includes('/api/v1/contracts/')).at(-1)!
    expect(listCall).toContain('contract_type=loan')
    expect(listCall).not.toContain('is_ship_contract')
  })
})
