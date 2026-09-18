import { useNotification } from '@refinedev/core'
import { Form, Input } from 'antd'

import type { UserDetail } from '../../api/types'
import { FormDrawer } from './FormDrawer'
import { useSaveUser } from './queries'
import { PASSWORD_RULES } from './users'

interface PasswordValues {
  password: string
}

const FIELDS = ['password']

interface PasswordDrawerProps {
  user: UserDetail
  open: boolean
  onClose: () => void
}

/** Password reset by the administrator (ТЗ п. 16): every session of the user ends, the new password is a hash only. */
export function PasswordDrawer({ user, open, onClose }: PasswordDrawerProps) {
  const [form] = Form.useForm<PasswordValues>()
  const save = useSaveUser()
  const { open: notify } = useNotification()

  const submit = ({ password }: PasswordValues) =>
    save.mutate(
      { id: user.id, body: { password } },
      {
        onSuccess: () => {
          notify?.({ type: 'success', message: 'Пароль сброшен', description: user.fullName })
          onClose()
        },
      },
    )

  return (
    <FormDrawer
      title={`Сбросить пароль: ${user.fullName}`}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<PasswordValues> form={form} layout="vertical" onFinish={submit}>
        <Form.Item
          label="Новый пароль"
          name="password"
          extra="Все сессии пользователя завершатся. Передайте новый пароль пользователю лично."
          rules={PASSWORD_RULES}
        >
          <Input.Password autoFocus autoComplete="new-password" />
        </Form.Item>
      </Form>
    </FormDrawer>
  )
}
