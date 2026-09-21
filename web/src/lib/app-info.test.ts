import { describe, expect, it } from 'vitest'

import { APP_NAME, APP_TAGLINE, APP_VERSION } from './app-info'

describe('app-info', () => {
  it('exposes the application name and its tagline', () => {
    expect(APP_NAME).toBe('Jyldam')
    expect(APP_TAGLINE).toBe('Мониторинг интернета в школах ВКО')
  })

  it('exposes a semver application version', () => {
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+$/)
  })
})
