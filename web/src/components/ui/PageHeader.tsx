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
}

export function PageHeader({ title, subtitle, breadcrumbs, actions }: PageHeaderProps) {
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
          <h1 className={styles.title}>{title}</h1>
          {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
        </div>
        {actions && <div className={styles.actions}>{actions}</div>}
      </div>
    </header>
  )
}
