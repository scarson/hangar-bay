import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Button } from '../../../components/Button'
import { useDocumentTitle } from '../../../lib/useDocumentTitle'
import { DEFAULT_PAGE, DEFAULT_SIZE, type ContractSearch, type SortField } from '../filters'
import { useContracts } from '../hooks/useContracts'
import { ContractTable, ContractTableSkeleton } from './ContractTable'
import { FilterRail } from './FilterRail'
import { Pagination } from './Pagination'

/** New sort field starts in its most useful direction: newest/soonest for dates, cheap-first for ISK. */
const DEFAULT_DIRECTION: Record<SortField, 'asc' | 'desc'> = {
  date_issued: 'desc',
  date_expired: 'asc',
  price: 'asc',
  collateral: 'asc',
  ship_name: 'asc',
  volume: 'desc',
}

export function ContractsPage({ search, from }: { search: ContractSearch; from: '/contracts/' }) {
  const navigate = useNavigate({ from })
  const { data, isPending, isError, isFetching, refetch } = useContracts(search)
  const [filtersOpen, setFiltersOpen] = useState(false)
  useDocumentTitle(search.ships_only ? 'Ship Contracts' : 'All Contracts')

  // Text inputs (search, min/max price) fire on every keystroke, so they
  // navigate with { replace: true } to avoid one history entry per character
  // (a back button that walks the search box char-by-char). Discrete controls
  // (region toggles, checkboxes, sort, pagination) keep the default push so
  // each is an undoable step.
  const update = (patch: Partial<ContractSearch>, options?: { replace?: boolean }) =>
    navigate({ search: (prev) => ({ ...prev, page: 1, ...patch }), ...options })

  const goToPage = (page: number) => navigate({ search: (prev) => ({ ...prev, page }) })

  const resetFilters = () =>
    navigate({
      search: (prev) => ({
        ships_only: true,
        page: DEFAULT_PAGE,
        size: prev.size,
        sort_by: prev.sort_by,
        sort_direction: prev.sort_direction,
      }),
    })

  const handleSort = (field: SortField) =>
    update({
      sort_by: field,
      sort_direction:
        search.sort_by === field
          ? search.sort_direction === 'asc'
            ? 'desc'
            : 'asc'
          : DEFAULT_DIRECTION[field],
    })

  // A shared `?page=N` URL (or in-session data drift on an expiring market) can
  // point past the last page — the backend echoes {total>0, items:[]} without
  // clamping. Redirect to the last page instead of rendering the false
  // "no contracts match" card, which contradicts the "N matching" header and
  // traps the user behind "Clear filters" (destroying their query).
  const pageCount = data ? Math.max(1, Math.ceil(data.total / (data.size ?? DEFAULT_SIZE))) : 1
  const pageOutOfRange = data !== undefined && data.total > 0 && search.page > pageCount
  useEffect(() => {
    if (pageOutOfRange) {
      navigate({ search: (prev) => ({ ...prev, page: pageCount }), replace: true })
    }
  }, [pageOutOfRange, pageCount, navigate])

  return (
    <div className="lg:grid lg:grid-cols-[236px_minmax(0,1fr)] lg:gap-8">
      {/* One FilterRail instance: a static column on desktop, toggled by the
          Filters button below lg. Single instance keeps labels unique in the
          accessibility tree; filter state lives in the URL either way. */}
      <Button
        className="mb-3 lg:hidden"
        aria-expanded={filtersOpen}
        aria-controls="filter-rail"
        onClick={() => setFiltersOpen((open) => !open)}
      >
        Filters
        {/* +/− disclosure marker — distinct from the table's ▲/▼ sort glyphs. */}
        <span aria-hidden="true" className="font-mono text-xs text-ink-dim">
          {filtersOpen ? '−' : '+'}
        </span>
      </Button>
      <aside
        id="filter-rail"
        aria-label="Contract filters"
        className={`${filtersOpen ? 'mb-5 block' : 'hidden'} rounded-md border border-line bg-surface p-4 lg:mb-0 lg:block lg:rounded-none lg:border-0 lg:bg-transparent lg:p-0`}
      >
        <FilterRail search={search} onUpdate={update} onReset={resetFilters} />
      </aside>

      <section aria-label="Contract results" className="flex min-w-0 flex-col gap-4">
        {/* Polite status so filter/sort/pagination outcomes reach assistive tech
            without moving focus off a rail control (WCAG 4.1.3). Always mounted
            so the text change is announced; the visible count below stays a plain
            label to avoid a double read. */}
        <p className="sr-only" role="status" aria-live="polite">
          {data !== undefined
            ? `${data.total.toLocaleString('en-US')} ${data.total === 1 ? 'contract matches' : 'contracts match'} your filters`
            : ''}
        </p>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-h1 font-semibold">
            {search.ships_only ? 'Ship Contracts' : 'All Contracts'}
          </h1>
          {data !== undefined ? (
            <p className="text-data text-ink-dim">
              {data.total.toLocaleString('en-US')} matching
            </p>
          ) : null}
        </div>

        {isPending ? (
          <ContractTableSkeleton />
        ) : isError ? (
          <div
            role="alert"
            className="flex flex-col items-start gap-3 rounded-md border border-danger/40 bg-danger-wash px-4 py-4"
          >
            <p className="text-sm text-ink">
              Failed to load contracts. The market data service may be unreachable.
            </p>
            <Button onClick={() => refetch()}>Retry</Button>
          </div>
        ) : pageOutOfRange ? (
          // Transient: the effect above is navigating to the last valid page.
          <ContractTableSkeleton />
        ) : data.total === 0 ? (
          <div className="flex flex-col items-start gap-3 rounded-md border border-line bg-surface px-5 py-8">
            <h2 className="text-base font-medium text-ink">No contracts match these filters</h2>
            <p className="max-w-[52ch] text-sm text-ink-dim">
              Loosen a price bound, widen the region selection, or clear everything to see the
              full market.
            </p>
            <Button onClick={resetFilters}>Clear filters</Button>
          </div>
        ) : (
          <>
            <ContractTable
              contracts={data.items}
              search={search}
              onSort={handleSort}
              isRefreshing={isFetching}
            />
            <Pagination
              page={search.page}
              size={data.size ?? DEFAULT_SIZE}
              total={data.total}
              onPage={goToPage}
            />
          </>
        )}
      </section>
    </div>
  )
}
