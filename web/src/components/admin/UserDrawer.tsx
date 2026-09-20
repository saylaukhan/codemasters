import { useNotification } from '@refinedev/core'
import { Form, Input, Select } from 'antd'
import { useState } from 'react'

import type { UserDetail, UserRole } from '../../api/types'
import { ROLE_LABELS } from '../../lib/labels'
import { FormDrawer } from './FormDrawer'
import { maxLength, required } from './form'
import { useProviderOptions, useRegionOptions, useSaveUser, useSchoolOptions } from './queries'
import {
  PASSWORD_RULES,
  ROLE_SCOPE_FIELD,
  TELEGRAM_CHAT_ID_MAX_LENGTH,
  userCreateBody,
  userFormValues,
  userUpdateBody,
  type UserFormValues,
} from './users'

const FIELDS = ['email', 'fullName', 'role', 'regionId', 'providerId', 'schoolId', 'password', 'telegramChatId']

const ROLE_OPTIONS = (Object.keys(ROLE_LABELS) as UserRole[]).map((role) => ({ value: role, label: ROLE_LABELS[role] }))

interface UserDrawerProps {
  open: boolean
  /** The user being edited; none — a new one. */
  user?: UserDetail
  /** The user is the one signed in: his role stays, the API refuses to change it. */
  isSelf?: boolean
  onClose: () => void
}

/** New user or a change of one (ТЗ п. 16): the role and the district, provider or school it sees. */
export function UserDrawer({ open, user, isSelf = false, onClose }: UserDrawerProps) {
  const [form] = Form.useForm<UserFormValues>()
  const [search, setSearch] = useState('')
  const role = Form.useWatch('role', form) ?? user?.role
  const scopeField = role ? ROLE_SCOPE_FIELD[role] : null
  const regions = useRegionOptions()
  const providers = useProviderOptions()
  const schools = useSchoolOptions(search)
  const save = useSaveUser()
  const { open: notify } = useNotification()
  const initial = userFormValues(user)

  const submit = (values: UserFormValues) => {
    const done = (saved: UserDetail) => {
      notify?.({
        type: 'success',
        message: user ? 'Пользователь изменён' : 'Пользователь добавлен',
        description: saved.fullName,
      })
      onClose()
    }
    if (!user) return save.mutate({ body: userCreateBody(values) }, { onSuccess: done })
    const body = userUpdateBody(initial, values)
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: user.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={user ? 'Изменить пользователя' : 'Новый пользователь'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<UserFormValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item label="ФИО" name="fullName" rules={[required('Введите ФИО'), maxLength(255)]}>
          <Input autoFocus />
        </Form.Item>
        <Form.Item
          label="E-mail"
          name="email"
          extra="Логин для входа в панель."
          rules={[required('Введите e-mail'), { type: 'email', message: 'Введите корректный e-mail' }, maxLength(254)]}
        >
          <Input type="email" autoComplete="off" />
        </Form.Item>
        <Form.Item
          label="Роль"
          name="role"
          extra={isSelf ? 'Свою роль сменить нельзя: панель может остаться без администратора.' : undefined}
          rules={[{ required: true, message: 'Выберите роль' }]}
        >
          <Select<UserRole> placeholder="Выберите из списка" options={ROLE_OPTIONS} disabled={isSelf} />
        </Form.Item>
        {scopeField === 'regionId' && (
          <Form.Item
            label="Район или город"
            name="regionId"
            rules={[{ required: true, message: 'Выберите район или город' }]}
          >
            <Select<number>
              showSearch
              optionFilterProp="label"
              placeholder="Выберите из списка"
              options={regions.data}
              loading={regions.isPending}
            />
          </Form.Item>
        )}
        {scopeField === 'providerId' && (
          <Form.Item
            label="Поставщик"
            name="providerId"
            extra="Провайдер видит только свои линии и их школы."
            rules={[{ required: true, message: 'Выберите поставщика' }]}
          >
            <Select<number>
              showSearch
              optionFilterProp="label"
              placeholder="Выберите из списка"
              options={providers.data}
              loading={providers.isPending}
            />
          </Form.Item>
        )}
        {scopeField === 'schoolId' && (
          <Form.Item label="Школа" name="schoolId" rules={[{ required: true, message: 'Выберите школу' }]}>
            <Select<UserFormValues['schoolId']>
              showSearch
              labelInValue
              filterOption={false}
              placeholder="Поиск по School ID или названию"
              options={schools.data}
              loading={schools.isFetching}
              onSearch={setSearch}
            />
          </Form.Item>
        )}
        <Form.Item
          label="Telegram chat id"
          name="telegramChatId"
          extra="Чат пользователя с ботом уведомлений; пусто — уведомления в Telegram ему не отправляются."
          rules={[maxLength(TELEGRAM_CHAT_ID_MAX_LENGTH)]}
        >
          <Input inputMode="numeric" autoComplete="off" />
        </Form.Item>
        {!user && (
          <Form.Item
            label="Начальный пароль"
            name="password"
            extra="Не короче 8 символов; хранится только хэшем. Передайте его пользователю лично."
            rules={PASSWORD_RULES}
          >
            <Input.Password autoComplete="new-password" />
          </Form.Item>
        )}
      </Form>
    </FormDrawer>
  )
}
