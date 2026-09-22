import type { TableColumnsType } from 'antd'
import { Plus } from 'lucide-react'

import type { AppealTemplateDetail } from '../../api/types'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { AppealTemplateDrawer } from '../../components/admin/AppealTemplateDrawer'
import { useAppealTemplates } from '../../components/admin/queries'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { Button } from '../../components/ui/Button'
import { SearchInput } from '../../components/ui/SearchInput'
import { formatDateTime, NO_VALUE } from '../../lib/format'
import { APPEAL_KIND_LABELS, CONFIG_ACTIVITY_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

const COLUMNS: TableColumnsType<AppealTemplateDetail> = [
  {
    key: 'name',
    title: 'Название',
    render: (_, template) => <span className={styles.name}>{template.name}</span>,
  },
  { key: 'kind', title: 'Вид письма', render: (_, template) => APPEAL_KIND_LABELS[template.kind] },
  {
    key: 'subject',
    title: 'Тема',
    render: (_, template) => (
      <span className={`${styles.name} ${styles.code}`} title={template.subject}>
        {template.subject}
      </span>
    ),
  },
  {
    key: 'default',
    title: 'По умолчанию',
    render: (_, template) => (template.isDefault ? 'Да' : <span className={styles.muted}>{NO_VALUE}</span>),
  },
  {
    key: 'updated',
    title: 'Изменён',
    render: (_, template) => <span className={styles.number}>{formatDateTime(template.updatedAt)}</span>,
  },
  {
    key: 'active',
    title: 'Состояние',
    render: (_, template) =>
      template.isActive ? (
        CONFIG_ACTIVITY_LABELS.active
      ) : (
        <span className={styles.muted}>{CONFIG_ACTIVITY_LABELS.disabled}</span>
      ),
  },
]

/**
 * Templates of the letters to providers (ТЗ п. 17, п. 20; ADR-011): the appeal and the claim the model writes by;
 * the default one is taken without a choice, the others are offered in the editor of a draft (T-60).
 */
export function AppealTemplatesPage() {
  const [view, setView] = useAdminListView()
  const templates = useAppealTemplates(view)
  const drawer = useDrawer<AppealTemplateDetail>()

  return (
    <AdminLayout
      tab="appeal-templates"
      action={
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          Добавить шаблон
        </Button>
      }
    >
      <p className={styles.lead}>
        Письмо поставщику пишется по шаблону: сервер заполняет подстановки фактами обращения — School ID, договор,
        период, показатели против порогов и договора, — а модель излагает его деловым текстом. ФИО и телефоны в
        шаблон и в модель не попадают: подпись добавляется после. Шаблон по умолчанию берётся без выбора, остальные
        предлагаются в редакторе черновика.
      </p>
      <div className={styles.toolbar}>
        <SearchInput
          className={styles.search}
          value={view.q}
          placeholder="Поиск по названию шаблона"
          onSearch={(q) => setView({ ...view, q, page: 1 })}
        />
      </div>
      <AdminTable
        query={templates}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{ title: 'Шаблонов пока нет', description: 'Шаблоны по умолчанию создаются при установке системы.' }}
        onEdit={(template) => drawer.show(template)}
      />
      <AppealTemplateDrawer key={drawer.key} open={drawer.open} template={drawer.item} onClose={drawer.close} />
    </AdminLayout>
  )
}
