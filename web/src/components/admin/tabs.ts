import type { AdminTabKey } from '../../lib/labels'

export interface AdminTab {
  key: AdminTabKey
  /** Code of backend/app/auth/permissions.py the tab needs; a tab without it is hidden (ТЗ п. 16). */
  permission: string
}

/** Tabs of «Администрирование» in their order; the logs are the Администратор's only (T-39). */
export const ADMIN_TABS: readonly AdminTab[] = [
  { key: 'schools', permission: 'schools:write' },
  { key: 'contracts', permission: 'schools:write' },
  { key: 'devices', permission: 'devices:manage' },
  { key: 'users', permission: 'users:manage' },
  { key: 'regions', permission: 'references:manage' },
  { key: 'providers', permission: 'references:manage' },
  { key: 'connection-types', permission: 'references:manage' },
  { key: 'thresholds', permission: 'thresholds:manage' },
  { key: 'schedules', permission: 'schedules:manage' },
  { key: 'incident-rules', permission: 'incident_rules:manage' },
  { key: 'appeal-templates', permission: 'appeal_templates:manage' },
  { key: 'settings', permission: 'settings:manage' },
  { key: 'audit', permission: 'audit:read' },
  { key: 'events', permission: 'audit:read' },
]

export const allowedTabs = (granted: readonly string[] | undefined): AdminTab[] =>
  ADMIN_TABS.filter((tab) => granted?.includes(tab.permission))
