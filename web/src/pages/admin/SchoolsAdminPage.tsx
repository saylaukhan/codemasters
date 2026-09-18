import { Segmented, type TableColumnsType } from 'antd'
import { Plus } from 'lucide-react'
import { Link } from 'react-router'

import type { SchoolListItem } from '../../api/types'
import { schoolCardPath } from '../../app/sections'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { useAdminSchools } from '../../components/admin/queries'
import { SchoolDrawer } from '../../components/admin/SchoolDrawer'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { Button } from '../../components/ui/Button'
import { SearchInput } from '../../components/ui/SearchInput'
import { SchoolActivityBadge } from '../../components/ui/StatusBadge'
import { SCHOOL_ACTIVITY_FILTER_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

type ActivityFilter = keyof typeof SCHOOL_ACTIVITY_FILTER_LABELS

const IS_ACTIVE: Record<ActivityFilter, boolean | undefined> = { all: undefined, active: true, disabled: false }

const ACTIVITY_OPTIONS = (Object.keys(SCHOOL_ACTIVITY_FILTER_LABELS) as ActivityFilter[]).map((value) => ({
  value,
  label: SCHOOL_ACTIVITY_FILTER_LABELS[value],
}))

const filterOf = (isActive: boolean | undefined): ActivityFilter =>
  isActive === undefined ? 'all' : isActive ? 'active' : 'disabled'

const COLUMNS: TableColumnsType<SchoolListItem> = [
  {
    key: 'code',
    title: 'School ID',
    render: (_, school) => <span className={styles.code}>{school.schoolCode}</span>,
  },
  {
    key: 'name',
    title: 'Название',
    render: (_, school) => (
      <Link className={styles.name} to={schoolCardPath(school.id)} title={school.fullName}>
        {school.fullName}
      </Link>
    ),
  },
  { key: 'region', title: 'Район', render: (_, school) => school.regionName },
  { key: 'activity', title: 'Состояние', render: (_, school) => <SchoolActivityBadge active={school.isActive} /> },
]

/** Schools of the oblast (ТЗ п. 20): add, change, deactivate; disabled ones keep their history. */
export function SchoolsAdminPage() {
  const [view, setView] = useAdminListView()
  const schools = useAdminSchools(view)
  const drawer = useDrawer<SchoolListItem>()

  return (
    <AdminLayout
      tab="schools"
      action={
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          Добавить школу
        </Button>
      }
    >
      <div className={styles.toolbar}>
        <SearchInput
          className={styles.search}
          value={view.q}
          placeholder="Поиск по School ID или названию"
          onSearch={(q) => setView({ ...view, q, page: 1 })}
        />
        <Segmented<ActivityFilter>
          aria-label="Состояние школы"
          value={filterOf(view.isActive)}
          options={ACTIVITY_OPTIONS}
          onChange={(filter) => setView({ ...view, isActive: IS_ACTIVE[filter], page: 1 })}
        />
      </div>
      <AdminTable
        query={schools}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{ title: 'Школ пока нет', description: 'Добавьте первую школу кнопкой «Добавить школу».' }}
        onEdit={(school) => drawer.show(school)}
      />
      <SchoolDrawer key={drawer.key} open={drawer.open} schoolId={drawer.item?.id} onClose={drawer.close} />
    </AdminLayout>
  )
}
