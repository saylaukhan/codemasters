import type { TableColumnsType } from 'antd'
import { Plus } from 'lucide-react'

import type { ProviderDetail } from '../../api/types'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { ProviderDrawer } from '../../components/admin/ProviderDrawer'
import { useProviders } from '../../components/admin/queries'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { Button } from '../../components/ui/Button'
import { SearchInput } from '../../components/ui/SearchInput'
import { NO_VALUE } from '../../lib/format'
import { SIZES } from '../../styles/theme'

const COLUMNS: TableColumnsType<ProviderDetail> = [
  { key: 'name', title: 'Название', render: (_, provider) => provider.name },
  {
    key: 'email',
    title: 'E-mail для обращений',
    render: (_, provider) => provider.appealsEmail ?? <span className={styles.muted}>{NO_VALUE}</span>,
  },
]

/** Internet providers of the schools: the lines refer to them, appeals go to their service address. */
export function ProvidersPage() {
  const [view, setView] = useAdminListView()
  const providers = useProviders(view)
  const drawer = useDrawer<ProviderDetail>()

  return (
    <AdminLayout
      tab="providers"
      action={
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          Добавить поставщика
        </Button>
      }
    >
      <div className={styles.toolbar}>
        <SearchInput
          className={styles.search}
          value={view.q}
          placeholder="Поиск по названию"
          onSearch={(q) => setView({ ...view, q, page: 1 })}
        />
      </div>
      <AdminTable
        query={providers}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{ title: 'Поставщиков пока нет', description: 'Добавьте поставщика кнопкой «Добавить поставщика».' }}
        onEdit={(provider) => drawer.show(provider)}
      />
      <ProviderDrawer key={drawer.key} open={drawer.open} provider={drawer.item} onClose={drawer.close} />
    </AdminLayout>
  )
}
