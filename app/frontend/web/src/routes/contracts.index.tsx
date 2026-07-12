import { createFileRoute, type SearchSchemaInput } from '@tanstack/react-router'
import { ContractsPage } from '../features/contracts/components/ContractsPage'
import { parseContractSearch, type ContractSearch } from '../features/contracts/filters'

export const Route = createFileRoute('/contracts/')({
  // The `& SearchSchemaInput` marker makes the /contracts search params optional
  // for navigation (parseContractSearch defaults every field), so the plan's bare
  // `redirect({ to: '/contracts' })` and `<Link to="/contracts">` type-check.
  // useSearch() still yields the fully-resolved ContractSearch.
  validateSearch: (input: Record<string, unknown> & SearchSchemaInput): ContractSearch =>
    parseContractSearch(input),
  component: RouteComponent,
})

// Named (uppercase) component so eslint-plugin-react-hooks@7 recognizes the
// Route.useSearch() call as a hook-in-a-component; an anonymous `component: () =>`
// arrow trips react-hooks/rules-of-hooks. Behavior is identical.
function RouteComponent() {
  return <ContractsPage search={Route.useSearch()} from={Route.fullPath} />
}
