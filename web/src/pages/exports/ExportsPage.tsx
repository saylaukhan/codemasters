import { useNotification } from '@refinedev/core'
import { Checkbox, DatePicker, Segmented, Select } from 'antd'
import dayjs from 'dayjs'
import { useMemo, useState, type ReactNode } from 'react'

import type { ExportColumn, ExportFormat, ExportMode, QualityStatus } from '../../api/types'
import styles from '../../components/exports/Exports.module.css'
import { useBuildExport, useDeviceOptions, useSchoolOptions } from '../../components/exports/queries'
import {
  AGGREGATE_COLUMNS,
  ALL_COLUMNS,
  exportBody,
  MIN_COLUMNS,
  orderedColumns,
  RAW_FORMATS,
  type ExportDraft,
} from '../../components/exports/request'
import { Button } from '../../components/ui/Button'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { formatDate, formatNumber } from '../../lib/format'
import {
  EXPORT_AGGREGATE_COLUMN_LABELS,
  EXPORT_COLUMN_LABELS,
  EXPORT_FORMAT_LABELS,
  EXPORT_MODE_LABELS,
  QUALITY_STATUS_LABELS,
  SECTION_LABELS,
} from '../../lib/labels'

// The PDF report (T-32) is shown but not chosen yet.
const MODE_OPTIONS = (Object.keys(EXPORT_MODE_LABELS) as ExportMode[]).map((mode) => ({
  value: mode,
  label: EXPORT_MODE_LABELS[mode],
  disabled: mode === 'school_report',
}))
const FORMAT_OPTIONS = RAW_FORMATS.map((format) => ({ value: format, label: EXPORT_FORMAT_LABELS[format] }))
const STATUS_OPTIONS = (Object.keys(QUALITY_STATUS_LABELS) as QualityStatus[]).map((status) => ({
  value: status,
  label: QUALITY_STATUS_LABELS[status],
}))
const EXTRA_COLUMNS = ALL_COLUMNS.filter((column) => !MIN_COLUMNS.includes(column))

const initialDraft = (): ExportDraft => ({
  mode: 'raw',
  format: 'xlsx',
  days: [dayjs().subtract(6, 'day'), dayjs()],
  deviceIds: [],
  statuses: [],
  columns: [...MIN_COLUMNS],
})

interface Option {
  value: number
  label: string
}

function Step({ number, title, children }: { number: number; title: string; children: ReactNode }) {
  return (
    <section className={styles.card}>
      <h2 className={styles.title}>
        <span className={styles.step}>{number}</span>
        {title}
      </h2>
      {children}
    </section>
  )
}

/**
 * Export constructor (ТЗ п. 9, DESIGN.md §3.24): raw measurements or the aggregates per school of
 * the scope in XLSX, CSV or JSON.
 */
export function ExportsPage() {
  const [draft, setDraft] = useState(initialDraft)
  const [school, setSchool] = useState<Option>()
  const [search, setSearch] = useState('')
  const schools = useSchoolOptions(search)
  const devices = useDeviceOptions(draft.schoolId)
  const build = useBuildExport()
  const { open } = useNotification()

  const set = (patch: Partial<ExportDraft>) => setDraft((current) => ({ ...current, ...patch }))
  // The chosen school stays among the options while another search is typed.
  const schoolOptions = useMemo(() => {
    const found = (schools.data?.items ?? []).map((item) => ({
      value: item.id,
      label: `${item.fullName} · ${item.schoolCode}`,
    }))
    return school && !found.some((option) => option.value === school.value) ? [school, ...found] : found
  }, [schools.data, school])
  const deviceOptions = (devices.data?.items ?? []).map((device) => ({
    value: device.id,
    label: device.room ? `${device.hostname ?? device.deviceUid} · ${device.room}` : (device.hostname ?? device.deviceUid),
  }))
  const extras = EXTRA_COLUMNS.filter((column) => draft.columns.includes(column))
  const columns = orderedColumns(draft.columns)
  const raw = draft.mode === 'raw'

  const chooseSchool = (option: Option | undefined) => {
    setSchool(option)
    set({ schoolId: option?.value, deviceIds: [] })
  }
  const submit = () =>
    build.mutate(exportBody(draft), {
      onSuccess: (job) =>
        open?.({
          type: 'success',
          message: 'Экспорт готов',
          description: `Строк в файле: ${formatNumber(job.rowsCount, 0)}`,
        }),
    })

  return (
    <>
      <PageHeader title={SECTION_LABELS.exports} subtitle="Замеры вашей области видимости в файл" />
      <div className={styles.layout}>
        <div className={styles.steps}>
          <Step number={1} title="Тип данных">
            <Segmented<ExportMode>
              aria-label="Тип данных"
              value={draft.mode}
              options={MODE_OPTIONS}
              onChange={(mode) => mode !== 'school_report' && set({ mode })}
            />
            <p className={styles.caption}>
              {raw
                ? 'Каждый замер — отдельная строка. PDF-отчёт появится в следующих версиях.'
                : 'Одна строка на школу: основная линия без Wi‑Fi, как в аналитике.'}
            </p>
          </Step>
          <Step number={2} title="Фильтры">
            <div className={styles.filters}>
              <label className={styles.field}>
                <span className={styles.label}>Период</span>
                <DatePicker.RangePicker
                  value={draft.days}
                  allowClear={false}
                  format="DD.MM.YYYY"
                  disabledDate={(day) => day.isAfter(dayjs(), 'day')}
                  onChange={(value) => value?.[0] && value[1] && set({ days: [value[0], value[1]] })}
                />
              </label>
              <label className={styles.field}>
                <span className={styles.label}>Школа</span>
                <Select<number, Option>
                  placeholder="Все школы"
                  value={school?.value}
                  options={schoolOptions}
                  onChange={(_, option) => chooseSchool(Array.isArray(option) ? undefined : option)}
                  onSearch={setSearch}
                  onClear={() => chooseSchool(undefined)}
                  filterOption={false}
                  loading={schools.isFetching}
                  allowClear
                  showSearch
                />
              </label>
              {raw && (
                <>
                  <label className={styles.field}>
                    <span className={styles.label}>Компьютеры</span>
                    <Select<number[]>
                      mode="multiple"
                      placeholder={draft.schoolId === undefined ? 'Сначала выберите школу' : 'Все компьютеры школы'}
                      value={draft.deviceIds}
                      options={deviceOptions}
                      onChange={(deviceIds) => set({ deviceIds })}
                      disabled={draft.schoolId === undefined}
                      loading={devices.isFetching}
                      optionFilterProp="label"
                      allowClear
                    />
                  </label>
                  <label className={styles.field}>
                    <span className={styles.label}>Статус замера</span>
                    <Select<QualityStatus[]>
                      mode="multiple"
                      placeholder="Все статусы"
                      value={draft.statuses}
                      options={STATUS_OPTIONS}
                      onChange={(statuses) => set({ statuses })}
                      allowClear
                    />
                  </label>
                </>
              )}
            </div>
          </Step>
          <Step number={3} title="Колонки">
            {raw ? (
              <>
                <Checkbox
                  className={styles.all}
                  checked={extras.length === EXTRA_COLUMNS.length}
                  indeterminate={extras.length > 0 && extras.length < EXTRA_COLUMNS.length}
                  onChange={(event) => set({ columns: event.target.checked ? ALL_COLUMNS : [...MIN_COLUMNS] })}
                >
                  Выбрать все
                </Checkbox>
                <Checkbox.Group<ExportColumn>
                  className={styles.columns}
                  value={columns}
                  onChange={(chosen) => set({ columns: chosen })}
                  options={ALL_COLUMNS.map((column) => ({
                    value: column,
                    label: EXPORT_COLUMN_LABELS[column],
                    disabled: MIN_COLUMNS.includes(column),
                  }))}
                />
                <p className={styles.caption}>Минимальный набор колонок выгружается всегда.</p>
              </>
            ) : (
              <>
                <Checkbox.Group
                  className={styles.columns}
                  value={AGGREGATE_COLUMNS}
                  options={AGGREGATE_COLUMNS.map((column) => ({
                    value: column,
                    label: EXPORT_AGGREGATE_COLUMN_LABELS[column],
                  }))}
                  disabled
                />
                <p className={styles.caption}>Состав колонок агрегатов задан ТЗ и не меняется.</p>
              </>
            )}
          </Step>
          <Step number={4} title="Формат">
            <Segmented<ExportFormat>
              aria-label="Формат"
              value={draft.format}
              options={FORMAT_OPTIONS}
              onChange={(format) => set({ format })}
            />
            <p className={styles.caption}>
              XLSX и CSV — с русскими заголовками, время по Алматы; CSV открывается в Excel двойным щелчком.
              JSON — коды полей и значений для программ.
            </p>
          </Step>
        </div>
        <aside className={styles.card} aria-label="Сводка">
          <h2 className={styles.title}>Сводка</h2>
          <dl className={styles.summary}>
            <dt>Тип данных</dt>
            <dd>{EXPORT_MODE_LABELS[draft.mode]}</dd>
            <dt>Период</dt>
            <dd>
              {formatDate(draft.days[0].toDate())} — {formatDate(draft.days[1].toDate())}
            </dd>
            <dt>Школа</dt>
            <dd>{school?.label ?? 'Все в области видимости'}</dd>
            {raw && (
              <>
                <dt>Компьютеры</dt>
                <dd>{draft.deviceIds.length ? formatNumber(draft.deviceIds.length, 0) : 'Все'}</dd>
                <dt>Статусы</dt>
                <dd>
                  {draft.statuses.length
                    ? draft.statuses.map((status) => QUALITY_STATUS_LABELS[status]).join(', ')
                    : 'Все'}
                </dd>
              </>
            )}
            <dt>Колонок</dt>
            <dd>{formatNumber(raw ? columns.length : AGGREGATE_COLUMNS.length, 0)}</dd>
            <dt>Формат</dt>
            <dd>{EXPORT_FORMAT_LABELS[draft.format]}</dd>
          </dl>
          {build.isError && (
            <div className={styles.error}>
              <ErrorState error={build.error} />
            </div>
          )}
          <Button kind="action" block loading={build.isPending} onClick={submit}>
            Сформировать
          </Button>
        </aside>
      </div>
    </>
  )
}
