import { Button } from '../../../components/Button'

export function Pagination({
  page,
  size,
  total,
  onPage,
}: {
  page: number
  size: number
  total: number
  onPage: (page: number) => void
}) {
  const pageCount = Math.max(1, Math.ceil(total / size))
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-4">
      <Button disabled={page <= 1} onClick={() => onPage(page - 1)}>
        ← Previous
      </Button>
      <span className="text-data text-ink-dim">
        Page {page} of {pageCount} · {total.toLocaleString('en-US')} contracts
      </span>
      <Button disabled={page >= pageCount} onClick={() => onPage(page + 1)}>
        Next →
      </Button>
    </nav>
  )
}
