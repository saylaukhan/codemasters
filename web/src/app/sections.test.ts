import { describe, expect, it } from 'vitest'

import type { CurrentUser, UserRole } from '../api/types'
import { SECTION_LABELS, type SectionKey } from '../lib/labels'
import { canOpenSection, landingPath, navigationSections, PROVIDER_SECTIONS, SECTIONS } from './sections'

// Rights of backend/app/auth/permissions.py: what GET /api/auth/me answers for a role.
const VIEW = [
  'dashboard:read',
  'map:read',
  'schools:read',
  'devices:read',
  'analytics:read',
  'incidents:read',
  'appeals:read',
  'exports:create',
  'notifications:read',
]
const MONITORING_SETUP = [
  'schools:write',
  'references:manage',
  'thresholds:manage',
  'schedules:manage',
  'incident_rules:manage',
  'settings:manage',
]
const ADMINISTRATION = ['users:manage', 'devices:manage', 'agent_releases:manage', 'audit:read']

const PERMISSIONS: Record<UserRole, string[]> = {
  school: [...VIEW, 'contacts:phone', 'appeals:create'],
  district: [...VIEW, 'contacts:phone', 'appeals:create', 'appeals:update', 'incidents:create', 'incidents:update'],
  provider: [...VIEW, 'appeals:update', 'incidents:update'],
  oblast: [...VIEW, 'contacts:phone', ...MONITORING_SETUP, 'appeals:create', 'incidents:create', 'incidents:update'],
  admin: [...VIEW, 'contacts:phone', ...MONITORING_SETUP, ...ADMINISTRATION, 'incidents:create', 'incidents:update'],
}

const user = (role: UserRole): Pick<CurrentUser, 'role' | 'permissions'> => ({
  role,
  permissions: PERMISSIONS[role],
})

const keys = (role: UserRole): SectionKey[] => navigationSections(user(role)).map((section) => section.key)

describe('navigation of a role', () => {
  it('leaves the provider his cabinet: his lines, their incidents and appeals (ТЗ п. 16)', () => {
    expect(keys('provider')).toEqual([...PROVIDER_SECTIONS])
    expect(keys('provider')).not.toContain('admin')
  })

  it('keeps the whole panel for the roles of the oblast', () => {
    expect(keys('oblast')).toEqual(['overview', 'map', 'schools', 'devices', 'analytics', 'incidents', 'appeals', 'exports', 'admin'])
    expect(keys('admin')).toContain('admin')
    // Школа and Район/город see everything but «Администрирование»: they have none of its rights.
    expect(keys('school')).not.toContain('admin')
    expect(keys('district')).not.toContain('admin')
  })

  it('opens nothing without permissions', () => {
    expect(navigationSections(undefined)).toEqual([])
    expect(navigationSections({ role: 'provider', permissions: [] })).toEqual([])
  })

  it('cuts the navigation of the provider, not his rights: the cards of his lines stay open', () => {
    // The school card of his line links to the card of a computer and reads the analytics of T-28.
    const byUrl = (key: SectionKey) =>
      canOpenSection(SECTIONS.find((section) => section.key === key)!, PERMISSIONS.provider)
    expect(byUrl('devices')).toBe(true)
    expect(byUrl('analytics')).toBe(true)
    expect(byUrl('admin')).toBe(false)
  })
})

describe('landing of «/»', () => {
  it('sends every role to the first section of its navigation', () => {
    expect(landingPath(user('provider'))).toBe('/schools')
    expect(landingPath(user('oblast'))).toBe('/overview')
    expect(landingPath(user('school'))).toBe('/overview')
  })

  it('falls back to the first section while the user is unknown', () => {
    expect(landingPath(undefined)).toBe(SECTIONS[0].path)
  })
})

describe('sections themselves', () => {
  it('names every section of the dictionary exactly once (ADR-013)', () => {
    expect(SECTIONS.map((section) => section.key).sort()).toEqual(Object.keys(SECTION_LABELS).sort())
    expect(PROVIDER_SECTIONS.every((key) => key in SECTION_LABELS)).toBe(true)
  })
})
