// ABOUTME: SaveSearchControl integration over the real /contracts route — hidden when anonymous; posts search-minus-page; 409 inline.
// ABOUTME: Asserts the POSTed wire payload (TEST-5), incl. the sub-MIN_SEARCH_LENGTH search-drop that mirrors toApiQuery.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { anonymousMe, emptyContractPage, jsonResponse } from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

interface Call { url: string; method?: string; body?: string }

const AUTHED = { character_id: 91000001, character_name: 'Sesta Hound' }
const EMPTY_PAGE = emptyContractPage()

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

afterEach(() => vi.unstubAllGlobals())

describe('SaveSearchControl', () => {
  it('is hidden for anonymous users', async () => {
    stubFetch(anonymousMe(() => jsonResponse(EMPTY_PAGE)))
    renderApp('/contracts')
    await screen.findByRole('heading', { level: 1, name: /ship contracts/i })
    expect(screen.queryByRole('button', { name: /save search/i })).not.toBeInTheDocument()
  })

  it('posts search-minus-page with the correct wire payload', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse({ id: 1, name: 'Cheap', search_parameters: {}, created_at: 'x', updated_at: 'x' }, 201)
      return jsonResponse(EMPTY_PAGE)
    })
    renderApp('/contracts?min_price=1000&contract_type=auction&sort_by=price&sort_direction=asc')
    await userEvent.click(await screen.findByRole('button', { name: /save search/i }))
    await userEvent.type(screen.getByLabelText(/search name/i), 'Cheap')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')).toBe(true))
    const post = calls.find((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')!
    const payload = JSON.parse(post.body!)
    expect(payload.name).toBe('Cheap')
    expect(payload.search_parameters).toMatchObject({
      min_price: 1000,
      contract_type: ['auction'],
      ships_only: true,
      sort_by: 'price',
      sort_direction: 'asc',
    })
    expect(payload.search_parameters).not.toHaveProperty('page')
  })

  it('persists an item-less segment and the widening it forces, so applying it restores the same view', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse({ id: 1, name: 'Hauls', search_parameters: {}, created_at: 'x', updated_at: 'x' }, 201)
      return jsonResponse(EMPTY_PAGE)
    })
    renderApp('/contracts?contract_type=courier&ships_only=false')
    await userEvent.click(await screen.findByRole('button', { name: /save search/i }))
    await userEvent.type(screen.getByLabelText(/search name/i), 'Hauls')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')).toBe(true))
    const post = calls.find((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')!
    // Dropping the segment while keeping ships_only:false would persist a strictly
    // WIDER view than the one saved: every type, ships-only off.
    expect(JSON.parse(post.body!).search_parameters).toMatchObject({
      contract_type: ['courier'],
      ships_only: false,
    })
  })

  it('drops a sub-3-character search from the persisted payload (mirrors toApiQuery)', async () => {
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse({ id: 1, name: 'x', search_parameters: {}, created_at: 'x', updated_at: 'x' }, 201)
      return jsonResponse(EMPTY_PAGE)
    })
    renderApp('/contracts?search=ab')
    await userEvent.click(await screen.findByRole('button', { name: /save search/i }))
    await userEvent.type(screen.getByLabelText(/search name/i), 'Typo hunt')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')).toBe(true))
    const post = calls.find((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')!
    expect(JSON.parse(post.body!).search_parameters).not.toHaveProperty('search')
  })

  it('persists the taxonomy and blueprint filters, which were unsaveable while inert', async () => {
    // F008 §14 / decision log D4: the blob deliberately rejected the ME/TE
    // params for as long as they filtered nothing. They filter now, so a saved
    // search that omitted them would restore a strictly wider view than the one
    // the reader saved — the same defect the courier case above pins.
    const calls = stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse({ id: 1, name: 'BPCs', search_parameters: {}, created_at: 'x', updated_at: 'x' }, 201)
      return jsonResponse(EMPTY_PAGE)
    })
    renderApp(
      '/contracts?category_id=9&group_id=105&min_runs=1&max_runs=20&min_me=2&max_me=10&min_te=4&max_te=20',
    )
    await userEvent.click(await screen.findByRole('button', { name: /save search/i }))
    await userEvent.type(screen.getByLabelText(/search name/i), 'BPCs')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    await waitFor(() => expect(calls.some((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')).toBe(true))
    const post = calls.find((c) => /\/me\/saved-searches\//.test(c.url) && c.method === 'POST')!
    expect(JSON.parse(post.body!).search_parameters).toMatchObject({
      category_id: [9],
      group_id: [105],
      min_runs: 1,
      max_runs: 20,
      min_me: 2,
      max_me: 10,
      min_te: 4,
      max_te: 20,
    })
  })

  it('renders an inline error when the name conflicts (409)', async () => {
    stubFetch((url) => {
      if (/\/api\/v1\/me$/.test(url)) return jsonResponse(AUTHED)
      if (/\/me\/saved-searches\//.test(url)) return jsonResponse({ detail: 'duplicate' }, 409)
      return jsonResponse(EMPTY_PAGE)
    })
    renderApp('/contracts')
    await userEvent.click(await screen.findByRole('button', { name: /save search/i }))
    await userEvent.type(screen.getByLabelText(/search name/i), 'Dupe')
    await userEvent.click(screen.getByRole('button', { name: /^save$/i }))
    expect(await screen.findByText(/name already exists/i)).toBeInTheDocument()
  })
})
