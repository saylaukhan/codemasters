import { Inbox, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { SIZES } from '../../styles/theme'
import styles from './EmptyState.module.css'

interface EmptyStateProps {
  title: string
  description?: string
  icon?: LucideIcon
  /** Optional action, e.g. «Сбросить фильтры». */
  action?: ReactNode
}

export function EmptyState({ title, description, icon: Icon = Inbox, action }: EmptyStateProps) {
  return (
    <div className={styles.empty}>
      <Icon className={styles.icon} size={SIZES.iconEmpty} strokeWidth={SIZES.iconStroke} aria-hidden />
      <h2 className={styles.title}>{title}</h2>
      {description && <p className={styles.description}>{description}</p>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  )
}
