import { describe, expect, it } from 'vitest'

import { APP_NAME, APP_VERSION } from './app-info'

describe('app-info', () => {
  it('exposes the application name', () => {
    expect(APP_NAME).toBe('Мониторинг интернета ВКО')
  })

  it('exposes a semver application version', () => {
    expect(APP_VERSION).toMatch(/^\d+\.\d+\.\d+$/)
  })
})
