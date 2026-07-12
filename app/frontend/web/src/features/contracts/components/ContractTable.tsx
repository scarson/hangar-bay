import { Link } from '@tanstack/react-router'
import type { Contract } from '../../../lib/api/client'
import { Badge } from '../../../components/Badge'
import { formatDate, formatIsk, primaryLabel, timeRemaining } from '../format'
import type { ContractSearch, SortField } from '../filters'

const COLUMNS: {
  key: string
  label: string
  sortField?: SortField
  align?: 'right'
  headerClass?: string
}[] = [
  { key: 'name', label: 'Ship / Contract', sortField: 'ship_name' },
  { key: 'type', label: 'Type' },
  { key: 'price', label: 'Price (ISK)', sortField: 'price', align: 'right' },
  { key: 'location', label: 'Location', headerClass: 'max-lg:hidden' },
  { key: 'expires', label: 'Time left', sortField: 'date_expired', align: 'right' },
  {
    key: 'issued',
    label: 'Issued',
    sortField: 'date_issued',
    align: 'right',
    headerClass: 'max-sm:hidden',
  },
]

function contractIsBpc(contract: Contract): boolean {
  return contract.items.some((item) => item.is_included && item.is_blueprint_copy)
}

export function ContractTable({
  contracts,
  search,
  onSort,
  isRefreshing,
}: {
  contracts: Contract[]
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
            {COLUMNS.map((column) => {
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
                  className={`sticky top-0 z-(--z-sticky) border-b border-line bg-surface p-0 ${alignment} ${column.headerClass ?? ''}`}
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
            const expiry = timeRemaining(contract.date_expired)
            return (
              <tr
                key={contract.contract_id}
                className="border-b border-line transition-colors duration-150 last:border-b-0 hover:bg-raised"
              >
                {/* The ship-name link is the only click target (no full-row
                    ::after overlay) so the spreadsheet-minded audience can still
                    select/copy the price, location, and time-left cell text. */}
                <td className="px-3 py-2 text-sm">
                  <Link
                    to="/contracts/$contractId"
                    params={{ contractId: String(contract.contract_id) }}
                    className="font-medium text-ink hover:text-brand-bright"
                  >
                    {primaryLabel(contract)}
                  </Link>
                  {contract.items.length > 1 ? (
                    <span className="ml-1.5 text-xs text-ink-faint">
                      +{contract.items.length - 1} more
                    </span>
                  ) : null}
                </td>
                <td className="px-3 py-2">
                  <span className="inline-flex gap-1">
                    <Badge tone="neutral">
                      {contract.type === 'auction' ? 'Auction' : 'Exchange'}
                    </Badge>
                    {contractIsBpc(contract) ? <Badge tone="copper">BPC</Badge> : null}
                  </span>
                </td>
                <td className="text-data px-3 py-2 text-right text-ink">
                  {formatIsk(contract.price)}
                </td>
                <td className="px-3 py-2 text-sm text-ink-dim max-lg:hidden">
                  {/* truncate needs a block child: `max-width` on a table cell
                      does not cap a nowrap string's min-content width, so long
                      Upwell structure names would stretch the column and shove
                      the price/time-left protagonists into horizontal scroll. */}
                  <div className="max-w-64 truncate">
                    {contract.start_location_name ?? `Location ${contract.start_location_id}`}
                  </div>
                </td>
                <td
                  className={`text-data px-3 py-2 text-right ${
                    expiry === 'Expired' ? 'text-warn' : 'text-ink-dim'
                  }`}
                >
                  {expiry}
                </td>
                <td className="text-data px-3 py-2 text-right text-ink-dim max-sm:hidden">
                  {formatDate(contract.date_issued)}
                </td>
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
