import { useGetIdentity, useLogout } from '@refinedev/core'
import { Dropdown, type MenuProps } from 'antd'
import { LogOut, Moon, Sun, Wifi } from 'lucide-react'

import type { CurrentUser } from '../api/types'
import { Button } from '../components/ui/Button'
import { APP_NAME } from '../lib/app-info'
import { ROLE_LABELS } from '../lib/labels'
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

/** Header, DESIGN.md §3.5: product name on the left; theme switch and profile menu on the right. */
export function AppHeader() {
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
        <Wifi size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} aria-hidden />
        {APP_NAME}
      </div>
      <div className={styles.tools}>
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
