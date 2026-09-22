import { useNotification } from '@refinedev/core'
import { DatePicker, Form, Input, Segmented, Select } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import timezone from 'dayjs/plugin/timezone'
import utc from 'dayjs/plugin/utc'
import { useState } from 'react'

import type {
  CalendarEventCreate,
  CalendarEventDetail,
  CalendarEventUpdate,
  CalendarKind,
  CalendarScope,
} from '../../api/types'
import { TIME_ZONE } from '../../lib/format'
import { CALENDAR_KIND_LABELS, CALENDAR_LABELS, CALENDAR_SCOPE_LABELS } from '../../lib/labels'
import { FormDrawer } from './FormDrawer'
import { changedFields } from './form'
import { useProviderOptions, useRegionOptions, useSaveCalendarEvent, useSchoolOptions } from './queries'

dayjs.extend(utc)
dayjs.extend(timezone)

const PLANNED_WORKS = 'planned_works'

// Errors of the school and of the period go to the alert: the form has no field of those names.
const FIELDS = ['regionId', 'providerId', 'title', 'comment']

const KIND_OPTIONS = (['vacation', 'holiday', PLANNED_WORKS] as CalendarKind[]).map((value) => ({
  value,
  label: CALENDAR_KIND_LABELS[value],
}))
const SCOPE_OPTIONS = (['oblast', 'district', 'school'] as CalendarScope[]).map((value) => ({
  value,
  label: CALENDAR_SCOPE_LABELS[value],
}))

interface CalendarValues {
  kind: CalendarKind
  scope: CalendarScope
  regionId?: number
  /** With its label: a school picked from one search stays named when the search changes. */
  school?: { value: number; label: string }
  providerId?: number
  period: [Dayjs, Dayjs]
  title: string
  comment?: string
}

/** The wall time the user picked, read in the zone of the system: the day ends when it ends there. */
const moment = (value: Dayjs, whole: boolean): string =>
  dayjs.tz(value.format(whole ? 'YYYY-MM-DD' : 'YYYY-MM-DDTHH:mm'), TIME_ZONE).toISOString()

const startsAt = (values: CalendarValues): string =>
  moment(values.period[0], values.kind !== PLANNED_WORKS)

/** A vacation ends with the last local day of the order, so its bound is the midnight after it. */
const endsAt = (values: CalendarValues): string =>
  values.kind === PLANNED_WORKS
    ? moment(values.period[1], false)
    : moment(values.period[1].add(1, 'day'), true)

const updatableOf = (values: CalendarValues): CalendarEventUpdate => ({
  startsAt: startsAt(values),
  endsAt: endsAt(values),
  title: values.title.trim(),
  comment: values.comment?.trim() || null,
})

const periodOf = (event: CalendarEventDetail): [Dayjs, Dayjs] => [
  dayjs(event.startsAt).tz(TIME_ZONE),
  event.kind === PLANNED_WORKS
    ? dayjs(event.endsAt).tz(TIME_ZONE)
    : dayjs(event.endsAt).tz(TIME_ZONE).subtract(1, 'day'),
]

interface CalendarDrawerProps {
  open: boolean
  /** The event being edited; none — a new one. */
  event?: CalendarEventDetail
  onClose: () => void
}

/**
 * Event of the calendar (T-70, docs/design/README.md §6.5): in a vacation and on a holiday availability is not
 * counted and incidents are not opened, a window of planned works also drops out of the score of its provider.
 */
export function CalendarDrawer({ open, event, onClose }: CalendarDrawerProps) {
  const [form] = Form.useForm<CalendarValues>()
  const save = useSaveCalendarEvent()
  const { open: notify } = useNotification()
  const [search, setSearch] = useState('')
  const kind = Form.useWatch('kind', form) ?? event?.kind ?? 'vacation'
  const scope = Form.useWatch('scope', form) ?? event?.scope ?? 'oblast'
  const regions = useRegionOptions()
  const providers = useProviderOptions()
  const schools = useSchoolOptions(search)
  const [initial] = useState<CalendarValues>(() => ({
    kind: event?.kind ?? 'vacation',
    scope: event?.scope ?? 'oblast',
    regionId: event?.regionId ?? undefined,
    providerId: event?.providerId ?? undefined,
    period: event ? periodOf(event) : [dayjs(), dayjs()],
    title: event?.title ?? '',
    comment: event?.comment ?? undefined,
  }))

  const submit = (values: CalendarValues) => {
    const done = () => {
      notify?.({
        type: 'success',
        message: event ? CALENDAR_LABELS.changed : CALENDAR_LABELS.created,
      })
      onClose()
    }
    if (!event) {
      const body: CalendarEventCreate = {
        kind: values.kind,
        scope: values.scope,
        regionId: values.scope === 'district' ? values.regionId : null,
        schoolId: values.scope === 'school' ? values.school?.value : null,
        providerId: values.kind === PLANNED_WORKS ? (values.providerId ?? null) : null,
        startsAt: startsAt(values),
        endsAt: endsAt(values),
        title: values.title.trim(),
        comment: values.comment?.trim() || null,
      }
      return save.mutate({ body }, { onSuccess: done })
    }
    const body = changedFields(updatableOf(initial), updatableOf(values))
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: event.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={event ? CALENDAR_LABELS.editTitle : CALENDAR_LABELS.newTitle}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<CalendarValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item label={CALENDAR_LABELS.kindField} name="kind">
          <Segmented options={KIND_OPTIONS} disabled={Boolean(event)} />
        </Form.Item>
        <Form.Item label={CALENDAR_LABELS.scopeField} name="scope">
          <Segmented options={SCOPE_OPTIONS} disabled={Boolean(event)} />
        </Form.Item>
        {!event && scope === 'district' && (
          <Form.Item
            label={CALENDAR_LABELS.regionField}
            name="regionId"
            rules={[{ required: true, message: CALENDAR_LABELS.requiredRegion }]}
          >
            <Select<number> options={regions.data} loading={regions.isPending} optionFilterProp="label" showSearch />
          </Form.Item>
        )}
        {!event && scope === 'school' && (
          <Form.Item
            label={CALENDAR_LABELS.schoolField}
            name="school"
            rules={[{ required: true, message: CALENDAR_LABELS.requiredSchool }]}
          >
            <Select<CalendarValues['school']>
              showSearch
              labelInValue
              filterOption={false}
              options={schools.data}
              loading={schools.isFetching}
              onSearch={setSearch}
            />
          </Form.Item>
        )}
        {!event && kind === PLANNED_WORKS && (
          <Form.Item label={CALENDAR_LABELS.providerField} name="providerId" extra={CALENDAR_LABELS.providerHint}>
            <Select<number>
              allowClear
              options={providers.data}
              loading={providers.isPending}
              optionFilterProp="label"
              showSearch
            />
          </Form.Item>
        )}
        <Form.Item
          label={CALENDAR_LABELS.periodField}
          name="period"
          extra={kind === PLANNED_WORKS ? undefined : CALENDAR_LABELS.periodHint}
          rules={[{ required: true, message: CALENDAR_LABELS.requiredPeriod }]}
        >
          <DatePicker.RangePicker
            format={kind === PLANNED_WORKS ? 'DD.MM.YYYY HH:mm' : 'DD.MM.YYYY'}
            showTime={kind === PLANNED_WORKS ? { format: 'HH:mm', minuteStep: 5 } : false}
            allowClear={false}
          />
        </Form.Item>
        <Form.Item
          label={CALENDAR_LABELS.titleField}
          name="title"
          rules={[{ required: true, message: CALENDAR_LABELS.requiredTitle }]}
        >
          <Input maxLength={200} />
        </Form.Item>
        <Form.Item label={CALENDAR_LABELS.commentField} name="comment">
          <Input.TextArea rows={2} maxLength={1000} />
        </Form.Item>
      </Form>
    </FormDrawer>
  )
}
