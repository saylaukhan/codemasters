import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { NARROW_SCREEN, PHONE_SCREEN } from '../styles/theme'
import { useMediaQuery } from './useMediaQuery'

function Probe({ query }: { query: string }) {
  return <span>{useMediaQuery(query) ? 'narrow' : 'wide'}</span>
}

// vitest runs on `node` (vite.config.ts), and every component test renders through
// renderToStaticMarkup — the path that reads the server snapshot. The client path
// (subscribe + getSnapshot) needs a real DOM and is checked in the browser, DESIGN.md §8.1.
describe('useMediaQuery', () => {
  it('answers «wide» where there is no window, instead of throwing', () => {
    expect(renderToStaticMarkup(<Probe query={NARROW_SCREEN} />)).toContain('wide')
    expect(renderToStaticMarkup(<Probe query={PHONE_SCREEN} />)).toContain('wide')
  })

  it('keeps the wide layout in markup even when a window is around', () => {
    const matchMedia = () => ({ matches: true, addEventListener: () => {}, removeEventListener: () => {} })
    Object.defineProperty(globalThis, 'window', { value: { matchMedia }, configurable: true })
    try {
      expect(renderToStaticMarkup(<Probe query={NARROW_SCREEN} />)).toContain('wide')
    } finally {
      Reflect.deleteProperty(globalThis, 'window')
    }
  })
})
