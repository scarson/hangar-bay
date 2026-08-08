// ABOUTME: Column definitions for the contract list table — label, sort field,
// ABOUTME: responsive visibility, and the per-column cell renderer.
import type { ReactNode } from 'react'
import { Link } from '@tanstack/react-router'
import type { Contract } from '../../lib/api/client'
import { Badge } from '../../components/Badge'
import {
  contractTypeLabel,
  formatBlueprintTerms,
  formatComposition,
  formatDate,
  formatDeadline,
  formatIsk,
  formatRewardPerVolume,
  formatVolume,
  locationLabel,
  routeLabel,
  timeRemaining,
} from './format'
import type { ContractTypeValue, SortField } from './filters'

/** Values shared by more than one renderer on the same row, computed once. */
export interface RowContext {
  expiry: string
  /**
   * Whether the corpus is enriched enough for the item-derived cells to say
   * anything (decision log D1). It selects the column SET as well, but the
   * label cell also chooses between two renderings on it, so it rides here
   * rather than being read twice.
   */
  itemSurfaceReady: boolean
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

export function rowContext(contract: Contract, itemSurfaceReady: boolean): RowContext {
  return { expiry: timeRemaining(contract.date_expired), itemSurfaceReady }
}

/**
 * The row's headline and its only click target (no full-row ::after overlay) so
 * the spreadsheet-minded audience can still select/copy the price, location,
 * and time-left cell text.
 */
function labelCell(contract: Contract, ctx: RowContext): ReactNode {
  // Composition is served only for a contract offering more than one item row,
  // so its presence IS the "there is more in here" signal. Counts are item rows
  // rather than summed quantities — a bundle, not an ammunition stack.
  const composition =
    contract.composition && contract.composition.total_item_rows > 1 ? contract.composition : null
  return (
    <>
      <Link
        to="/contracts/$contractId"
        params={{ contractId: String(contract.contract_id) }}
        className="font-medium text-ink hover:text-brand-bright"
      >
        {contract.primary_label}
      </Link>
      {/* Criterion 6.1 wants the per-category breakdown, which needs the item
          categories named — so while the corpus is still being enriched the row
          falls back to the bare count it has always shown. A breakdown from an
          unnamed corpus would read "4 other", which says less than "+3 more". */}
      {composition ? (
        ctx.itemSurfaceReady ? (
          <div className="text-xs text-ink-faint">{formatComposition(composition)}</div>
        ) : (
          <span className="ml-1.5 text-xs text-ink-faint">
            +{composition.total_item_rows - 1} more
          </span>
        )
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

/**
 * The blueprint terms, per §8's discriminator: exactly one offered copy shows
 * its runs/ME/TE, several show how many and send the reader to the detail page
 * (no single set of terms describes them, and picking one copy's would
 * misdescribe the others), none shows nothing at all.
 *
 * ONE column rather than three. The spec's "first-class columns" reads as
 * Runs | ME | TE, but none of the three is a server sort field, so nothing is
 * gained by separating them — and the cost is three columns that are empty for
 * almost every row of the DEFAULT view, which is ships-only and therefore
 * almost never blueprints. The multi-copy state has no three-column rendering
 * either: "3 BPCs" repeated three times, or nominated into one column with two
 * left blank beside it.
 */
const BLUEPRINT_COLUMN: Column = {
  key: 'blueprint',
  label: 'Blueprint',
  hiddenClass: 'max-lg:hidden',
  cellClass: 'text-data text-ink-dim',
  cell: (contract) => {
    const summary = contract.blueprint_summary
    if (!summary) return null
    if (summary.copy_count > 1) {
      return (
        <Link
          to="/contracts/$contractId"
          params={{ contractId: String(contract.contract_id) }}
          className="text-ink-dim hover:text-brand-bright"
        >
          {summary.copy_count} BPCs
        </Link>
      )
    }
    return formatBlueprintTerms(summary)
  },
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
    // Not formatIsk: a sub-1 m³ cargo would render as "0" beside a non-zero
    // Reward/m³ computed from it, which reads as a division by nothing.
    cell: (contract) => formatVolume(contract.volume),
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
    // The server sorts on it (§6.2), so the header must disclose it — a sort
    // reachable only by URL with no header to show or clear it is the
    // invisible-ordering defect.
    sortField: 'days_to_complete',
    align: 'right',
    cellClass: 'text-data text-ink-dim',
    cell: (contract) => formatDeadline(contract.days_to_complete),
  },
  EXPIRES_COLUMN,
]

/**
 * The blueprint column sits with the goods rather than with the money: right
 * before Location in both item-bearing sets, so the terms read next to the item
 * they describe. Couriers never get it — they carry no items at all.
 */
function withBlueprintColumn(columns: Column[]): Column[] {
  const before = columns.findIndex((column) => column.key === LOCATION_COLUMN.key)
  return [...columns.slice(0, before), BLUEPRINT_COLUMN, ...columns.slice(before)]
}

/**
 * The columns a segment shows (spec §8 axis 1). The types with no set of their
 * own — item exchange, loan, unknown, and no selection at all — keep the
 * default: a loan has no route and no bid, and the default columns describe it
 * as well as anything else does.
 *
 * `itemSurfaceReady` OMITS the blueprint column rather than emptying it while
 * the corpus is being enriched (decision log D1): runs/ME/TE are NULL for most
 * of the corpus mid-resweep, and a column blank down its whole length reads as
 * a broken feature rather than as a corpus of non-blueprints.
 */
export function columnsFor(
  type: ContractTypeValue | undefined,
  itemSurfaceReady = false,
): Column[] {
  if (type === 'courier') return COURIER_COLUMNS
  const columns = type === 'auction' ? AUCTION_COLUMNS : DEFAULT_COLUMNS
  return itemSurfaceReady ? withBlueprintColumn(columns) : columns
}

/**
 * The sort fields a segment's column set can actually disclose in a header,
 * computed over the WIDEST set the segment can show. The gated columns carry no
 * `sortField` (pinned by a test), so readiness cannot change this answer — and
 * taking the widest set means a readiness flip could never silently reset a
 * sort the reader had chosen.
 */
export function sortableFieldsFor(type: ContractTypeValue | undefined): ReadonlySet<SortField> {
  return new Set(
    columnsFor(type, true).flatMap((column) => (column.sortField ? [column.sortField] : [])),
  )
}
