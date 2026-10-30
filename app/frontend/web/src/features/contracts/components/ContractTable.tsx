import type { Contract } from '../../../lib/api/client'
import { rowContext, type Column, type RowContext } from '../columns'
import type { ContractSearch, SortField } from '../filters'

function cellClass(column: Column, contract: Contract, ctx: RowContext): string {
  if (typeof column.cellClass === 'function') return column.cellClass(contract, ctx)
  return column.cellClass ?? ''
}

export function ContractTable({
  contracts,
  columns,
  itemSurfaceReady,
  search,
  onSort,
  isRefreshing,
}: {
  contracts: Contract[]
  /** The active segment's column set — one frame, per-segment columns (spec §8). */
  columns: Column[]
  /** Whether the item-derived cells can say anything yet (decision log D1). */
  itemSurfaceReady: boolean
  search: ContractSearch
  onSort: (field: SortField) => void
  isRefreshing: boolean
}) {
  return (
    // Bounded height turns this wrapper into the vertical scroll context, so the
    // sticky header below sticks to the top of THIS container (not the viewport):
    // scanning a 50-row page keeps the column labels and sort toggles in view.
    // The wrapper wins the scroll context because `overflow-x-auto` already makes
    // it a scroll container on both axes; a page-level sticky would need the
    // vertical scroll pulled out, so we keep it self-contained here instead.
    <div className="max-h-[calc(100vh-11rem)] overflow-auto rounded-md border border-line">
      <table
        className={`w-full border-collapse transition-opacity duration-200 ${isRefreshing ? 'opacity-60' : ''}`}
      >
        <thead>
          <tr>
            {columns.map((column) => {
              const sorted = column.sortField !== undefined && search.sort_by === column.sortField
              const alignment = column.align === 'right' ? 'text-right' : 'text-left'
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={
                    sorted
                      ? search.sort_direction === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : undefined
                  }
                  // Solid bg (rows scroll UNDER the header) + the semantic
                  // --z-sticky token keeps the header above the tbody cells.
                  className={`sticky top-0 z-(--z-sticky) border-b border-line bg-surface p-0 ${alignment} ${column.hiddenClass ?? ''}`}
                >
                  {column.sortField ? (
                    <button
                      onClick={() => onSort(column.sortField!)}
                      className={`text-label flex h-9 w-full cursor-pointer items-center gap-1 px-3 transition-colors duration-150 hover:text-ink ${
                        column.align === 'right' ? 'justify-end' : ''
                      } ${sorted ? 'text-brand' : ''}`}
                    >
                      {column.label}
                      <span aria-hidden="true" className="w-2 font-mono">
                        {sorted ? (search.sort_direction === 'asc' ? '▲' : '▼') : ''}
                      </span>
                    </button>
                  ) : (
                    <span className="text-label flex h-9 items-center px-3">{column.label}</span>
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {contracts.map((contract) => {
            const ctx = rowContext(contract, itemSurfaceReady)
            return (
              <tr
                key={contract.contract_id}
                className="border-b border-line transition-colors duration-150 last:border-b-0 hover:bg-raised"
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`px-3 py-2 ${column.align === 'right' ? 'text-right' : ''} ${cellClass(
                      column,
                      contract,
                      ctx,
                    )} ${column.hiddenClass ?? ''}`}
                  >
                    {column.cell(contract, ctx)}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function ContractTableSkeleton() {
  return (
    <div
      className="overflow-hidden rounded-md border border-line"
      role="status"
      aria-label="Loading contracts"
    >
      <div className="h-9 border-b border-line bg-surface" />
      {Array.from({ length: 10 }, (_, index) => (
        <div key={index} className="flex items-center gap-4 border-b border-line px-3 py-2.5 last:border-b-0">
          <span className="skeleton h-4 w-40" />
          <span className="skeleton h-4 w-16" />
          <span className="skeleton ml-auto h-4 w-24" />
          <span className="skeleton h-4 w-32 max-lg:hidden" />
          <span className="skeleton h-4 w-14" />
        </div>
      ))}
      <span className="sr-only">Loading contracts…</span>
    </div>
  )
}
