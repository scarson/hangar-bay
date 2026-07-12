import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/contracts/$contractId')({
  component: () => <main className="p-4">Contract detail arrives in Task 8.</main>,
})
