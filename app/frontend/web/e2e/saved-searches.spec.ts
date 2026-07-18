import { expect, test } from '@playwright/test'
import { SEVEN_SHIPS, pageOf } from './fixtures/contracts'
import { makeCurrentUser } from './fixtures/auth'
import { makeSavedSearch } from './fixtures/account'
import { interceptContractList, interceptCurrentUser, interceptNotifications, interceptSavedSearches, stubPortraits } from './helpers/api'

test.describe('saved searches', () => {
  test('anonymous /saved-searches shows the sign-in prompt', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await page.goto('/saved-searches')
    await expect(page.getByRole('heading', { name: /sign in to use saved searches/i })).toBeVisible()
    // The header banner also renders a "Log in with EVE" link for anonymous users, so scope
    // this assertion to the main content region where the RequireSignIn prompt lives.
    await expect(page.getByRole('main').getByRole('link', { name: /log in with eve/i })).toBeVisible()
  })

  test('authed user saves the current search and the POST carries search-minus-page', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 0 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    const calls = await interceptSavedSearches(page, [])
    await stubPortraits(page)

    await page.goto('/contracts?min_price=1000&sort_by=price&sort_direction=asc')
    await page.getByRole('button', { name: /save search/i }).click()
    await page.getByLabel(/search name/i).fill('Cheap ships')
    await page.getByRole('button', { name: /^save$/i }).click()

    await expect.poll(() => calls.filter((c) => c.method === 'POST').length).toBe(1)
    const post = calls.find((c) => c.method === 'POST')!
    const body = post.body as { name: string; search_parameters: Record<string, unknown> }
    expect(body.name).toBe('Cheap ships')
    expect(body.search_parameters).toMatchObject({ min_price: 1000, ships_only: true, sort_by: 'price', sort_direction: 'asc' })
    expect(body.search_parameters).not.toHaveProperty('page')
  })

  test('authed header nav exposes both account links and reaches saved searches', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 0 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    await interceptSavedSearches(page, [makeSavedSearch({ name: 'Cheap frigates' })])
    await stubPortraits(page)

    await page.goto('/contracts')
    const nav = page.getByRole('navigation', { name: /account/i })
    await expect(nav.getByRole('link', { name: /saved searches/i })).toBeVisible()
    await expect(nav.getByRole('link', { name: /watchlist/i })).toBeVisible()

    await nav.getByRole('link', { name: /saved searches/i }).click()
    await expect(page).toHaveURL(/\/saved-searches$/)
    await expect(page.getByRole('heading', { level: 1, name: /saved searches/i })).toBeVisible()
  })

  test('authed /saved-searches lists a saved search and applies it', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 0 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    await interceptSavedSearches(page, [makeSavedSearch({ name: 'Cheap frigates' })])
    await stubPortraits(page)

    await page.goto('/saved-searches')
    await expect(page.getByText('Cheap frigates')).toBeVisible()
    await page.getByRole('button', { name: /apply/i }).click()
    await expect(page).toHaveURL(/\/contracts\?/)
    await expect(page).toHaveURL(/sort_by=price/)
  })
})
