import { useNotification } from '@refinedev/core'
import { Form, Select } from 'antd'
import { useState } from 'react'

import type { DeviceDetail } from '../../api/types'
import { useSchoolPoints } from '../schools/queries'
import { deviceName, pointOption, schoolOption } from './devices'
import { FormDrawer } from './FormDrawer'
import { useRebindDevice, useSchoolOptions } from './queries'

interface RebindValues {
  /** With its label: a school picked from one search stays named when the search changes. */
  school: { value: number; label: string }
  monitoringPointId?: number
}

// Only the point is checked by the API: an unknown one is a 422 on `monitoring_point_id`.
const FIELDS = ['monitoringPointId']

interface RebindDrawerProps {
  device: DeviceDetail
  open: boolean
  onClose: () => void
}

/**
 * Another monitoring point for a computer, of its school or of another one (ТЗ п. 20): the school and the line of
 * new measurements follow the point, the measurements already taken keep theirs (ADR-005).
 */
export function RebindDrawer({ device, open, onClose }: RebindDrawerProps) {
  const [form] = Form.useForm<RebindValues>()
  const [search, setSearch] = useState('')
  const schoolId = Form.useWatch('school', form)?.value ?? device.schoolId
  const schools = useSchoolOptions(search)
  const points = useSchoolPoints(schoolId)
  const rebind = useRebindDevice(device.id)
  const { open: notify } = useNotification()

  const submit = ({ monitoringPointId }: RebindValues) => {
    if (monitoringPointId === undefined || monitoringPointId === device.monitoringPointId) return onClose()
    rebind.mutate(monitoringPointId, {
      onSuccess: (saved) => {
        notify?.({ type: 'success', message: 'Компьютер перепривязан', description: deviceName(saved) })
        onClose()
      },
    })
  }

  return (
    <FormDrawer
      title={`Перепривязать ${deviceName(device)}`}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={rebind.isPending}
      error={rebind.error}
    >
      <Form<RebindValues>
        form={form}
        layout="vertical"
        initialValues={{
          school: schoolOption({ id: device.schoolId, schoolCode: device.schoolCode, fullName: device.schoolName }),
          monitoringPointId: device.monitoringPointId,
        }}
        onValuesChange={(changed: Partial<RebindValues>) => {
          if ('school' in changed) form.setFieldValue('monitoringPointId', undefined)
        }}
        onFinish={submit}
      >
        <Form.Item label="Школа" name="school" rules={[{ required: true, message: 'Выберите школу' }]}>
          <Select<RebindValues['school']>
            showSearch
            labelInValue
            filterOption={false}
            placeholder="Поиск по School ID или названию"
            options={schools.data}
            loading={schools.isFetching}
            onSearch={setSearch}
          />
        </Form.Item>
        <Form.Item
          label="Точка мониторинга"
          name="monitoringPointId"
          extra="Новые замеры компьютера пойдут на линию этой точки; прежние остаются со своей линией."
          rules={[{ required: true, message: 'Выберите точку мониторинга' }]}
        >
          <Select<number>
            placeholder={points.data?.items.length === 0 ? 'У школы нет точек мониторинга' : 'Выберите из списка'}
            options={points.data?.items.map(pointOption)}
            loading={points.isPending}
            disabled={points.data?.items.length === 0}
          />
        </Form.Item>
      </Form>
    </FormDrawer>
  )
}
