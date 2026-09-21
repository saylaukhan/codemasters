import { useGetIdentity } from '@refinedev/core'
import { Drawer, Layout, Menu, type MenuProps } from 'antd'
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react'
import { useState, type PropsWithChildren, type ReactNode } from 'react'
import { Link, useLocation } from 'react-router'

import type { CurrentUser } from '../api/types'
import { Button } from '../components/ui/Button'
import { NAVIGATION_LABELS, SECTION_LABELS } from '../lib/labels'
import { COMPACT_SCREEN, NARROW_SCREEN, PHONE_SCREEN, SIZES } from '../styles/theme'
import { AppHeader } from './AppHeader'
import styles from './AppLayout.module.css'
import { SECTIONS, navigationSections, type Section } from './sections'
import { useMediaQuery } from './useMediaQuery'

// `title` is what AntD shows as the tooltip of a collapsed item; the label itself stays a Link.
const menuItem = ({ key, path, icon: Icon }: Section): NonNullable<MenuProps['items']>[number] => ({
  key,
  icon: <Icon size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} />,
  label: <Link to={path}>{SECTION_LABELS[key]}</Link>,
  title: SECTION_LABELS[key],
})

/**
 * Shell of every signed-in page: header, side navigation, content (DESIGN.md §2.2, §9.3). The
 * navigation is 232px with labels from 1280px, 64px of icons with tooltips at 1025–1279 and, at
 * 1024px and narrower, not on the page at all — the menu button of the header opens the same
 * items in a drawer from the left, full width on a phone.
 */
export function AppLayout({ children }: PropsWithChildren) {
  const compact = useMediaQuery(COMPACT_SCREEN)
  const narrow = useMediaQuery(NARROW_SCREEN)
  const phone = useMediaQuery(PHONE_SCREEN)
  const [folded, setFolded] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  // Between 1025 and 1279 the rail is always icons; wider than that the fold button decides.
  const collapsed = compact || folded
  const { pathname } = useLocation()
  // Role and permissions of one request: the navigation of a provider is his cabinet (T-44).
  const { data: user } = useGetIdentity<CurrentUser>()

  const visible = navigationSections(user)
  const main = visible.filter((section) => section.key !== 'admin').map(menuItem)
  // «Администрирование» is pinned to the bottom of the navigation (DESIGN.md §3.6).
  const bottom = visible.filter((section) => section.key === 'admin').map(menuItem)
  const selected = SECTIONS.filter((section) => pathname.startsWith(section.path)).map((section) => section.key)

  // The same two menus serve the rail and the drawer: one interface on every width (§9.2). In the
  // drawer a tap navigates, so the same click closes it and it never covers the page it opened.
  const menus = (onClick?: MenuProps['onClick'], extra?: ReactNode) => (
    <>
      <Menu className={styles.menu} mode="inline" selectedKeys={selected} items={main} onClick={onClick} />
      <div className={styles.bottom}>
        {bottom.length > 0 && (
          <Menu className={styles.menu} mode="inline" selectedKeys={selected} items={bottom} onClick={onClick} />
        )}
        {extra}
      </div>
    </>
  )

  // The fold button belongs to the rail alone, and only where the rail can still be unfolded.
  const foldButton = !compact && (
    <div className={styles.collapse}>
      <Button
        kind="flat"
        tooltip={collapsed ? NAVIGATION_LABELS.expand : NAVIGATION_LABELS.fold}
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
  )

  return (
    <Layout className={styles.shell}>
      <Layout.Header className={styles.header}>
        <AppHeader onOpenNavigation={narrow ? () => setDrawerOpen(true) : undefined} />
      </Layout.Header>
      <Layout>
        {!narrow && (
          <Layout.Sider
            className={styles.sider}
            width={SIZES.siderWidth}
            collapsedWidth={SIZES.siderCollapsedWidth}
            collapsed={collapsed}
            trigger={null}
          >
            {menus(undefined, foldButton)}
          </Layout.Sider>
        )}
        {narrow && (
          <Drawer
            className={styles.drawer}
            title={NAVIGATION_LABELS.title}
            placement="left"
            width={phone ? '100%' : SIZES.drawerWidth}
            open={drawerOpen}
            onClose={() => setDrawerOpen(false)}
          >
            {menus(() => setDrawerOpen(false))}
          </Drawer>
        )}
        <Layout.Content className={styles.content}>
          <div className={styles.container}>{children}</div>
        </Layout.Content>
      </Layout>
    </Layout>
  )
}
