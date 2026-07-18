// ABOUTME: Automated axe accessibility checks for the saved-searches page — authed-with-data and anonymous states.
// ABOUTME: Mirrors src/features/contracts/components/a11y.test.tsx (vitest-axe on the designed UI, design §6).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { axe } from 'vitest-axe'
import * as matchers from 'vitest-axe/matchers'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

expect.extend(matchers)

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const SAVED = [
  { id: 1, name: 'Cheap frigates', search_parameters: { ships_only: true, min_price: 0, max_price: 5000000, size: 50, sort_by: 'price', sort_direction: 'asc' }, created_at: '2026-07-17T00:00:00Z', updated_at: '2026-07-17T00:00:00Z' },
]

function stubFetch(handler: (url: string) => Response) {
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    return handler(url)
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('accessibility (axe) — saved searches', () => {
  it('authed list view has no violations', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 0, page: 1, size: 1, items: [] })
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse(SAVED)
      return jsonResponse([])
    })
    const { container } = renderApp('/saved-searches')
    await screen.findByText('Cheap frigates')
    expect(await axe(container)).toHaveNoViolations()
  })

  it('anonymous sign-in prompt has no violations', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauthenticated' }, 401) : jsonResponse([])))
    const { container } = renderApp('/saved-searches')
    await screen.findByRole('heading', { name: /sign in to use saved searches/i })
    expect(await axe(container)).toHaveNoViolations()
  })
})
