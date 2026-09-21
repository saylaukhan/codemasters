import { Breadcrumb } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { useMediaQuery } from '../../app/useMediaQuery'
import { PHONE_SCREEN } from '../../styles/theme'
import styles from './PageHeader.module.css'

export interface Crumb {
  title: string
  path?: string
}

interface PageHeaderProps {
  /**
   * Usually the name of the screen. The verdict of the school cabinet carries a status dot inside
   * the heading (DESIGN.md §3.27), so a node is allowed here as well as a string.
   */
  title: ReactNode
  /** For example «Обновлено 2 мин назад» from format.ts. */
  subtitle?: ReactNode
  breadcrumbs?: Crumb[]
  /** Page actions, right-aligned; at most one Action button on the screen. */
  actions?: ReactNode
  /**
   * The single Action of the screen. At 768px and narrower it leaves the header for a bar pinned to
   * the bottom of the window, full width on `--bg-surface` (DESIGN.md §9.3); wider it stands right of
   * `actions`. The bar carries `data-sticky-action`, and the shell reserves its height so the last
   * block of the page is not covered by it.
   */
  stickyAction?: ReactNode
  /** The title is an identifier, e.g. «INC-2026-000123»: JetBrains Mono (DESIGN.md §5). */
  mono?: boolean
}

export function PageHeader({ title, subtitle, breadcrumbs, actions, stickyAction, mono = false }: PageHeaderProps) {
  const phone = useMediaQuery(PHONE_SCREEN)
  const inHeader = phone ? undefined : stickyAction

  return (
    <header className={styles.header}>
      {breadcrumbs && breadcrumbs.length > 0 && (
        <Breadcrumb
          className={styles.breadcrumbs}
          items={breadcrumbs.map((crumb) => ({
            title: crumb.path ? <Link to={crumb.path}>{crumb.title}</Link> : crumb.title,
          }))}
        />
      )}
      <div className={styles.row}>
        <div>
          <h1 className={mono ? `${styles.title} ${styles.mono}` : styles.title}>{title}</h1>
          {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
        </div>
        {(actions || inHeader) && (
          <div className={styles.actions}>
            {actions}
            {inHeader}
          </div>
        )}
      </div>
      {phone && stickyAction && (
        <div className={styles.sticky} data-sticky-action>
          {stickyAction}
        </div>
      )}
    </header>
  )
}
