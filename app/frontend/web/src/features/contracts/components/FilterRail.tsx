import { useState } from 'react'
import { Button } from '../../../components/Button'
import { CheckboxField } from '../../../components/Checkbox'
import { Input } from '../../../components/Input'
import { MIN_SEARCH_LENGTH, type ContractSearch } from '../filters'
import { REGIONS } from '../regions'

export function FilterRail({
  search,
  onUpdate,
  onReset,
}: {
  search: ContractSearch
  /** Text inputs pass { replace: true } to avoid per-keystroke history entries. */
  onUpdate: (patch: Partial<ContractSearch>, options?: { replace?: boolean }) => void
  onReset: () => void
}) {
  const [regionQuery, setRegionQuery] = useState('')
  const selectedRegions = new Set(search.region_ids ?? [])
  const query = regionQuery.trim().toLowerCase()
  const visibleRegions = query
    ? REGIONS.filter((region) => region.name.toLowerCase().includes(query))
    : REGIONS

  const hasActiveFilters =
    search.search !== undefined ||
    search.min_price !== undefined ||
    search.max_price !== undefined ||
    search.region_ids !== undefined ||
    search.is_bpc !== undefined ||
    !search.ships_only

  const toggleRegion = (id: number, checked: boolean) => {
    const next = new Set(selectedRegions)
    if (checked) next.add(id)
    else next.delete(id)
    onUpdate({ region_ids: next.size > 0 ? [...next].sort((a, b) => a - b) : undefined })
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <label className="flex flex-col gap-1.5">
          <span className="text-label">Search</span>
          <Input
            type="search"
            placeholder="Ship or contract name…"
            value={search.search ?? ''}
            onChange={(event) =>
              onUpdate({ search: event.target.value || undefined }, { replace: true })
            }
          />
        </label>
        <p className="mt-1 text-xs text-ink-faint">Searches from {MIN_SEARCH_LENGTH} characters</p>
      </div>

      <fieldset className="flex flex-col gap-1">
        <legend className="text-label mb-1.5">Show</legend>
        <CheckboxField
          label="Ships only"
          checked={search.ships_only}
          onChange={(checked) => onUpdate({ ships_only: checked })}
        />
        <CheckboxField
          label="Blueprint copies only"
          checked={search.is_bpc === true}
          onChange={(checked) => onUpdate({ is_bpc: checked ? true : undefined })}
        />
      </fieldset>

      <fieldset>
        <legend className="text-label mb-1.5">Price (ISK)</legend>
        <div className="flex items-center gap-2">
          <label className="flex-1">
            <span className="sr-only">Minimum price</span>
            <Input
              type="number"
              min="0"
              placeholder="Min"
              className="text-data"
              value={search.min_price ?? ''}
              onChange={(event) =>
                onUpdate(
                  { min_price: event.target.value === '' ? undefined : Number(event.target.value) },
                  { replace: true },
                )
              }
            />
          </label>
          <span aria-hidden="true" className="text-ink-faint">
            –
          </span>
          <label className="flex-1">
            <span className="sr-only">Maximum price</span>
            <Input
              type="number"
              min="0"
              placeholder="Max"
              className="text-data"
              value={search.max_price ?? ''}
              onChange={(event) =>
                onUpdate(
                  { max_price: event.target.value === '' ? undefined : Number(event.target.value) },
                  { replace: true },
                )
              }
            />
          </label>
        </div>
      </fieldset>

      <fieldset>
        <legend className="text-label mb-1.5">
          Regions
          {selectedRegions.size > 0 ? (
            <span className="ml-1.5 rounded-sm bg-brand-wash px-1 font-mono text-brand normal-case">
              {selectedRegions.size}
            </span>
          ) : null}
        </legend>
        <label className="mb-1.5 block">
          <span className="sr-only">Filter region list</span>
          <Input
            type="search"
            placeholder="Filter regions…"
            value={regionQuery}
            onChange={(event) => setRegionQuery(event.target.value)}
          />
        </label>
        <div className="max-h-52 overflow-y-auto rounded-sm border border-line bg-surface px-1.5 py-1">
          {visibleRegions.length === 0 ? (
            <p className="px-1 py-2 text-xs text-ink-faint">No region matches “{regionQuery}”</p>
          ) : (
            visibleRegions.map((region) => (
              <CheckboxField
                key={region.id}
                label={region.name}
                checked={selectedRegions.has(region.id)}
                onChange={(checked) => toggleRegion(region.id, checked)}
              />
            ))
          )}
        </div>
      </fieldset>

      {hasActiveFilters ? (
        <Button onClick={onReset} className="self-start">
          Clear filters
        </Button>
      ) : null}
    </div>
  )
}
