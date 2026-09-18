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

import type { SectionKey } from '../lib/labels'

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

/** Card of one school (T-25): the popover of the map and the lists lead here. */
export const schoolCardPath = (schoolId: number): string => `/schools/${schoolId}`
