import { DatePicker, Select } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'

import type { MapFilterOptions, SchoolStatus } from '../../api/types'
import { SCHOOL_STATUS_LABELS } from '../../lib/labels'
import { Button } from '../ui/Button'
import { NO_FILTERS, isFiltered, type MapFilters } from './filters'
import styles from './MapFilterBar.module.css'

interface Option {
  id: number
  name: string
}

interface OptionSelectProps {
  caption: string
  value: number | undefined
  options: Option[] | undefined
  onChange: (value: number | undefined) => void
}

/** Single choice; the active one shows the caption with its value: «Район: Усть-Каменогорск». */
function OptionSelect({ caption, value, options, onChange }: OptionSelectProps) {
  return (
    <Select<number>
      className={value === undefined ? styles.filter : `${styles.filter} ${styles.active}`}
      aria-label={caption}
      placeholder={caption}
      value={value}
      options={options?.map((option) => ({ value: option.id, label: option.name }))}
      labelRender={({ label, value: id }) => `${caption}: ${label ?? id}`}
      onChange={(id) => onChange(id ?? undefined)}
      allowClear
      showSearch
      optionFilterProp="label"
      popupMatchSelectWidth={false}
    />
  )
}

const STATUS_OPTIONS = (Object.keys(SCHOOL_STATUS_LABELS) as SchoolStatus[]).map((status) => ({
  value: status,
  label: SCHOOL_STATUS_LABELS[status],
}))

// Quick ranges of the period picker (DESIGN.md §3.3); each ends now.
const PERIOD_PRESETS: { label: string; start: () => Dayjs }[] = [
  { label: 'Сегодня', start: () => dayjs().startOf('day') },
  { label: 'Неделя', start: () => dayjs().subtract(7, 'day') },
  { label: 'Месяц', start: () => dayjs().subtract(1, 'month') },
  { label: 'Квартал', start: () => dayjs().subtract(3, 'month') },
]

type Range = [Dayjs | null, Dayjs | null] | null

interface MapFilterBarProps {
  filters: MapFilters
  options: MapFilterOptions | undefined
  onChange: (filters: MapFilters) => void
}

/** Filter bar of the overview and the map (DESIGN.md §3.9): one set of filters for both screens. */
export function MapFilterBar({ filters, options, onChange }: MapFilterBarProps) {
  const set = (patch: Partial<MapFilters>) => onChange({ ...filters, ...patch })

  const period: Range = filters.periodFrom
    ? [dayjs(filters.periodFrom), filters.periodTo ? dayjs(filters.periodTo) : dayjs()]
    : null
  const changePeriod = (range: Range) => {
    const [start, end] = range ?? [null, null]
    if (!start || !end) return set({ periodFrom: undefined, periodTo: undefined })
    // A period that ends today ends now: a status «at the end of the day» would be a guess.
    const until = end.endOf('day')
    set({
      periodFrom: start.toISOString(),
      periodTo: until.isAfter(dayjs()) ? undefined : until.toISOString(),
    })
  }

  return (
    <div className={styles.bar} role="search" aria-label="Фильтры">
      <OptionSelect
        caption="Район"
        value={filters.regionId}
        options={options?.regions}
        onChange={(regionId) => set({ regionId })}
      />
      <OptionSelect
        caption="Провайдер"
        value={filters.providerId}
        options={options?.providers}
        onChange={(providerId) => set({ providerId })}
      />
      <OptionSelect
        caption="Тип подключения"
        value={filters.connectionTypeId}
        options={options?.connectionTypes}
        onChange={(connectionTypeId) => set({ connectionTypeId })}
      />
      <Select<SchoolStatus[]>
        className={filters.status.length ? `${styles.filter} ${styles.active}` : styles.filter}
        aria-label="Статус"
        mode="multiple"
        placeholder="Статус"
        value={filters.status}
        options={STATUS_OPTIONS}
        onChange={(status) => set({ status })}
        prefix={filters.status.length ? 'Статус:' : undefined}
        maxTagCount={1}
        maxTagPlaceholder={(omitted) => `+${omitted.length}`}
        allowClear
      />
      <DatePicker.RangePicker
        className={period ? `${styles.filter} ${styles.active}` : styles.filter}
        aria-label="Период"
        placeholder={['Период с', 'по']}
        value={period}
        onChange={changePeriod}
        presets={PERIOD_PRESETS.map((preset) => ({ label: preset.label, value: () => [preset.start(), dayjs()] }))}
        format="DD.MM.YYYY"
        disabledDate={(day) => day.isAfter(dayjs(), 'day')}
      />
      {isFiltered(filters) && (
        <Button kind="link" className={styles.reset} onClick={() => onChange(NO_FILTERS)}>
          Сбросить
        </Button>
      )}
    </div>
  )
}
