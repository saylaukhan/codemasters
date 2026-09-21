import { useEffect, useState } from 'react'

/**
 * `value` as it was `delayMs` after the last change: filters that fire a request wait for the person to stop
 * changing them. Every change restarts the wait, and unmounting drops it.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [delayed, setDelayed] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setDelayed(value), delayMs)
    return () => clearTimeout(timer)
  }, [value, delayMs])
  return delayed
}
