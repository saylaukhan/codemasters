import styles from './KpiStrip.module.css'

/** How a delta reads: better, worse or not worth colouring (DESIGN.md §3.10). */
export type KpiDeltaTone = 'good' | 'bad' | 'neutral'

export interface KpiStripItem {
  key: string
  /** Russian caption of the metric, from labels.ts (ADR-013). */
  label: string
  /** Already formatted by lib/format.ts: the strip never formats a number itself. */
  value: string
  /** «Мбит/с», «мс»; printed next to the number in 12px muted. */
  unit?: string
  /** A note instead of or next to the delta: «из 366 в реестре», «95,7 %», «4 слота в день». */
  hint?: string
  /** «▲ 1,8 за неделю» with its tone; the text comes ready from the caller. */
  delta?: { text: string; tone: KpiDeltaTone }
  /** Sparkline points, DESIGN.md §3.10. Kept in the contract for T-60; not drawn yet. */
  series?: readonly number[]
  /** The value is worse than its threshold: printed in `status.critical.text` (DESIGN.md §3.12). */
  alert?: boolean
}

export interface KpiStripProps {
  items: readonly KpiStripItem[]
  /** Read out by screen readers, e.g. «Показатели за 7 дней»; the caption itself is drawn by the card. */
  label?: string
}

/**
 * Strip of indicators, DESIGN.md §3.10: ONE bordered card whose cells are split by hairlines,
 * 4 in a row, 2 at 1024px and narrower, 1 on a phone with the number to the right of the caption
 * (§9.3). Replaces a row of `KpiCard` boxes; the card around it belongs to the page.
 */
export function KpiStrip({ items, label }: KpiStripProps) {
  return (
    <div className={styles.strip} role="group" aria-label={label}>
      {items.map((item) => (
        <div key={item.key} className={styles.cell}>
          <span className={styles.label}>{item.label}</span>
          <span className={styles.figure}>
            <span className={item.alert ? `${styles.value} ${styles.alert}` : styles.value}>{item.value}</span>
            {item.unit && <span className={styles.unit}>{item.unit}</span>}
          </span>
          {item.hint && <span className={styles.hint}>{item.hint}</span>}
          {item.delta && (
            <span className={styles.delta} data-tone={item.delta.tone}>
              {item.delta.text}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
