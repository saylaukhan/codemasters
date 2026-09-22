import { Drawer } from 'antd'
import { SlidersHorizontal } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { FILTER_SHEET_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import { Button } from '../ui/Button'
import styles from './FilterSheet.module.css'

/** Height of a bottom sheet, DESIGN.md §9.3: 90 % of the screen, the rest keeps the page visible. */
export const SHEET_HEIGHT = '90%'

interface FilterSheetProps {
  /** How many dimensions are set: «Фильтры · 2»; zero leaves the button without a count. */
  count: number
  /** Active values under the button, e.g. «Район: Усть-Каменогорск». */
  summary: readonly string[]
  /** The same controls the wide bar shows, unchanged (DESIGN.md §9.3). */
  children: ReactNode
}

/**
 * Filters of a phone, DESIGN.md §9.3 (row «Панель фильтров»): one button «Фильтры · N» with the
 * active values under it, opening the very same controls in a bottom sheet of 90 % height.
 */
export function FilterSheet({ count, summary, children }: FilterSheetProps) {
  const [open, setOpen] = useState(false)
  return (
    <div className={styles.sheet}>
      <Button
        kind="outlined"
        className={styles.open}
        icon={<SlidersHorizontal size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} aria-hidden />}
        onClick={() => setOpen(true)}
      >
        {count > 0 ? `${FILTER_SHEET_LABELS.open} · ${count}` : FILTER_SHEET_LABELS.open}
      </Button>
      {summary.length > 0 && <p className={styles.summary}>{summary.join(' · ')}</p>}
      <Drawer
        title={FILTER_SHEET_LABELS.title}
        placement="bottom"
        height={SHEET_HEIGHT}
        open={open}
        onClose={() => setOpen(false)}
      >
        <div className={styles.controls}>{children}</div>
      </Drawer>
    </div>
  )
}
