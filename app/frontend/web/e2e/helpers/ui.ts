import type { Page } from '@playwright/test'

/**
 * Below the `lg` breakpoint the filter rail collapses behind a "Filters"
 * disclosure button (single DOM instance, aria-expanded). Call this after the
 * page has rendered (await a heading or row first) and before touching any
 * filter control, so the same spec runs on both the desktop and mobile
 * projects. On desktop the button doesn't exist and this is a no-op.
 */
export async function openFiltersIfCollapsed(page: Page): Promise<void> {
  const toggle = page.getByRole('button', { name: 'Filters', exact: true })
  if ((await toggle.count()) === 0) return
  if ((await toggle.getAttribute('aria-expanded')) === 'false') {
    await toggle.click()
  }
}

/** Row links inside the results table (one link per contract row). */
export function rowLinks(page: Page) {
  return page.getByRole('region', { name: 'Contract results' }).getByRole('link')
}
