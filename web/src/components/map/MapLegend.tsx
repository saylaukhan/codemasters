import { useState } from 'react'

import type { SchoolMapCollection, SchoolStatus } from '../../api/types'
import { useMediaQuery } from '../../app/useMediaQuery'
import { formatNumber } from '../../lib/format'
import { MAP_LEGEND_LABELS, SCHOOL_STATUS_LABELS } from '../../lib/labels'
import { NARROW_SCREEN } from '../../styles/theme'
import styles from './MapLegend.module.css'

// Worst first: what needs attention is read first.
const ORDER: readonly SchoolStatus[] = ['critical', 'offline', 'unstable', 'normal', 'no_data']

interface MapLegendProps {
  schools: SchoolMapCollection
  hidden: readonly SchoolStatus[]
  onToggle: (status: SchoolStatus) => void
}

/**
 * Legend of the map (DESIGN.md §3.13): dot, caption, number of schools; a click hides the status.
 * At 1024px and narrower it folds into one button with the total (§9.3), so it stops covering the
 * map, and expands into the very same list.
 */
export function MapLegend({ schools, hidden, onToggle }: MapLegendProps) {
  const narrow = useMediaQuery(NARROW_SCREEN)
  const [open, setOpen] = useState(false)
  const counts = new Map<SchoolStatus, number>()
  for (const school of schools.features) {
    counts.set(school.properties.status, (counts.get(school.properties.status) ?? 0) + 1)
  }
  const total = schools.features.length
  return (
    <div className={styles.legend}>
      {narrow && (
        <button
          type="button"
          className={styles.toggle}
          aria-expanded={open}
          aria-label={open ? MAP_LEGEND_LABELS.hide : MAP_LEGEND_LABELS.show}
          onClick={() => setOpen((shown) => !shown)}
        >
          {MAP_LEGEND_LABELS.title} · {formatNumber(total, 0)}
        </button>
      )}
      {(!narrow || open) && (
        <ul className={styles.items} aria-label={MAP_LEGEND_LABELS.title}>
          {ORDER.map((status) => (
            <li key={status}>
              <button
                type="button"
                className={styles.item}
                data-status={status}
                aria-pressed={!hidden.includes(status)}
                onClick={() => onToggle(status)}
              >
                <span className={styles.dot} aria-hidden />
                {SCHOOL_STATUS_LABELS[status]} · {formatNumber(counts.get(status) ?? 0, 0)}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
