import { Tooltip } from 'antd'
import { ChevronDown, X } from 'lucide-react'
import type { ReactNode } from 'react'

import { FILTER_BAR_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import { Button } from './Button'
import styles from './FilterBar.module.css'

export interface FilterChipProps {
  /** Dimension of the filter: «Район», «Поставщик». */
  label: string
  /** Chosen value; without it the chip is inactive and shows a chevron. */
  value?: string
  /** Opens the menu of the filter; the chip itself holds no menu (DESIGN.md §3.9). */
  onClick?: () => void
  /** Clears this one dimension; the button appears only on an active chip. */
  onClear?: () => void
  /** `aria-label` of the clear button; the default comes from labels.ts. */
  clearLabel?: string
  disabled?: boolean
}

/**
 * Chip of the filter bar, DESIGN.md §3.9: 36px with radius 10. Inactive — `--bg-surface` with
 * `--border-strong` and a chevron; active — `--accent-soft` with `--accent-pressed` text,
 * «Подпись: значение» and a clear button.
 */
export function FilterChip({
  label,
  value,
  onClick,
  onClear,
  clearLabel = FILTER_BAR_LABELS.clear,
  disabled,
}: FilterChipProps) {
  const active = value !== undefined && value !== ''
  const clearable = active && onClear !== undefined
  const clearTitle = `${clearLabel}: ${label}`
  // One pill, two controls inside it: the chip opens the menu, the cross clears the dimension on
  // its own, so Tab reaches both (DESIGN.md §3.9 draws the pill, §9.4 asks for the keyboard).
  return (
    <span className={styles.group} data-active={active} data-clearable={clearable} data-disabled={disabled}>
      <button type="button" className={styles.chip} data-active={active} disabled={disabled} onClick={onClick}>
        <span className={styles.chipLabel}>{active ? `${label}:` : label}</span>
        {active && <span className={styles.chipValue}>{value}</span>}
        {!active && (
          <ChevronDown className={styles.chipIcon} size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />
        )}
      </button>
      {clearable && (
        <Tooltip title={clearTitle}>
          <button type="button" className={styles.clear} aria-label={clearTitle} disabled={disabled} onClick={onClear}>
            <X size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />
          </button>
        </Tooltip>
      )}
    </span>
  )
}

export interface FilterBarProps {
  /** Search field, always the first slot of the bar (DESIGN.md §3.9). */
  search?: ReactNode
  /** The chips themselves, usually `FilterChip` or an AntD control styled as one. */
  children?: ReactNode
  /** Clears every dimension at once; the link is shown only when something is set. */
  onReset?: () => void
  resetLabel?: string
  /** Read out by screen readers, e.g. «Фильтры школ»; the row is a `group`, not a landmark. */
  label?: string
}

/**
 * Filter bar, DESIGN.md §3.9: a flex row with the search first, the chips after it and the
 * «Сбросить» link on the right. The row wraps at 1024px and narrower (§9.3); the bottom sheet
 * of a phone is T-62, the bar only supplies the same chips to it.
 */
export function FilterBar({ search, children, onReset, resetLabel = FILTER_BAR_LABELS.reset, label }: FilterBarProps) {
  return (
    <div className={styles.bar} role="group" aria-label={label}>
      {search && <div className={styles.search}>{search}</div>}
      <div className={styles.chips}>{children}</div>
      {onReset && (
        <Button className={styles.reset} kind="link" onClick={onReset}>
          {resetLabel}
        </Button>
      )}
    </div>
  )
}
