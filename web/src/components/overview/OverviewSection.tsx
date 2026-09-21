import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { formatNumber } from '../../lib/format'
import styles from './OverviewSection.module.css'

interface OverviewSectionProps {
  title: string
  /** Counter pill next to the caption, DESIGN.md §3.11: «17» on `--bg-subtle`. */
  count?: number
  /** Link on the right of the caption: «Открыть карту», «Все инциденты». */
  link?: { to: string; label: string }
  /** Note on the right instead of a link: «к предыдущему периоду». */
  note?: string
  /** The block draws a card of its own; a strip that is already a card passes `false`. */
  card?: boolean
  className?: string
  children: ReactNode
}

/** Block of the main screen (DESIGN.md §3.28): caption 15/600, a link or a note on the right. */
export function OverviewSection({ title, count, link, note, card = true, className, children }: OverviewSectionProps) {
  const classes = [styles.section, card ? styles.card : '', className ?? ''].filter(Boolean).join(' ')
  return (
    <section className={classes} aria-label={title}>
      <div className={styles.head}>
        <h2 className={styles.title}>
          {title}
          {count !== undefined && <span className={styles.count}>{formatNumber(count, 0)}</span>}
        </h2>
        {link && (
          <Link className={styles.link} to={link.to}>
            {link.label}
          </Link>
        )}
        {note && <span className={styles.note}>{note}</span>}
      </div>
      {children}
    </section>
  )
}
