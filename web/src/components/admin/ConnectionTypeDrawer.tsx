import { useNotification } from '@refinedev/core'
import { Form, Input } from 'antd'

import type { ConnectionTypeCreate, ConnectionTypeDetail } from '../../api/types'
import styles from './Admin.module.css'
import { FormDrawer } from './FormDrawer'
import { changedFields, maxLength, required } from './form'
import { useSaveConnectionType } from './queries'

type ConnectionTypeValues = ConnectionTypeCreate

const FIELDS = ['code', 'name']

const bodyOf = (values: ConnectionTypeValues): ConnectionTypeCreate => ({
  code: values.code.trim(),
  name: values.name.trim(),
})

interface ConnectionTypeDrawerProps {
  open: boolean
  /** The type being edited; none — a new one. */
  connectionType?: ConnectionTypeDetail
  onClose: () => void
}

/** New connection type or a change of one: a permanent code and the name shown in the panel. */
export function ConnectionTypeDrawer({ open, connectionType, onClose }: ConnectionTypeDrawerProps) {
  const [form] = Form.useForm<ConnectionTypeValues>()
  const save = useSaveConnectionType()
  const { open: notify } = useNotification()
  const initial: ConnectionTypeValues = { code: connectionType?.code ?? '', name: connectionType?.name ?? '' }

  const submit = (values: ConnectionTypeValues) => {
    const done = (saved: ConnectionTypeDetail) => {
      notify?.({
        type: 'success',
        message: connectionType ? 'Тип подключения изменён' : 'Тип подключения добавлен',
        description: saved.name,
      })
      onClose()
    }
    if (!connectionType) return save.mutate({ body: bodyOf(values) }, { onSuccess: done })
    const body = changedFields(bodyOf(initial), bodyOf(values))
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: connectionType.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={connectionType ? 'Изменить тип подключения' : 'Новый тип подключения'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<ConnectionTypeValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item
          label="Код"
          name="code"
          normalize={(value: string) => value.toLowerCase()}
          extra="Постоянный код: строчная латиница, цифры и «_», начинается с буквы."
          rules={[
            required('Введите код'),
            maxLength(32),
            { pattern: /^[a-z][a-z0-9_]*$/, message: 'Строчная латиница, цифры и «_», первая — буква' },
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
