// ABOUTME: Exercises contract filter controls through the real router and query layer.
// ABOUTME: Pins filter URL state and request parameters at the fetch boundary.
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  anonymousMe,
  emptyContractPage,
  jsonResponse,
  taxonomyResponse,
  withTaxonomy,
  type FetchHandler,
} from '../../../test/http'
import { renderApp } from '../../../test/renderApp'

const COMPLETE_EMPTY_TAXONOMY = taxonomyResponse({ coverage: 'complete' })

function stubFetch(handler: FetchHandler) {
  const calls: string[] = []
  vi.stubGlobal('fetch', async (input: RequestInfo | URL) => {
    const url =
      typeof input === 'string' ? input : input instanceof URL ? input.toString() : input.url
    calls.push(url)
    return handler(url)
  })
  return calls
}

function readyEmptyPage(taxonomy: unknown = COMPLETE_EMPTY_TAXONOMY) {
  return withTaxonomy(
    anonymousMe(() => jsonResponse(emptyContractPage())),
    taxonomy,
  )
}

function listCalls(calls: string[]) {
  return calls.filter((url) => /\/api\/v1\/contracts\/\?/.test(url))
}

function queryOf(url: string) {
  return new URL(url, 'http://localhost').searchParams
}

afterEach(() => vi.unstubAllGlobals())

describe('FilterRail URL filters', () => {
  it('says when the region type-ahead has no matches', async () => {
    const user = userEvent.setup()
    stubFetch(readyEmptyPage())

    renderApp('/contracts')
    const filter = await screen.findByLabelText('Filter region list')

    await user.type(filter, 'not-a-region')

    expect(screen.getByText('No region matches “not-a-region”')).toBeInTheDocument()
  })

  it('removes the region from the URL and request when the last selection is unchecked', async () => {
    const user = userEvent.setup()
    const calls = stubFetch(readyEmptyPage())

    const { router } = renderApp('/contracts?region_ids=10000002')
    const region = await screen.findByRole('checkbox', { name: 'The Forge' })
    expect(region).toBeChecked()
    expect(screen.getByRole('button', { name: 'Clear filters' })).toBeInTheDocument()
    const callsBeforeUncheck = listCalls(calls).length

    await user.click(region)

    await waitFor(() => expect(router.state.location.search).not.toHaveProperty('region_ids'))
    await waitFor(() => expect(listCalls(calls).length).toBeGreaterThan(callsBeforeUncheck))
    expect(queryOf(listCalls(calls).at(-1)!).has('region_ids')).toBe(false)
    expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument()
  })

  it('offers Clear filters when ships-only is the sole changed setting', async () => {
    const user = userEvent.setup()
    stubFetch(readyEmptyPage())

    const { router } = renderApp('/contracts?ships_only=false')
    expect(await screen.findByRole('checkbox', { name: 'Ships only' })).not.toBeChecked()

    await user.click(screen.getByRole('button', { name: 'Clear filters' }))

    await waitFor(() => expect(router.state.location.search).toHaveProperty('ships_only', true))
    expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument()
  })

  it('offers Clear filters when category_id is the sole active filter', async () => {
    const user = userEvent.setup()
    stubFetch(readyEmptyPage())

    const { router } = renderApp('/contracts?category_id=6')
    const clear = await screen.findByRole('button', { name: 'Clear filters' })

    await user.click(clear)

    await waitFor(() => expect(router.state.location.search).not.toHaveProperty('category_id'))
    expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument()
  })

  it.each([true, false])(
    'offers Clear filters when is_bpc=%s is the sole active filter',
    async (isBpc) => {
      const user = userEvent.setup()
      stubFetch(readyEmptyPage())

      const { router } = renderApp(`/contracts?is_bpc=${isBpc}`)
      const clear = await screen.findByRole('button', { name: 'Clear filters' })

      await user.click(clear)

      await waitFor(() => expect(router.state.location.search).not.toHaveProperty('is_bpc'))
      expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument()
    },
  )

  it('shows the selected counts in the region, category, and group legends', async () => {
    const taxonomy = taxonomyResponse({
      coverage: 'complete',
      categories: [
        { category_id: 6, name: 'Ship' },
        { category_id: 7, name: 'Module' },
      ],
      groups: [
        { group_id: 25, category_id: 6, name: 'Frigate' },
        { group_id: 60, category_id: 7, name: 'Shield Booster' },
      ],
    })
    stubFetch(readyEmptyPage(taxonomy))

    renderApp(
      '/contracts?region_ids=10000002&region_ids=10000043&category_id=6&category_id=7&group_id=25&group_id=60',
    )

    const regions = await screen.findByRole('group', { name: /^Regions/ })
    const categories = await screen.findByRole('group', { name: /^Category/ })
    const groups = await screen.findByRole('group', { name: /^Group/ })
    expect(within(regions).getByText('2')).toBeInTheDocument()
    expect(within(categories).getByText('2')).toBeInTheDocument()
    expect(within(groups).getByText('2')).toBeInTheDocument()
  })
})

describe('TaxonomyFilter empty and nullable taxonomy states', () => {
  it('states when a complete corpus has no categories', async () => {
    stubFetch(readyEmptyPage())

    renderApp('/contracts')

    expect(await screen.findByText('No category in the corpus yet')).toBeInTheDocument()
  })

  it('states when the selected categories contain no groups without requiring a query', async () => {
    const taxonomy = taxonomyResponse({
      coverage: 'complete',
      categories: [
        { category_id: 6, name: 'Ship' },
        { category_id: 7, name: 'Module' },
      ],
      groups: [{ group_id: 60, category_id: 7, name: 'Shield Booster' }],
    })
    stubFetch(readyEmptyPage(taxonomy))

    renderApp('/contracts?category_id=6')

    expect(await screen.findByText('No group in the selected categories')).toBeInTheDocument()
    expect(screen.getByLabelText('Filter group list')).toHaveValue('')
  })

  it('offers a category-less group only while unscoped and prunes it when the scope narrows', async () => {
    const user = userEvent.setup()
    const taxonomy = taxonomyResponse({
      coverage: 'complete',
      categories: [{ category_id: 6, name: 'Ship' }],
      groups: [
        { group_id: 25, category_id: 6, name: 'Frigate' },
        { group_id: 999, category_id: null, name: 'Unresolved group' },
      ],
    })
    const calls = stubFetch(readyEmptyPage(taxonomy))

    const { router } = renderApp('/contracts?group_id=999')
    const unresolved = await screen.findByRole('checkbox', { name: 'Unresolved group' })
    expect(unresolved).toBeChecked()
    const callsBeforeNarrowing = listCalls(calls).length

    await user.click(screen.getByRole('checkbox', { name: 'Ship' }))

    await waitFor(() => expect(router.state.location.search).toMatchObject({ category_id: [6] }))
    expect(router.state.location.search).not.toHaveProperty('group_id')
    expect(screen.queryByRole('checkbox', { name: 'Unresolved group' })).not.toBeInTheDocument()
    await waitFor(() => expect(listCalls(calls).length).toBeGreaterThan(callsBeforeNarrowing))
    const narrowedQuery = queryOf(listCalls(calls).at(-1)!)
    expect(narrowedQuery.getAll('category_id')).toEqual(['6'])
    expect(narrowedQuery.has('group_id')).toBe(false)
  })
})

describe('price and blueprint bounds', () => {
  it.each([
    { label: 'Minimum price', parameter: 'min_price', value: 7 },
    { label: 'Maximum price', parameter: 'max_price', value: 8 },
    { label: 'Minimum runs', parameter: 'min_runs', value: 9 },
    { label: 'Maximum runs', parameter: 'max_runs', value: 10 },
    { label: 'Minimum material efficiency', parameter: 'min_me', value: 11 },
    { label: 'Maximum material efficiency', parameter: 'max_me', value: 12 },
    { label: 'Minimum time efficiency', parameter: 'min_te', value: 13 },
    { label: 'Maximum time efficiency', parameter: 'max_te', value: 14 },
  ])(
    'sets and clears $parameter through its labelled input',
    async ({ label, parameter, value }) => {
      const user = userEvent.setup()
      const calls = stubFetch(readyEmptyPage())

      const { router } = renderApp('/contracts')
      const input = await screen.findByLabelText(label)
      const callsBeforeSet = listCalls(calls).length

      await user.type(input, String(value))

      await waitFor(() => expect(router.state.location.search).toHaveProperty(parameter, value))
      await waitFor(() => {
        expect(listCalls(calls).length).toBeGreaterThan(callsBeforeSet)
        expect(queryOf(listCalls(calls).at(-1)!).get(parameter)).toBe(String(value))
      })
      expect(screen.getByRole('button', { name: 'Clear filters' })).toBeInTheDocument()
      const callsBeforeClear = listCalls(calls).length

      await user.clear(input)

      await waitFor(() => expect(router.state.location.search).not.toHaveProperty(parameter))
      await waitFor(() => {
        expect(listCalls(calls).length).toBeGreaterThan(callsBeforeClear)
        expect(queryOf(listCalls(calls).at(-1)!).has(parameter)).toBe(false)
      })
      expect(screen.queryByRole('button', { name: 'Clear filters' })).not.toBeInTheDocument()
    },
  )
})
