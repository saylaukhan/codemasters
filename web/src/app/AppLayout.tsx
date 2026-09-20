import { useGetIdentity } from '@refinedev/core'
import { Layout, Menu, type MenuProps } from 'antd'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { useState, type PropsWithChildren } from 'react'
import { Link, useLocation } from 'react-router'

import type { CurrentUser } from '../api/types'
import { Button } from '../components/ui/Button'
import { SECTION_LABELS } from '../lib/labels'
import { NARROW_SCREEN, SIZES } from '../styles/theme'
import { AppHeader } from './AppHeader'
import styles from './AppLayout.module.css'
import { SECTIONS, navigationSections, type Section } from './sections'
import { useMediaQuery } from './useMediaQuery'

const menuItem = ({ key, path, icon: Icon }: Section): NonNullable<MenuProps['items']>[number] => ({
  key,
  icon: <Icon size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} />,
  label: <Link to={path}>{SECTION_LABELS[key]}</Link>,
})

/** Shell of every signed-in page: header, side navigation, content (DESIGN.md §2.2). */
export function AppLayout({ children }: PropsWithChildren) {
  const narrow = useMediaQuery(NARROW_SCREEN)
  const [folded, setFolded] = useState(false)
  // At 1024px and narrower the navigation is always collapsed.
  const collapsed = narrow || folded
  const { pathname } = useLocation()
  // Role and permissions of one request: the navigation of a provider is his cabinet (T-44).
  const { data: user } = useGetIdentity<CurrentUser>()

  const visible = navigationSections(user)
  const main = visible.filter((section) => section.key !== 'admin').map(menuItem)
  // «Администрирование» is pinned to the bottom of the navigation (DESIGN.md §3.6).
  const bottom = visible.filter((section) => section.key === 'admin').map(menuItem)
  const selected = SECTIONS.filter((section) => pathname.startsWith(section.path)).map((section) => section.key)

  return (
    <Layout className={styles.shell}>
      <Layout.Header className={styles.header}>
        <AppHeader />
      </Layout.Header>
      <Layout>
        <Layout.Sider
          className={styles.sider}
          width={SIZES.siderWidth}
          collapsedWidth={SIZES.siderCollapsedWidth}
          collapsed={collapsed}
          trigger={null}
        >
          <Menu className={styles.menu} mode="inline" selectedKeys={selected} items={main} />
          <div className={styles.bottom}>
            {bottom.length > 0 && <Menu className={styles.menu} mode="inline" selectedKeys={selected} items={bottom} />}
            {!narrow && (
              <div className={styles.collapse}>
                <Button
                  kind="flat"
                  tooltip={collapsed ? 'Развернуть меню' : 'Свернуть меню'}
                  icon={
                    collapsed ? (
                      <PanelLeftOpen size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} />
                    ) : (
                      <PanelLeftClose size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} />
                    )
                  }
                  onClick={() => setFolded((value) => !value)}
                />
              </div>
            )}
          </div>
        </Layout.Sider>
        <Layout.Content className={styles.content}>
          <div className={styles.container}>{children}</div>
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
