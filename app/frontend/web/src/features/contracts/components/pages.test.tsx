import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import {
  anonymousMe,
  jsonResponse,
  taxonomyResponse,
  withTaxonomy,
  type FetchHandler,
} from '../../../test/http'
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
  // Clock-anchored like date_expired: the detail view renders it through a
  // relative formatter that reads the real Date.now() (TEST-17).
  last_seen_at: minutesFromNow(-11),
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

/**
 * The rendered column labels, in order. The ▲/▼ glyph on the active header is
 * aria-hidden decoration rather than part of the label, so it is stripped here
 * instead of leaking into every expected column set.
 */
function headerNames(): string[] {
  return screen.getAllByRole('columnheader').map((th) => th.textContent!.replace(/[▲▼]/g, '').trim())
}

/**
 * The contract-LIST request among the captured calls. `/contracts/taxonomy` is
 * a sibling path under the same prefix and every contracts view queries it, so
 * a substring match on `/api/v1/contracts/` returns whichever fired first
 * rather than the one the assertion is about. The list request always carries a
 * query string — `toApiQuery` emits page, size and both sort keys unconditionally.
 */
function listCall(calls: string[]): string {
  return calls.find((url) => /\/api\/v1\/contracts\/\?/.test(url))!
}

function stubFetch(handler: FetchHandler) {
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
    // Order-independent: whether /me, the taxonomy query or the contracts query
    // fires first is scheduling, not contract.
    const request = listCall(calls)
    expect(request).toContain('region_ids=10000002')
    expect(request).toContain('is_bpc=true')
    expect(request).toContain('sort_by=price')
  })

  it('carries a repeated region_ids URL through to repeated API params (shareable-URL contract)', async () => {
    // Drives the full multi-value inbound seam end-to-end: TanStack Router's
    // qss decode of ?region_ids=…&region_ids=… -> parseContractSearch array
    // coercion -> toApiQuery -> openapi-fetch's repeated-array serializer.
    // Guards the two-repeat case that single-value URL tests can't (TEST-5).
    // Both regions are covered in this response so the empty state stays the
    // ordinary one — an uncovered selection renders the coverage explanation
    // instead, which is a different branch than the one this test waits on.
    const calls = stubFetch(
      anonymousMe(() =>
        jsonResponse(
          listPage([], {
            coverage: { ingested_region_ids: [10000002, 10000020], as_of: minutesFromNow(-5) },
          }),
        ),
      ),
    )

    renderApp('/contracts?region_ids=10000002&region_ids=10000020')

    await screen.findByText(/no contracts match/i)
    // Order-independent: see the rationale above.
    expect(listCall(calls)).toContain('region_ids=10000002&region_ids=10000020')
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

  it('says when the contract was last seen in the corpus', async () => {
    // Criterion 7.1: last_seen_at is computed at ingestion and, until now, was
    // returned to nobody. A market row nobody can date is a row nobody can
    // trust — the price could be from a minute ago or from last week.
    stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))

    renderApp('/contracts/101')

    await screen.findByRole('heading', { name: 'Tristan' })
    expect(screen.getByText('Last seen')).toBeInTheDocument()
    expect(screen.getByText('11m ago')).toBeInTheDocument()
  })

  it('omits the last-seen row entirely for a contract carrying no stamp', async () => {
    // The field is nullable, and an unstamped row has no freshness to report.
    // A dash there would read as "we looked and there is nothing", which is a
    // different claim from "we never recorded when we looked".
    stubFetch(anonymousMe(() => jsonResponse({ ...CONTRACT, last_seen_at: null })))

    renderApp('/contracts/101')

    await screen.findByRole('heading', { name: 'Tristan' })
    expect(screen.queryByText('Last seen')).not.toBeInTheDocument()
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

    await userEvent.click(screen.getByRole('button', { name: /^All$/ }))

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

  it('resets a sort the destination segment cannot express', async () => {
    // Reward/m³ exists only on the courier column set. Carrying it into All
    // would order the list by a criterion no on-screen header discloses or can
    // clear — an invisible sort is the silent-control defect in sort form.
    const calls = stubFetch(anonymousMe(segmentedPage))

    const { router } = renderApp(
      '/contracts?contract_type=courier&ships_only=false&sort_by=reward_per_volume&sort_direction=asc',
    )
    await screen.findByText('Jita to Amarr rush')

    await userEvent.click(screen.getByRole('button', { name: /^All$/ }))

    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ sort_by: 'date_issued' }),
    )
    expect(router.state.location.searchStr).not.toContain('reward_per_volume')
    await waitFor(() => {
      const listCall = calls.filter((u) => u.includes('/api/v1/contracts/')).at(-1)!
      expect(listCall).toContain('sort_by=date_issued')
      expect(listCall).not.toContain('reward_per_volume')
    })
  })

  it('resets the ship-name sort to a field the courier set can disclose', async () => {
    // The courier Contract column deliberately drops the ship_name sortField —
    // and the courier set has no Issued column either, so the parser's fallback
    // is the Time-left field every set shares. The sort must end VISIBLE: a
    // header carrying aria-sort, not an invisible default.
    const calls = stubFetch(anonymousMe(segmentedPage))

    const { router } = renderApp('/contracts?sort_by=ship_name&sort_direction=asc')
    await screen.findByText('Tristan')

    await userEvent.click(screen.getByRole('button', { name: /^Courier 115$/ }))

    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ sort_by: 'date_expired' }),
    )
    await waitFor(() => {
      const listCall = calls.filter((u) => u.includes('/api/v1/contracts/')).at(-1)!
      expect(listCall).not.toContain('ship_name')
      expect(listCall).toContain('sort_by=date_expired')
    })
    await screen.findByText('Jita to Amarr rush')
    const sortedHeaders = screen
      .getAllByRole('columnheader')
      .filter((th) => th.getAttribute('aria-sort') !== null)
    expect(sortedHeaders).toHaveLength(1)
    expect(sortedHeaders[0]).toHaveTextContent(/Time left/)
  })

  it('gives a courier deep link a sort its own columns disclose', async () => {
    // Codex PR-C finding: the parser default was date_issued, which no courier
    // header carries — every default courier view was invisibly sorted.
    const calls = stubFetch(anonymousMe(segmentedPage))

    renderApp('/contracts?contract_type=courier&ships_only=false')
    await screen.findByText('Jita to Amarr rush')

    await waitFor(() => {
      const listCall = calls.filter((u) => u.includes('/api/v1/contracts/')).at(-1)!
      expect(listCall).toContain('sort_by=date_expired')
    })
    const sortedHeaders = screen
      .getAllByRole('columnheader')
      .filter((th) => th.getAttribute('aria-sort') !== null)
    expect(sortedHeaders).toHaveLength(1)
  })

  it('clears an orphaned sort when Clear filters drops the segment that offered it', async () => {
    // Reconciliation lives in the parser, so it also covers routes that never
    // touch the segment buttons — Clear filters keeps the sort keys but drops
    // the auction segment, and buyout has no header outside it.
    const calls = stubFetch(anonymousMe(segmentedPage))

    const { router } = renderApp(
      '/contracts?contract_type=auction&sort_by=buyout&sort_direction=asc',
    )
    await screen.findByText('Vargur')

    await userEvent.click(screen.getByRole('button', { name: 'Clear filters' }))

    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ sort_by: 'date_issued' }),
    )
    await waitFor(() => {
      const listCall = calls.filter((u) => u.includes('/api/v1/contracts/')).at(-1)!
      expect(listCall).not.toContain('buyout')
    })
  })

  it('shows the All control without a count while an item-less segment is active', async () => {
    // The request that produced this envelope carried no ships-only filter, so
    // the item-bearing counts are lifted — but clicking All restores ships-only,
    // a population those counts cannot describe. No numeral beats a wrong one.
    stubFetch(anonymousMe(segmentedPage))

    renderApp('/contracts?contract_type=courier&ships_only=false')
    await screen.findByText('Jita to Amarr rush')

    const all = screen.getByRole('button', { name: /^All$/ })
    expect(all.textContent).toBe('All')
  })

  it('keeps a sort both segments can express', async () => {
    // Price is sortable in All and in Auction alike — resetting it would throw
    // away the user's choice for no disclosure gain.
    const calls = stubFetch(anonymousMe(segmentedPage))

    const { router } = renderApp('/contracts?sort_by=price&sort_direction=asc')
    await screen.findByText('Tristan')

    await userEvent.click(screen.getByRole('button', { name: /^Auction 60$/ }))

    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({
        contract_type: ['auction'],
        sort_by: 'price',
        sort_direction: 'asc',
      }),
    )
    await waitFor(() => {
      const listCall = calls.filter((u) => u.includes('/api/v1/contracts/')).at(-1)!
      expect(listCall).toContain('sort_by=price')
      expect(listCall).toContain('sort_direction=asc')
    })
  })

  it('keeps the default column set for All and for item exchange', async () => {
    // The segment selects the columns (spec §8 axis 1), so the two segments
    // that describe a fixed-price sale keep the set the table has always had —
    // the auction and courier sets below are departures from THIS.
    stubFetch(anonymousMe(segmentedPage))

    renderApp('/contracts')
    await screen.findByText('Tristan')
    expect(headerNames()).toEqual([
      'Ship / Contract',
      'Type',
      'Price (ISK)',
      'Location',
      'Time left',
      'Issued',
    ])

    await userEvent.click(screen.getByRole('button', { name: /^Item exchange 1,240$/ }))

    await waitFor(() =>
      expect(headerNames()).toEqual([
        'Ship / Contract',
        'Type',
        'Price (ISK)',
        'Location',
        'Time left',
        'Issued',
      ]),
    )
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

/**
 * Two auctions with distinct bids and buyouts, one of them with no buyout at
 * all — the case Criterion 4.3 says the row must state in words.
 */
const AUCTION_ROWS = [
  {
    ...ROW,
    contract_id: 301,
    type: 'auction',
    title: 'Vargur, no reserve',
    primary_label: 'Vargur',
    price: 1_900_000_000,
    buyout: 2_600_000_000,
  },
  {
    ...ROW,
    contract_id: 302,
    type: 'auction',
    title: '',
    primary_label: 'Cynabal',
    price: 240_000_000,
    buyout: null,
  },
]

/**
 * Two couriers: one fully resolved, and one whose destination is a player
 * structure nothing could name, carrying no rate and no deadline either.
 */
const COURIER_ROWS = [
  COURIER_ROW,
  {
    ...COURIER_ROW,
    contract_id: 506,
    title: 'Bulk ore run',
    primary_label: 'Bulk ore run',
    end_location_name: null,
    reward: 5_000_000,
    collateral: 0,
    volume: 0,
    reward_per_volume: null,
    days_to_complete: null,
  },
]

/** Rows keyed off the requested segment, so a column set can't drift from its rows. */
function typedPage(url: string) {
  const type = new URL(url, 'http://localhost').searchParams.get('contract_type')
  const rows = type === 'auction' ? AUCTION_ROWS : type === 'courier' ? COURIER_ROWS : [ROW]
  return jsonResponse(listPage(rows))
}

describe('per-segment column sets', () => {
  it('gives the auction segment a starting bid and a buyout instead of one price', async () => {
    // Criterion 4.2: a bid is not a price, and a buyout is a third thing again.
    // The Type column goes with them — every row in this segment is an auction,
    // so the badge would repeat the segment control back at the reader.
    stubFetch(anonymousMe(typedPage))

    renderApp('/contracts?contract_type=auction')

    await screen.findByText('Vargur')
    expect(headerNames()).toEqual([
      'Ship / Contract',
      'Starting bid',
      'Buyout',
      'Location',
      'Time left',
      'Issued',
    ])

    const vargur = within(screen.getByRole('row', { name: /Vargur/ }))
    expect(vargur.getByText('1,900,000,000')).toBeInTheDocument()
    expect(vargur.getByText('2,600,000,000')).toBeInTheDocument()
  })

  it('says a buyout-less auction has none rather than leaving the cell blank', async () => {
    // Criterion 4.3: not 0 (which reads as "buy it for nothing"), not a dash
    // (which reads as missing data), but the fact that the seller set none.
    stubFetch(anonymousMe(typedPage))

    renderApp('/contracts?contract_type=auction')

    const cynabal = within(await screen.findByRole('row', { name: /Cynabal/ }))
    expect(cynabal.getByText('No buyout')).toBeInTheDocument()
    expect(cynabal.queryByText('—')).not.toBeInTheDocument()
    expect(cynabal.queryByText('0')).not.toBeInTheDocument()
  })

  it('sorts the auction segment on buyout from its own header', async () => {
    const calls = stubFetch(anonymousMe(typedPage))

    const { router } = renderApp('/contracts?contract_type=auction')
    await screen.findByText('Vargur')

    await userEvent.click(screen.getByRole('button', { name: 'Buyout' }))

    await waitFor(() => expect(router.state.location.search).toMatchObject({ sort_by: 'buyout' }))
    await waitFor(() => {
      const listCall = calls.filter((u) => u.includes('/api/v1/contracts/')).at(-1)!
      expect(listCall).toContain('sort_by=buyout')
    })
  })

  it('gives the courier segment route, reward, collateral, volume, rate and deadline', async () => {
    // Criterion 5.3 in full, plus 5.4's rate. There is no Location column: the
    // origin is half the route, and repeating it would cost a column the
    // deadline needs. Criterion 5.6 — nothing here is or implies a distance.
    stubFetch(anonymousMe(typedPage))

    renderApp('/contracts?contract_type=courier')

    await screen.findByText('Jita to Amarr rush')
    expect(headerNames()).toEqual([
      'Contract',
      'Route',
      'Reward',
      'Collateral',
      'Volume',
      'Reward/m³',
      'Deadline',
      'Time left',
    ])

    const rush = within(screen.getByRole('row', { name: /Jita to Amarr rush/ }))
    expect(
      rush.getByText('Airaken V - Moon 6 - Impro Warehouse → Amarr VIII (Oris) - Emperor Family Academy'),
    ).toBeInTheDocument()
    expect(rush.getByText('80,000,000')).toBeInTheDocument()
    expect(rush.getByText('8,000,000,000')).toBeInTheDocument()
    expect(rush.getByText('899,999')).toBeInTheDocument()
    expect(rush.getByText('88.89')).toBeInTheDocument()
    expect(rush.getByText('3d')).toBeInTheDocument()
  })

  it('names an unresolvable courier destination instead of blanking the route', async () => {
    // Spec §8: about 5% of Forge courier destinations are player structures no
    // public token can resolve. The row says so; the rate and deadline it also
    // lacks fall back to the dash, which is a different statement.
    stubFetch(anonymousMe(typedPage))

    renderApp('/contracts?contract_type=courier')

    const bulk = within(await screen.findByRole('row', { name: /Bulk ore run/ }))
    expect(
      bulk.getByText('Airaken V - Moon 6 - Impro Warehouse → Unknown structure'),
    ).toBeInTheDocument()
    expect(bulk.queryByText(/Location \d/)).not.toBeInTheDocument()
    expect(bulk.getAllByText('—')).toHaveLength(2)
  })

  it('describes the rows still on screen with their own columns while the next segment loads', async () => {
    // The table holds the previous segment's rows until the new response lands
    // (keepPreviousData), and the unfiltered list takes seconds in production —
    // this window is not a sub-frame flicker. Columns taken from the URL rather
    // than from the rows would describe THIS sale as a hauling job: its price
    // read as a reward, its hull volume read as cargo, and a destination
    // invented for a contract that has no route at all.
    let releaseCouriers!: (page: Response) => void
    const couriersInFlight = new Promise<Response>((resolve) => {
      releaseCouriers = resolve
    })
    const calls = stubFetch(
      anonymousMe((url) =>
        url.includes('contract_type=courier') ? couriersInFlight : typedPage(url),
      ),
    )

    renderApp('/contracts')
    await screen.findByText('Tristan')

    await userEvent.click(screen.getByRole('button', { name: /^Courier/ }))
    await waitFor(() => expect(calls.some((url) => url.includes('contract_type=courier'))).toBe(true))

    expect(screen.getByRole('row', { name: /Tristan/ })).toBeInTheDocument()
    expect(headerNames()).toEqual([
      'Ship / Contract',
      'Type',
      'Price (ISK)',
      'Location',
      'Time left',
      'Issued',
    ])
    // Spec §8 reserves this wording for a courier endpoint no public token can
    // resolve; a sale has no endpoint to fail to resolve.
    expect(screen.queryByText(/Unknown structure/)).not.toBeInTheDocument()

    releaseCouriers(jsonResponse(listPage(COURIER_ROWS)))

    expect(await screen.findByText('Jita to Amarr rush')).toBeInTheDocument()
    expect(headerNames()).toEqual([
      'Contract',
      'Route',
      'Reward',
      'Collateral',
      'Volume',
      'Reward/m³',
      'Deadline',
      'Time left',
    ])
    expect(screen.queryByRole('row', { name: /Tristan/ })).not.toBeInTheDocument()
  })

  it('sorts the courier segment on reward per m³ from its own header', async () => {
    const calls = stubFetch(anonymousMe(typedPage))

    const { router } = renderApp('/contracts?contract_type=courier')
    await screen.findByText('Jita to Amarr rush')

    await userEvent.click(screen.getByRole('button', { name: 'Reward/m³' }))

    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ sort_by: 'reward_per_volume' }),
    )
    await waitFor(() => {
      const listCall = calls.filter((u) => u.includes('/api/v1/contracts/')).at(-1)!
      expect(listCall).toContain('sort_by=reward_per_volume')
    })
  })
})

describe('freshness and coverage', () => {
  /** The results section alone: the filter rail carries a Clear filters button of its own. */
  function results() {
    return within(screen.getByRole('region', { name: 'Contract results' }))
  }

  it('states how fresh the corpus is beside the result count', async () => {
    // Criterion 7.1. The stamp is the envelope's, not the row's: it describes
    // the dataset the page was drawn from, so it belongs with the count rather
    // than in a column.
    stubFetch(anonymousMe(() => jsonResponse(listPage([ROW]))))

    renderApp('/contracts')

    expect(await screen.findByText('Data as of 5m ago')).toBeInTheDocument()
  })

  it('claims no freshness at all when nothing has been stamped', async () => {
    // coverage.as_of is null before the first ingestion run finishes. That is
    // the absence of a freshness signal, and rendering a dash beside "Data as
    // of" would dress the absence up as a reading.
    stubFetch(
      anonymousMe(() =>
        jsonResponse(listPage([ROW], { coverage: { ingested_region_ids: [], as_of: null } })),
      ),
    )

    renderApp('/contracts')

    await screen.findByText('Tristan')
    expect(screen.queryByText(/Data as of/)).not.toBeInTheDocument()
  })

  it('explains an empty result for a region the corpus does not cover', async () => {
    // Criterion 7.2/7.3: "not covered" and "nothing matched" are different
    // facts, and the region that separates them is named from the envelope's
    // ids — the client embeds no region literal of its own.
    stubFetch(anonymousMe(() => jsonResponse(listPage([]))))

    renderApp('/contracts?region_ids=10000043')

    expect(await screen.findByRole('heading', { name: 'No data for Domain yet' })).toBeInTheDocument()
    expect(screen.getByText(/currently covers The Forge/)).toBeInTheDocument()
    // The covered-empty advice is a false lead here: no price bound loosens
    // its way into a region that holds no rows at all.
    expect(screen.queryByText(/Loosen a price bound/)).not.toBeInTheDocument()
    expect(results().getByRole('button', { name: 'Clear filters' })).toBeInTheDocument()
  })

  it('pluralizes the coverage explanation for several uncovered regions', async () => {
    // Only the singular ternary arm was pinned before; a swapped pair would
    // have shipped green.
    stubFetch(anonymousMe(() => jsonResponse(listPage([]))))

    renderApp('/contracts?region_ids=10000043&region_ids=10000030')

    expect(
      await screen.findByRole('heading', { name: /No data for (Domain and Heimatar|Heimatar and Domain) yet/ }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Those regions hold nothing here yet/)).toBeInTheDocument()
    expect(screen.queryByText(/That region holds/)).not.toBeInTheDocument()
  })

  it('announces the coverage gap in the same breath as the zero count', async () => {
    // The polite live region is what assistive tech hears. "0 contracts match"
    // alone is misleading when the real story is "that region is not covered" —
    // the explanation must ride the same announcement, not sit in a card the
    // listener has to go find.
    stubFetch(anonymousMe(() => jsonResponse(listPage([]))))

    renderApp('/contracts?region_ids=10000043')

    await screen.findByRole('heading', { name: 'No data for Domain yet' })
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('0 contracts match your filters')
    expect(status).toHaveTextContent('Domain is not covered yet')
  })

  it('keeps the courier coverage statement on an empty courier view', async () => {
    // Criterion 5.7's reader is exactly the hauler staring at zero jobs: the
    // statement that origins are one region's worth must not vanish with the
    // rows.
    stubFetch(anonymousMe(() => jsonResponse(listPage([]))))

    renderApp('/contracts?contract_type=courier&ships_only=false')

    await screen.findByText(/no contracts match/i)
    expect(screen.getByText('Couriers originating in The Forge only.')).toBeInTheDocument()
  })

  it('says nothing is ingested yet when the corpus is empty, instead of blaming filters', async () => {
    // Codex PR-C finding: with ingested_region_ids empty and no region filter,
    // the covered-empty branch advised loosening filters no filter can help.
    stubFetch(
      anonymousMe(() =>
        jsonResponse(listPage([], { coverage: { ingested_region_ids: [], as_of: null } })),
      ),
    )

    renderApp('/contracts')

    expect(await screen.findByRole('heading', { name: 'No data ingested yet' })).toBeInTheDocument()
    expect(screen.queryByText(/Loosen a price bound/)).not.toBeInTheDocument()
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('No region has been ingested yet')
  })

  it('keeps the loosen-your-filters copy when every selected region is covered', async () => {
    // A covered region that happens to hold nothing matching is the ordinary
    // empty, and the advice that fits it must not be replaced by a coverage
    // story that would be false.
    stubFetch(anonymousMe(() => jsonResponse(listPage([]))))

    renderApp('/contracts?region_ids=10000002')

    expect(await screen.findByText(/no contracts match/i)).toBeInTheDocument()
    expect(screen.getByText(/Loosen a price bound/)).toBeInTheDocument()
    expect(screen.queryByText(/currently covers/)).not.toBeInTheDocument()
  })

  it('separates the uncovered half of a mixed selection from the covered half', async () => {
    // With both kinds selected the empty result has two causes at once, and
    // naming only the uncovered one would imply the covered selection was
    // never consulted.
    stubFetch(anonymousMe(() => jsonResponse(listPage([]))))

    renderApp('/contracts?region_ids=10000002&region_ids=10000043')

    expect(await screen.findByRole('heading', { name: 'No data for Domain yet' })).toBeInTheDocument()
    expect(screen.getByText(/also selected The Forge, which matched nothing/)).toBeInTheDocument()
  })

  it('names the covered regions in the empty state even before anything is ingested', async () => {
    // A corpus with no rows yet covers nothing, so there is no covered set to
    // name — the sentence has to change rather than read "currently covers .".
    stubFetch(
      anonymousMe(() =>
        jsonResponse(listPage([], { coverage: { ingested_region_ids: [], as_of: null } })),
      ),
    )

    renderApp('/contracts?region_ids=10000002')

    expect(
      await screen.findByRole('heading', { name: 'No data for The Forge yet' }),
    ).toBeInTheDocument()
    // The sentence appears twice on purpose: in the visible card AND in the
    // polite live region, so assistive tech hears the same truth it shows.
    expect(screen.getAllByText(/No region has been ingested yet/)).toHaveLength(2)
  })

  it('keeps describing the result on screen while the next region loads', async () => {
    // WEB-1: keepPreviousData holds the previous empty result through the whole
    // of the next request, so an explanation read off the live URL would call
    // Domain uncovered while the rows on screen came from a Forge query — a
    // specific, confident falsehood for as long as the request takes.
    let releaseDomain!: (page: Response) => void
    const domainInFlight = new Promise<Response>((resolve) => {
      releaseDomain = resolve
    })
    const calls = stubFetch(
      anonymousMe((url) =>
        url.includes('region_ids=10000043') ? domainInFlight : jsonResponse(listPage([])),
      ),
    )

    renderApp('/contracts?region_ids=10000002')
    await screen.findByText(/Loosen a price bound/)

    await userEvent.click(screen.getByLabelText('Domain'))
    await waitFor(() =>
      expect(calls.some((url) => url.includes('region_ids=10000043'))).toBe(true),
    )

    expect(screen.getByText(/Loosen a price bound/)).toBeInTheDocument()
    expect(screen.queryByText(/No data for Domain/)).not.toBeInTheDocument()

    releaseDomain(jsonResponse(listPage([])))

    expect(await screen.findByRole('heading', { name: 'No data for Domain yet' })).toBeInTheDocument()
  })

  it('states where couriers may originate, above the courier rows', async () => {
    // Criterion 5.7. A hauler reading a route list has to know the origins are
    // one region's worth rather than the whole cluster's.
    stubFetch(anonymousMe(() => jsonResponse(listPage([COURIER_ROW]))))

    renderApp('/contracts?contract_type=courier')

    expect(await screen.findByText('Couriers originating in The Forge only.')).toBeInTheDocument()
  })

  it('makes no origin claim outside the courier segment', async () => {
    // The statement is about routes; a sale has an origin only in the sense
    // that everything in the corpus does.
    stubFetch(anonymousMe(() => jsonResponse(listPage([ROW]))))

    renderApp('/contracts')

    await screen.findByText('Tristan')
    expect(screen.queryByText(/originating in/)).not.toBeInTheDocument()
  })
})

/**
 * The item-level surface waits on observed reality rather than on a flag
 * (decision log D1): `GET /contracts/taxonomy` reports `complete` only once the
 * corpus is enriched at the current enrichment version, which follows the
 * post-release resweep on its own. Until then the controls are honestly absent
 * and a filter that arrived by URL says the results may be short.
 */
const INDEXING_LINE = 'Item filters are still indexing.'
const INCOMPLETE_NOTICE = 'Item filters are still indexing; results may be incomplete.'

/** A taxonomy the resweep has finished with — the state that opens the surface. */
const READY_TAXONOMY = taxonomyResponse({
  coverage: 'complete',
  categories: [
    { category_id: 6, name: 'Ship' },
    { category_id: 7, name: 'Module' },
  ],
  groups: [
    { group_id: 25, category_id: 6, name: 'Frigate' },
    { group_id: 60, category_id: 7, name: 'Shield Booster' },
  ],
})

describe('item-level surface gate', () => {
  it('asks the taxonomy endpoint for the readiness signal, at its schema path', async () => {
    const calls = stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([ROW])))))

    renderApp('/contracts')

    await screen.findByText('Tristan')
    expect(calls.filter((url) => /\/api\/v1\/contracts\/taxonomy$/.test(url))).toHaveLength(1)
  })

  it('offers no item filters while the corpus is still being enriched', async () => {
    stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([ROW])))))

    renderApp('/contracts')

    await screen.findByText('Tristan')
    expect(await screen.findByText(INDEXING_LINE)).toBeInTheDocument()
  })

  it('opens the item filters once the corpus is enriched', async () => {
    stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([ROW]))), READY_TAXONOMY))

    renderApp('/contracts')

    await screen.findByText('Tristan')
    await waitFor(() => expect(screen.queryByText(INDEXING_LINE)).not.toBeInTheDocument())
  })

  it('treats an unreachable taxonomy endpoint as still indexing, without a retry control', async () => {
    // A 500 leaves the readiness unknown, and unknown is not ready: offering
    // controls whose option list never arrived would be worse than saying so.
    // No spinner and no Retry — the state is expected for the ~80 minutes after
    // a release, and inviting a retry frames it as a failure of this page.
    stubFetch(
      anonymousMe((url) =>
        /\/contracts\/taxonomy$/.test(url)
          ? jsonResponse({ detail: 'boom' }, 500)
          : jsonResponse(listPage([ROW])),
      ),
    )

    renderApp('/contracts')

    await screen.findByText('Tristan')
    expect(await screen.findByText(INDEXING_LINE)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
  })

  it('warns that a deep-linked item filter may be answered from a half-enriched corpus', async () => {
    // The request still goes out: the rows it matches are real, and a 422 here
    // would break every saved search the moment a future resweep starts.
    const calls = stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([ROW])))))

    renderApp('/contracts?category_id=6')

    expect(await screen.findByText(INCOMPLETE_NOTICE)).toBeInTheDocument()
    expect(calls.some((url) => /[?&]category_id=6(&|$)/.test(url))).toBe(true)
  })

  it('keeps warning about the rows on screen while an unfiltered page loads over them', async () => {
    // WEB-1: the warning is a claim about the RESULTS, and `keepPreviousData`
    // holds the filtered rows on screen for the whole of the request that drops
    // the filter. Reading the live URL would withdraw the warning while the
    // rows it was about are still the ones being read.
    let releaseUnfiltered: (() => void) | undefined
    stubFetch(
      withTaxonomy(
        anonymousMe((url) => {
          if (/\/contracts\/\?/.test(url) && !/[?&]min_me=/.test(url)) {
            return new Promise<Response>((resolve) => {
              releaseUnfiltered = () => resolve(jsonResponse(listPage([ROW])))
            })
          }
          return jsonResponse(listPage([ROW]))
        }),
      ),
    )

    // Navigated rather than typed: the rail's ME control is itself gated shut
    // while the corpus is partial, and a shared link is exactly how a filter
    // reaches this state anyway.
    const { router } = renderApp('/contracts?min_me=5')
    expect(await screen.findByText(INCOMPLETE_NOTICE)).toBeInTheDocument()

    await router.navigate({ to: '/contracts', search: {} })

    // The unfiltered response is still in flight; the filtered rows are still
    // what the reader is looking at, so the warning about them stands.
    await waitFor(() => expect(releaseUnfiltered).toBeDefined())
    expect(screen.getByText(INCOMPLETE_NOTICE)).toBeInTheDocument()

    releaseUnfiltered!()
    await waitFor(() => expect(screen.queryByText(INCOMPLETE_NOTICE)).not.toBeInTheDocument())
  })

  it('drops the incomplete-results warning once the corpus is enriched', async () => {
    stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([ROW]))), READY_TAXONOMY))

    renderApp('/contracts?min_me=5')

    await screen.findByText('Tristan')
    await waitFor(() => expect(screen.queryByText(INCOMPLETE_NOTICE)).not.toBeInTheDocument())
  })

  it('shows an item-less segment without a count while an offered-item filter is active', async () => {
    // The envelope's courier figure was computed with the category filter
    // applied, but arriving at the courier segment drops that filter (nothing
    // item-less can satisfy it), so the number describes a view the click does
    // not deliver. No numeral beats a wrong one — the same rule the All control
    // already follows from an item-less segment.
    stubFetch(withTaxonomy(anonymousMe(segmentedPage), READY_TAXONOMY))

    renderApp('/contracts?category_id=6')

    expect(await screen.findByRole('button', { name: /^Courier$/ })).toBeInTheDocument()
    // The item-bearing segments keep theirs: their counts were computed under
    // the same filter their destination keeps.
    expect(screen.getByRole('button', { name: /^Item exchange 1,240$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^Auction 60$/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /^All 1,300$/ })).toBeInTheDocument()
  })

  it('warns only when a filter that reads the new item columns is in play', async () => {
    // is_bpc reads is_blueprint_copy, which ingestion has written since M1, so
    // it answers just as completely mid-resweep as it does after one. Warning
    // about it would cry wolf on the one item filter that was never at risk.
    stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([ROW])))))

    renderApp('/contracts?is_bpc=true')

    await screen.findByText('Tristan')
    expect(screen.queryByText(INCOMPLETE_NOTICE)).not.toBeInTheDocument()
    // The rail still says the controls are not ready — that claim is about the
    // controls, not about this request.
    expect(screen.getByText(INDEXING_LINE)).toBeInTheDocument()
  })
})

/**
 * The cascading dogma filter (Criteria 3.2–3.4). The option lists come from the
 * server so the client embeds no taxonomy of its own (Criterion 3.5), and the
 * group list is scoped client-side because §17.6 serves it flat for exactly
 * that reason — narrowing a category costs no round trip.
 */
describe('taxonomy filters', () => {
  const readyList = (rows = [ROW]) =>
    withTaxonomy(anonymousMe(() => jsonResponse(listPage(rows))), READY_TAXONOMY)

  it('offers the categories the corpus actually holds', async () => {
    stubFetch(readyList())

    renderApp('/contracts')

    expect(await screen.findByRole('checkbox', { name: 'Ship' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Module' })).toBeInTheDocument()
  })

  it('scopes the group list to the selected categories', async () => {
    stubFetch(readyList())

    renderApp('/contracts?category_id=6')

    // Frigate belongs to Ship; Shield Booster belongs to Module, which is not
    // selected, so offering it would offer a combination matching nothing.
    expect(await screen.findByRole('checkbox', { name: 'Frigate' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Shield Booster' })).not.toBeInTheDocument()
  })

  it('offers every group while no category narrows the list', async () => {
    stubFetch(readyList())

    renderApp('/contracts')

    expect(await screen.findByRole('checkbox', { name: 'Frigate' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Shield Booster' })).toBeInTheDocument()
  })

  it('narrows the group list by type-ahead, and says when nothing matches', async () => {
    // Criterion 3.3: the Module category alone holds hundreds of groups in the
    // real taxonomy, so the list is unusable without one.
    const user = userEvent.setup()
    stubFetch(readyList())

    renderApp('/contracts')
    await screen.findByRole('checkbox', { name: 'Frigate' })

    await user.type(screen.getByLabelText('Filter group list'), 'fri')
    expect(screen.getByRole('checkbox', { name: 'Frigate' })).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'Shield Booster' })).not.toBeInTheDocument()

    await user.clear(screen.getByLabelText('Filter group list'))
    await user.type(screen.getByLabelText('Filter group list'), 'zzz')
    expect(screen.getByText('No group matches “zzz”')).toBeInTheDocument()
  })

  it('sends a category selection to the API and puts it in the URL', async () => {
    const user = userEvent.setup()
    const calls = stubFetch(readyList())

    const { router } = renderApp('/contracts')
    await screen.findByRole('checkbox', { name: 'Ship' })

    await user.click(screen.getByRole('checkbox', { name: 'Ship' }))

    await waitFor(() => expect(router.state.location.search).toMatchObject({ category_id: [6] }))
    await waitFor(() =>
      expect(calls.some((url) => /[?&]category_id=6(&|$)/.test(url))).toBe(true),
    )
  })

  it('prunes group selections the narrowed category scope no longer contains', async () => {
    // One navigation, not two: leaving Shield Booster in the URL after its
    // category goes would keep filtering on a group no visible control could
    // clear.
    const user = userEvent.setup()
    stubFetch(readyList())

    const { router } = renderApp('/contracts?category_id=6&category_id=7&group_id=25&group_id=60')
    await screen.findByRole('checkbox', { name: 'Module' })
    expect(screen.getByRole('checkbox', { name: 'Shield Booster' })).toBeChecked()

    await user.click(screen.getByRole('checkbox', { name: 'Module' }))

    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ category_id: [6], group_id: [25] }),
    )
  })

  it('keeps every group selection when the category scope opens up again', async () => {
    // Deselecting the last category widens the scope to every group, so nothing
    // is out of scope and nothing may be pruned.
    const user = userEvent.setup()
    stubFetch(readyList())

    const { router } = renderApp('/contracts?category_id=6&group_id=25')
    await screen.findByRole('checkbox', { name: 'Ship' })

    await user.click(screen.getByRole('checkbox', { name: 'Ship' }))

    await waitFor(() =>
      expect(router.state.location.search).toMatchObject({ group_id: [25] }),
    )
    expect(router.state.location.search).not.toHaveProperty('category_id')
  })

  it('says in words that the group list follows the category selection', async () => {
    // Criterion 12: changing category changes the available groups, and that
    // has to be announced — as plain described-by text, not invented ARIA.
    stubFetch(readyList())

    renderApp('/contracts?category_id=6')

    const groups = await screen.findByRole('group', { name: /^Group/ })
    expect(groups).toHaveAccessibleDescription('1 group within the selected categories')
  })

  it('describes an unscoped group list as the whole taxonomy', async () => {
    stubFetch(readyList())

    renderApp('/contracts')

    const groups = await screen.findByRole('group', { name: /^Group/ })
    expect(groups).toHaveAccessibleDescription(
      'All 2 groups; select a category to narrow this list',
    )
  })

  it('announces the new scope when a category change resizes the group list', async () => {
    // A described-by sentence is read when focus reaches the fieldset — which
    // is not where the reader is when they tick a category. Criterion 12 asks
    // for the CHANGE to be announced, so the sentence is a polite live region
    // and carries the count that makes each change audible.
    const user = userEvent.setup()
    stubFetch(readyList())

    renderApp('/contracts')
    const scope = await screen.findByText('All 2 groups; select a category to narrow this list')
    expect(scope).toHaveAttribute('aria-live', 'polite')

    await user.click(screen.getByRole('checkbox', { name: 'Ship' }))

    expect(await screen.findByText('1 group within the selected categories')).toBeInTheDocument()
  })

  it('offers no taxonomy controls while the corpus is still being enriched', async () => {
    stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([ROW])))))

    renderApp('/contracts')

    await screen.findByText(INDEXING_LINE)
    expect(screen.queryByRole('checkbox', { name: 'Ship' })).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: /^Group/ })).not.toBeInTheDocument()
  })

  it('offers no taxonomy controls on an item-less segment, which no item can satisfy', async () => {
    stubFetch(withTaxonomy(anonymousMe(segmentedPage), READY_TAXONOMY))

    renderApp('/contracts?contract_type=courier')

    await screen.findByText('Jita to Amarr rush')
    expect(screen.queryByRole('checkbox', { name: 'Ship' })).not.toBeInTheDocument()
    expect(
      screen.getByText('Item filters do not apply to contracts that carry no items.'),
    ).toBeInTheDocument()
  })

  it('offers the blueprint stat bounds beside the taxonomy lists', async () => {
    stubFetch(readyList())

    renderApp('/contracts')

    // Criterion 2.5's four ME/TE params and Criterion 2.3's runs pair, each a
    // separate control rather than one "blueprint" box: the three families are
    // independent EXISTS clauses on the wire, and a reader filtering on ME
    // must not be made to state a runs window they do not care about.
    for (const label of [
      'Minimum runs',
      'Maximum runs',
      'Minimum material efficiency',
      'Maximum material efficiency',
      'Minimum time efficiency',
      'Maximum time efficiency',
    ]) {
      expect(await screen.findByLabelText(label)).toHaveAttribute('min', '0')
    }
  })

  it('sends a blueprint stat window to the API and puts it in the URL', async () => {
    const user = userEvent.setup()
    const calls = stubFetch(readyList())

    const { router } = renderApp('/contracts')
    await screen.findByLabelText('Minimum material efficiency')

    await user.type(screen.getByLabelText('Minimum material efficiency'), '5')

    await waitFor(() => expect(router.state.location.search).toMatchObject({ min_me: 5 }))
    await waitFor(() => expect(calls.some((url) => /[?&]min_me=5(&|$)/.test(url))).toBe(true))
  })

  it('clears a blueprint bound out of the URL when its input is emptied', async () => {
    // An empty box means "no bound", not zero: min_me=0 matches every blueprint
    // with any ME at all, which is a filter, not the absence of one.
    const user = userEvent.setup()
    stubFetch(readyList())

    const { router } = renderApp('/contracts?max_runs=20')
    await screen.findByLabelText('Maximum runs')

    await user.clear(screen.getByLabelText('Maximum runs'))

    await waitFor(() => expect(router.state.location.search).not.toHaveProperty('max_runs'))
  })

  it('offers no blueprint stat bounds while the corpus is still being enriched', async () => {
    stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([ROW])))))

    renderApp('/contracts')

    await screen.findByText(INDEXING_LINE)
    expect(screen.queryByLabelText('Minimum runs')).not.toBeInTheDocument()
  })

  it('offers no taxonomy or blueprint controls while a taxonomy request is unanswered', async () => {
    stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([ROW])))))

    renderApp('/contracts')

    await screen.findByText(INDEXING_LINE)
    expect(screen.queryByLabelText('Filter group list')).not.toBeInTheDocument()
  })

  it('offers Clear filters for a taxonomy selection that arrived by URL', async () => {
    // The rail's Clear button is the only way back from a deep link, and the
    // predicate behind it has to know about every param the parser accepts.
    // Rows on screen deliberately: the empty-state card carries a Clear button
    // of its own, which would answer this query whatever the rail decided.
    stubFetch(readyList())

    renderApp('/contracts?group_id=25')

    await screen.findByText('Tristan')
    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeInTheDocument()
  })
})

/**
 * The blueprint and composition cells (Criteria 2.2, 6.1–6.3, 8.1, §8's
 * discriminator). Every one of them reads a column the F008 resweep fills, so
 * every one of them is behind the readiness gate: a column that is blank across
 * a mostly-unenriched corpus reads as breakage, which is the state §7 gates.
 */
describe('blueprint and composition cells', () => {
  const readyList = (rows: { type: string }[]) =>
    withTaxonomy(anonymousMe(() => jsonResponse(listPage(rows))), READY_TAXONOMY)

  /** A contract offering exactly one blueprint copy — §8's "values" case. */
  const ONE_COPY = {
    ...ROW,
    contract_id: 811,
    primary_label: 'Draugur Blueprint',
    is_blueprint_copy_contract: true,
    blueprint_summary: { copy_count: 1, runs: 10, material_efficiency: 4, time_efficiency: 8 },
  }

  /** Several copies: no single set of terms describes them (§8's "count" case). */
  const THREE_COPIES = {
    ...ROW,
    contract_id: 822,
    primary_label: 'Blueprint lot',
    is_blueprint_copy_contract: true,
    blueprint_summary: {
      copy_count: 3,
      runs: null,
      material_efficiency: null,
      time_efficiency: null,
    },
  }

  function blueprintCell(rowName: RegExp): string {
    const cells = within(screen.getByRole('row', { name: rowName })).getAllByRole('cell')
    const index = headerNames().indexOf('Blueprint')
    return cells[index].textContent!
  }

  it('reads a single offered copy’s terms in the row', async () => {
    stubFetch(readyList([ONE_COPY]))

    renderApp('/contracts')

    await screen.findByText('Draugur Blueprint')
    expect(blueprintCell(/Draugur Blueprint/)).toBe('10 runs · ME 4 · TE 8')
  })

  it('counts several copies instead of reporting one of them, and links to the detail', async () => {
    // There is no single ME/TE to report, and picking one copy's numbers would
    // misdescribe the others — so the cell says how many and where to look.
    stubFetch(readyList([THREE_COPIES]))

    renderApp('/contracts')

    const link = await screen.findByRole('link', { name: '3 BPCs' })
    expect(link).toHaveAttribute('href', '/contracts/822')
  })

  it('leaves the blueprint cell empty for a contract offering no copy', async () => {
    // §8's third case. Empty, not a dash: a dash reads as "we looked and found
    // nothing", and there was nothing to look for.
    stubFetch(readyList([ROW]))

    renderApp('/contracts')

    await screen.findByText('Tristan')
    expect(blueprintCell(/Tristan/)).toBe('')
  })

  it('omits the blueprint column entirely while the corpus is still being enriched', async () => {
    // Omitted rather than emptied: runs/ME/TE are NULL for most of the corpus
    // mid-resweep, and a column blank down its whole length reads as breakage.
    stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([ONE_COPY])))))

    renderApp('/contracts')

    await screen.findByText('Draugur Blueprint')
    expect(headerNames()).not.toContain('Blueprint')
  })

  it('gives the auction segment the blueprint column too, and the courier segment never', async () => {
    // §8: blueprint columns are per-row content within the two item-bearing
    // segments, not a segment of their own. A courier carries no items at all.
    stubFetch(withTaxonomy(anonymousMe(segmentedPage), READY_TAXONOMY))

    const auction = renderApp('/contracts?contract_type=auction')
    await screen.findByText('Vargur')
    expect(headerNames()).toContain('Blueprint')
    auction.unmount()
    vi.unstubAllGlobals()

    stubFetch(withTaxonomy(anonymousMe(segmentedPage), READY_TAXONOMY))
    renderApp('/contracts?contract_type=courier')
    await screen.findByText('Jita to Amarr rush')
    expect(headerNames()).not.toContain('Blueprint')
  })

  it('describes a mixed lot by category instead of only counting the rest of it', async () => {
    // Criterion 6.1: a bare "+2 more" says how much is in the bundle and
    // nothing about what — the breakdown is what lets a reader judge it.
    const bundle = {
      ...ROW,
      contract_id: 833,
      primary_label: 'Myrmidon',
      composition: {
        categories: [
          { category_id: 7, name: 'Module', item_row_count: 3 },
          { category_id: 6, name: 'Ship', item_row_count: 1 },
        ],
        total_item_rows: 4,
        total_volume: 120_000,
      },
    }
    stubFetch(readyList([bundle]))

    renderApp('/contracts')

    await screen.findByText('Myrmidon')
    expect(screen.getByText('3 Modules · 1 Ship · 120,000 m³')).toBeInTheDocument()
    expect(screen.queryByText('+3 more')).not.toBeInTheDocument()
  })

  it('falls back to the bundle count while the categories are still being named', async () => {
    // Mid-resweep the categories are mostly unnamed, so the breakdown would
    // read "4 other" — less than the count it replaced.
    const bundle = {
      ...ROW,
      contract_id: 844,
      primary_label: 'Myrmidon',
      composition: {
        categories: [{ category_id: null, name: null, item_row_count: 4 }],
        total_item_rows: 4,
        total_volume: 120_000,
      },
    }
    stubFetch(withTaxonomy(anonymousMe(() => jsonResponse(listPage([bundle])))))

    renderApp('/contracts')

    await screen.findByText('Myrmidon')
    expect(screen.getByText('+3 more')).toBeInTheDocument()
  })
})

describe('ContractDetailPage item sides', () => {
  const OFFERED = {
    record_id: 1,
    type_id: 587,
    quantity: 1,
    is_included: true,
    type_name: 'Rifter',
    category: 'ship',
  }
  const REQUESTED = {
    record_id: 2,
    type_id: 34,
    quantity: 1_000_000,
    is_included: false,
    type_name: 'Tritanium',
  }

  it('renders what is offered and what is asked for as two separate lists', async () => {
    // Criterion 8.1. Merged, the two sides read as one inventory and a
    // want-to-buy contract looks like a sale of the thing it wants to buy.
    stubFetch(anonymousMe(() => jsonResponse({ ...CONTRACT, items: [OFFERED, REQUESTED] })))

    renderApp('/contracts/101')

    const offered = within(await screen.findByRole('region', { name: /^Offered/ }))
    expect(offered.getByText(/Rifter/)).toBeInTheDocument()
    expect(offered.queryByText(/Tritanium/)).not.toBeInTheDocument()

    const requested = within(screen.getByRole('region', { name: /^Requested/ }))
    expect(requested.getByText(/Tritanium/)).toBeInTheDocument()
    expect(requested.queryByText(/Rifter/)).not.toBeInTheDocument()
  })

  it('renders the requested side of a want-to-buy contract that offers nothing', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ ...CONTRACT, items: [REQUESTED] })))

    renderApp('/contracts/101')

    const requested = within(await screen.findByRole('region', { name: /^Requested/ }))
    expect(requested.getByText(/Tritanium/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: /^Offered/ })).not.toBeInTheDocument()
  })

  it('names an unresolved requested item by its type id rather than dropping the row', async () => {
    // The A7 completion-predicate widening guarantees a route back for a
    // contract whose requested item failed name resolution; until it lands,
    // the row must still say something rather than vanish.
    stubFetch(
      anonymousMe(() =>
        jsonResponse({ ...CONTRACT, items: [{ ...REQUESTED, type_name: null }] }),
      ),
    )

    renderApp('/contracts/101')

    const requested = within(await screen.findByRole('region', { name: /^Requested/ }))
    expect(requested.getByText(/Type 34/)).toBeInTheDocument()
  })

  it('shows each offered copy’s terms, so the row’s "N BPCs" link answers what it raises', async () => {
    stubFetch(
      anonymousMe(() =>
        jsonResponse({
          ...CONTRACT,
          items: [
            { ...OFFERED, record_id: 3, type_name: 'Draugur Blueprint', category: null, is_blueprint_copy: true, runs: 10, material_efficiency: 4, time_efficiency: 8 },
            { ...OFFERED, record_id: 4, type_name: 'Phoenix Blueprint', category: null, is_blueprint_copy: true, runs: 3, material_efficiency: 2, time_efficiency: 0 },
          ],
        }),
      ),
    )

    renderApp('/contracts/101')

    const offered = within(await screen.findByRole('region', { name: /^Offered/ }))
    expect(offered.getByText('10 runs · ME 4 · TE 8')).toBeInTheDocument()
    expect(offered.getByText('3 runs · ME 2 · TE 0')).toBeInTheDocument()
  })
})
