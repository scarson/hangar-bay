import { createFileRoute } from '@tanstack/react-router'
import { ContractDetailPage } from '../features/contracts/components/ContractDetailPage'

export const Route = createFileRoute('/contracts/$contractId')({
  component: RouteComponent,
})

// Named (uppercase) component so eslint-plugin-react-hooks@7 recognizes the
// Route.useParams() call as a hook-in-a-component; an anonymous `component: () =>`
// arrow trips react-hooks/rules-of-hooks. Behavior is identical.
function RouteComponent() {
  const { contractId } = Route.useParams()
  return <ContractDetailPage contractId={Number(contractId)} />
}
