// Mechanical scaffold UI: correct data flow and states only.
// Presentation is redesigned wholesale in the /impeccable phase.
import { Link, useNavigate } from '@tanstack/react-router'
import type { Contract } from '../../../lib/api/client'
import { MIN_SEARCH_LENGTH, SORT_FIELDS, type ContractSearch } from '../filters'
import { REGIONS } from '../regions'
import { useContracts } from '../hooks/useContracts'

export function ContractsPage({
  search,
  from,
}: {
  search: ContractSearch
  from: '/contracts/'
}) {
  const navigate = useNavigate({ from })
  const { data, isPending, isError, refetch } = useContracts(search)

  // Text inputs (search, min/max price) fire on every keystroke, so they
  // navigate with { replace: true } to avoid one history entry per character
  // (a back button that walks the search box char-by-char). Discrete controls
  // (region select, BPC toggle, sort, pagination) keep the default push so
  // each is an undoable step.
  const update = (patch: Partial<ContractSearch>, options?: { replace?: boolean }) =>
    navigate({ search: (prev) => ({ ...prev, page: 1, ...patch }), ...options })

  return (
    <main className="p-4">
      <h1 className="text-xl font-bold">Hangar Bay — Ship Contracts</h1>

      <form
        role="search"
        onSubmit={(event) => event.preventDefault()}
        className="my-4 flex flex-wrap items-end gap-4"
      >
        <label className="flex flex-col">
          Search (min {MIN_SEARCH_LENGTH} chars)
          <input
            type="search"
            className="border p-1"
            value={search.search ?? ''}
            onChange={(e) => update({ search: e.target.value || undefined }, { replace: true })}
          />
        </label>
        <label className="flex flex-col">
          Min price
          <input
            type="number"
            min="0"
            className="border p-1"
            value={search.min_price ?? ''}
            onChange={(e) =>
              update(
                { min_price: e.target.value === '' ? undefined : Number(e.target.value) },
                { replace: true },
              )
            }
          />
        </label>
        <label className="flex flex-col">
          Max price
          <input
            type="number"
            min="0"
            className="border p-1"
            value={search.max_price ?? ''}
            onChange={(e) =>
              update(
                { max_price: e.target.value === '' ? undefined : Number(e.target.value) },
                { replace: true },
              )
            }
          />
        </label>
        <label className="flex flex-col">
          Regions
          <select
            multiple
            className="border p-1"
            size={4}
            value={(search.region_ids ?? []).map(String)}
            onChange={(e) => {
              const ids = Array.from(e.target.selectedOptions, (o) => Number(o.value))
              update({ region_ids: ids.length > 0 ? ids : undefined })
            }}
          >
            {REGIONS.map((region) => (
              <option key={region.id} value={region.id}>
                {region.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={search.is_bpc === true}
            onChange={(e) => update({ is_bpc: e.target.checked ? true : undefined })}
          />
          Blueprint copies only
        </label>
        <label className="flex flex-col">
          Sort by
          <select
            className="border p-1"
            value={search.sort_by}
            onChange={(e) => update({ sort_by: e.target.value as ContractSearch['sort_by'] })}
          >
            {SORT_FIELDS.map((field) => (
              <option key={field} value={field}>
                {field}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col">
          Direction
          <select
            className="border p-1"
            value={search.sort_direction}
            onChange={(e) =>
              update({ sort_direction: e.target.value as ContractSearch['sort_direction'] })
            }
          >
            <option value="desc">desc</option>
            <option value="asc">asc</option>
          </select>
        </label>
      </form>

      {isPending ? (
        <p>Loading contracts…</p>
      ) : isError ? (
        <p role="alert">
          Failed to load contracts.{' '}
          <button className="underline" onClick={() => refetch()}>
            Retry
          </button>
        </p>
      ) : data.items.length === 0 ? (
        <p>No contracts match these filters.</p>
      ) : (
        <>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b">
                <th className="p-2">Ship / Title</th>
                <th className="p-2">Type</th>
                <th className="p-2">Price (ISK)</th>
                <th className="p-2">Location</th>
                <th className="p-2">Issued</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((contract) => (
                <tr key={contract.contract_id} className="border-b">
                  <td className="p-2">
                    <Link
                      to="/contracts/$contractId"
                      params={{ contractId: String(contract.contract_id) }}
                      className="underline"
                    >
                      {primaryLabel(contract)}
                    </Link>
                  </td>
                  <td className="p-2">{contract.type}</td>
                  <td className="p-2">
                    {/* Fixed locale: M1 is explicitly English-only (spec Non-goals),
                        and tests assert the formatted value (pitfall TEST-3). */}
                    {contract.price != null ? contract.price.toLocaleString('en-US') : '—'}
                  </td>
                  <td className="p-2">
                    {contract.start_location_name ?? contract.start_location_id}
                  </td>
                  <td className="p-2">{new Date(contract.date_issued).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <nav aria-label="Pagination" className="my-4 flex items-center gap-4">
            <button
              className="border px-2 disabled:opacity-50"
              disabled={search.page <= 1}
              onClick={() => navigate({ search: (prev) => ({ ...prev, page: search.page - 1 }) })}
            >
              Previous
            </button>
            <span>
              Page {data.page} of {Math.max(1, Math.ceil(data.total / data.size))} ({data.total}{' '}
              contracts)
            </span>
            <button
              className="border px-2 disabled:opacity-50"
              disabled={search.page * data.size >= data.total}
              onClick={() => navigate({ search: (prev) => ({ ...prev, page: search.page + 1 }) })}
            >
              Next
            </button>
          </nav>
        </>
      )}
    </main>
  )
}

function primaryLabel(contract: Contract): string {
  const included = contract.items.find((item) => item.is_included && item.type_name)
  // Real ESI titles are often "" (not null), which ?? passes through — the
  // row link would render empty. Treat blank titles as absent.
  return included?.type_name ?? (contract.title?.trim() || `Contract ${contract.contract_id}`)
}
