import { Link } from '@tanstack/react-router'
import { Badge } from '../../../components/Badge'
import { Button } from '../../../components/Button'
import { ApiError } from '../../../lib/api/client'
import { formatIsk, primaryLabel, timeRemaining } from '../format'
import { useContract } from '../hooks/useContract'

const DATETIME = new Intl.DateTimeFormat('en-US', {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: 'UTC',
})

function BackLink() {
  return (
    <Link
      to="/contracts"
      className="text-sm text-ink-dim transition-colors duration-150 hover:text-brand"
    >
      ← All contracts
    </Link>
  )
}

function Field({ label, children, mono = true }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-line py-2 last:border-b-0">
      <dt className="text-sm text-ink-dim">{label}</dt>
      <dd className={`text-right ${mono ? 'text-data' : 'text-sm'} text-ink`}>{children}</dd>
    </div>
  )
}

export function ContractDetailPage({ contractId }: { contractId: number }) {
  const { data, isPending, isError, error, refetch } = useContract(contractId)

  if (!Number.isInteger(contractId) || contractId <= 0) {
    return <NotFound />
  }
  if (isPending) {
    return (
      <div className="mx-auto max-w-3xl" role="status" aria-label="Loading contract">
        <span className="skeleton block h-4 w-28" />
        <span className="skeleton mt-4 block h-7 w-64" />
        <span className="skeleton mt-6 block h-40 w-full" />
        <span className="sr-only">Loading contract…</span>
      </div>
    )
  }
  if (isError) {
    if (error instanceof ApiError && error.status === 404) return <NotFound />
    return (
      <div className="mx-auto max-w-3xl">
        <BackLink />
        <div
          role="alert"
          className="mt-4 flex flex-col items-start gap-3 rounded-md border border-danger/40 bg-danger-wash px-4 py-4"
        >
          <p className="text-sm text-ink">Failed to load this contract.</p>
          <Button onClick={() => refetch()}>Retry</Button>
        </div>
      </div>
    )
  }

  const isBpc = data.items.some((item) => item.is_included && item.is_blueprint_copy)
  const expiry = timeRemaining(data.date_expired)

  return (
    <div className="mx-auto max-w-3xl">
      <BackLink />
      <header className="mt-3 mb-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          {/* Hull-first, matching the list (primaryLabel prefers the included
              ship, then first item, then the seller's title, then the id). */}
          <h1 className="text-[1.375rem] font-semibold">{primaryLabel(data)}</h1>
          <span className="inline-flex gap-1.5">
            <Badge tone={data.type === 'auction' ? 'brand' : 'neutral'}>
              {data.type === 'auction' ? 'Auction' : 'Exchange'}
            </Badge>
            {isBpc ? <Badge tone="copper">BPC</Badge> : null}
            {expiry === 'Expired' ? <Badge tone="neutral">Expired</Badge> : null}
          </span>
        </div>
        {/* The seller's own words, when they wrote any and they aren't already
            the heading. */}
        {data.title?.trim() && data.title.trim() !== primaryLabel(data) ? (
          <p className="mt-1 text-sm text-ink-dim">“{data.title.trim()}”</p>
        ) : null}
      </header>

      <div className="grid gap-x-10 gap-y-6 md:grid-cols-2">
        <section aria-labelledby="economics-heading">
          <h2 id="economics-heading" className="text-label mb-1">
            Economics
          </h2>
          <dl>
            <div className="flex items-baseline justify-between gap-4 border-b border-line py-2">
              <dt className="text-sm text-ink-dim">Price</dt>
              <dd className="text-data text-right !text-base font-medium text-(--color-copper)">
                {formatIsk(data.price)} ISK
              </dd>
            </div>
            {data.reward != null && data.reward > 0 ? (
              <Field label="Reward">{formatIsk(data.reward)} ISK</Field>
            ) : null}
            <Field label="Volume">
              {data.volume != null ? `${data.volume.toLocaleString('en-US')} m³` : '—'}
            </Field>
            <Field label="For corporation" mono={false}>
              {data.for_corporation ? 'Yes' : 'No'}
            </Field>
          </dl>
        </section>

        <section aria-labelledby="identification-heading">
          <h2 id="identification-heading" className="text-label mb-1">
            Identification
          </h2>
          <dl>
            <Field label="Issuer" mono={false}>
              {data.issuer_name ?? `Character ${data.issuer_id}`}
            </Field>
            <Field label="Corporation" mono={false}>
              {data.issuer_corporation_name ?? `Corporation ${data.issuer_corporation_id}`}
            </Field>
            <Field label="Location" mono={false}>
              {data.start_location_name ?? `Location ${data.start_location_id}`}
            </Field>
            <Field label="Issued">{DATETIME.format(new Date(data.date_issued))}</Field>
            <Field label="Expires">
              {DATETIME.format(new Date(data.date_expired))}
              {expiry !== 'Expired' ? (
                <span className="ml-2 text-ink-dim">({expiry})</span>
              ) : null}
            </Field>
          </dl>
        </section>
      </div>

      <section aria-labelledby="contents-heading" className="mt-8">
        <h2 id="contents-heading" className="text-label mb-2">
          Contents · {data.items.length.toLocaleString('en-US')}
        </h2>
        {data.items.length === 0 ? (
          <p className="rounded-md border border-line bg-surface px-4 py-3 text-sm text-ink-dim">
            No item data recorded for this contract.
          </p>
        ) : (
          <ul className="rounded-md border border-line">
            {data.items.map((item) => (
              <li
                key={item.record_id}
                className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-line px-4 py-2 last:border-b-0"
              >
                <span className="text-data text-ink">
                  {item.quantity.toLocaleString('en-US')}×{' '}
                  {item.type_name ?? `Type ${item.type_id}`}
                </span>
                {item.category === 'ship' ? <Badge tone="brand">Ship</Badge> : null}
                {item.is_blueprint_copy ? <Badge tone="copper">BPC</Badge> : null}
                {!item.is_included ? (
                  <span className="text-xs text-warn">asked for, not included</span>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}

function NotFound() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col items-start gap-3">
      <h1 className="text-[1.375rem] font-semibold">Contract not found.</h1>
      <p className="text-sm text-ink-dim">
        It may have expired, been claimed, or never existed in this dataset.
      </p>
      <BackLink />
    </div>
  )
}
