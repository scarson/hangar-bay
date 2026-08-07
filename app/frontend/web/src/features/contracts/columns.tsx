// ABOUTME: Column definitions for the contract list table — label, sort field,
// ABOUTME: responsive visibility, and the per-column cell renderer.
import type { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import type { Contract } from '../../lib/api/client'
import { Badge } from '../../components/Badge'
import { contractTypeLabel, formatDate, formatIsk, locationLabel, timeRemaining } from './format'
import type { SortField } from './filters'

/** Values shared by more than one renderer on the same row, computed once. */
export interface RowContext {
  expiry: string
}

export interface Column {
  key: string
  label: string
  sortField?: SortField
  align?: 'right'
  /**
   * ONE class list for both the `<th>` and the `<td>`, so a responsive
   * visibility rule cannot drift between a header and the cells under it.
   */
  hiddenClass?: string
  /**
   * Cell classes beyond the padding and alignment every cell shares. A
   * function where they depend on the row — the expiry cell warns once the
   * countdown has run out.
   */
  cellClass?: string | ((contract: Contract, ctx: RowContext) => string)
  cell: (contract: Contract, ctx: RowContext) => ReactNode
}

export function rowContext(contract: Contract): RowContext {
  return { expiry: timeRemaining(contract.date_expired) }
}

export const DEFAULT_COLUMNS: Column[] = [
  {
    key: 'name',
    label: 'Ship / Contract',
    sortField: 'ship_name',
    cellClass: 'text-sm',
    // The ship-name link is the only click target (no full-row ::after
    // overlay) so the spreadsheet-minded audience can still select/copy the
    // price, location, and time-left cell text.
    cell: (contract) => (
      <>
        <Link
          to="/contracts/$contractId"
          params={{ contractId: String(contract.contract_id) }}
          className="font-medium text-ink hover:text-brand-bright"
        >
          {contract.primary_label}
        </Link>
        {/* Composition is served only for a contract offering more than one item
            row, so its presence IS the "there is more in here" signal. Counts are
            item rows rather than summed quantities — "+2 more" describes a bundle,
            "+3,000 more" would describe an ammunition stack. */}
        {contract.composition && contract.composition.total_item_rows > 1 ? (
          <span className="ml-1.5 text-xs text-ink-faint">
            +{contract.composition.total_item_rows - 1} more
          </span>
        ) : null}
      </>
    ),
  },
  {
    key: 'type',
    label: 'Type',
    cell: (contract) => (
      <span className="inline-flex gap-1">
        <Badge tone="neutral">{contractTypeLabel(contract.type)}</Badge>
        {contract.is_blueprint_copy_contract ? <Badge tone="copper">BPC</Badge> : null}
      </span>
    ),
  },
  {
    key: 'price',
    label: 'Price (ISK)',
    sortField: 'price',
    align: 'right',
    cellClass: 'text-data text-ink',
    cell: (contract) => formatIsk(contract.price),
  },
  {
    key: 'location',
    label: 'Location',
    hiddenClass: 'max-lg:hidden',
    cellClass: 'text-sm text-ink-dim',
    // truncate needs a block child: `max-width` on a table cell does not cap a
    // nowrap string's min-content width, so long Upwell structure names would
    // stretch the column and shove the price/time-left protagonists into
    // horizontal scroll.
    cell: (contract) => <div className="max-w-64 truncate">{locationLabel(contract)}</div>,
  },
  {
    key: 'expires',
    label: 'Time left',
    sortField: 'date_expired',
    align: 'right',
    cellClass: (_contract, ctx) =>
      `text-data ${ctx.expiry === 'Expired' ? 'text-warn' : 'text-ink-dim'}`,
    cell: (_contract, ctx) => ctx.expiry,
  },
  {
    key: 'issued',
    label: 'Issued',
    sortField: 'date_issued',
    align: 'right',
    hiddenClass: 'max-sm:hidden',
    cellClass: 'text-data text-ink-dim',
    cell: (contract) => formatDate(contract.date_issued),
  },
]
