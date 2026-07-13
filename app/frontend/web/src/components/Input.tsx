import type { InputHTMLAttributes } from 'react'

// Tailwind v4 resolves same-specificity utility clashes by source order in the
// compiled stylesheet, not by className/DOM order — `.text-sm` is emitted
// AFTER the custom `.text-data` @utility, so appending `text-data` alongside
// the base `text-sm` silently loses the font-size half of `text-data` (its
// font-family/tabular-nums still apply; the size reverts to 14px). Drop the
// base size whenever the caller supplies its own text-size utility so only
// one font-size utility ever lands on the element (§9.6 M1 nit).
const TEXT_SIZE_CLASS = /(?:^|\s)text-(?:data|xs|sm|base|lg|xl)(?:\s|$)/

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  const size = TEXT_SIZE_CLASS.test(className) ? '' : 'text-sm'
  return (
    <input
      className={`h-8 w-full rounded-sm border border-line-strong bg-void px-2 ${size} text-ink transition-colors duration-150 placeholder:text-ink-faint hover:border-ink-faint focus:border-brand ${className}`}
      {...props}
    />
  )
}
