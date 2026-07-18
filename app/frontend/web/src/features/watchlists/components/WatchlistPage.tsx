// ABOUTME: F006 watchlist page — add-by-name form (name + optional max price/notes) and inline-editable rows with clear-to-null and two-step remove.
// ABOUTME: Empty max-price/notes on ADD is omitted (create); an emptied field on EDIT sends explicit null (clear) per the backend PUT semantics.
import { useEffect, useState } from 'react'
import { Button } from '../../../components/Button'
import { Input } from '../../../components/Input'
import { ApiError, type WatchlistItem } from '../../../lib/api/client'
import { useDocumentTitle } from '../../../lib/useDocumentTitle'
import { RequireSignIn } from '../../auth/components/RequireSignIn'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'
import { formatIsk } from '../../contracts/format'
import { useAddWatchlistItem, useRemoveWatchlistItem, useUpdateWatchlistItem, useWatchlist } from '../hooks/useWatchlist'

export function WatchlistPage() {
  useDocumentTitle('Watchlist')
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return (
      <div role="status" aria-label="Loading account" className="mx-auto max-w-3xl">
        <span className="skeleton block h-7 w-48" />
        <span className="sr-only">Loading…</span>
      </div>
    )
  }
  if (!user) return <RequireSignIn feature="your watchlist" />
  return <WatchlistBody />
}

function WatchlistBody() {
  const { data, isPending, isError } = useWatchlist()
  return (
    <div className="mx-auto max-w-3xl">
      <p className="sr-only" role="status" aria-live="polite" />
      <h1 className="text-h1 mb-4 font-semibold">Watchlist</h1>
      <AddByNameForm />
      {isPending ? (
        <div role="status" aria-label="Loading watchlist" className="mt-4">
          <span className="skeleton block h-16 w-full" />
          <span className="sr-only">Loading watchlist…</span>
        </div>
      ) : isError ? (
        <div role="alert" className="mt-4 rounded-md border border-danger/40 bg-danger-wash px-4 py-4 text-sm text-ink">
          Couldn’t load your watchlist. Reload the page to try again.
        </div>
      ) : data.length === 0 ? (
        <div className="mt-4 rounded-md border border-line bg-surface px-5 py-8">
          <h2 className="text-base font-medium text-ink">Your watchlist is empty</h2>
          <p className="mt-1 max-w-[52ch] text-sm text-ink-dim">
            Add a ship by name above, or use the “Watch” button on any contract that lists one.
          </p>
        </div>
      ) : (
        <ul className="mt-4 flex flex-col gap-2">
          {data.map((item) => (
            <WatchlistRow key={item.id} item={item} />
          ))}
        </ul>
      )}
    </div>
  )
}

function AddByNameForm() {
  const add = useAddWatchlistItem()
  const [name, setName] = useState('')
  const [maxPrice, setMaxPrice] = useState('')
  const [notes, setNotes] = useState('')
  const [priceError, setPriceError] = useState('')

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    const typeName = name.trim()
    if (typeName.length === 0) return
    const price = maxPrice.trim()
    const note = notes.trim()
    // The backend requires max_price >= 0.01; guard 0 (and anything below) here and show an inline
    // message instead of POSTing a value we know will 422.
    if (price !== '' && Number(price) < 0.01) {
      setPriceError('Max price must be at least 0.01 ISK, or leave it blank for any price.')
      return
    }
    setPriceError('')
    add.mutate(
      {
        type_name: typeName,
        ...(price !== '' ? { max_price: Number(price) } : {}),
        ...(note !== '' ? { notes: note } : {}),
      },
      {
        onSuccess: () => {
          setName('')
          setMaxPrice('')
          setNotes('')
        },
      },
    )
  }

  const status = add.error instanceof ApiError ? add.error.status : undefined
  const message =
    status === 400 ? 'Couldn’t find a ship with that exact name. Check the spelling.'
    : status === 409 ? 'You’re already watching that ship.'
    : status === 502 ? 'EVE’s type service is unavailable right now. Try again shortly.'
    : add.isError ? 'Couldn’t add that ship. Try again.'
    : undefined

  return (
    <form onSubmit={submit} noValidate aria-label="Add a ship to your watchlist" className="flex flex-wrap items-end gap-3 rounded-md border border-line bg-surface p-4">
      <div className="flex min-w-[12rem] flex-1 flex-col gap-1">
        <label htmlFor="watch-name" className="text-label">Ship name</label>
        <Input id="watch-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Maelstrom" />
      </div>
      <div className="flex w-40 flex-col gap-1">
        <label htmlFor="watch-price" className="text-label">Max price (ISK)</label>
        <Input
          id="watch-price"
          type="number"
          min="0.01"
          step="0.01"
          value={maxPrice}
          onChange={(e) => { setMaxPrice(e.target.value); if (priceError) setPriceError('') }}
          placeholder="optional"
          aria-invalid={priceError ? true : undefined}
          aria-describedby={priceError ? 'watch-price-error' : undefined}
        />
      </div>
      <div className="flex min-w-[10rem] flex-1 flex-col gap-1">
        <label htmlFor="watch-notes" className="text-label">Notes</label>
        <Input id="watch-notes" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="optional" />
      </div>
      <Button type="submit" variant="primary" disabled={add.isPending || name.trim().length === 0}>
        Add to watchlist
      </Button>
      {priceError ? (
        <p id="watch-price-error" role="alert" aria-live="polite" className="w-full text-xs text-danger">{priceError}</p>
      ) : message ? (
        <p role="alert" aria-live="polite" className="w-full text-xs text-danger">{message}</p>
      ) : null}
    </form>
  )
}

function WatchlistRow({ item }: { item: WatchlistItem }) {
  const update = useUpdateWatchlistItem()
  const remove = useRemoveWatchlistItem()
  const [maxPrice, setMaxPrice] = useState(item.max_price != null ? String(item.max_price) : '')
  const [notes, setNotes] = useState(item.notes ?? '')
  const [confirmRemove, setConfirmRemove] = useState(false)

  // Auto-disarm the two-step remove after 5s so a stray first click can't leave the row armed
  // indefinitely (blur also disarms; this covers the focus-retained case). Cleared on unmount/re-arm.
  useEffect(() => {
    if (!confirmRemove) return
    const timer = setTimeout(() => setConfirmRemove(false), 5000)
    return () => clearTimeout(timer)
  }, [confirmRemove])

  // Empty input → explicit null (clear); a value → the number/string. Both fields are
  // always sent, so the backend's omit-preserves path is never relied on from the UI.
  const save = () =>
    update.mutate({
      id: item.id,
      body: {
        max_price: maxPrice.trim() === '' ? null : Number(maxPrice),
        notes: notes.trim() === '' ? null : notes.trim(),
      },
    })

  const clearMaxPrice = () => {
    setMaxPrice('')
    update.mutate({ id: item.id, body: { max_price: null } })
  }

  return (
    <li className="flex flex-wrap items-center gap-3 rounded-md border border-line bg-surface px-4 py-3">
      <img
        src={`https://images.evetech.net/types/${item.type_id}/render?size=64`}
        alt=""
        width={32}
        height={32}
        className="h-8 w-8 rounded-sm"
      />
      <span className="min-w-0 flex-1 truncate font-medium text-ink">{item.type_name}</span>
      <div className="flex items-center gap-1">
        <label htmlFor={`price-${item.id}`} className="sr-only">Max price for {item.type_name}</label>
        <Input
          id={`price-${item.id}`}
          type="number"
          min="0.01"
          step="0.01"
          className="w-32 text-data"
          value={maxPrice}
          onChange={(e) => setMaxPrice(e.target.value)}
          placeholder={item.max_price != null ? formatIsk(item.max_price) : 'any price'}
        />
        <Button type="button" onClick={clearMaxPrice} aria-label={`Clear max price for ${item.type_name}`}>Clear</Button>
      </div>
      <div className="flex items-center gap-1">
        <label htmlFor={`notes-${item.id}`} className="sr-only">Notes for {item.type_name}</label>
        <Input id={`notes-${item.id}`} className="w-40" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="notes" />
      </div>
      <Button type="button" variant="primary" onClick={save} disabled={update.isPending}>Save</Button>
      {confirmRemove ? (
        <Button type="button" className="text-danger" disabled={remove.isPending} onClick={() => remove.mutate(item.id)} onBlur={() => setConfirmRemove(false)}>
          Confirm remove?
        </Button>
      ) : (
        <Button type="button" className="text-danger" onClick={() => setConfirmRemove(true)}>Remove</Button>
      )}
    </li>
  )
}
