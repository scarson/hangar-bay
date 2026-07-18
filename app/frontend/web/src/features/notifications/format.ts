// ABOUTME: Relative-time formatting for notification timestamps ("3h ago"); now is injectable for deterministic tests.
// ABOUTME: Coarse by design — minutes, hours, then days — mirroring the list view's timeRemaining granularity.
export function timeAgo(iso: string, now: number = Date.now()): string {
  const ms = now - new Date(iso).getTime()
  if (Number.isNaN(ms)) return '—'
  const minutes = Math.floor(ms / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}
