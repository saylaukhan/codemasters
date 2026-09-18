import { useGetIdentity, useNotification } from '@refinedev/core'
import { Checkbox, DatePicker, Form, Input, Select } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useState } from 'react'
import { useNavigate } from 'react-router'

import type { CurrentUser, IncidentMetric, LineDetail } from '../../api/types'
import { incidentCardPath } from '../../app/sections'
import { INCIDENT_METRIC_LABELS, LINE_STATUS_LABELS } from '../../lib/labels'
import { FormDrawer } from '../admin/FormDrawer'
import { maxLength, required } from '../admin/form'
import {
  DESCRIPTION_MAX_LENGTH,
  INCIDENT_FORM_DEFAULTS,
  incidentCreateBody,
  type IncidentFormValues,
} from './incidents'
import { useCreateIncident } from './queries'

// An unknown responsible has no field of its own: that error goes to the alert.
const FIELDS = ['lineId', 'metrics', 'description', 'startedAt']

const METRIC_OPTIONS = (Object.keys(INCIDENT_METRIC_LABELS) as IncidentMetric[]).map((value) => ({
  value,
  label: INCIDENT_METRIC_LABELS[value],
}))

interface IncidentCreateDrawerProps {
  open: boolean
  /** Lines of the school; a disabled one takes no new incidents. */
  lines: LineDetail[]
  onClose: () => void
}

/**
 * Manual incident from the school card (ТЗ п. 19, ADR-007): it starts as «Новый» without a rule; the school and the
 * provider come from the line. The new card opens after saving.
 */
export function IncidentCreateDrawer({ open, lines, onClose }: IncidentCreateDrawerProps) {
  const [form] = Form.useForm<IncidentFormValues>()
  const create = useCreateIncident()
  const { data: user } = useGetIdentity<CurrentUser>()
  const { open: notify } = useNotification()
  const navigate = useNavigate()
  const active = lines.filter((line) => line.status !== 'disabled')
  const [initial] = useState<IncidentFormValues>(() => ({
    ...INCIDENT_FORM_DEFAULTS,
    lineId: (active.find((line) => line.status === 'main') ?? active[0])?.id,
  }))

  const submit = (values: IncidentFormValues) =>
    create.mutate(incidentCreateBody(values, user?.id), {
      onSuccess: (saved) => {
        notify?.({ type: 'success', message: 'Инцидент создан', description: saved.number })
        onClose()
        navigate(incidentCardPath(saved.id))
      },
    })

  return (
    <FormDrawer
      title="Новый инцидент"
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={create.isPending}
      error={create.error}
    >
      <Form<IncidentFormValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item label="Линия" name="lineId" rules={[{ required: true, message: 'Выберите линию' }]}>
          <Select<number>
            placeholder="Выберите из списка"
            options={active.map((line) => ({
              value: line.id,
              label: `${LINE_STATUS_LABELS[line.status]} · ${line.providerName}`,
            }))}
          />
        </Form.Item>
        <Form.Item
          label="Показатели-основания"
          name="metrics"
          rules={[{ required: true, type: 'array', min: 1, message: 'Выберите хотя бы один показатель' }]}
        >
          <Select<IncidentMetric[]> mode="multiple" placeholder="Выберите из списка" options={METRIC_OPTIONS} />
        </Form.Item>
        <Form.Item
          label="Описание"
          name="description"
          rules={[required('Опишите проблему'), maxLength(DESCRIPTION_MAX_LENGTH)]}
        >
          <Input.TextArea autoSize={{ minRows: 3, maxRows: 8 }} />
        </Form.Item>
        <Form.Item
          label="Начало проблемы"
          name="startedAt"
          extra="Не указано — момент создания инцидента."
          rules={[
            {
              validator: (_, value: Dayjs | null) =>
                value && value.isAfter(dayjs())
                  ? Promise.reject(new Error('Начало не может быть в будущем'))
                  : Promise.resolve(),
            },
          ]}
        >
          <DatePicker
            showTime={{ format: 'HH:mm' }}
            format="DD.MM.YYYY HH:mm"
            placeholder="Выберите дату и время"
            disabledDate={(day) => day.isAfter(dayjs(), 'day')}
          />
        </Form.Item>
        <Form.Item name="responsible" valuePropName="checked">
          <Checkbox>Я ответственный</Checkbox>
        </Form.Item>
      </Form>
    </FormDrawer>
  )
}
