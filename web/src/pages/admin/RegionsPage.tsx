import type { TableColumnsType } from 'antd'
import { Plus } from 'lucide-react'

import type { RegionListItem } from '../../api/types'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { useRegions } from '../../components/admin/queries'
import { RegionDrawer } from '../../components/admin/RegionDrawer'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { Button } from '../../components/ui/Button'
import { SearchInput } from '../../components/ui/SearchInput'
import { REGION_BOUNDARY_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

const COLUMNS: TableColumnsType<RegionListItem> = [
  { key: 'code', title: 'Код', render: (_, region) => <span className={styles.code}>{region.code}</span> },
  { key: 'name', title: 'Название', render: (_, region) => region.name },
  {
    key: 'boundary',
    title: 'Граница',
    render: (_, region) =>
      region.hasBoundary ? (
        REGION_BOUNDARY_LABELS.loaded
      ) : (
        <span className={styles.muted}>{REGION_BOUNDARY_LABELS.missing}</span>
      ),
  },
]

/** Districts and cities of VKO: the code is part of School ID VKO-<код>-<номер>; boundaries come from GeoJSON. */
export function RegionsPage() {
  const [view, setView] = useAdminListView()
  const regions = useRegions(view)
  const drawer = useDrawer<RegionListItem>()

  return (
    <AdminLayout
      tab="regions"
      action={
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          Добавить район
        </Button>
      }
    >
      <div className={styles.toolbar}>
        <SearchInput
          className={styles.search}
          value={view.q}
          placeholder="Поиск по названию или коду"
          onSearch={(q) => setView({ ...view, q, page: 1 })}
        />
      </div>
      <AdminTable
        query={regions}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{ title: 'Районов пока нет', description: 'Добавьте район или город кнопкой «Добавить район».' }}
        onEdit={(region) => drawer.show(region)}
      />
      <RegionDrawer key={drawer.key} open={drawer.open} region={drawer.item} onClose={drawer.close} />
    </AdminLayout>
  )
}
