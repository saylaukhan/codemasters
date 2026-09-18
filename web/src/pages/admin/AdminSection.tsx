import { usePermissions } from '@refinedev/core'
import { Construction, ShieldX } from 'lucide-react'
import type { ComponentType } from 'react'
import { Navigate, Route, Routes } from 'react-router'

import { ADMIN_TABS, allowedTabs } from '../../components/admin/tabs'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader } from '../../components/ui/PageHeader'
import { SECTION_LABELS, type AdminTabKey } from '../../lib/labels'
import { NotFoundPage } from '../section/NotFoundPage'
import { AuditLogPage, EventLogPage } from './AuditLogPage'
import { ConnectionTypesPage } from './ConnectionTypesPage'
import { DevicesAdminPage } from './DevicesAdminPage'
import { IncidentRulesPage } from './IncidentRulesPage'
import { ProvidersPage } from './ProvidersPage'
import { RegionsPage } from './RegionsPage'
import { SchedulesPage } from './SchedulesPage'
import { SchoolsAdminPage } from './SchoolsAdminPage'
import { SettingsPage } from './SettingsPage'
import { ThresholdsPage } from './ThresholdsPage'
import { UsersPage } from './UsersPage'

const PAGES: Record<AdminTabKey, ComponentType> = {
  schools: SchoolsAdminPage,
  devices: DevicesAdminPage,
  users: UsersPage,
  regions: RegionsPage,
  providers: ProvidersPage,
  'connection-types': ConnectionTypesPage,
  thresholds: ThresholdsPage,
  schedules: SchedulesPage,
  'incident-rules': IncidentRulesPage,
  settings: SettingsPage,
  audit: AuditLogPage,
  events: EventLogPage,
}

/**
 * Section «Администрирование» (T-34): a tab per list at /admin/<tab>; /admin opens the first tab the role may.
 * A tab opened by URL without its permission shows «Нет доступа», as a section does (ТЗ п. 16).
 */
export function AdminSection() {
  const { data: permissions } = usePermissions<string[]>({})
  const [first] = allowedTabs(permissions)
  return (
    <Routes>
      <Route
        index
        element={
          first ? (
            <Navigate to={first.key} replace />
          ) : (
            <>
              <PageHeader title={SECTION_LABELS.admin} />
              <EmptyState
                icon={Construction}
                title="Для вашей роли вкладок пока нет"
                description="Настройки появятся вместе со следующими разделами администрирования."
              />
            </>
          )
        }
      />
      {ADMIN_TABS.map(({ key, permission }) => {
        const Page = PAGES[key]
        return (
          <Route
            key={key}
            path={key}
            element={
              permissions?.includes(permission) ? (
                <Page />
              ) : (
                <EmptyState icon={ShieldX} title="Нет доступа" description="Этот раздел недоступен для вашей роли." />
              )
            }
          />
        )
      })}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
