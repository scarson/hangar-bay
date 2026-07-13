// Automated accessibility assertions on the two key views (M1 spec Testing
// posture: vitest-axe on list + detail once the designed UI exists).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { axe } from 'vitest-axe'
import * as matchers from 'vitest-axe/matchers'
import { anonymousMe, jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

expect.extend(matchers)

const CONTRACT = {
  contract_id: 101,
  issuer_id: 1,
  issuer_corporation_id: 101,
  start_location_id: 60003760,
  type: 'item_exchange',
  status: 'outstanding',
  title: 'Tristan for Sale',
  for_corporation: false,
  date_issued: '2026-07-01T00:00:00Z',
  date_expired: '2030-07-08T00:00:00Z',
  price: 1000000,
  start_location_name: 'Jita IV - Moon 4 - Caldari Navy Assembly Plant',
  issuer_name: 'Test Pilot',
  issuer_corporation_name: 'Test Corp',
  is_ship_contract: true,
  items: [
    {
      record_id: 1011,
      type_id: 587,
      quantity: 1,
      is_included: true,
      is_singleton: false,
      is_blueprint_copy: false,
      type_name: 'Tristan',
    },
  ],
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
    stubFetch(anonymousMe(() => jsonResponse({ total: 1, page: 1, size: 50, items: [CONTRACT] })))
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

  it('empty and error states have no violations', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ total: 0, page: 1, size: 50, items: [] })))
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
