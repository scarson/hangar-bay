import { expect, test } from '@playwright/test'
import { makeCurrentUser } from './fixtures/auth'
import { makeWatchlistItem } from './fixtures/account'
import { interceptCurrentUser, interceptNotifications, interceptWatchlist, stubPortraits } from './helpers/api'

test.describe('watchlist', () => {
  test('anonymous /watchlist shows the sign-in prompt', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await page.goto('/watchlist')
    await expect(page.getByRole('heading', { name: /sign in to use your watchlist/i })).toBeVisible()
  })

  test('add-by-name POSTs the exact wire payload', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 0 })
    const calls = await interceptWatchlist(page, [])
    await stubPortraits(page)

    await page.goto('/watchlist')
    await page.getByLabel(/ship name/i).fill('Maelstrom')
    await page.getByLabel(/max price/i).fill('300000000')
    await page.getByLabel(/notes/i).fill('flagship')
    await page.getByRole('button', { name: /add to watchlist/i }).click()

    await expect.poll(() => calls.filter((c) => c.method === 'POST').length).toBe(1)
    expect(calls.find((c) => c.method === 'POST')!.body).toEqual({ type_name: 'Maelstrom', max_price: 300000000, notes: 'flagship' })
  })

  test('two-step remove DELETEs only after confirm', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 0 })
    const calls = await interceptWatchlist(page, [makeWatchlistItem({ id: 1, type_name: 'Rifter' })])
    await stubPortraits(page)

    await page.goto('/watchlist')
    // `exact` pins this to the row's name span; the row's sr-only a11y labels ("Max price for Rifter",
    // "Notes for Rifter") also contain "Rifter", and getByText substring-matches by default.
    await expect(page.getByText('Rifter', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: /^remove$/i }).click()
    expect(calls.filter((c) => c.method === 'DELETE')).toHaveLength(0)
    await page.getByRole('button', { name: /confirm remove/i }).click()
    await expect.poll(() => calls.filter((c) => c.method === 'DELETE').length).toBe(1)
  })
})
