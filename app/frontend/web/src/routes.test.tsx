import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { anonymousMe, jsonResponse } from './test/http'
import { renderApp } from './test/renderApp'

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

describe('route skeleton', () => {
  it('redirects / to /contracts', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ total: 0, page: 1, size: 50, items: [] })))
    const { router } = renderApp('/')
    await screen.findByRole('heading', { name: /ship contracts/i })
    expect(router.state.location.pathname).toBe('/contracts')
  })

  it('renders the contract detail route', async () => {
    stubFetch(anonymousMe(() => jsonResponse({ detail: 'Contract not found' }, 404)))
    renderApp('/contracts/12345')
    await screen.findByText(/not found/i)
  })
})
