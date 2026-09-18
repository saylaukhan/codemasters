import { useHref, useLinkClickHandler } from 'react-router'

import type { SchoolMapFeature } from '../../api/types'
import { schoolCardPath } from '../../app/sections'
import { NO_VALUE, formatDateTime, formatMs, formatSpeedPair } from '../../lib/format'
import { Button } from '../ui/Button'
import { ConnectionStatusBadge } from '../ui/StatusBadge'
import styles from './SchoolPopover.module.css'

type Metric = number | null | undefined

const below = (value: Metric, min: Metric): boolean => value != null && min != null && value < min
const above = (value: Metric, max: Metric): boolean => value != null && max != null && value > max
const text = (value: string | null | undefined): string => value?.trim() || NO_VALUE

interface Row {
  caption: string
  value: string
  /** Worse than the threshold of the snapshot of the last measurement: shown in red (DESIGN.md §3.14). */
  alert?: boolean
}

/**
 * Popover of a school on the map (ТЗ п. 13, DESIGN.md §3.14): name, School ID and status in the
 * header, the other fields of п. 13 in their order below; metrics of the main line.
 */
export function SchoolPopover({ school }: { school: SchoolMapFeature }) {
  const card = schoolCardPath(school.id)
  const href = useHref(card)
  const openCard = useLinkClickHandler<HTMLElement>(card)
  const p = school.properties
  const rows: Row[] = [
    { caption: 'Район/город', value: text(p.regionName) },
    { caption: 'Поставщик', value: text(p.providerName) },
    { caption: 'Тип подключения', value: text(p.connectionTypeName) },
    { caption: 'Договорная скорость', value: formatSpeedPair(p.contractDownMbps, p.contractUpMbps) },
    {
      caption: 'Download',
      value: formatSpeedPair(p.downloadMbps, p.contractDownMbps),
      alert: below(p.downloadMbps, p.downloadMinMbps),
    },
    {
      caption: 'Upload',
      value: formatSpeedPair(p.uploadMbps, p.contractUpMbps),
      alert: below(p.uploadMbps, p.uploadMinMbps),
    },
    { caption: 'Ping', value: formatMs(p.pingMs), alert: above(p.pingMs, p.pingMaxMs) },
    { caption: 'Последний замер', value: formatDateTime(p.lastMeasuredAt) },
  ]

  return (
    <section className={styles.popover} aria-label={text(p.fullName)}>
      <header className={styles.header}>
        <div className={styles.title}>
          <h3 className={styles.name}>{text(p.fullName)}</h3>
          <span className={styles.code}>{text(p.schoolCode)}</span>
        </div>
        <ConnectionStatusBadge status={p.status} />
      </header>
      <dl className={styles.table}>
        {rows.map((row) => (
          <div key={row.caption} className={styles.row}>
            <dt>{row.caption}</dt>
            <dd data-alert={row.alert || undefined}>{row.value}</dd>
          </div>
        ))}
      </dl>
      <Button block href={href} onClick={openCard}>
        Открыть карточку
      </Button>
    </section>
  )
}
