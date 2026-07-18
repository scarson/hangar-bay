// ABOUTME: Authed-only "Save search" control for the ContractsPage results header — inline name disclosure, posts search-minus-page.
// ABOUTME: toSavedSearchParameters drops `page` and gates a sub-MIN_SEARCH_LENGTH search exactly as toApiQuery does, so a mid-typing 1–2-char search never 422s the save.
import { useState } from 'react'
import { Button } from '../../../components/Button'
import { Input } from '../../../components/Input'
import { ApiError } from '../../../lib/api/client'
import type { components } from '../../../lib/api/schema'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'
import { MIN_SEARCH_LENGTH, type ContractSearch } from '../../contracts/filters'
import { useCreateSavedSearch } from '../hooks/useSavedSearches'

type SavedSearchParameters = components['schemas']['SavedSearchParameters']

export function toSavedSearchParameters(search: ContractSearch): SavedSearchParameters {
  const trimmed = search.search?.trim()
  return {
    min_price: search.min_price,
    max_price: search.max_price,
    region_ids: search.region_ids,
    is_bpc: search.is_bpc,
    ships_only: search.ships_only,
    size: search.size,
    sort_by: search.sort_by,
    sort_direction: search.sort_direction,
    search: trimmed !== undefined && trimmed.length >= MIN_SEARCH_LENGTH ? trimmed : undefined,
  }
}

export function SaveSearchControl({ search }: { search: ContractSearch }) {
  const { data: user } = useCurrentUser()
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const create = useCreateSavedSearch()

  if (!user) return null

  if (!open) {
    return (
      <Button
        className="ml-auto"
        onClick={() => {
          create.reset()
          setOpen(true)
        }}
      >
        Save search
      </Button>
    )
  }

  const conflict = create.error instanceof ApiError && create.error.status === 409
  const close = () => {
    setOpen(false)
    setName('')
    create.reset()
  }

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const trimmed = name.trim()
    if (trimmed.length === 0) return
    create.mutate(
      { name: trimmed, search_parameters: toSavedSearchParameters(search) },
      { onSuccess: () => close() },
    )
  }

  return (
    <form onSubmit={submit} aria-label="Save this search" className="ml-auto flex flex-wrap items-center gap-2">
      <label htmlFor="save-search-name" className="sr-only">Search name</label>
      <Input
        id="save-search-name"
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="Name this search"
      />
      <Button type="submit" variant="primary" disabled={create.isPending || name.trim().length === 0}>
        Save
      </Button>
      <Button type="button" onClick={close}>Cancel</Button>
      {conflict ? (
        <p role="alert" aria-live="polite" className="w-full text-xs text-danger">
          A saved search with that name already exists.
        </p>
      ) : create.isError ? (
        <p role="alert" aria-live="polite" className="w-full text-xs text-danger">
          Could not save the search. Try again.
        </p>
      ) : null}
    </form>
  )
}
