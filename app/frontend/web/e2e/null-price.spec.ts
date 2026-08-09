import { expect, test } from '@playwright/test'
import { expiryInDays, makeContract, makeShipItem, pageOf } from './fixtures/contracts'
import { interceptContractList, interceptCurrentUser, interceptTaxonomy } from './helpers/api'

/**
 * The price-nullable journey PR #156 deferred.
 *
 * ESI marks `price` optional and migration f2a91c3b7e04 made the column nullable,
 * so `WireContract.price` is `number | null` — but until now NO fixture anywhere
 * assigned it null. That had two consequences: the null branch of the list and
 * detail price rendering was never walked end to end, and the wire type itself was
 * unpinned (narrowing it back to `number` typechecked cleanly, because nothing
 * contradicted it).
 *
 * This fixture is what makes the nullable type load-bearing. A dash is not an
 * amount of ISK, so an unpriced contract must render the same bare placeholder the
 * rest of the surface uses rather than "0 ISK" — which would be a price, and a
 * wrong one.
 */
const UNPRICED = makeContract({
  contract_id: 232_900_001,
  price: null,
  date_issued: '2026-06-30T00:00:00Z',
  date_expired: expiryInDays(21),
  items: [makeShipItem('Rifter')],
})

const PRICED = makeContract({
  contract_id: 232_900_002,
  price: 12_500_000,
  date_issued: '2026-06-29T00:00:00Z',
  date_expired: expiryInDays(20),
  items: [makeShipItem('Tristan')],
})

test.beforeEach(async ({ page }) => {
  await interceptCurrentUser(page, { status: 401 })
  await interceptTaxonomy(page)
  await interceptContractList(page, () => pageOf([UNPRICED, PRICED]))
})

test('a contract with no price renders a dash, not a zero', async ({ page }) => {
  await page.goto('/contracts')

  const unpricedRow = page.getByRole('row').filter({ hasText: 'Rifter' })
  await expect(unpricedRow).toBeVisible()

  // The priced sibling proves the column is rendering at all, so the assertion
  // below cannot pass because the whole cell is missing.
  const pricedRow = page.getByRole('row').filter({ hasText: 'Tristan' })
  await expect(pricedRow).toContainText('12,500,000')

  await expect(unpricedRow).not.toContainText('0 ISK')
  await expect(unpricedRow).toContainText('—')
})
