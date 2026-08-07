// Automated accessibility assertions on the two key views (M1 spec Testing
// posture: vitest-axe on list + detail once the designed UI exists).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { axe } from 'vitest-axe'
import * as matchers from 'vitest-axe/matchers'
import { anonymousMe, jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'
import { daysFromNow, minutesFromNow } from '../../../test/dates'

expect.extend(matchers)

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
  issuer_name: 'Test Pilot',
  issuer_corporation_name: 'Test Corp',
  is_ship_contract: true,
  is_blueprint_copy_contract: false,
  primary_label: 'Tristan',
  composition: null,
}

/** An item-less row, so the segmented view under test is one with a cleared ships-only. */
const COURIER_ROW = {
  ...ROW,
  contract_id: 505,
  type: 'courier',
  title: 'Jita to Amarr rush',
  is_ship_contract: false,
  primary_label: 'Jita to Amarr rush',
}

const CONTRACT = {
  ...ROW,
  items: [
    {
      record_id: 1011,
      type_id: 587,
      quantity: 1,
      is_included: true,
      is_blueprint_copy: false,
      type_name: 'Tristan',
    },
  ],
}

/** The list envelope, with the segment counts and coverage every response carries. */
function listPage(rows: { type: string }[]) {
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
  }
}

function stubFetch(handler: (url: string) => Response) {
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    return handler(url)
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('accessibility (axe)', () => {
  it('contract list view has no violations', async () => {
    stubFetch(anonymousMe(() => jsonResponse(listPage([ROW]))))
    const { container } = renderApp('/contracts')
    await screen.findByText('Tristan')

    expect(await axe(container)).toHaveNoViolations()
  })

  it('contract detail view has no violations', async () => {
    stubFetch(anonymousMe(() => jsonResponse(CONTRACT)))
    const { container } = renderApp('/contracts/101')
    await screen.findByRole('heading', { name: 'Tristan' })

    expect(await axe(container)).toHaveNoViolations()
  })

  it('the contract-type segments have no violations with one selected', async () => {
    // The segment toolbar exposes its selected state with aria-pressed on plain
    // buttons inside a labelled fieldset (Criterion 12), which axe checks for
    // name/role/value coherence as well as the surrounding grouping.
    stubFetch(anonymousMe(() => jsonResponse(listPage([COURIER_ROW]))))
    const { container } = renderApp('/contracts?contract_type=courier&ships_only=false')
    await screen.findByText('Jita to Amarr rush')

    expect(await axe(container)).toHaveNoViolations()
  })

  it('empty and error states have no violations', async () => {
    stubFetch(anonymousMe(() => jsonResponse(listPage([]))))
    const empty = renderApp('/contracts')
    await screen.findByText(/no contracts match/i)
    expect(await axe(empty.container)).toHaveNoViolations()
    empty.unmount()

    stubFetch(anonymousMe(() => jsonResponse({ detail: 'boom' }, 500)))
    const errored = renderApp('/contracts?search=xyz')
    await screen.findByRole('alert')
    expect(await axe(errored.container)).toHaveNoViolations()
  })
})
