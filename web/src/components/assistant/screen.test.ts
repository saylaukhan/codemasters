import { describe, expect, it } from 'vitest'

import { assistantScreen } from './screen'

describe('assistantScreen (T-84)', () => {
  it('names the section behind an address of the navigation', () => {
    expect(assistantScreen('/overview', 'oblast')).toBe('overview')
    expect(assistantScreen('/map', 'district')).toBe('map')
    expect(assistantScreen('/schools', 'admin')).toBe('schools')
    expect(assistantScreen('/incidents', 'provider')).toBe('incidents')
    expect(assistantScreen('/appeals', 'school')).toBe('appeals')
    expect(assistantScreen('/providers', 'oblast')).toBe('providers')
    expect(assistantScreen('/rollout', 'oblast')).toBe('rollout')
    expect(assistantScreen('/analytics?period=week', 'district')).toBe('analytics')
    expect(assistantScreen('/exports', 'school')).toBe('exports')
    expect(assistantScreen('/admin/thresholds', 'admin')).toBe('admin')
  })

  it('tells a card from its list by the id, and the cabinet of a school by the role (T-61)', () => {
    expect(assistantScreen('/schools/12', 'school')).toBe('school_cabinet')
    expect(assistantScreen('/schools/12', 'district')).toBe('school_card')
    expect(assistantScreen('/schools/12', undefined)).toBe('school_card')
    expect(assistantScreen('/devices/7', 'admin')).toBe('device_card')
    expect(assistantScreen('/incidents/412', 'provider')).toBe('incident_card')
    expect(assistantScreen('/appeals/45', 'school')).toBe('appeal_card')
    expect(assistantScreen('/appeals/new?incident_id=412', 'district')).toBe('appeal_draft')
  })

  it('answers «other» for an address without a screen of its own', () => {
    for (const path of ['/', '/login', '/wall', '/devices', '/password-reset', '/nowhere']) {
      expect(assistantScreen(path, 'admin'), path).toBe('other')
    }
  })
})
