import type { ReactNode } from 'react'

export function CheckboxField({
  label,
  checked,
  onChange,
  disabled = false,
}: {
  label: ReactNode
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2 rounded-sm py-0.5 text-sm text-ink-body select-none hover:text-ink">
      <input
        type="checkbox"
        className="size-4 shrink-0 cursor-pointer accent-(--color-brand)"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
      />
      {label}
    </label>
  )
}
