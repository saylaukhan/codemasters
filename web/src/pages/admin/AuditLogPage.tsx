import { DatePicker, Select, Table, type TableColumnsType } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { SearchX } from 'lucide-react'
import { useCallback, useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'

import type { AuditAction, AuditLogListItem } from '../../api/types'
import { deviceCardPath } from '../../app/sections'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import {
  auditLogQuery,
  changeLines,
  isFiltered,
  KIND_ACTIONS,
  readAuditLogView,
  writeAuditLogView,
  type AuditLogKind,
  type AuditLogView,
} from '../../components/admin/auditLog'
import { useAuditLog } from '../../components/admin/queries'
import { PAGE_SIZES } from '../../components/schools/useSchoolListView'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { SearchInput } from '../../components/ui/SearchInput'
import { formatDateTime, NO_VALUE } from '../../lib/format'
import { AUDIT_ACTION_LABELS, AUDIT_ENTITY_LABELS, AUDIT_ERROR_LABELS } from '../../lib/labels'

const DAY_FORMAT = 'YYYY-MM-DD'

const ACTION_OPTIONS = KIND_ACTIONS.audit.map((action) => ({ value: action, label: AUDIT_ACTION_LABELS[action] }))

const errorLabel = (errorType: string | null) => (errorType ? (AUDIT_ERROR_LABELS[errorType] ?? errorType) : null)

const WHEN: TableColumnsType<AuditLogListItem>[number] = {
  key: 'when',
  title: 'Когда',
  fixed: 'left',
  render: (_, record) => <span className={styles.code}>{formatDateTime(record.createdAt)}</span>,
}

/** «Аудит»: who, when, what — sign-ins, changes with their fields, blocks and exports (ТЗ п. 12, п. 16). */
const AUDIT_COLUMNS: TableColumnsType<AuditLogListItem> = [
  WHEN,
  {
    key: 'who',
    title: 'Кто',
    render: (_, record) => (
      <span className={styles.stack}>
        <span className={styles.name}>{record.userEmail ?? NO_VALUE}</span>
        {record.ip && <span className={styles.muted}>{record.ip}</span>}
      </span>
    ),
  },
  {
    key: 'action',
    title: 'Действие',
    render: (_, record) => (
      <span className={styles.stack}>
        <span>{AUDIT_ACTION_LABELS[record.action]}</span>
        {record.errorType && <span className={styles.muted}>{errorLabel(record.errorType)}</span>}
      </span>
    ),
  },
  {
    key: 'entity',
    title: 'Объект',
    render: (_, record) =>
      record.entityId === null
        ? AUDIT_ENTITY_LABELS[record.entityType]
        : `${AUDIT_ENTITY_LABELS[record.entityType]} № ${record.entityId}`,
  },
  {
    key: 'changes',
    title: 'Изменения',
    render: (_, record) => {
      const lines = changeLines(record.changes)
      if (lines.length === 0) return <span className={styles.muted}>{NO_VALUE}</span>
      return (
        <ul className={styles.changes}>
          {lines.map((line) => (
            <li key={line.field}>
              <span className={styles.muted}>{line.field}:</span> {line.old} → {line.new}
            </li>
          ))}
        </ul>
      )
    },
  },
]

/** «События»: rejected requests of agents — an unknown token, a blocked device, invalid data (ТЗ п. 12). */
const EVENT_COLUMNS: TableColumnsType<AuditLogListItem> = [
  WHEN,
  {
    key: 'device',
    title: 'Устройство',
    render: (_, record) =>
      record.entityId === null ? (
        <span className={styles.muted}>Не определено по токену</span>
      ) : (
        <Link to={deviceCardPath(record.entityId)}>
          {AUDIT_ENTITY_LABELS.device} № {record.entityId}
        </Link>
      ),
  },
  { key: 'error', title: 'Ошибка', render: (_, record) => errorLabel(record.errorType) ?? NO_VALUE },
  {
    key: 'ip',
    title: 'IP-адрес',
    render: (_, record) => <span className={styles.code}>{record.ip ?? NO_VALUE}</span>,
  },
]

const EMPTY: Record<AuditLogKind, { title: string; description: string }> = {
  audit: {
    title: 'Записей пока нет',
    description: 'Сюда попадают входы в панель и изменения школ, справочников, настроек и пользователей.',
  },
  events: {
    title: 'Ошибок передачи нет',
    description:
      'Сюда попадают отклонённые запросы агентов: неверный токен, заблокированное устройство, невалидные данные.',
  },
}

function useAuditLogView(kind: AuditLogKind): [AuditLogView, (view: AuditLogView) => void] {
  const [params, setParams] = useSearchParams()
  const view = useMemo(() => readAuditLogView(params, kind), [params, kind])
  const setView = useCallback(
    (next: AuditLogView) => setParams((current) => writeAuditLogView(current, next), { replace: true }),
    [setParams],
  )
  return [view, setView]
}

/** A log of the administration over GET /api/admin/audit-log: read-only, newest first, the Администратор's only. */
function LogPage({ kind }: { kind: AuditLogKind }) {
  const [view, setView] = useAuditLogView(kind)
  const log = useAuditLog(auditLogQuery(view, kind))

  const period: [Dayjs, Dayjs] | null = view.days ? [dayjs(view.days[0]), dayjs(view.days[1])] : null
  const reset = () => setView({ q: '', actions: [], days: undefined, page: 1, pageSize: view.pageSize })

  const table = () => {
    if (log.isError) return <ErrorState error={log.error} onRetry={() => void log.refetch()} />
    if (log.isPending) return <ContentSkeleton />
    const emptyText = isFiltered(view) ? (
      <EmptyState
        icon={SearchX}
        title="Ничего не найдено"
        description="Измените фильтры или сбросьте их."
        action={<Button onClick={reset}>Сбросить фильтры</Button>}
      />
    ) : (
      <EmptyState title={EMPTY[kind].title} description={EMPTY[kind].description} />
    )
    return (
      <Table<AuditLogListItem>
        rowKey="id"
        size="middle"
        columns={kind === 'audit' ? AUDIT_COLUMNS : EVENT_COLUMNS}
        dataSource={log.data.items}
        loading={log.isFetching && log.isPlaceholderData}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText }}
        pagination={{
          current: view.page,
          pageSize: view.pageSize,
          total: log.data.total,
          pageSizeOptions: PAGE_SIZES.map(String),
          showSizeChanger: true,
          showTotal: (count, [from, to]) => `${from}–${to} из ${count}`,
        }}
        onChange={(pagination) => {
          const pageSize = pagination.pageSize ?? view.pageSize
          setView({ ...view, pageSize, page: pageSize === view.pageSize ? (pagination.current ?? 1) : 1 })
        }}
      />
    )
  }

  return (
    <AdminLayout tab={kind} action={null}>
      <div className={styles.toolbar}>
        <SearchInput
          className={styles.search}
          value={view.q}
          placeholder={kind === 'audit' ? 'Поиск по e-mail или IP-адресу' : 'Поиск по IP-адресу'}
          onSearch={(q) => setView({ ...view, q, page: 1 })}
        />
        {kind === 'audit' && (
          <Select<AuditAction[]>
            className={styles.logFilter}
            mode="multiple"
            allowClear
            maxTagCount="responsive"
            aria-label="Действие"
            placeholder="Все действия"
            options={ACTION_OPTIONS}
            value={view.actions}
            onChange={(actions) => setView({ ...view, actions, page: 1 })}
          />
        )}
        <DatePicker.RangePicker
          aria-label="Период"
          placeholder={['Начало', 'Конец']}
          format="DD.MM.YYYY"
          value={period}
          disabledDate={(day) => day.isAfter(dayjs(), 'day')}
          onChange={(range) =>
            setView({
              ...view,
              days: range?.[0] && range[1] ? [range[0].format(DAY_FORMAT), range[1].format(DAY_FORMAT)] : undefined,
              page: 1,
            })
          }
        />
      </div>
      {table()}
    </AdminLayout>
  )
}

/** «Аудит» of «Администрирование» (T-39): sign-ins, changes of references and settings, who and when. */
export function AuditLogPage() {
  return <LogPage kind="audit" />
}

/** «События» of «Администрирование» (T-39): transfer errors of agents; notifications join them with T-42. */
export function EventLogPage() {
  return <LogPage kind="events" />
}
