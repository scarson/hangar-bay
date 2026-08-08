// ABOUTME: Trailing-edge debounce for a changing value — returns the input once it has
// ABOUTME: held still for delayMs. Initializes AT the first value, so cold loads see no delay.
import { useEffect, useState } from 'react'

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return debounced
}
