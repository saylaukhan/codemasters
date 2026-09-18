import type { SchoolMapCollection, SchoolStatus } from '../../api/types'
import { formatNumber } from '../../lib/format'
import { SCHOOL_STATUS_LABELS } from '../../lib/labels'
import styles from './MapLegend.module.css'

// Worst first: what needs attention is read first.
const ORDER: readonly SchoolStatus[] = ['critical', 'offline', 'unstable', 'normal', 'no_data']

interface MapLegendProps {
  schools: SchoolMapCollection
  hidden: readonly SchoolStatus[]
  onToggle: (status: SchoolStatus) => void
}

/** Legend of the map (DESIGN.md §3.13): dot, caption, number of schools; a click hides the status. */
export function MapLegend({ schools, hidden, onToggle }: MapLegendProps) {
  const counts = new Map<SchoolStatus, number>()
  for (const school of schools.features) {
    counts.set(school.properties.status, (counts.get(school.properties.status) ?? 0) + 1)
  }
  return (
    <ul className={styles.legend} aria-label="Легенда">
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
  )
}
