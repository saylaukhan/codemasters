import type { UseQueryResult } from '@tanstack/react-query'
import { MapPinOff } from 'lucide-react'

import type { RegionMapCollection, SchoolMapCollection } from '../../api/types'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import { Button } from '../ui/Button'
import { isFiltered, type MapFilters } from './filters'
import { SchoolMap } from './SchoolMap'
import styles from './SchoolMapView.module.css'

interface SchoolMapViewProps {
  schools: UseQueryResult<SchoolMapCollection>
  regions: RegionMapCollection | undefined
  filters: MapFilters
  onReset: () => void
  /** Height of the map on the page. */
  className: string
}

/** The map with its three states (DESIGN.md §2.7): skeleton, empty with a hint, error with a retry. */
export function SchoolMapView({ schools, regions, filters, onReset, className }: SchoolMapViewProps) {
  if (schools.isPending)
    return <div className={`${styles.skeleton} ${className}`} aria-busy aria-label="Загрузка карты" />
  if (schools.isError) return <ErrorState error={schools.error} onRetry={() => void schools.refetch()} />
  if (schools.data.features.length === 0) {
    return (
      <div className={styles.empty}>
        {isFiltered(filters) ? (
          <EmptyState
            icon={MapPinOff}
            title="По заданным фильтрам ничего не найдено"
            description="Измените фильтры или сбросьте их."
            action={<Button onClick={onReset}>Сбросить фильтры</Button>}
          />
        ) : (
          <EmptyState icon={MapPinOff} title="Школ пока нет" description="Школы появятся на карте после добавления." />
        )}
      </div>
    )
  }
  return <SchoolMap schools={schools.data} regions={regions} regionId={filters.regionId} className={className} />
}
