import { Fragment, type ReactNode } from 'react'
import { Link } from 'react-router'

import type { LatestMeasurement } from '../../api/types'
import { formatMs, formatNumber, formatPercent, NO_VALUE } from '../../lib/format'
import { CABINET_LABELS, CABINET_TERM_LABELS } from '../../lib/labels'
import { FactBar } from '../ui/FactBar'
import type { CabinetTile } from './cabinet'
import styles from './SchoolCabinet.module.css'

interface CabinetTilesProps {
  tiles: readonly CabinetTile[]
  latest: LatestMeasurement | null
  /** Availability of the last seven days (T-16, ADR-014); `undefined` while the analytics loads. */
  availabilityPct: number | null | undefined
  /** «Все замеры»: the history of the computer with the agent (T-26); without a computer — no link. */
  measurementsHref?: string
  /** SchoolPhone.html shortens the footer line and puts the availability first (DESIGN.md §9.3). */
  phone?: boolean
}

/**
 * Card «Текущие показатели» of the cabinet (DESIGN.md §3.27): three tiles — the fact, the bar
 * against the norm and the contract, the captions of the ticks — and a footer line with the rest of
 * the last measurement. At 768px and narrower the tiles stand one under another (§9.3).
 */
export function CabinetTiles({ tiles, latest, availabilityPct, measurementsHref, phone = false }: CabinetTilesProps) {
  const availability: ReactNode = (
    <>
      {phone ? CABINET_LABELS.availabilityCap : CABINET_LABELS.availability}{' '}
      <span className={styles.strong}>
        {availabilityPct === undefined ? NO_VALUE : formatPercent(availabilityPct)}
      </span>
    </>
  )
  const jitter = `${phone ? CABINET_LABELS.jitterLow : CABINET_LABELS.jitter} ${formatMs(latest?.jitterMs)}`
  const loss = `${phone ? CABINET_LABELS.packetLossShort : CABINET_LABELS.packetLoss} ${formatPercent(latest?.packetLossPct, 0)}`
  // The phone leads with the availability and drops the word «пакетов» (SchoolPhone.html).
  const facts: ReactNode[] = phone ? [availability, jitter, loss] : [jitter, loss, availability]

  return (
    <section className={`${styles.card} ${styles.flush}`} aria-label={CABINET_LABELS.tiles}>
      <div className={styles.tiles}>
        {tiles.map((tile) => (
          <div key={tile.key} className={styles.tile}>
            <span className={styles.tileCaption}>
              {CABINET_LABELS[tile.key]}
              <span className={styles.term}>· {CABINET_TERM_LABELS[tile.key]}</span>
            </span>
            <span className={styles.figure}>
              <span className={styles.value}>{formatNumber(tile.value, tile.key === 'ping' ? 0 : 1)}</span>
              <span className={styles.unit}>{tile.unit}</span>
            </span>
            <FactBar
              value={tile.value}
              scale={tile.scale}
              threshold={tile.threshold}
              contract={tile.contract}
              status={tile.status}
              unit={tile.unit}
              higherIsBetter={tile.higherIsBetter}
            />
          </div>
        ))}
      </div>
      <p className={styles.footer}>
        <span>
          {facts.map((fact, index) => (
            <Fragment key={index}>
              {index > 0 && ' · '}
              {fact}
            </Fragment>
          ))}
        </span>
        {measurementsHref && <Link to={measurementsHref}>{CABINET_LABELS.allMeasurements}</Link>}
      </p>
    </section>
  )
}
