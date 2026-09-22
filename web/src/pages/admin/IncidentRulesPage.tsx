import type { TableColumnsType } from 'antd'
import { Plus } from 'lucide-react'

import type { IncidentRuleDetail } from '../../api/types'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { IncidentRuleDrawer } from '../../components/admin/IncidentRuleDrawer'
import { formatOpening, formatRecovery, formatTarget } from '../../components/admin/incidentRules'
import { useIncidentRules } from '../../components/admin/queries'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { Button } from '../../components/ui/Button'
import { SearchInput } from '../../components/ui/SearchInput'
import { CONFIG_ACTIVITY_LABELS, INCIDENT_METRIC_LABELS, INCIDENT_RULE_SCOPE_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

const COLUMNS: TableColumnsType<IncidentRuleDetail> = [
  {
    key: 'name',
    title: 'Название',
    render: (_, rule) => <span className={styles.name}>{rule.name}</span>,
  },
  {
    key: 'metric',
    title: 'Показатель',
    render: (_, rule) => INCIDENT_METRIC_LABELS[rule.metric],
  },
  { key: 'scope', title: 'Уровень', render: (_, rule) => INCIDENT_RULE_SCOPE_LABELS[rule.scope] },
  {
    key: 'target',
    title: 'Для кого',
    render: (_, rule) =>
      rule.scope === 'school' ? (
        <span className={styles.name}>{formatTarget(rule)}</span>
      ) : (
        <span className={styles.muted}>{formatTarget(rule)}</span>
      ),
  },
  {
    key: 'opening',
    title: 'Открывает',
    render: (_, rule) => formatOpening(rule),
  },
  {
    key: 'recovery',
    title: 'Восстановление',
    render: (_, rule) => formatRecovery(rule.recoveryNormalCount),
  },
  {
    key: 'active',
    title: 'Состояние',
    render: (_, rule) =>
      rule.isActive ? (
        CONFIG_ACTIVITY_LABELS.active
      ) : (
        <span className={styles.muted}>{CONFIG_ACTIVITY_LABELS.disabled}</span>
      ),
  },
]

/**
 * Incident rules (ТЗ п. 18, ADR-007): each watches one metric on every line, or on the lines of one school in
 * place of the rule of the oblast (T-85); N violations in a row or T minutes open an incident, M normal results in
 * a row restore it.
 */
export function IncidentRulesPage() {
  const [view, setView] = useAdminListView()
  const rules = useIncidentRules(view)
  const drawer = useDrawer<IncidentRuleDetail>()

  return (
    <AdminLayout
      tab="incident-rules"
      action={
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          Добавить правило
        </Button>
      }
    >
      <p className={styles.lead}>
        Инцидент по линии открывается, когда выполнено любое условие правила: N нарушений подряд или нарушение
        дольше T минут; единичное отклонение инцидент не открывает. «{INCIDENT_METRIC_LABELS.no_connection}» по
        длительности считается и по молчанию агента в рабочие часы. Правило школы заменяет для её линий правило
        области по тому же показателю. Изменения действуют со следующей проверки, ничего перезапускать не нужно.
      </p>
      <div className={styles.toolbar}>
        <SearchInput
          className={styles.search}
          value={view.q}
          placeholder="Поиск по названию правила, School ID или школе"
          onSearch={(q) => setView({ ...view, q, page: 1 })}
        />
      </div>
      <AdminTable
        query={rules}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{
          title: 'Правил пока нет',
          description: 'Правила по умолчанию создаются при установке системы.',
        }}
        onEdit={(rule) => drawer.show(rule)}
      />
      <IncidentRuleDrawer key={drawer.key} open={drawer.open} rule={drawer.item} onClose={drawer.close} />
    </AdminLayout>
  )
}
