import type { Contract } from '../../lib/api/client'

// Fixed locale: M1 is explicitly English-only (spec Non-goals), and tests
// assert formatted values (pitfall TEST-3).
const ISK = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const DATE = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' })

export function formatIsk(value: number | null | undefined): string {
  return value == null ? '—' : ISK.format(value)
}

export function formatDate(iso: string): string {
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? '—' : DATE.format(date)
}

/**
 * Coarse countdown for the list view ("3d 4h", "5h 12m", "42m", "Expired").
 * `now` is injectable so tests stay deterministic (TEST-3).
 */
export function timeRemaining(dateExpired: string, now: number = Date.now()): string {
  const ms = new Date(dateExpired).getTime() - now
  if (Number.isNaN(ms)) return '—'
  if (ms <= 0) return 'Expired'
  const totalMinutes = Math.floor(ms / 60_000)
  const days = Math.floor(totalMinutes / 1_440)
  const hours = Math.floor((totalMinutes % 1_440) / 60)
  const minutes = totalMinutes % 60
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${Math.max(1, minutes)}m`
}

/**
 * Row/heading label. Real ESI titles are often "" (not null), which ?? passes
 * through — treat blank titles as absent (found live during M1 acceptance).
 */
export function primaryLabel(contract: Contract): string {
  const included = contract.items.find((item) => item.is_included && item.type_name)
  return included?.type_name ?? (contract.title?.trim() || `Contract ${contract.contract_id}`)
}
