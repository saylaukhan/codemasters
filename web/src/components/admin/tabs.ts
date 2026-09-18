import type { AdminTabKey } from '../../lib/labels'

export interface AdminTab {
  key: AdminTabKey
  /** Code of backend/app/auth/permissions.py the tab needs; a tab without it is hidden (ТЗ п. 16). */
  permission: string
}

/** Tabs of «Администрирование» in their order; logs come with T-39. */
export const ADMIN_TABS: readonly AdminTab[] = [
  { key: 'schools', permission: 'schools:write' },
  { key: 'devices', permission: 'devices:manage' },
  { key: 'users', permission: 'users:manage' },
  { key: 'regions', permission: 'references:manage' },
  { key: 'providers', permission: 'references:manage' },
  { key: 'connection-types', permission: 'references:manage' },
  { key: 'thresholds', permission: 'thresholds:manage' },
  { key: 'schedules', permission: 'schedules:manage' },
  { key: 'settings', permission: 'settings:manage' },
]

export const allowedTabs = (granted: readonly string[] | undefined): AdminTab[] =>
  ADMIN_TABS.filter((tab) => granted?.includes(tab.permission))
