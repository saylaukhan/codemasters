import { useNotification } from '@refinedev/core'
import { Checkbox, Form, Input, Select } from 'antd'
import { useState } from 'react'

import type { LineDetail, MonitoringPointDetail } from '../../api/types'
import { LINE_STATUS_LABELS } from '../../lib/labels'
import { FormDrawer } from './FormDrawer'
import { maxLength, required } from './form'
import { useSavePoint } from './queries'
import { pointCreateBody, pointFormValues, pointUpdateBody, type PointFormValues } from './schoolSetupForm'

const FIELDS = ['name', 'room', 'lineId', 'isPrimary']

interface PointDrawerProps {
  schoolId: number
  open: boolean
  /** The point being edited; none — a new one. */
  point?: MonitoringPointDetail
  /** Lines of the school the point may be bound to, the main one first. */
  lines: LineDetail[]
  onClose: () => void
}

/** New monitoring point of a school or a change of one (ТЗ п. 10): name, room, line, primary mark. */
export function PointDrawer({ schoolId, open, point, lines, onClose }: PointDrawerProps) {
  const [form] = Form.useForm<PointFormValues>()
  const [initial] = useState(() => pointFormValues(point, lines.find((line) => line.status === 'main')?.id))
  const save = useSavePoint(schoolId)
  const { open: notify } = useNotification()
  const lineOptions = lines.map((line) => ({
    value: line.id,
    label: `${LINE_STATUS_LABELS[line.status]} · ${line.providerName}`,
  }))

  const submit = (values: PointFormValues) => {
    const done = (saved: MonitoringPointDetail) => {
      notify?.({ type: 'success', message: point ? 'Точка изменена' : 'Точка добавлена', description: saved.name })
      onClose()
    }
    if (!point) return save.mutate({ body: pointCreateBody(values) }, { onSuccess: done })
    const body = pointUpdateBody(initial, values)
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: point.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={point ? 'Изменить точку мониторинга' : 'Новая точка мониторинга'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<PointFormValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item label="Название" name="name" rules={[required('Введите название точки'), maxLength(255)]}>
          <Input autoFocus />
        </Form.Item>
        <Form.Item
          label="Кабинет"
          name="room"
          extra="Агент при установке садится на точку, кабинет которой совпал с параметром ROOM."
          rules={[maxLength(255)]}
        >
          <Input autoComplete="off" />
        </Form.Item>
        <Form.Item
          label="Линия"
          name="lineId"
          extra="Замеры компьютеров точки относятся к этой линии."
          rules={[{ required: true, message: 'Выберите линию' }]}
        >
          <Select<number> placeholder="Выберите из списка" options={lineOptions} />
        </Form.Item>
        <Form.Item
          name="isPrimary"
          valuePropName="checked"
          extra="Главная точка у школы одна: признак снимется с прежней главной."
        >
          <Checkbox>Главная точка школы</Checkbox>
        </Form.Item>
      </Form>
    </FormDrawer>
  )
}
