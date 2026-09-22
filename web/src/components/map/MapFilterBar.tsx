import { DatePicker, Select } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'

import type { MapFilterOptions, SchoolStatus } from '../../api/types'
import { useMediaQuery } from '../../app/useMediaQuery'
import { FILTER_SHEET_LABELS, MAP_FILTER_LABELS, SCHOOL_STATUS_LABELS } from '../../lib/labels'
import { PHONE_SCREEN } from '../../styles/theme'
import { Button } from '../ui/Button'
import { FilterSheet } from './FilterSheet'
import { NO_FILTERS, countFilters, filterSummary, isFiltered, type MapFilters } from './filters'
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
export function OptionSelect({ caption, value, options, onChange }: OptionSelectProps) {
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
  const phone = useMediaQuery(PHONE_SCREEN)
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

  const controls = (
    <>
      <OptionSelect
        caption={MAP_FILTER_LABELS.region}
        value={filters.regionId}
        options={options?.regions}
        onChange={(regionId) => set({ regionId })}
      />
      <OptionSelect
        caption={MAP_FILTER_LABELS.provider}
        value={filters.providerId}
        options={options?.providers}
        onChange={(providerId) => set({ providerId })}
      />
      <OptionSelect
        caption={MAP_FILTER_LABELS.connectionType}
        value={filters.connectionTypeId}
        options={options?.connectionTypes}
        onChange={(connectionTypeId) => set({ connectionTypeId })}
      />
      <Select<SchoolStatus[]>
        className={filters.status.length ? `${styles.filter} ${styles.active}` : styles.filter}
        aria-label={MAP_FILTER_LABELS.status}
        mode="multiple"
        placeholder={MAP_FILTER_LABELS.status}
        value={filters.status}
        options={STATUS_OPTIONS}
        onChange={(status) => set({ status })}
        prefix={filters.status.length ? `${MAP_FILTER_LABELS.status}:` : undefined}
        maxTagCount={1}
        maxTagPlaceholder={(omitted) => `+${omitted.length}`}
        allowClear
      />
      <DatePicker.RangePicker
        className={period ? `${styles.filter} ${styles.active}` : styles.filter}
        aria-label={MAP_FILTER_LABELS.period}
        placeholder={[`${MAP_FILTER_LABELS.period} с`, 'по']}
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
    </>
  )

  // DESIGN.md §9.3, row «Панель фильтров»: at 768px and narrower the same controls move into a
  // bottom sheet behind one button, so five selects do not push the map below the fold.
  if (phone) {
    return (
      <FilterSheet count={countFilters(filters)} summary={filterSummary(filters, options)}>
        {controls}
      </FilterSheet>
    )
  }
  return (
    <div className={styles.bar} role="search" aria-label={FILTER_SHEET_LABELS.title}>
      {controls}
    </div>
  )
}
