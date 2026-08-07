// ABOUTME: Column definitions for the contract list table — label, sort field,
// ABOUTME: responsive visibility, and the per-column cell renderer.
import type { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import type { Contract } from '../../lib/api/client'
import { Badge } from '../../components/Badge'
import {
  contractTypeLabel,
  formatDate,
  formatDeadline,
  formatIsk,
  formatRewardPerVolume,
  locationLabel,
  routeLabel,
  timeRemaining,
} from './format'
import type { ContractTypeValue, SortField } from './filters'

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

/**
 * The row's headline and its only click target (no full-row ::after overlay) so
 * the spreadsheet-minded audience can still select/copy the price, location,
 * and time-left cell text.
 */
function labelCell(contract: Contract): ReactNode {
  return (
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
  )
}

const NAME_COLUMN: Column = {
  key: 'name',
  label: 'Ship / Contract',
  sortField: 'ship_name',
  cellClass: 'text-sm',
  cell: labelCell,
}

const TYPE_COLUMN: Column = {
  key: 'type',
  label: 'Type',
  cell: (contract) => (
    <span className="inline-flex gap-1">
      <Badge tone="neutral">{contractTypeLabel(contract.type)}</Badge>
      {contract.is_blueprint_copy_contract ? <Badge tone="copper">BPC</Badge> : null}
    </span>
  ),
}

const PRICE_COLUMN: Column = {
  key: 'price',
  label: 'Price (ISK)',
  sortField: 'price',
  align: 'right',
  cellClass: 'text-data text-ink',
  cell: (contract) => formatIsk(contract.price),
}

const LOCATION_COLUMN: Column = {
  key: 'location',
  label: 'Location',
  hiddenClass: 'max-lg:hidden',
  cellClass: 'text-sm text-ink-dim',
  // truncate needs a block child: `max-width` on a table cell does not cap a
  // nowrap string's min-content width, so long Upwell structure names would
  // stretch the column and shove the price/time-left protagonists into
  // horizontal scroll.
  cell: (contract) => <div className="max-w-64 truncate">{locationLabel(contract)}</div>,
}

const EXPIRES_COLUMN: Column = {
  key: 'expires',
  label: 'Time left',
  sortField: 'date_expired',
  align: 'right',
  cellClass: (_contract, ctx) =>
    `text-data ${ctx.expiry === 'Expired' ? 'text-warn' : 'text-ink-dim'}`,
  cell: (_contract, ctx) => ctx.expiry,
}

const ISSUED_COLUMN: Column = {
  key: 'issued',
  label: 'Issued',
  sortField: 'date_issued',
  align: 'right',
  hiddenClass: 'max-sm:hidden',
  cellClass: 'text-data text-ink-dim',
  cell: (contract) => formatDate(contract.date_issued),
}

export const DEFAULT_COLUMNS: Column[] = [
  NAME_COLUMN,
  TYPE_COLUMN,
  PRICE_COLUMN,
  LOCATION_COLUMN,
  EXPIRES_COLUMN,
  ISSUED_COLUMN,
]

/**
 * Auctions. A bid is not a price and a buyout is a third thing again, so the
 * one price column splits in two; the type badge goes, because every row here
 * is an auction and the badge would only repeat the segment control.
 */
export const AUCTION_COLUMNS: Column[] = [
  NAME_COLUMN,
  {
    key: 'price',
    label: 'Starting bid',
    sortField: 'price',
    align: 'right',
    cellClass: 'text-data text-ink',
    cell: (contract) => formatIsk(contract.price),
  },
  {
    key: 'buyout',
    label: 'Buyout',
    sortField: 'buyout',
    align: 'right',
    // A seller who set no buyout is not missing data, so the cell says so in
    // words and drops the mono treatment the figures wear (Criterion 4.3): a
    // dash reads as "we do not know", and 0 reads as "take it for free".
    cellClass: (contract) =>
      contract.buyout == null ? 'text-sm text-ink-faint' : 'text-data text-ink',
    cell: (contract) => (contract.buyout == null ? 'No buyout' : formatIsk(contract.buyout)),
  },
  LOCATION_COLUMN,
  EXPIRES_COLUMN,
  ISSUED_COLUMN,
]

/**
 * Couriers. A hauling job's money is in the reward against the collateral, and
 * its shape is the route and the cargo — none of which the sale columns carry.
 * Reward per m³ is the only normalization the row offers: jumps, reward per
 * jump, and route security are deferred work, and a row must not imply a
 * distance it cannot compute (Criterion 5.6, spec §8).
 */
export const COURIER_COLUMNS: Column[] = [
  { ...NAME_COLUMN, label: 'Contract', sortField: undefined },
  {
    key: 'route',
    label: 'Route',
    cellClass: 'text-sm text-ink-dim',
    // Truncated for the same reason the Location column is: two structure names
    // in one cell is the longest string the table ever holds.
    cell: (contract) => <div className="max-w-72 truncate">{routeLabel(contract)}</div>,
  },
  {
    key: 'reward',
    label: 'Reward',
    align: 'right',
    cellClass: 'text-data text-ink',
    cell: (contract) => formatIsk(contract.reward),
  },
  {
    key: 'collateral',
    label: 'Collateral',
    align: 'right',
    hiddenClass: 'max-lg:hidden',
    cellClass: 'text-data text-ink-dim',
    cell: (contract) => formatIsk(contract.collateral),
  },
  {
    key: 'volume',
    label: 'Volume',
    align: 'right',
    hiddenClass: 'max-lg:hidden',
    cellClass: 'text-data text-ink-dim',
    cell: (contract) => formatIsk(contract.volume),
  },
  {
    key: 'reward_per_volume',
    label: 'Reward/m³',
    sortField: 'reward_per_volume',
    align: 'right',
    cellClass: 'text-data text-ink',
    cell: (contract) => formatRewardPerVolume(contract.reward_per_volume),
  },
  {
    key: 'days_to_complete',
    // Never hidden at a breakpoint, unlike Collateral and Volume below: the
    // detail page carries those two, but the days a hauler has to deliver in
    // appear nowhere else in the app, so hiding the column deletes a field
    // Criterion 5.3 requires. "7d" is also the narrowest cell in the set.
    label: 'Deadline',
    align: 'right',
    cellClass: 'text-data text-ink-dim',
    cell: (contract) => formatDeadline(contract.days_to_complete),
  },
  EXPIRES_COLUMN,
]

/**
 * The columns a segment shows (spec §8 axis 1). The types with no set of their
 * own — item exchange, loan, unknown, and no selection at all — keep the
 * default: a loan has no route and no bid, and the default columns describe it
 * as well as anything else does.
 */
export function columnsFor(type: ContractTypeValue | undefined): Column[] {
  if (type === 'auction') return AUCTION_COLUMNS
  if (type === 'courier') return COURIER_COLUMNS
  return DEFAULT_COLUMNS
}
