import { createFileRoute } from '@tanstack/react-router'
import { WatchlistPage } from '../features/watchlists/components/WatchlistPage'

export const Route = createFileRoute('/watchlist')({
  component: RouteComponent,
})

function RouteComponent() {
  return <WatchlistPage />
}
