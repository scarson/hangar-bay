// ABOUTME: Automated axe accessibility checks for the watchlist page — authed-with-data and anonymous states.
// ABOUTME: Mirrors src/features/contracts/components/a11y.test.tsx (vitest-axe on the designed UI, design §6).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { axe } from 'vitest-axe'
import * as matchers from 'vitest-axe/matchers'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

expect.extend(matchers)

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const ROWS = [{ id: 1, type_id: 587, type_name: 'Rifter', max_price: 5000000, notes: 'cheap', created_at: 'x', updated_at: 'x' }]

function stubFetch(handler: (url: string) => Response) {
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    return handler(url)
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('accessibility (axe) — watchlist', () => {
  it('authed list view has no violations', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/watchlist-items\//.test(url)) return jsonResponse(ROWS)
      return jsonResponse([])
    })
    const { container } = renderApp('/watchlist')
    await screen.findByText('Rifter')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('anonymous sign-in prompt has no violations', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauth' }, 401) : jsonResponse([])))
    const { container } = renderApp('/watchlist')
    await screen.findByRole('heading', { name: /sign in to use your watchlist/i })
    expect(await axe(container)).toHaveNoViolations()
  })
})
