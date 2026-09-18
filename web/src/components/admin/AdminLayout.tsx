import { usePermissions } from '@refinedev/core'
import { Tabs } from 'antd'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router'

import { adminTabPath } from '../../app/sections'
import { ADMIN_TAB_LABELS, SECTION_LABELS, type AdminTabKey } from '../../lib/labels'
import { PageHeader } from '../ui/PageHeader'
import { allowedTabs } from './tabs'

interface AdminLayoutProps {
  tab: AdminTabKey
  /** The Action button of the tab, e.g. «Добавить школу». */
  action: ReactNode
  children: ReactNode
}

/** Frame of a tab of «Администрирование»: title with the action, tabs the role may open (DESIGN.md §3.8). */
export function AdminLayout({ tab, action, children }: AdminLayoutProps) {
  const { data: permissions } = usePermissions<string[]>({})
  const navigate = useNavigate()
  return (
    <>
      <PageHeader title={SECTION_LABELS.admin} actions={action} />
      <Tabs
        activeKey={tab}
        items={allowedTabs(permissions).map(({ key }) => ({ key, label: ADMIN_TAB_LABELS[key] }))}
        onChange={(key) => navigate(adminTabPath(key as AdminTabKey))}
      />
      {children}
    </>
  )
}
