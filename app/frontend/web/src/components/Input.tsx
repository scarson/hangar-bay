import type { InputHTMLAttributes } from 'react'

export function Input({ className = '', ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`h-8 w-full rounded-sm border border-line-strong bg-void px-2 text-sm text-ink transition-colors duration-150 placeholder:text-ink-faint hover:border-ink-faint focus:border-brand focus:outline-none ${className}`}
      {...props}
    />
  )
}
