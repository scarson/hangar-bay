import { createFileRoute } from '@tanstack/react-router'
import { SavedSearchesPage } from '../features/saved-searches/components/SavedSearchesPage'

export const Route = createFileRoute('/saved-searches')({
  component: RouteComponent,
})

// Named (uppercase) component so eslint-plugin-react-hooks@7 recognizes the hooks
// inside SavedSearchesPage as hooks-in-a-component (same rationale as contracts.index.tsx).
function RouteComponent() {
  return <SavedSearchesPage />
}
