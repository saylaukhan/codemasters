import { Breadcrumb } from 'antd'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import styles from './PageHeader.module.css'

export interface Crumb {
  title: string
  path?: string
}

interface PageHeaderProps {
  title: string
  /** For example «Обновлено 2 мин назад» from format.ts. */
  subtitle?: ReactNode
  breadcrumbs?: Crumb[]
  /** Page actions, right-aligned; at most one Action button on the screen. */
  actions?: ReactNode
  /** The title is an identifier, e.g. «INC-2026-000123»: JetBrains Mono (DESIGN.md §5). */
  mono?: boolean
}

export function PageHeader({ title, subtitle, breadcrumbs, actions, mono = false }: PageHeaderProps) {
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
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
    </header>
  )
}
