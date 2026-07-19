// ABOUTME: NotificationBell over the real header — Link to /notifications with an unread badge; badge hidden at zero.
// ABOUTME: aria-label announces the unread count; zero-count renders the link but no numeric badge.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }

function stubFetch(unreadTotal: number) {
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : (input as Request).url
    if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
    if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: unreadTotal, page: 1, size: 1, items: [] })
    return jsonResponse({ total: 0, page: 1, size: 50, items: [] })
  })
}
afterEach(() => vi.unstubAllGlobals())

describe('NotificationBell', () => {
  it('links to /notifications and shows the unread count in the accessible name and badge', async () => {
    stubFetch(3)
    renderApp('/contracts')
    const bell = await screen.findByRole('link', { name: /notifications \(3 unread\)/i })
    expect(bell).toHaveAttribute('href', '/notifications')
    expect(bell).toHaveTextContent('3')
  })

  it('renders no numeric badge when there are zero unread', async () => {
    stubFetch(0)
    renderApp('/contracts')
    const bell = await screen.findByRole('link', { name: /notifications \(0 unread\)/i })
    expect(bell).not.toHaveTextContent('0')
  })
})
