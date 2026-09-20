// Sections of the panel: side navigation, routes and Refine resources (DESIGN.md §3.6).
import {
  ChartLine,
  Download,
  LayoutDashboard,
  Mail,
  Map as MapIcon,
  Monitor,
  School,
  Settings,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-react'

import type { CurrentUser, UserRole } from '../api/types'
import type { AdminTabKey, SectionKey } from '../lib/labels'

export interface Section {
  key: SectionKey
  path: string
  icon: LucideIcon
  /** The section is shown when the user has any of these permissions (GET /api/auth/me). */
  permissions: readonly string[]
  /** Task of docs/tasks/README.md that builds the screen; the shell shows a placeholder until then. */
  task: string
}

// Codes of backend/app/auth/permissions.py: technical settings and administration.
const ADMIN_PERMISSIONS = [
  'schools:write',
  'references:manage',
  'thresholds:manage',
  'schedules:manage',
  'incident_rules:manage',
  'settings:manage',
  'users:manage',
  'devices:manage',
  'agent_releases:manage',
  'audit:read',
] as const

export const SECTIONS: readonly Section[] = [
  { key: 'overview', path: '/overview', icon: LayoutDashboard, permissions: ['dashboard:read'], task: 'T-22' },
  { key: 'map', path: '/map', icon: MapIcon, permissions: ['map:read'], task: 'T-22' },
  { key: 'schools', path: '/schools', icon: School, permissions: ['schools:read'], task: 'T-24' },
  { key: 'devices', path: '/devices', icon: Monitor, permissions: ['devices:read'], task: 'T-26' },
  { key: 'analytics', path: '/analytics', icon: ChartLine, permissions: ['analytics:read'], task: 'T-27' },
  { key: 'incidents', path: '/incidents', icon: TriangleAlert, permissions: ['incidents:read'], task: 'T-41' },
  { key: 'appeals', path: '/appeals', icon: Mail, permissions: ['appeals:read'], task: 'T-47' },
  { key: 'exports', path: '/exports', icon: Download, permissions: ['exports:create'], task: 'T-30' },
  { key: 'admin', path: '/admin', icon: Settings, permissions: ADMIN_PERMISSIONS, task: 'T-34' },
]

/** Hidden, not disabled: a role never sees a section it cannot use (ТЗ п. 16, ADR-008). */
export const canOpenSection = (section: Section, granted: readonly string[] | undefined): boolean =>
  section.permissions.some((permission) => granted?.includes(permission))

/**
 * Cabinet of the provider (T-44, plan.md §9, §11; ТЗ п. 16): its lines, their incidents and the appeals about them —
 * the provider is a participant of the fix, not a viewer of the whole oblast. Only the navigation is cut: the rights
 * of the role stay as they are (backend/app/auth/permissions.py), so the card of his school opens its charts and the
 * card of a computer on his line opens from it. What he sees inside every screen is decided by the scope and RLS.
 */
export const PROVIDER_SECTIONS: readonly SectionKey[] = ['schools', 'incidents', 'appeals']

export const isProviderCabinet = (role: UserRole | undefined): boolean => role === 'provider'

const inCabinet = (section: Section, role: UserRole | undefined): boolean =>
  !isProviderCabinet(role) || PROVIDER_SECTIONS.includes(section.key)

/** Sections of the side navigation for the user: his permissions and, for the provider, his cabinet. */
export const navigationSections = (
  user: Pick<CurrentUser, 'role' | 'permissions'> | undefined,
  granted: readonly string[] | undefined = user?.permissions,
): Section[] => SECTIONS.filter((section) => canOpenSection(section, granted) && inCabinet(section, user?.role))

/** Where «/» leads: the first section of the navigation — «Обзор» for most roles, «Школы» in the provider cabinet. */
export const landingPath = (user: Pick<CurrentUser, 'role' | 'permissions'> | undefined): string =>
  navigationSections(user)[0]?.path ?? SECTIONS[0].path

/** Card of one school (T-25): the popover of the map and the lists lead here. */
export const schoolCardPath = (schoolId: number): string => `/schools/${schoolId}`

/** Card of one computer (T-26): the computers of the school card lead here. */
export const deviceCardPath = (deviceId: number): string => `/devices/${deviceId}`

/** Card of one incident (T-41): the list, the school card and notifications lead here. */
export const incidentCardPath = (incidentId: number): string => `/incidents/${incidentId}`

/** Tab of «Администрирование» (T-34): schools and the references, each at its own address. */
export const adminTabPath = (tab: AdminTabKey): string => `/admin/${tab}`
