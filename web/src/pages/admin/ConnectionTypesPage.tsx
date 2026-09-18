import type { TableColumnsType } from 'antd'
import { Plus } from 'lucide-react'

import type { ConnectionTypeDetail } from '../../api/types'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { ConnectionTypeDrawer } from '../../components/admin/ConnectionTypeDrawer'
import { useConnectionTypes } from '../../components/admin/queries'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { Button } from '../../components/ui/Button'
import { SearchInput } from '../../components/ui/SearchInput'
import { SIZES } from '../../styles/theme'

const COLUMNS: TableColumnsType<ConnectionTypeDetail> = [
  { key: 'code', title: 'Код', render: (_, type) => <span className={styles.code}>{type.code}</span> },
  { key: 'name', title: 'Название', render: (_, type) => type.name },
]

/** Connection types of the lines (оптоволокно, ADSL, спутник…): filters of the map, analytics and exports. */
export function ConnectionTypesPage() {
  const [view, setView] = useAdminListView()
  const connectionTypes = useConnectionTypes(view)
  const drawer = useDrawer<ConnectionTypeDetail>()

  return (
    <AdminLayout
      tab="connection-types"
      action={
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          Добавить тип
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
        query={connectionTypes}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{ title: 'Типов подключения пока нет', description: 'Добавьте тип кнопкой «Добавить тип».' }}
        onEdit={(type) => drawer.show(type)}
      />
      <ConnectionTypeDrawer key={drawer.key} open={drawer.open} connectionType={drawer.item} onClose={drawer.close} />
    </AdminLayout>
  )
}
