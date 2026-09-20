import { Fragment, type ReactNode } from 'react'
import { Link } from 'react-router'

import type { AppealContext } from '../../api/types'
import { incidentCardPath, schoolCardPath } from '../../app/sections'
import { formatDuration, formatNumber, formatSpeed, NO_VALUE } from '../../lib/format'
import { APPEAL_FIELD_LABELS, APPEAL_NO_RECIPIENT_HINT, INCIDENT_METRIC_LABELS } from '../../lib/labels'
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
    [APPEAL_FIELD_LABELS.schoolCode, <span className={styles.code}>{context.schoolCode}</span>],
    [APPEAL_FIELD_LABELS.school, <Link to={schoolCardPath(context.schoolId)}>{context.schoolName}</Link>],
    [APPEAL_FIELD_LABELS.provider, context.providerName],
    [
      APPEAL_FIELD_LABELS.recipient,
      recipientEmail ?? <span className={styles.muted}>{APPEAL_NO_RECIPIENT_HINT}</span>,
    ],
    [
      APPEAL_FIELD_LABELS.line,
      context.lineIdentifier ? <span className={styles.code}>{context.lineIdentifier}</span> : NO_VALUE,
    ],
    [APPEAL_FIELD_LABELS.contract, contractCaption(context)],
    [APPEAL_FIELD_LABELS.contractDown, <span className={styles.number}>{formatSpeed(context.contractDownMbps)}</span>],
    [APPEAL_FIELD_LABELS.contractUp, <span className={styles.number}>{formatSpeed(context.contractUpMbps)}</span>],
    [
      APPEAL_FIELD_LABELS.period,
      <span className={styles.number}>{periodCaption(context.periodFrom, context.periodTo)}</span>,
    ],
    [APPEAL_FIELD_LABELS.measurements, count(context.measurementsCount)],
    [APPEAL_FIELD_LABELS.problems, count(context.problemCount)],
    ...metricRows(context).map(
      ({ metric, value, threshold }): [string, ReactNode] => [
        INCIDENT_METRIC_LABELS[metric],
        <span className={styles.number}>
          {formatMetricValue(metric, value)}
          <span className={styles.muted}>
            {' '}
            · {APPEAL_FIELD_LABELS.threshold} {formatMetricValue(metric, threshold)}
          </span>
        </span>,
      ],
    ),
    [APPEAL_FIELD_LABELS.outages, count(context.outagesCount)],
    [
      APPEAL_FIELD_LABELS.outagesDuration,
      <span className={styles.number}>{formatDuration(context.outagesDurationS)}</span>,
    ],
  ]
  if (context.incidentId !== null && context.incidentNumber !== null) {
    pairs.splice(3, 0, [
      APPEAL_FIELD_LABELS.incident,
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
