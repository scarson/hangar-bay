// Mechanical scaffold UI — redesigned in the /impeccable phase.
import { Link } from '@tanstack/react-router'
import { ApiError } from '../../../lib/api/client'
import { useContract } from '../hooks/useContract'

export function ContractDetailPage({ contractId }: { contractId: number }) {
  const { data, isPending, isError, error, refetch } = useContract(contractId)

  if (!Number.isInteger(contractId) || contractId <= 0) {
    return <NotFound />
  }
  if (isPending) {
    return <main className="p-4">Loading contract…</main>
  }
  if (isError) {
    if (error instanceof ApiError && error.status === 404) return <NotFound />
    return (
      <main className="p-4">
        <p role="alert">
          Failed to load this contract.{' '}
          <button className="underline" onClick={() => refetch()}>
            Retry
          </button>
        </p>
      </main>
    )
  }

  return (
    <main className="p-4">
      <Link to="/contracts" className="underline">
        ← All contracts
      </Link>
      {/* Real ESI titles are often "" (not null), which ?? passes through —
          the heading would render empty. Treat blank titles as absent, matching
          ContractsPage's primaryLabel (found live during Task 9 acceptance). */}
      <h1 className="my-2 text-xl font-bold">{data.title?.trim() || `Contract ${data.contract_id}`}</h1>
      <dl className="grid max-w-xl grid-cols-2 gap-1">
        <dt className="font-semibold">Type</dt>
        <dd>{data.type}</dd>
        <dt className="font-semibold">Status</dt>
        <dd>{data.status}</dd>
        <dt className="font-semibold">Price (ISK)</dt>
        <dd>{data.price != null ? data.price.toLocaleString('en-US') : '—'}</dd>
        <dt className="font-semibold">Location</dt>
        <dd>{data.start_location_name ?? data.start_location_id}</dd>
        <dt className="font-semibold">Issuer</dt>
        <dd>{data.issuer_name ?? data.issuer_id}</dd>
        <dt className="font-semibold">Issued</dt>
        <dd>{new Date(data.date_issued).toLocaleString()}</dd>
        <dt className="font-semibold">Expires</dt>
        <dd>{new Date(data.date_expired).toLocaleString()}</dd>
      </dl>
      <h2 className="mt-4 font-semibold">Items</h2>
      <ul className="list-disc pl-6">
        {data.items.map((item) => (
          <li key={item.record_id}>
            {item.quantity}× {item.type_name ?? `Type ${item.type_id}`}
            {item.is_blueprint_copy ? ' (BPC)' : ''}
            {item.is_included ? '' : ' — asked for, not included'}
          </li>
        ))}
      </ul>
    </main>
  )
}

function NotFound() {
  return (
    <main className="p-4">
      <p>Contract not found.</p>
      <Link to="/contracts" className="underline">
        ← All contracts
      </Link>
    </main>
  )
}
