import { useNotification } from '@refinedev/core'
import { Popconfirm } from 'antd'
import dayjs from 'dayjs'
import { Plus, Upload } from 'lucide-react'
import { useRef } from 'react'

import type { CalendarEventDetail } from '../../api/types'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { CalendarDrawer } from '../../components/admin/CalendarDrawer'
import { useCalendarEvents, useDeleteCalendarEvent, useImportCalendar } from '../../components/admin/queries'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { Button } from '../../components/ui/Button'
import type { ResponsiveColumn } from '../../components/ui/ResponsiveTable'
import { formatDate, formatDateTime } from '../../lib/format'
import { CALENDAR_KIND_LABELS, CALENDAR_LABELS, CALENDAR_SCOPE_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

const PLANNED_WORKS = 'planned_works'

/** A window of works is read to the minute; a vacation is whole days, so its last day is shown. */
const period = (event: CalendarEventDetail): string =>
  event.kind === PLANNED_WORKS
    ? `${formatDateTime(event.startsAt)} – ${formatDateTime(event.endsAt)}`
    : `${formatDate(event.startsAt)} – ${formatDate(dayjs(event.endsAt).subtract(1, 'day').toISOString())}`

const target = (event: CalendarEventDetail): string =>
  [event.regionName ?? event.schoolName ?? CALENDAR_LABELS.wholeOblast, event.providerName]
    .filter(Boolean)
    .join(' · ')

const COLUMNS: readonly ResponsiveColumn<CalendarEventDetail>[] = [
  {
    key: 'title',
    title: CALENDAR_LABELS.columnTitle,
    render: (_, event) => (
      <div className={styles.stack}>
        <span className={styles.name}>{event.title}</span>
        {event.comment && <span className={styles.muted}>{event.comment}</span>}
      </div>
    ),
  },
  { key: 'kind', title: CALENDAR_LABELS.columnKind, render: (_, event) => CALENDAR_KIND_LABELS[event.kind] },
  { key: 'period', title: CALENDAR_LABELS.columnPeriod, render: (_, event) => period(event) },
  {
    key: 'target',
    title: CALENDAR_LABELS.columnTarget,
    render: (_, event) => (
      <div className={styles.stack}>
        <span>{target(event)}</span>
        <span className={styles.muted}>{CALENDAR_SCOPE_LABELS[event.scope]}</span>
      </div>
    ),
  },
]

/**
 * Календарь каникул, праздников и плановых работ (T-70, docs/design/README.md §6.5): эти дни выключают расчёты,
 * поэтому событие заводится здесь, а не в коде (ТЗ п. 11, п. 20).
 */
export function CalendarPage() {
  const [view, setView] = useAdminListView()
  const events = useCalendarEvents(view)
  const drawer = useDrawer<CalendarEventDetail>()
  const remove = useDeleteCalendarEvent()
  const load = useImportCalendar()
  const { open: notify } = useNotification()
  const file = useRef<HTMLInputElement>(null)

  const importFile = (picked: File | undefined) => {
    if (!picked) return
    void picked.text().then((text) =>
      load.mutate(text, {
        onSuccess: (result) =>
          notify?.({
            type: 'success',
            message: CALENDAR_LABELS.imported(String(result.created)),
            description: result.errors.length ? CALENDAR_LABELS.importErrors(String(result.errors.length)) : undefined,
          }),
        onError: () => notify?.({ type: 'error', message: CALENDAR_LABELS.importFailed }),
      }),
    )
  }

  return (
    <AdminLayout
      tab="calendar"
      action={
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          {CALENDAR_LABELS.add}
        </Button>
      }
    >
      <p className={styles.lead}>{CALENDAR_LABELS.lead}</p>
      <Button
        kind="outlined"
        loading={load.isPending}
        tooltip={CALENDAR_LABELS.importHint}
        icon={<Upload size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
        onClick={() => file.current?.click()}
      >
        {CALENDAR_LABELS.import}
      </Button>
      <input
        ref={file}
        type="file"
        accept=".csv,text/csv"
        hidden
        onChange={(picked) => importFile(picked.target.files?.[0])}
      />
      <AdminTable
        query={events}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{ title: CALENDAR_LABELS.emptyTitle, description: CALENDAR_LABELS.emptyDescription }}
        rowActions={(event) => (
          <>
            <Button kind="flat" size="small" onClick={() => drawer.show(event)}>
              {CALENDAR_LABELS.edit}
            </Button>
            <Popconfirm
              title={CALENDAR_LABELS.deleteTitle}
              description={CALENDAR_LABELS.deleteText}
              okText={CALENDAR_LABELS.deleteOk}
              cancelText={CALENDAR_LABELS.deleteCancel}
              onConfirm={() =>
                remove.mutate(event.id, {
                  onSuccess: () => notify?.({ type: 'success', message: CALENDAR_LABELS.deleted }),
                })
              }
            >
              <Button kind="flat" size="small">
                {CALENDAR_LABELS.delete}
              </Button>
            </Popconfirm>
          </>
        )}
      />
      <CalendarDrawer key={drawer.key} open={drawer.open} event={drawer.item} onClose={drawer.close} />
    </AdminLayout>
  )
}
