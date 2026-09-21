import type { SchoolStatus } from '../../api/types'
import { formatNumber } from '../../lib/format'
import { FACT_BAR_LABELS } from '../../lib/labels'
import styles from './FactBar.module.css'
import { factBarGeometry } from './fact-bar'

export interface FactBarProps {
  /** The measured value; `null` draws an empty track. */
  value: number | null | undefined
  /** Right end of the track the value is read against. */
  scale: number
  /** Norm from the thresholds of the server (ADR-004); without it no norm tick is drawn. */
  threshold?: number | null
  /** Contract value (ТЗ п. 14); speeds get this tick, ping does not (DESIGN.md §3.27). */
  contract?: number | null
  /** Colour of the fill: the status the value was evaluated as (ADR-004). */
  status: SchoolStatus
  /** Unit of the value, from format.ts; read out with the value, not printed on the track. */
  unit: string
  /** Speeds are better when higher, ping and loss when lower — this picks the caption wording. */
  higherIsBetter: boolean
}

/**
 * Bar «fact against the threshold», DESIGN.md §3.10 (large tile of the cabinet) and §3.27: an 8px
 * track on `--bg-subtle`, the fill in the colour of the metric's status, a 2×14 tick for the norm
 * (muted) and one for the contract (primary), captions 12px below. The geometry lives in
 * `fact-bar.ts`; this file only paints it.
 */
export function FactBar({ value, scale, threshold, contract, status, unit, higherIsBetter }: FactBarProps) {
  const { fillPct, thresholdPct, contractPct } = factBarGeometry({ value, scale, threshold, contract })

  // «норма от 20» / «по договору 50» for a speed; «чем меньше, тем лучше» / «норма до 100» for ping.
  const normCaption =
    threshold == null
      ? null
      : `${higherIsBetter ? FACT_BAR_LABELS.normFrom : FACT_BAR_LABELS.normTo} ${formatNumber(threshold, 0)}`
  const start = higherIsBetter ? normCaption : FACT_BAR_LABELS.lowerIsBetter
  const end = higherIsBetter
    ? contract == null
      ? null
      : `${FACT_BAR_LABELS.contract} ${formatNumber(contract, 0)}`
    : normCaption

  return (
    <div className={styles.bar} data-status={status}>
      <div
        className={styles.track}
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={scale}
        aria-valuenow={value ?? undefined}
        aria-valuetext={`${formatNumber(value, 1)} ${unit}`}
      >
        <div className={styles.fill} style={{ width: `${fillPct}%` }} />
        {thresholdPct !== null && (
          <span className={styles.tick} data-kind="threshold" style={{ insetInlineStart: `${thresholdPct}%` }} />
        )}
        {contractPct !== null && (
          <span className={styles.tick} data-kind="contract" style={{ insetInlineStart: `${contractPct}%` }} />
        )}
      </div>
      {(start || end) && (
        <div className={styles.captions}>
          <span className={styles.caption}>{start}</span>
          <span className={styles.caption}>{end}</span>
        </div>
      )}
    </div>
  )
}
