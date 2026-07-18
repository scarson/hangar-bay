// ABOUTME: F005 saved-searches manage page — auth-gated list with per-row Apply (navigate to /contracts), inline Rename, and two-step Delete.
// ABOUTME: summarizeSearch renders a human-readable criteria line from the stored SavedSearchParameters blob.
import { useEffect, useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { Button } from '../../../components/Button'
import { Input } from '../../../components/Input'
import type { SavedSearch } from '../../../lib/api/client'
import type { components } from '../../../lib/api/schema'
import { useDocumentTitle } from '../../../lib/useDocumentTitle'
import { RequireSignIn } from '../../auth/components/RequireSignIn'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'
import { parseContractSearch } from '../../contracts/filters'
import { formatIsk } from '../../contracts/format'
import { useDeleteSavedSearch, useRenameSavedSearch, useSavedSearches } from '../hooks/useSavedSearches'

type SavedSearchParameters = components['schemas']['SavedSearchParameters']

export function summarizeSearch(p: Partial<SavedSearchParameters>): string {
  const parts: string[] = []
  if (p.search) parts.push(`“${p.search}”`)
  parts.push(p.ships_only ? 'Ships only' : 'All contracts')
  if (p.is_bpc) parts.push('BPC only')
  if (p.min_price != null || p.max_price != null) {
    const lo = p.min_price != null ? formatIsk(p.min_price) : '0'
    const hi = p.max_price != null ? formatIsk(p.max_price) : '∞'
    parts.push(`${lo}–${hi} ISK`)
  }
  if (p.region_ids && p.region_ids.length > 0) {
    parts.push(`${p.region_ids.length} region${p.region_ids.length === 1 ? '' : 's'}`)
  }
  // The parameter is Partial: a stored blob from an older schema version may omit any field,
  // including the server-defaulted sort_by/sort_direction. Default before use — a `.replace()` on
  // undefined would crash at runtime (and would be a TS18048 error were these non-optional here).
  parts.push(`sorted by ${(p.sort_by ?? 'date_issued').replace(/_/g, ' ')} ${p.sort_direction ?? 'desc'}`)
  return parts.join(' · ')
}

export function SavedSearchesPage() {
  useDocumentTitle('Saved Searches')
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return (
      <div role="status" aria-label="Loading account" className="mx-auto max-w-3xl">
        <span className="skeleton block h-7 w-48" />
        <span className="sr-only">Loading…</span>
      </div>
    )
  }
  if (!user) return <RequireSignIn feature="saved searches" />
  return <SavedSearchesList />
}

function SavedSearchesList() {
  const { data, isPending, isError } = useSavedSearches()
  return (
    <div className="mx-auto max-w-3xl">
      {/* Always-mounted polite region so mutation outcomes reach assistive tech (WCAG 4.1.3). */}
      <p className="sr-only" role="status" aria-live="polite" />
      <h1 className="text-h1 mb-4 font-semibold">Saved Searches</h1>
      {isPending ? (
        <div role="status" aria-label="Loading saved searches">
          <span className="skeleton block h-16 w-full" />
          <span className="sr-only">Loading saved searches…</span>
        </div>
      ) : isError ? (
        <div role="alert" className="rounded-md border border-danger/40 bg-danger-wash px-4 py-4 text-sm text-ink">
          Couldn’t load your saved searches. Reload the page to try again.
        </div>
      ) : data.length === 0 ? (
        <div className="rounded-md border border-line bg-surface px-5 py-8">
          <h2 className="text-base font-medium text-ink">No saved searches yet</h2>
          <p className="mt-1 max-w-[52ch] text-sm text-ink-dim">
            On the contracts page, set up a filter you like and choose “Save search” to keep it here.
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {data.map((saved) => (
            <SavedSearchRow key={saved.id} saved={saved} />
          ))}
        </ul>
      )}
    </div>
  )
}

function SavedSearchRow({ saved }: { saved: SavedSearch }) {
  const navigate = useNavigate()
  const rename = useRenameSavedSearch()
  const remove = useDeleteSavedSearch()
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(saved.name)
  const [confirmDelete, setConfirmDelete] = useState(false)

  // Auto-disarm the two-step delete after 5s so a stray first click can't leave the row armed
  // indefinitely (blur also disarms; this covers the focus-retained case). Cleared on unmount/re-arm.
  useEffect(() => {
    if (!confirmDelete) return
    const timer = setTimeout(() => setConfirmDelete(false), 5000)
    return () => clearTimeout(timer)
  }, [confirmDelete])

  const apply = () =>
    // parseContractSearch returns a ContractSearch (an interface — no implicit index signature), but
    // the cross-route navigate `search` slot wants { [k: string]: unknown }. Bridge through unknown
    // (the two types don't overlap enough for a direct assertion); the runtime value is identical.
    navigate({
      to: '/contracts',
      search: parseContractSearch(saved.search_parameters as Record<string, unknown>) as unknown as Record<string, unknown>,
    })

  const submitRename = (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (trimmed.length === 0) return
    rename.mutate({ id: saved.id, name: trimmed }, { onSuccess: () => setRenaming(false) })
  }

  return (
    <li className="flex flex-wrap items-center gap-3 rounded-md border border-line bg-surface px-4 py-3">
      <div className="min-w-0 flex-1">
        {renaming ? (
          <form onSubmit={submitRename} className="flex flex-wrap items-center gap-2" aria-label={`Rename ${saved.name}`}>
            <label htmlFor={`rename-${saved.id}`} className="sr-only">New name</label>
            {/* autoFocus is safe here: the field is revealed by the user's own Rename click, so moving
                focus into it follows the disclosure (WCAG-recommended) rather than the page-load
                disorientation jsx-a11y/no-autofocus guards against. */}
            {/* eslint-disable-next-line jsx-a11y/no-autofocus */}
            <Input id={`rename-${saved.id}`} value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            <Button type="submit" variant="primary" disabled={rename.isPending || name.trim().length === 0}>Save</Button>
            <Button type="button" onClick={() => { setRenaming(false); setName(saved.name) }}>Cancel</Button>
          </form>
        ) : (
          <>
            <p className="truncate font-medium text-ink">{saved.name}</p>
            <p className="truncate text-xs text-ink-dim">{summarizeSearch(saved.search_parameters as SavedSearchParameters)}</p>
          </>
        )}
      </div>
      {!renaming ? (
        <div className="flex shrink-0 items-center gap-2">
          <Button variant="primary" onClick={apply}>Apply</Button>
          <Button onClick={() => setRenaming(true)}>Rename</Button>
          {confirmDelete ? (
            <Button
              className="text-danger"
              disabled={remove.isPending}
              onClick={() => remove.mutate(saved.id)}
              onBlur={() => setConfirmDelete(false)}
            >
              Confirm delete?
            </Button>
          ) : (
            <Button className="text-danger" onClick={() => setConfirmDelete(true)}>Delete</Button>
          )}
        </div>
      ) : null}
    </li>
  )
}
