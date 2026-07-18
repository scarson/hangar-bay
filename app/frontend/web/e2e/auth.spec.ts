import { expect, test } from '@playwright/test'
import { SEVEN_SHIPS, pageOf } from './fixtures/contracts'
import { makeCurrentUser } from './fixtures/auth'
import { interceptContractList, interceptCurrentUser, interceptLogout, stubPortraits } from './helpers/api'

test.describe('SSO header identity', () => {
  test('anonymous header shows a login link with the encoded next', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    await page.goto('/contracts?is_bpc=true')
    const login = page.getByRole('link', { name: /log in with eve/i })
    await expect(login).toBeVisible()
    // The /contracts route's validateSearch defaults every field (page, size,
    // sort_by, …) and the router writes the fully-resolved search back onto the
    // URL, so "next" carries that resolved query, not the bare '?is_bpc=true'
    // that was typed in (same root cause as the equivalent vitest assertion in
    // HeaderIdentity.test.tsx — verified against this app's own URL-normalizing
    // behavior, e.g. sorting.spec.ts's bare goto('/contracts') asserting
    // sort_by/sort_direction land in the URL).
    const url = new URL(page.url())
    const expectedNext = encodeURIComponent(url.pathname + url.search)
    await expect(login).toHaveAttribute('href', '/api/v1/auth/sso/login?next=' + expectedNext)
    expect(expectedNext).toContain('is_bpc%3Dtrue')
  })

  test('authenticated header shows portrait, name, and logout', async ({ page }) => {
    await interceptCurrentUser(page, makeCurrentUser({ character_name: 'Sesta Hound' }))
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    await stubPortraits(page)   // keep the fixture lane offline — portrait is an external CDN URL
    await page.goto('/contracts')
    await expect(page.getByText('Sesta Hound')).toBeVisible()
    // The portrait is decorative (alt="") so it exposes NO accessible role — this CSS
    // attribute selector is the sanctioned exception to the role/label-selectors rule
    // (same rationale as the HeaderIdentity vitest test).
    await expect(page.locator('img[src*="images.evetech.net"]')).toHaveAttribute('src', /characters\/91000001\/portrait\?size=64/)
    await expect(page.getByRole('button', { name: /log out/i })).toBeVisible()
  })

  test('logout POSTs exactly once and returns to anonymous', async ({ page }) => {
    let authed = true
    await page.route(/\/api\/v1\/me$/, async (route) => {
      await route.fulfill({
        status: authed ? 200 : 401,
        contentType: 'application/json',
        body: JSON.stringify(authed ? makeCurrentUser() : { detail: 'unauthenticated' }),
      })
    })
    // Flip to anonymous INSIDE the logout handler, before the 204 is fulfilled: the
    // /me refetch can only fire after the 204, so it always observes authed=false.
    // A post-click flip in Node would race the in-page refetch (retries are 0 and
    // TEST-2 forbids masking timing flakes).
    const logoutCalls = await interceptLogout(page, () => {
      authed = false
    })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    await stubPortraits(page)   // authenticated render → portrait request; stay offline
    await page.goto('/contracts')
    await page.getByRole('button', { name: /log out/i }).click()
    // Assert the POST landed (204) BEFORE asserting the transition, so the test
    // cannot pass on a logout that never reached the backend.
    await expect.poll(() => logoutCalls.length).toBe(1)
    expect(logoutCalls[0].method).toBe('POST')
    await expect(page.getByRole('link', { name: /log in with eve/i })).toBeVisible()
  })

  test('?sso=denied renders a dismissible notice', async ({ page }) => {
    await interceptCurrentUser(page, { status: 401 })
    await interceptContractList(page, pageOf(SEVEN_SHIPS))
    await page.goto('/contracts?sso=denied')
    await expect(page.getByText(/cancelled/i)).toBeVisible()
    await page.getByRole('button', { name: /dismiss/i }).click()
    await expect(page).not.toHaveURL(/sso=denied/)
    await expect(page.getByText(/cancelled/i)).toHaveCount(0)
  })
})
