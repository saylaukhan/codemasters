import { useNotification } from '@refinedev/core'
import { DatePicker, Form, Input, InputNumber, Segmented, Select } from 'antd'
import { useState } from 'react'

import type { LineDetail, LineStatus } from '../../api/types'
import { LINE_STATUS_LABELS } from '../../lib/labels'
import styles from './Admin.module.css'
import { FormDrawer } from './FormDrawer'
import { maxLength } from './form'
import { useConnectionTypeOptions, useProviderOptions, useSaveLine } from './queries'
import { cidrList, lineCreateBody, lineFormValues, lineUpdateBody, type LineFormValues } from './schoolSetupForm'

const FIELDS = [
  'providerId',
  'connectionTypeId',
  'status',
  'lineIdentifier',
  'contractDownMbps',
  'contractUpMbps',
  'contractNumber',
  'contractDate',
  'ipRanges',
]

const STATUS_OPTIONS = (Object.keys(LINE_STATUS_LABELS) as LineStatus[]).map((value) => ({
  value,
  label: LINE_STATUS_LABELS[value],
}))

interface LineDrawerProps {
  schoolId: number
  open: boolean
  /** The line being edited; none — a new one. */
  line?: LineDetail
  /** Status of a new line: main when the school has none yet. */
  newStatus: LineStatus
  onClose: () => void
}

/** New line of a school or a change of one (ТЗ п. 10, п. 14): provider, type, status, contract, IP ranges. */
export function LineDrawer({ schoolId, open, line, newStatus, onClose }: LineDrawerProps) {
  const [form] = Form.useForm<LineFormValues>()
  const [initial] = useState(() => lineFormValues(line, newStatus))
  const providers = useProviderOptions()
  const types = useConnectionTypeOptions()
  const save = useSaveLine(schoolId)
  const { open: notify } = useNotification()

  const submit = (values: LineFormValues) => {
    const done = (saved: LineDetail) => {
      notify?.({
        type: 'success',
        message: line ? 'Линия изменена' : 'Линия добавлена',
        description: `${LINE_STATUS_LABELS[saved.status]} · ${saved.providerName}`,
      })
      onClose()
    }
    if (!line) return save.mutate({ body: lineCreateBody(values) }, { onSuccess: done })
    const body = lineUpdateBody(initial, values)
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: line.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={line ? 'Изменить линию' : 'Новая линия'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<LineFormValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item
          label="Статус"
          name="status"
          extra="Основная линия у школы одна. Отключённая линия сохраняет историю замеров."
        >
          <Segmented<LineStatus> block options={STATUS_OPTIONS} />
        </Form.Item>
        <Form.Item label="Поставщик" name="providerId" rules={[{ required: true, message: 'Выберите поставщика' }]}>
          <Select<number>
            placeholder="Выберите из списка"
            options={providers.data}
            loading={providers.isPending}
            notFoundContent={providers.isError ? 'Список не загрузился, откройте форму ещё раз' : undefined}
            optionFilterProp="label"
            showSearch
          />
        </Form.Item>
        <Form.Item label="Тип подключения" name="connectionTypeId">
          <Select<number>
            placeholder="Не указан"
            options={types.data}
            loading={types.isPending}
            optionFilterProp="label"
            allowClear
            showSearch
          />
        </Form.Item>
        <Form.Item label="Идентификатор линии у поставщика" name="lineIdentifier" rules={[maxLength(255)]}>
          <Input className={styles.code} autoComplete="off" />
        </Form.Item>
        <div className={styles.coordinates}>
          <Form.Item label="Договор Download, Мбит/с" name="contractDownMbps">
            <InputNumber<number> className={styles.number} min={0.1} step={1} />
          </Form.Item>
          <Form.Item label="Договор Upload, Мбит/с" name="contractUpMbps">
            <InputNumber<number> className={styles.number} min={0.1} step={1} />
          </Form.Item>
        </div>
        <div className={styles.coordinates}>
          <Form.Item label="Номер договора" name="contractNumber" rules={[maxLength(255)]}>
            <Input autoComplete="off" />
          </Form.Item>
          <Form.Item label="Дата договора" name="contractDate">
            <DatePicker className={styles.number} format="DD.MM.YYYY" placeholder="ДД.ММ.ГГГГ" />
          </Form.Item>
        </div>
        <Form.Item
          label="Внешние IP-диапазоны"
          name="ipRanges"
          extra="CIDR через запятую, например 203.0.113.0/24: по ним замер относится к линии."
          rules={[cidrList]}
        >
          <Input.TextArea className={styles.code} autoSize={{ minRows: 1, maxRows: 4 }} />
        </Form.Item>
      </Form>
    </FormDrawer>
  )
}
