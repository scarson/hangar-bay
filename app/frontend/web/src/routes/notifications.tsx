// ABOUTME: /notifications route — registered here so the header bell's typed Link compiles (Task 8.2 deviation);
// ABOUTME: Task 8.3 replaces this placeholder with the full NotificationsPage.
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/notifications')({
  component: RouteComponent,
})

function RouteComponent() {
  return <h1 className="text-h1 text-ink">Notifications</h1>
}
