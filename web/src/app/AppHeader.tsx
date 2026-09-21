import { useGetIdentity, useLogout } from '@refinedev/core'
import { Dropdown, type MenuProps } from 'antd'
import { Activity, LogOut, Menu as MenuIcon, Moon, Sun } from 'lucide-react'

import type { CurrentUser } from '../api/types'
import { NotificationBell } from '../components/notifications/NotificationBell'
import { Button } from '../components/ui/Button'
import { APP_NAME } from '../lib/app-info'
import { NAVIGATION_LABELS, ROLE_LABELS } from '../lib/labels'
import { SIZES } from '../styles/theme'
import styles from './AppLayout.module.css'
import { useThemeMode } from './themeMode'

const initials = (name: string): string =>
  name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')

// Every role has its own bell (backend/app/auth/permissions.py); a role without it never sees one.
const NOTIFICATIONS_PERMISSION = 'notifications:read'

interface AppHeaderProps {
  /** Opens the navigation drawer; given only at 1024px and narrower, where the rail is gone. */
  onOpenNavigation?: () => void
}

/**
 * Header, DESIGN.md §3.5: 64px on `--bg-page` without a line under it. On the left the 28px mark
 * and «Jyldam» 16/600, preceded by the menu button once the side navigation has moved into a
 * drawer; on the right the bell with its counter, the theme switch and the 40px profile chip,
 * which is the avatar alone at 1024px and narrower (§9.3). The panel has no header search —
 * search belongs to each screen through `components/ui/SearchInput`; the language switch is T-66.
 */
export function AppHeader({ onOpenNavigation }: AppHeaderProps) {
  const { mode, toggle } = useThemeMode()
  const { data: user } = useGetIdentity<CurrentUser>()
  const { mutate: logout } = useLogout()

  const profileItems: MenuProps['items'] = user
    ? [
        { key: 'email', label: user.email, disabled: true },
        { key: 'role', label: ROLE_LABELS[user.role], disabled: true },
        ...(user.scope.regionName ? [{ key: 'region', label: user.scope.regionName, disabled: true }] : []),
        { type: 'divider' },
        {
          key: 'logout',
          label: 'Выйти',
          icon: <LogOut size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} />,
          onClick: () => logout(),
        },
      ]
    : []

  return (
    <>
      <div className={styles.brand}>
        {onOpenNavigation && (
          <Button
            kind="flat"
            tooltip={NAVIGATION_LABELS.open}
            icon={<MenuIcon size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} />}
            onClick={onOpenNavigation}
          />
        )}
        <span className={styles.mark} aria-hidden>
          <Activity size={SIZES.iconNav} strokeWidth={SIZES.iconStroke} />
        </span>
        {APP_NAME}
      </div>
      <div className={styles.tools}>
        {user?.permissions.includes(NOTIFICATIONS_PERMISSION) && <NotificationBell />}
        <Button
          kind="flat"
          tooltip={mode === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
          icon={
            mode === 'dark' ? (
              <Sun size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} />
            ) : (
              <Moon size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} />
            )
          }
          onClick={toggle}
        />
        {user && (
          <Dropdown menu={{ items: profileItems }} trigger={['click']} placement="bottomRight">
            <button type="button" className={styles.profile} aria-label="Меню профиля">
              <span className={styles.avatar}>{initials(user.fullName)}</span>
              <span className={styles.profileMeta}>
                <strong>{user.fullName}</strong>
                {ROLE_LABELS[user.role]}
              </span>
            </button>
          </Dropdown>
        )}
      </div>
    </>
  )
}
