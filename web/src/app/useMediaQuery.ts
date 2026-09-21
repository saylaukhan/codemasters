import { useSyncExternalStore } from 'react'

const NEVER_CHANGES = () => {}

/**
 * Whether a CSS media query matches right now; re-renders when it flips (DESIGN.md §9.2). The
 * width decides, never the user agent. Outside a browser — the vitest `node` environment and
 * `renderToStaticMarkup` — there is no `window.matchMedia`, so the hook answers `false`: the
 * server snapshot is the wide layout, which is what the component tests assert.
 */
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const list = globalThis.window?.matchMedia?.(query)
      if (!list) return NEVER_CHANGES
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    () => globalThis.window?.matchMedia?.(query).matches ?? false,
    () => false,
  )
}
