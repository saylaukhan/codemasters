import { PageHeader } from '../../components/ui/PageHeader'
import { MapFilterBar } from '../../components/map/MapFilterBar'
import { NO_FILTERS } from '../../components/map/filters'
import { useMapFilterOptions, useRegionBoundaries, useSchoolMap } from '../../components/map/queries'
import { SchoolMapView } from '../../components/map/SchoolMapView'
import { useMapFilters } from '../../components/map/useMapFilters'
import { SECTION_LABELS } from '../../lib/labels'
import styles from './MapPage.module.css'

/** Interactive map of VKO (ТЗ п. 13): every school in the scope, coloured by its status. */
export function MapPage() {
  const [filters, setFilters] = useMapFilters()
  const schools = useSchoolMap(filters)
  const regions = useRegionBoundaries()
  const options = useMapFilterOptions()

  return (
    <>
      <PageHeader title={SECTION_LABELS.map} />
      <MapFilterBar filters={filters} options={options.data} onChange={setFilters} />
      <SchoolMapView
        schools={schools}
        regions={regions.data}
        filters={filters}
        onReset={() => setFilters(NO_FILTERS)}
        className={styles.map}
      />
    </>
  )
}
