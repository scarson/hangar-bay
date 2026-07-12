import type { ReactNode } from 'react'

type Tone = 'neutral' | 'brand' | 'copper'

const tones: Record<Tone, string> = {
  neutral: 'border-line-strong text-ink-dim',
  brand: 'border-brand-dim text-brand',
  copper: 'border-(--color-copper)/50 text-(--color-copper)',
}

export function Badge({ tone = 'neutral', children }: { tone?: Tone; children: ReactNode }) {
  return (
    <span
      className={`inline-flex items-center rounded-sm border px-1.5 py-px font-mono text-[0.6875rem] tracking-[0.08em] uppercase ${tones[tone]}`}
    >
      {children}
    </span>
  )
}
