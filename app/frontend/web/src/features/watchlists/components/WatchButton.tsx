// ABOUTME: Quick-watch button for a listed ship on the contract-detail page — authed-only, one-click add by type_id, no price field.
// ABOUTME: 409 renders "Already watching" inline; success renders "Watching" (display-tier feedback, no toast primitive exists).
import { Button } from '../../../components/Button'
import { ApiError } from '../../../lib/api/client'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'
import { useAddWatchlistItem } from '../hooks/useWatchlist'

export function WatchButton({ typeId }: { typeId: number }) {
  const { data: user } = useCurrentUser()
  const add = useAddWatchlistItem()

  if (!user) return null
  if (add.isSuccess) return <span className="text-xs text-ok">Watching</span>
  if (add.error instanceof ApiError && add.error.status === 409) {
    return <span className="text-xs text-ink-dim">Already watching</span>
  }
  return (
    <Button variant="ghost" disabled={add.isPending} onClick={() => add.mutate({ type_id: typeId })}>
      Watch
    </Button>
  )
}
