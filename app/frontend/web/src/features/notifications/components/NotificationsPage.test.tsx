// ABOUTME: NotificationsPage tests over the real /notifications route — auth branches, mark-read on click, pagination, mark-all-read, settings toggle.
// ABOUTME: Asserts mark-read/mark-all-read/settings wire calls (TEST-5); TEST-8 skeleton-unmount sync before list assertions.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, waitForElementToBeRemoved } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const N = (over: Record<string, unknown> = {}) => ({
  id: 1, type: 'watchlist_match', message: 'Rifter available in an auction priced 900,000 ISK in Jita IV - Moon 4',
  contract_id: 101, watch_type_id: 587, price: 900000, is_read: false, created_at: '2026-07-17T11:00:00Z', ...over,
})

interface Call { url: string; method?: string; body?: string }
function stubFetch(handler: (url: string, call: Call) => Response): Call[] {
  const calls: Call[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
    const req = input as Request
    const url = req.url ?? String(input)
    const call: Call = { url, method: req.method ?? init?.method, body: await req.clone().text() }
    calls.push(call)
    return handler(url, call)
  })
  return calls
}
// Route notifications endpoints; the list vs count vs settings vs mark endpoints share a prefix.
function notificationsHandler(unread: typeof N extends never ? never : ReturnType<typeof N>[], settings = { watchlist_alerts_enabled: true }) {
  return (url: string): Response | null => {
    if (/\/me\/notification-settings/.test(url)) return jsonResponse(settings)
    if (/\/me\/notifications\/mark-all-read/.test(url)) return new Response(null, { status: 204 })
    if (/\/me\/notifications\/\d+\/mark-read/.test(url)) return new Response(null, { status: 204 })
    if (/is_read=false&size=1/.test(url) || /size=1&is_read=false/.test(url)) return jsonResponse({ total: unread.length, page: 1, size: 1, items: [] })
    if (/\/me\/notifications\//.test(url)) {
      const u = new URL(url)
      const page = Number(u.searchParams.get('page') ?? '1')
      return jsonResponse({ total: unread.length, page, size: 20, items: unread })
    }
    return null
  }
}
afterEach(() => vi.unstubAllGlobals())

describe('NotificationsPage', () => {
  it('prompts anonymous users to sign in', async () => {
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauth' }, 401) : jsonResponse({ total: 0, page: 1, size: 20, items: [] })))
    renderApp('/notifications')
    expect(await screen.findByRole('heading', { name: /sign in to use notifications/i })).toBeInTheDocument()
  })

  it('lists notifications after the skeleton unmounts and links to the contract', async () => {
    const handle = notificationsHandler([N()])
    stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse(AUTHED) : (handle(url) ?? jsonResponse({}, 404))))
    renderApp('/notifications')
    const skeleton = await screen.findByRole('status', { name: /loading notifications/i })
    await waitForElementToBeRemoved(skeleton)
    expect(screen.getByText(/rifter available/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /rifter available/i })).toHaveAttribute('href', '/contracts/101')
  })

  it('marks a notification read on click', async () => {
    const handle = notificationsHandler([N()])
    const calls = stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse(AUTHED) : (handle(url) ?? jsonResponse({}, 404))))
    renderApp('/notifications')
    await screen.findByText(/rifter available/i)
    await userEvent.click(screen.getByRole('link', { name: /rifter available/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/notifications\/1\/mark-read/.test(c.url) && c.method === 'POST')).toBe(true))
  })

  it('requests page 2 when Next is clicked', async () => {
    const many = Array.from({ length: 25 }, (_, i) => N({ id: i + 1, message: `Alert ${i + 1}`, contract_id: null }))
    const handle = notificationsHandler(many)
    const calls = stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse(AUTHED) : (handle(url) ?? jsonResponse({}, 404))))
    renderApp('/notifications')
    await screen.findByText('Alert 1')
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/notifications\//.test(c.url) && /page=2/.test(c.url))).toBe(true))
  })

  it('marks all read', async () => {
    const handle = notificationsHandler([N()])
    const calls = stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse(AUTHED) : (handle(url) ?? jsonResponse({}, 404))))
    renderApp('/notifications')
    await screen.findByText(/rifter available/i)
    await userEvent.click(screen.getByRole('button', { name: /mark all as read/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/notifications\/mark-all-read/.test(c.url) && c.method === 'POST')).toBe(true))
  })

  it('toggles the watchlist-alerts setting (PUT body)', async () => {
    const handle = notificationsHandler([N()])
    const calls = stubFetch((url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse(AUTHED) : (handle(url) ?? jsonResponse({}, 404))))
    renderApp('/notifications')
    await screen.findByText(/rifter available/i)
    await userEvent.click(await screen.findByLabelText(/watchlist alerts/i))
    await waitFor(() => expect(calls.some((c) => /\/me\/notification-settings/.test(c.url) && c.method === 'PUT')).toBe(true))
    const put = calls.find((c) => /\/me\/notification-settings/.test(c.url) && c.method === 'PUT')!
    expect(JSON.parse(put.body!)).toEqual({ watchlist_alerts_enabled: false })
  })

  it('disables the watchlist-alerts toggle until settings load (no PUT before load)', async () => {
    const calls: Call[] = []
    vi.stubGlobal('fetch', async (input: RequestInfo | URL, init?: RequestInit) => {
      const req = input as Request
      const url = req.url ?? String(input)
      calls.push({ url, method: req.method ?? init?.method, body: await req.clone().text() })
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      // Settings GET never resolves → useNotificationSettings stays isPending → the checkbox is disabled.
      if (/\/me\/notification-settings/.test(url)) return new Promise<Response>(() => {})
      if (/\/me\/notifications\//.test(url)) return jsonResponse({ total: 1, page: 1, size: 20, items: [N()] })
      return jsonResponse({}, 404)
    })
    renderApp('/notifications')
    await screen.findByText(/rifter available/i)
    const toggle = screen.getByLabelText(/watchlist alerts/i)
    expect(toggle).toBeDisabled()
    await userEvent.click(toggle)   // disabled → no interaction, so no settings write
    expect(calls.some((c) => /\/me\/notification-settings/.test(c.url) && c.method === 'PUT')).toBe(false)
  })
})
