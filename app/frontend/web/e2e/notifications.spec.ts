import { expect, test } from '@playwright/test'
import { SEVEN_SHIPS, pageOf } from './fixtures/contracts'
import { makeCurrentUser } from './fixtures/auth'
import { makeNotification } from './fixtures/account'
import { interceptContractList, interceptCurrentUser, interceptNotifications, stubPortraits } from './helpers/api'

test.describe('notifications', () => {
  test('header bell renders the unread count from total', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    await interceptNotifications(page, { unread: 4 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    await stubPortraits(page)

    await page.goto('/contracts')
    const bell = page.getByRole('link', { name: /notifications \(4 unread\)/i })
    await expect(bell).toBeVisible()
    await expect(bell).toContainText('4')
  })

  test('notifications page lists rows (after skeleton unmount) and marks all read', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser())
    const calls = await interceptNotifications(page, {
      items: [makeNotification({ id: 1, message: 'Rifter available in an auction priced 900,000 ISK' })],
      unread: 1,
    })
    await stubPortraits(page)

    await page.goto('/notifications')
    // TEST-8: the loading skeleton (role=status "Loading notifications") must unmount before the list
    // shows. `interceptNotifications` resolves instantly, so asserting the skeleton *visible* first
    // would race the fixture; instead use the loaded row as the deterministic synchronization gate,
    // then assert the skeleton has detached (a non-vacuous check now that content is confirmed loaded).
    // Do NOT weaken this to a bare toHaveCount(0) before the row renders (TEST-2 / TEST-8).
    await expect(page.getByText(/rifter available/i)).toBeVisible()
    await expect(page.getByRole('status', { name: 'Loading notifications' })).toHaveCount(0)

    await page.getByRole('button', { name: /mark all as read/i }).click()
    await expect.poll(() => calls.some((c) => /\/mark-all-read$/.test(c.url.pathname) && c.method === 'POST')).toBe(true)
  })

  test('anonymous /notifications shows the sign-in prompt', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await page.goto('/notifications')
    await expect(page.getByRole('heading', { name: /sign in to use notifications/i })).toBeVisible()
  })
})
