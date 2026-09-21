import type { UseQueryResult } from '@tanstack/react-query'
import { Link } from 'react-router'

import type { AttentionItem, AttentionPage, SchoolStatus } from '../../api/types'
import { appealCardPath, incidentCardPath, schoolCardPath } from '../../app/sections'
import { formatDate, formatDayMonth, formatNumber, formatTime, plural } from '../../lib/format'
import {
  ATTENTION_LABELS,
  ATTENTION_METRIC_LABELS,
  ATTENTION_REASON_LABELS,
  OVERVIEW_LABELS,
  SCHOOL_COUNT_FORMS,
} from '../../lib/labels'
import { ContentSkeleton } from '../ui/ContentSkeleton'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import styles from './AttentionCard.module.css'
import { OverviewSection } from './OverviewSection'

/** Colour of a row that is not about a school: the incident and the appeal borrow the status scale. */
const REASON_STATUS: Record<AttentionItem['reason'], SchoolStatus> = {
  offline: 'offline',
  critical: 'critical',
  incident_unassigned: 'critical',
  appeal_unanswered: 'unstable',
}

/** Where the row leads: the card of the incident, of the appeal, or of the school itself. */
function rowPath(item: AttentionItem): string {
  if (item.incidentId !== null) return incidentCardPath(item.incidentId)
  if (item.appealId !== null) return appealCardPath(item.appealId)
  return schoolCardPath(item.schoolId)
}

/** The reason in words: an incident says its first basis metric (docs/design/README.md §4.1). */
const reasonText = (item: AttentionItem): string =>
  item.reason === 'incident_unassigned' && item.metric
    ? ATTENTION_METRIC_LABELS[item.metric]
    : ATTENTION_REASON_LABELS[item.reason]

/** Since when: the time of the day it started, or «18.09» once it is older than that day. */
function sinceText(item: AttentionItem, now: Date): string {
  const since = new Date(item.since)
  const sameDay = formatDate(since) === formatDate(now)
  const moment = sameDay ? formatTime(since) : formatDayMonth(since)
  if (item.reason === 'incident_unassigned') return ATTENTION_LABELS.unassignedSince(moment)
  return ATTENTION_LABELS.since(moment)
}

/** One school can be in the list twice: as a school and as its incident (§4.1). */
const rowKey = (item: AttentionItem): string =>
  `${item.kind}-${item.incidentId ?? item.appealId ?? item.schoolId}`

export function AttentionRow({ item, now }: { item: AttentionItem; now: Date }) {
  const status = item.status ?? REASON_STATUS[item.reason]
  return (
    <Link className={styles.row} to={rowPath(item)} data-status={status}>
      <span className={styles.dot} aria-hidden />
      <span className={styles.what}>
        <span className={styles.school}>{item.schoolName}</span>
        <span className={styles.where}>
          {item.providerName ? `${item.regionName} · ${item.providerName}` : item.regionName}
        </span>
      </span>
      <span className={styles.why}>
        <span className={styles.reason}>{reasonText(item)}</span>
        <span className={styles.since}>{sinceText(item, now)}</span>
      </span>
    </Link>
  )
}

interface AttentionCardProps {
  attention: UseQueryResult<AttentionPage>
  className?: string
}

/**
 * «Требуют внимания» (DESIGN.md §3.28, docs/design/README.md §4.1): schools without a connection or
 * in a critical state, incidents nobody owns and appeals a provider never answered — worst first.
 */
export function AttentionCard({ attention, className }: AttentionCardProps) {
  const page = attention.data
  const rest = page ? page.total - page.items.length : 0

  function body() {
    if (attention.isError) return <ErrorState error={attention.error} onRetry={() => void attention.refetch()} />
    if (attention.isPending) return <ContentSkeleton rows={6} />
    const items = attention.data.items
    if (items.length === 0) {
      return <EmptyState title={ATTENTION_LABELS.empty} description={ATTENTION_LABELS.emptyHint} />
    }
    const now = new Date(attention.data.periodTo)
    return (
      <div className={styles.rows}>
        {items.map((item) => (
          <AttentionRow key={rowKey(item)} item={item} now={now} />
        ))}
      </div>
    )
  }

  return (
    <OverviewSection title={OVERVIEW_LABELS.attention} count={page?.total} className={className}>
      <div className={styles.body}>{body()}</div>
      {rest > 0 && (
        <p className={styles.more}>{ATTENTION_LABELS.more(formatNumber(rest, 0), plural(rest, SCHOOL_COUNT_FORMS))}</p>
      )}
    </OverviewSection>
  )
}
