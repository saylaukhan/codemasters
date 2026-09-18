import { useNotification } from '@refinedev/core'
import { Form, Input } from 'antd'

import type { RegionCreate, RegionDetail, RegionListItem } from '../../api/types'
import styles from './Admin.module.css'
import { FormDrawer } from './FormDrawer'
import { changedFields, maxLength, required } from './form'
import { useSaveRegion } from './queries'

type RegionValues = RegionCreate

const FIELDS = ['code', 'name']

const bodyOf = (values: RegionValues): RegionCreate => ({ code: values.code.trim(), name: values.name.trim() })

interface RegionDrawerProps {
  open: boolean
  /** The district or city being edited; none — a new one. */
  region?: RegionListItem
  onClose: () => void
}

/** New district or city or a change of one; the boundary comes from GeoJSON and is not edited here. */
export function RegionDrawer({ open, region, onClose }: RegionDrawerProps) {
  const [form] = Form.useForm<RegionValues>()
  const save = useSaveRegion()
  const { open: notify } = useNotification()
  const initial: RegionValues = { code: region?.code ?? '', name: region?.name ?? '' }

  const submit = (values: RegionValues) => {
    const done = (saved: RegionDetail) => {
      notify?.({ type: 'success', message: region ? 'Район изменён' : 'Район добавлен', description: saved.name })
      onClose()
    }
    if (!region) return save.mutate({ body: bodyOf(values) }, { onSuccess: done })
    const body = changedFields(bodyOf(initial), bodyOf(values))
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: region.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={region ? 'Изменить район или город' : 'Новый район или город'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<RegionValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item
          label="Код"
          name="code"
          normalize={(value: string) => value.toUpperCase()}
          extra={
            region
              ? 'Латинские заглавные и цифры. Смена кода не меняет School ID уже созданных школ.'
              : 'Латинские заглавные и цифры, часть School ID VKO-<код>-<номер>.'
          }
          rules={[
            required('Введите код'),
            maxLength(16),
            { pattern: /^[A-Z0-9]+$/, message: 'Только латинские заглавные буквы и цифры' },
          ]}
        >
          <Input className={styles.code} autoComplete="off" autoFocus />
        </Form.Item>
        <Form.Item label="Название" name="name" rules={[required('Введите название'), maxLength(255)]}>
          <Input />
        </Form.Item>
      </Form>
    </FormDrawer>
  )
}
