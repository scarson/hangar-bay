import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'ghost'

const variants: Record<Variant, string> = {
  primary:
    'bg-brand font-medium text-brand-ink hover:bg-brand-bright active:bg-brand-dim active:text-ink',
  ghost: 'border border-line-strong text-ink-body hover:bg-raised active:bg-overlay',
}

export function Button({
  variant = 'ghost',
  className = '',
  ...props
}: { variant?: Variant } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`inline-flex h-8 shrink-0 cursor-pointer items-center gap-1.5 rounded-md px-3 text-sm transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-40 ${variants[variant]} ${className}`}
      {...props}
    />
  )
}
