import { Checkbox, Form, TimePicker } from 'antd'

import { WEEKDAY_LABELS, WEEKDAY_ORDER } from '../../lib/labels'
import type { TimeRange } from './hours'

const WEEKDAY_OPTIONS = WEEKDAY_ORDER.map((day) => ({ value: day, label: WEEKDAY_LABELS[day] }))

interface WorkingHoursFieldsProps {
  /** Path of the `HoursValues` in the form, e.g. `['workingHours']`. */
  name: string[]
  extra?: string
}

/** Days and hours of a school (ADR-014): downtime and «Нет соединения» count only inside them. */
export function WorkingHoursFields({ name, extra }: WorkingHoursFieldsProps) {
  return (
    <>
      <Form.Item
        label="Рабочие дни"
        name={[...name, 'weekdays']}
        rules={[{ required: true, type: 'array', min: 1, message: 'Выберите хотя бы один день' }]}
      >
        <Checkbox.Group options={WEEKDAY_OPTIONS} />
      </Form.Item>
      <Form.Item
        label="Рабочие часы, Asia/Almaty"
        name={[...name, 'hours']}
        extra={extra}
        rules={[
          { required: true, message: 'Укажите начало и конец' },
          {
            validator: (_, value: TimeRange | undefined) =>
              value && !value[1].isAfter(value[0])
                ? Promise.reject(new Error('Конец должен быть позже начала'))
                : Promise.resolve(),
          },
        ]}
      >
        <TimePicker.RangePicker format="HH:mm" minuteStep={5} allowClear={false} />
      </Form.Item>
    </>
  )
}
