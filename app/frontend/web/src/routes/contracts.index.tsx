import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/contracts/')({
  component: () => <main className="p-4">Contract browsing arrives in Task 8.</main>,
})
