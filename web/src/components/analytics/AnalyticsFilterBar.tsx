import { DatePicker, Segmented } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'

import type { AnalyticsLevel, AnalyticsPeriod, MapFilterOptions } from '../../api/types'
import { useMediaQuery } from '../../app/useMediaQuery'
import {
  ANALYTICS_LEVEL_LABELS,
  CUSTOM_PERIOD_LABEL,
  FILTER_SHEET_LABELS,
  MAP_FILTER_LABELS,
  PERIOD_LABELS,
} from '../../lib/labels'
import { PHONE_SCREEN } from '../../styles/theme'
import { FilterSheet } from '../map/FilterSheet'
import { filterSummary } from '../map/filters'
import { OptionSelect } from '../map/MapFilterBar'
import styles from '../map/MapFilterBar.module.css'
import { Button } from '../ui/Button'
import { isFiltered, LEVELS, PRESETS, type AnalyticsView } from './view'

const PERIOD_OPTIONS = [
  ...PRESETS.map((value) => ({ value, label: PERIOD_LABELS[value] })),
  { value: 'custom' as const, label: CUSTOM_PERIOD_LABEL },
]

/** Dimensions of the «Фильтры · N» button (DESIGN.md §9.3); the level and the period always show. */
const countFilters = (view: AnalyticsView): number =>
  [view.regionId, view.providerId, view.connectionTypeId].filter((id) => id !== undefined).length

interface AnalyticsFilterBarProps {
  view: AnalyticsView
  options: MapFilterOptions | undefined
  onChange: (view: AnalyticsView) => void
}

/** Level, period and slices of the analytics (ТЗ п. 5, п. 13; DESIGN.md §3.9). */
export function AnalyticsFilterBar({ view, options, onChange }: AnalyticsFilterBarProps) {
  const phone = useMediaQuery(PHONE_SCREEN)
  const set = (patch: Partial<AnalyticsView>) => onChange({ ...view, ...patch })

  // Whole days: the end of the API period is exclusive, so the last chosen day ends at midnight.
  const setRange = (start: Dayjs, end: Dayjs) =>
    set({
      period: 'custom',
      periodFrom: start.startOf('day').toISOString(),
      periodTo: end.add(1, 'day').startOf('day').toISOString(),
    })
  const range: [Dayjs, Dayjs] | null =
    view.periodFrom && view.periodTo ? [dayjs(view.periodFrom), dayjs(view.periodTo).subtract(1, 'day')] : null

  const controls = (
    <>
      <Segmented<AnalyticsLevel>
        aria-label={MAP_FILTER_LABELS.level}
        value={view.level}
        options={LEVELS.map((value) => ({ value, label: ANALYTICS_LEVEL_LABELS[value] }))}
        onChange={(level) => set({ level })}
      />
      <Segmented<AnalyticsPeriod>
        aria-label={MAP_FILTER_LABELS.period}
        value={view.period}
        options={PERIOD_OPTIONS}
        onChange={(period) =>
          period === 'custom'
            ? setRange(dayjs().subtract(6, 'day'), dayjs())
            : set({ period, periodFrom: undefined, periodTo: undefined })
        }
      />
      {view.period === 'custom' && (
        <DatePicker.RangePicker
          className={`${styles.filter} ${styles.active}`}
          aria-label={CUSTOM_PERIOD_LABEL}
          value={range}
          allowClear={false}
          onChange={(value) => value?.[0] && value[1] && setRange(value[0], value[1])}
          format="DD.MM.YYYY"
          disabledDate={(day) => day.isAfter(dayjs(), 'day')}
        />
      )}
      <OptionSelect
        caption={MAP_FILTER_LABELS.region}
        value={view.regionId}
        options={options?.regions}
        onChange={(regionId) => set({ regionId })}
      />
      <OptionSelect
        caption={MAP_FILTER_LABELS.provider}
        value={view.providerId}
        options={options?.providers}
        onChange={(providerId) => set({ providerId })}
      />
      <OptionSelect
        caption={MAP_FILTER_LABELS.connectionType}
        value={view.connectionTypeId}
        options={options?.connectionTypes}
        onChange={(connectionTypeId) => set({ connectionTypeId })}
      />
      {isFiltered(view) && (
        <Button
          kind="link"
          className={styles.reset}
          onClick={() => set({ regionId: undefined, providerId: undefined, connectionTypeId: undefined })}
        >
          Сбросить
        </Button>
      )}
    </>
  )

  // DESIGN.md §9.3, row «Панель фильтров»: the same bottom sheet as the filter bar of the map.
  if (phone) {
    return (
      <FilterSheet count={countFilters(view)} summary={filterSummary(view, options)}>
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
