// ABOUTME: Automated axe accessibility checks for the notifications page — authed-with-data and anonymous states.
// ABOUTME: Mirrors src/features/contracts/components/a11y.test.tsx (vitest-axe on the designed UI, design §6).
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { axe } from 'vitest-axe'
import * as matchers from 'vitest-axe/matchers'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

expect.extend(matchers)

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const NOTE = {
  id: 1, type: 'watchlist_match', message: 'Rifter available in an auction priced 900,000 ISK in Jita IV - Moon 4',
  contract_id: 101, watch_type_id: 587, price: 900000, is_read: false, created_at: '2026-07-17T11:00:00Z',
}

function stubFetch(handler: (url: string) => Response) {
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    return handler(url)
  })
}

afterEach(() => vi.unstubAllGlobals())

describe('accessibility (axe) — notifications', () => {
  it('authed list view has no violations', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/notification-settings/.test(url)) return jsonResponse({ watchlist_alerts_enabled: true })
      if (/is_read=false&size=1/.test(url)) return jsonResponse({ total: 1, page: 1, size: 1, items: [] })
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 1, page: 1, size: 20, items: [NOTE] })
      return jsonResponse({}, 404)
    })
    const { container } = renderApp('/notifications')
    await screen.findByText(/rifter available/i)
    expect(await axe(container)).toHaveNoViolations()
  })

  it('anonymous sign-in prompt has no violations', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauth' }, 401) : jsonResponse({ total: 0, page: 1, size: 20, items: [] })))
    const { container } = renderApp('/notifications')
    await screen.findByRole('heading', { name: /sign in to use notifications/i })
    expect(await axe(container)).toHaveNoViolations()
  })
})
