import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderApp } from './test/renderApp'

describe('route skeleton', () => {
  it('redirects / to /contracts', async () => {
    const { router } = renderApp('/')
    await screen.findByText(/Task 8/)
    expect(router.state.location.pathname).toBe('/contracts')
  })

  it('renders the contract detail route', async () => {
    renderApp('/contracts/12345')
    await screen.findByText(/detail/i)
  })
})
