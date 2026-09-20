import { Fragment, type ReactNode } from 'react'
import { Link } from 'react-router'

import type { AppealContext } from '../../api/types'
import { incidentCardPath, schoolCardPath } from '../../app/sections'
import { formatDuration, formatNumber, formatSpeed, NO_VALUE } from '../../lib/format'
import { INCIDENT_METRIC_LABELS } from '../../lib/labels'
import { formatMetricValue } from '../incidents/incidents'
import styles from './Appeal.module.css'
import { contractCaption, metricRows, periodCaption } from './appeals'

/**
 * Facts of the appeal the server collected (ТЗ п. 17, plan.md §8, DESIGN.md §3.19): School ID, school, provider,
 * contract, period, averages against the thresholds applied to them and the outages of the line. No personal
 * data: the contacts of the school are put into the letter after generation, not into this panel (ADR-011).
 */
export function AppealFacts({ context, recipientEmail }: { context: AppealContext; recipientEmail: string | null }) {
  const count = (value: number) => <span className={styles.number}>{formatNumber(value, 0)}</span>
  const pairs: [string, ReactNode][] = [
    ['School ID', <span className={styles.code}>{context.schoolCode}</span>],
    ['Школа', <Link to={schoolCardPath(context.schoolId)}>{context.schoolName}</Link>],
    ['Поставщик', context.providerName],
    [
      'Получатель',
      recipientEmail ?? <span className={styles.muted}>Адрес не задан, письмо не уйдёт</span>,
    ],
    ['Линия', context.lineIdentifier ? <span className={styles.code}>{context.lineIdentifier}</span> : NO_VALUE],
    ['Договор', contractCaption(context)],
    ['Договор Download', <span className={styles.number}>{formatSpeed(context.contractDownMbps)}</span>],
    ['Договор Upload', <span className={styles.number}>{formatSpeed(context.contractUpMbps)}</span>],
    ['Период', <span className={styles.number}>{periodCaption(context.periodFrom, context.periodTo)}</span>],
    ['Замеров', count(context.measurementsCount)],
    ['Проблемных замеров', count(context.problemCount)],
    ...metricRows(context).map(
      ({ metric, value, threshold }): [string, ReactNode] => [
        INCIDENT_METRIC_LABELS[metric],
        <span className={styles.number}>
          {formatMetricValue(metric, value)}
          <span className={styles.muted}> · порог {formatMetricValue(metric, threshold)}</span>
        </span>,
      ],
    ),
    ['Простоев', count(context.outagesCount)],
    ['Длительность простоев', <span className={styles.number}>{formatDuration(context.outagesDurationS)}</span>],
  ]
  if (context.incidentId !== null && context.incidentNumber !== null) {
    pairs.splice(3, 0, [
      'Инцидент',
      <Link className={styles.code} to={incidentCardPath(context.incidentId)}>
        {context.incidentNumber}
      </Link>,
    ])
  }

  return (
    <dl className={styles.pairs}>
      {pairs.map(([label, value]) => (
        <Fragment key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </Fragment>
      ))}
    </dl>
  )
}
