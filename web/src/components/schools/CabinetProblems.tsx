import { ChevronRight } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { CABINET_APPEAL_STATUS_LABELS, CABINET_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import { IncidentStatusBadge } from '../ui/StatusBadge'
import type { CabinetProblem } from './cabinet'
import styles from './SchoolCabinet.module.css'

interface CabinetProblemsProps {
  problems: readonly CabinetProblem[]
  /** «Вся история»: the list of the letters to the provider (T-48). */
  historyHref: string
  /** SchoolPhone.html shortens the link to «Все» (DESIGN.md §9.3). */
  phone?: boolean
  placeholder?: ReactNode
}

/**
 * Card «Проблемы и обращения» (DESIGN.md §3.27): what broke and what came of the letter about it,
 * in the words of the cabinet — one line per incident of the school and per appeal it sent.
 */
export function CabinetProblems({ problems, historyHref, phone = false, placeholder }: CabinetProblemsProps) {
  return (
    <section className={`${styles.card} ${styles.flush}`} aria-label={CABINET_LABELS.problems}>
      <div className={styles.head}>
        <h2 className={styles.title}>{CABINET_LABELS.problems}</h2>
        <Link to={historyHref}>{phone ? CABINET_LABELS.all : CABINET_LABELS.history}</Link>
      </div>
      {placeholder ?? (
        <ul className={styles.list}>
          {problems.map((problem) => (
            <li key={problem.key}>
              <Link className={styles.row} to={problem.href}>
                <span className={styles.rowDot} data-status={problem.tone} aria-hidden />
                <span className={styles.rowText}>
                  <span className={styles.rowTitle}>{problem.title}</span>
                  <span className={styles.rowMeta}>{problem.meta}</span>
                </span>
                <IncidentStatusBadge status={problem.status} labels={CABINET_APPEAL_STATUS_LABELS} />
                <ChevronRight
                  className={styles.chevron}
                  size={SIZES.iconSm}
                  strokeWidth={SIZES.iconStroke}
                  aria-hidden
                />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
