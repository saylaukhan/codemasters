import type { AnalyticsRow, LineDetail } from '../../api/types'
import { formatPercent, formatSpeedPair } from '../../lib/format'
import styles from './SchoolCard.module.css'

interface Metric {
  name: string
  fact: number | null | undefined
  contract: number | null | undefined
}

/** Fact against the contract as a horizontal bar: the fill is the average, the tick is the contract. */
function ContractBar({ name, fact, contract }: Metric) {
  const below = fact != null && contract != null && fact < contract
  const scale = Math.max(fact ?? 0, contract ?? 0) || 1
  const share = (value: number | null | undefined) => `${((value ?? 0) / scale) * 100}%`
  return (
    <div className={styles.bar}>
      <div className={styles.barCaption}>
        <span>{name}</span>
        <span className={below ? `${styles.number} ${styles.below}` : styles.number}>
          {formatSpeedPair(fact, contract)}
        </span>
      </div>
      <div className={styles.track} aria-hidden>
        <div className={below ? `${styles.fill} ${styles.fillBelow}` : styles.fill} style={{ width: share(fact) }} />
        {contract != null && <div className={styles.contractTick} style={{ left: share(contract) }} />}
      </div>
    </div>
  )
}

interface ContractFactProps {
  /** Main line of the school: the contract values live there (ТЗ п. 14). */
  line: LineDetail | undefined
  /** The school row of `GET /api/analytics` for the period: average speeds and share below contract. */
  row: AnalyticsRow | undefined
  /** «7 дней», «Сегодня». */
  periodLabel: string
}

/** Contract and fact of the main line (ТЗ п. 11, п. 14; DESIGN.md §3.15). */
export function ContractFact({ line, row, periodLabel }: ContractFactProps) {
  const metrics: Metric[] = [
    { name: 'Download', fact: row?.downloadMbps?.avg, contract: line?.contractDownMbps },
    { name: 'Upload', fact: row?.uploadMbps?.avg, contract: line?.contractUpMbps },
  ].filter((metric) => metric.contract != null)

  let content
  if (!line) {
    content = <p className={styles.muted}>Основной линии нет — сравнивать не с чем.</p>
  } else if (metrics.length === 0) {
    content = <p className={styles.muted}>Договорная скорость основной линии не указана. Её заводят в админке.</p>
  } else {
    const below = row?.belowContractPct
    content = (
      <>
        {metrics.map((metric) => (
          <ContractBar key={metric.name} {...metric} />
        ))}
        {below != null ? (
          <p className={styles.share}>
            <span className={below > 0 ? `${styles.shareValue} ${styles.below}` : styles.shareValue}>
              {formatPercent(below, 0)}
            </span>{' '}
            замеров ниже договора за {periodLabel.toLowerCase()}
          </p>
        ) : (
          <p className={styles.muted}>Замеров за {periodLabel.toLowerCase()} нет.</p>
        )}
        <p className={styles.muted}>Средняя скорость основной линии за период против договорной; метка — договор.</p>
      </>
    )
  }

  return (
    <section className={styles.panel} aria-label="Договор и факт">
      <h2 className={styles.panelTitle}>Договор и факт</h2>
      {content}
    </section>
  )
}
