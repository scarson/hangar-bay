import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Button } from '../../../components/Button'
import { timeAgo } from '../../../lib/timeAgo'
import { useDocumentTitle } from '../../../lib/useDocumentTitle'
import { columnsFor } from '../columns'
import { regionNames } from '../format'
import { DEFAULT_DIRECTION, DEFAULT_PAGE, DEFAULT_SIZE, type ContractSearch, type SortField } from '../filters'
import { SaveSearchControl } from '../../saved-searches/components/SaveSearchControl'
import { useContracts } from '../hooks/useContracts'
import { ContractTable, ContractTableSkeleton } from './ContractTable'
import { FilterRail } from './FilterRail'
import { Pagination } from './Pagination'
import { SegmentTabs, listTitle } from './SegmentTabs'

/**
 * Why the page is empty, and which of the two reasons it is (Criterion 7.2).
 * A region the corpus holds no rows for cannot match anything whatever the rest
 * of the filters say, so telling that reader to loosen a price bound sends them
 * looking for a market that was never there. Which regions those are is read
 * from the response's coverage block rather than a literal here (Criterion 7.3
 * — a literal becomes wrong the day coverage expands), and the selection is the
 * one the response was fetched under rather than the live URL (WEB-1).
 */
function EmptyResults({
  selectedRegionIds,
  coveredRegionIds,
  itemFilteredItemLessSegment,
  onReset,
}: {
  selectedRegionIds: number[]
  coveredRegionIds: number[]
  /** An item-level filter against a segment whose contracts carry no items. */
  itemFilteredItemLessSegment: boolean
  onReset: () => void
}) {
  const uncovered = selectedRegionIds.filter((id) => !coveredRegionIds.includes(id))
  const coveredSelection = selectedRegionIds.filter((id) => coveredRegionIds.includes(id))

  if (itemFilteredItemLessSegment) {
    // The combination cannot match, and saying so is what Criterion 7.2 asks
    // for. The alternative once shipped here — silently dropping the item
    // filters on the way into the segment — destroyed a selection the reader
    // would want back on the way out, and rewrote a stored saved search's
    // meaning from "no matches" to "every contract of this type".
    return (
      <div className="flex flex-col items-start gap-3 rounded-md border border-line bg-surface px-5 py-8">
        <h2 className="text-base font-medium text-ink">
          These contracts carry no items to filter on
        </h2>
        <p className="max-w-[52ch] text-sm text-ink-dim">
          Courier, loan and unknown contracts hold no item list, so a category, group or
          blueprint filter can never match one. Clear those filters, or pick a contract
          type that carries items.
        </p>
        <Button onClick={onReset}>Clear filters</Button>
      </div>
    )
  }

  if (coveredRegionIds.length === 0 && selectedRegionIds.length === 0) {
    // Nothing ingested and nothing selected — no filter can reach any data, so
    // the loosen-your-filters advice would be a false lead. With a region
    // SELECTED, the uncovered branch below already tells the truer story
    // (that region has no data yet, and no covered region exists).
    return (
      <div className="flex flex-col items-start gap-3 rounded-md border border-line bg-surface px-5 py-8">
        <h2 className="text-base font-medium text-ink">No data ingested yet</h2>
        <p className="max-w-[52ch] text-sm text-ink-dim">
          The corpus is empty right now. Contracts appear a few minutes after
          ingestion starts; no filter change can hurry that along.
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-start gap-3 rounded-md border border-line bg-surface px-5 py-8">
      {uncovered.length > 0 ? (
        <>
          <h2 className="text-base font-medium text-ink">
            No data for {regionNames(uncovered)} yet
          </h2>
          <p className="max-w-[52ch] text-sm text-ink-dim">
            {coveredRegionIds.length > 0
              ? `Hangar Bay currently covers ${regionNames(coveredRegionIds)}.`
              : 'No region has been ingested yet.'}{' '}
            {uncovered.length === 1 ? 'That region holds' : 'Those regions hold'} nothing here yet,
            so no filter can reach into {uncovered.length === 1 ? 'it' : 'them'}.
            {coveredSelection.length > 0
              ? ` You also selected ${regionNames(coveredSelection)}, which matched nothing.`
              : ''}
          </p>
        </>
      ) : (
        <>
          <h2 className="text-base font-medium text-ink">No contracts match these filters</h2>
          <p className="max-w-[52ch] text-sm text-ink-dim">
            Loosen a price bound, widen the region selection, or clear everything to see the
            full market.
          </p>
        </>
      )}
      <Button onClick={onReset}>Clear filters</Button>
    </div>
  )
}

export function ContractsPage({ search, from }: { search: ContractSearch; from: '/contracts/' }) {
  const navigate = useNavigate({ from })
  const { data, isPending, isError, isFetching, refetch } = useContracts(search)
  const [filtersOpen, setFiltersOpen] = useState(false)
  const title = listTitle(search)
  useDocumentTitle(title)
  // The selection the RESPONSE was fetched under (WEB-1), for the live-region
  // coverage sentence; EmptyResults derives the same split for the visible card.
  const uncoveredSelection =
    data !== undefined
      ? data.regionIds.filter((id) => !data.coverage.ingested_region_ids.includes(id))
      : []

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
            ? `${data.total.toLocaleString('en-US')} ${data.total === 1 ? 'contract matches' : 'contracts match'} your filters` +
              // A bare zero is misleading when the cause is coverage, and the
              // explanation must ride the same announcement assistive tech
              // hears — not sit in a card the listener has to go find.
              (data.total === 0 && data.coverage.ingested_region_ids.length === 0
                ? ' No region has been ingested yet.'
                : data.total === 0 && uncoveredSelection.length > 0
                  ? ` ${regionNames(uncoveredSelection)} ${uncoveredSelection.length === 1 ? 'is' : 'are'} not covered yet.`
                  : '')
            : ''}
        </p>
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h1 className="text-h1 font-semibold">{title}</h1>
          {data !== undefined ? (
            <p className="text-data text-ink-dim">
              {data.total.toLocaleString('en-US')} matching
            </p>
          ) : null}
          {/* Criterion 7.1. The stamp describes the corpus the page was drawn
              from, so it sits with the count rather than in a column. A null
              as_of is the absence of a freshness signal — nothing has been
              stamped yet — and gets no line at all: a dash beside "Data as of"
              would dress that absence up as a reading. */}
          {data?.coverage.as_of ? (
            <p className="text-xs text-ink-faint">Data as of {timeAgo(data.coverage.as_of)}</p>
          ) : null}
          <SaveSearchControl search={search} />
        </div>

        {/* The segments need the envelope's counts, so they appear with the
            first response and stay through later ones (keepPreviousData holds
            the previous page while a new segment loads). */}
        {data !== undefined ? (
          <SegmentTabs search={search} counts={data.segment_counts} onSelect={update} />
        ) : null}

        {/* A shared URL can carry a taxonomy or blueprint filter into a corpus
            that is still being enriched — the rows it matches are real, so the
            request goes out unchanged, but the page it returns is short by
            however much is not yet restamped and has to say so (Criterion 7.2's
            explain-rather-than-empty rule, applied to a temporary population
            rather than an uncovered region). Rejecting the params server-side
            was declined: it would break every saved search the moment a future
            resweep started.

            Whether a filter was in play comes off the response, not the live
            URL (WEB-1): the claim is about the rows on screen, and those are
            the previous request's for the whole of the next one. */}
        {data !== undefined && !data.itemSurfaceReady && data.enrichmentFiltered ? (
          <p className="text-xs text-ink-dim">
            Item filters are still indexing; results may be incomplete.
          </p>
        ) : null}

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
        ) : (
          <>
            {/* Criterion 5.7: a hauler reading a list of routes has to know the
                origins are one region's worth rather than the cluster's — and
                the hauler staring at ZERO jobs needs it most, so the line sits
                above the empty/populated split. Named from the envelope, so it
                follows coverage instead of freezing today's into this file
                (Criterion 7.3). */}
            {data.segment === 'courier' && data.coverage.ingested_region_ids.length > 0 ? (
              <p className="text-xs text-ink-dim">
                Couriers originating in {regionNames(data.coverage.ingested_region_ids)} only.
              </p>
            ) : null}
            {data.total === 0 ? (
              <EmptyResults
                selectedRegionIds={data.regionIds}
                coveredRegionIds={data.coverage.ingested_region_ids}
                itemFilteredItemLessSegment={data.itemFilteredItemLessSegment}
                onReset={resetFilters}
              />
            ) : (
              <>
                <ContractTable
                  contracts={data.items}
                  // The segment picks the columns; the table frame is the same one
                  // every segment renders through (spec §8). It comes off the
                  // response rather than the URL so the columns always describe the
                  // rows beneath them — the two disagree for the whole of a segment
                  // switch, which `keepPreviousData` renders with the old rows.
                  columns={columnsFor(data.segment, data.itemSurfaceReady)}
                  itemSurfaceReady={data.itemSurfaceReady}
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
          </>
        )}
      </section>
    </div>
  )
}
