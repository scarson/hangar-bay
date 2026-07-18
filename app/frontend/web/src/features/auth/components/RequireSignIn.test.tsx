// ABOUTME: RequireSignIn renders the sign-in prompt; its login href mirrors HeaderIdentity (next=encoded path+search, sso stripped).
import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { createMemoryHistory, createRootRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { RequireSignIn } from './RequireSignIn'

afterEach(cleanup)

function renderAt(initialUrl: string) {
  const rootRoute = createRootRoute({ component: () => <RequireSignIn feature="saved searches" /> })
  const router = createRouter({
    routeTree: rootRoute,
    history: createMemoryHistory({ initialEntries: [initialUrl] }),
  })
  render(<RouterProvider router={router} />)
}

describe('RequireSignIn', () => {
  it('renders a prompt naming the feature and a login link with the encoded next', async () => {
    renderAt('/saved-searches?foo=bar')
    expect(await screen.findByRole('heading', { name: /sign in to use saved searches/i })).toBeInTheDocument()
    const link = screen.getByRole('link', { name: /log in with eve/i })
    const next = encodeURIComponent('/saved-searches?foo=bar')
    expect(link).toHaveAttribute('href', `/api/v1/auth/sso/login?next=${next}`)
  })

  it('strips a transient ?sso flag out of the encoded next', async () => {
    renderAt('/saved-searches?sso=denied&foo=bar')
    const link = await screen.findByRole('link', { name: /log in with eve/i })
    const next = encodeURIComponent('/saved-searches?foo=bar')
    expect(link).toHaveAttribute('href', `/api/v1/auth/sso/login?next=${next}`)
    // The href legitimately contains "/auth/sso/login", so `.not.toContain('sso')` could never pass.
    // The thing that must be stripped is the transient `sso` QUERY param inside `next` — parse the
    // URL and assert the DECODED next carries no `sso=`, while the endpoint path is untouched.
    const href = link.getAttribute('href')!
    expect(href.startsWith('/api/v1/auth/sso/login')).toBe(true)
    const decodedNext = decodeURIComponent(new URL(href, 'https://localhost:5173').searchParams.get('next')!)
    expect(decodedNext).not.toContain('sso=')
  })
})
