import { describe, expect, it } from 'vitest'

import type { CurrentUser, UserRole } from '../api/types'
import { SECTION_LABELS, type SectionKey } from '../lib/labels'
import {
  canOpenSection,
  landingPath,
  navigationSections,
  PROVIDER_SECTIONS,
  SCHOOL_SECTIONS,
  SECTIONS,
  sectionPath,
} from './sections'

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

// The scope of GET /api/auth/me: only the school role carries a school of its own (ADR-008).
const SCOPES: Record<UserRole, CurrentUser['scope']> = {
  school: { regionId: 7, regionName: 'Усть-Каменогорск', providerId: null, schoolId: 12 },
  district: { regionId: 7, regionName: 'Усть-Каменогорск', providerId: null, schoolId: null },
  provider: { regionId: null, regionName: null, providerId: 3, schoolId: null },
  oblast: { regionId: null, regionName: null, providerId: null, schoolId: null },
  admin: { regionId: null, regionName: null, providerId: null, schoolId: null },
}

const user = (role: UserRole): Pick<CurrentUser, 'role' | 'permissions' | 'scope'> => ({
  role,
  permissions: PERMISSIONS[role],
  scope: SCOPES[role],
})

const keys = (role: UserRole): SectionKey[] => navigationSections(user(role)).map((section) => section.key)

describe('navigation of a role', () => {
  it('leaves the provider his cabinet: his lines, their incidents and appeals (ТЗ п. 16)', () => {
    expect(keys('provider')).toEqual([...PROVIDER_SECTIONS])
    expect(keys('provider')).not.toContain('admin')
  })

  it('leaves the school its own card and its letters to the provider (DESIGN.md §3.27)', () => {
    expect(keys('school')).toEqual([...SCHOOL_SECTIONS])
  })

  it('keeps the whole panel for the roles of the oblast', () => {
    expect(keys('oblast')).toEqual(['overview', 'map', 'schools', 'devices', 'incidents', 'appeals', 'rollout', 'analytics', 'exports', 'admin'])
    expect(keys('admin')).toContain('admin')
    // Район/город sees everything but «Администрирование»: it has none of its rights.
    expect(keys('district')).toEqual(['overview', 'map', 'schools', 'devices', 'incidents', 'appeals', 'rollout', 'analytics', 'exports'])
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
  })

  it('sends the school role to its own card, which renders the cabinet (T-61)', () => {
    expect(landingPath(user('school'))).toBe('/schools/12')
  })

  it('falls back to the first section while the user is unknown or has no school of his own', () => {
    expect(landingPath(undefined)).toBe(SECTIONS[0].path)
    const homeless = { ...user('school'), scope: { ...SCOPES.school, schoolId: null } }
    expect(landingPath(homeless)).toBe('/schools')
  })
})

describe('sections themselves', () => {
  it('keeps the order of DESIGN.md §3.6, with «Администрирование» last', () => {
    expect(SECTIONS.map((section) => section.key)).toEqual([
      'overview',
      'map',
      'schools',
      'devices',
      'incidents',
      'appeals',
      'rollout',
      'analytics',
      'exports',
      'admin',
    ])
  })

  it('gives the address of a section to a link that crosses sections', () => {
    expect(sectionPath('appeals')).toBe('/appeals')
    expect(sectionPath('schools')).toBe('/schools')
  })

  it('names every section of the dictionary exactly once (ADR-013)', () => {
    expect(SECTIONS.map((section) => section.key).sort()).toEqual(Object.keys(SECTION_LABELS).sort())
    expect(PROVIDER_SECTIONS.every((key) => key in SECTION_LABELS)).toBe(true)
    expect(SCHOOL_SECTIONS.every((key) => key in SECTION_LABELS)).toBe(true)
  })
})
