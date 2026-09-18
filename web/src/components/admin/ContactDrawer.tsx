import { useNotification } from '@refinedev/core'
import { Form, Input } from 'antd'
import { useState } from 'react'

import type { SchoolContactDetail } from '../../api/types'
import { FormDrawer } from './FormDrawer'
import { maxLength, required } from './form'
import { useSaveContact } from './queries'
import { contactCreateBody, contactFormValues, contactUpdateBody, type ContactFormValues } from './schoolSetupForm'

const FIELDS = ['fullName', 'position', 'phone', 'email', 'providerSupportContact']

interface ContactDrawerProps {
  schoolId: number
  open: boolean
  /** The contact being edited; none — a new one. */
  contact?: SchoolContactDetail
  onClose: () => void
}

/** Responsible person of a school (ТЗ п. 15); the date of the change is set by the server. */
export function ContactDrawer({ schoolId, open, contact, onClose }: ContactDrawerProps) {
  const [form] = Form.useForm<ContactFormValues>()
  const [initial] = useState(() => contactFormValues(contact))
  const save = useSaveContact(schoolId)
  const { open: notify } = useNotification()

  const submit = (values: ContactFormValues) => {
    const done = (saved: SchoolContactDetail) => {
      notify?.({ type: 'success', message: contact ? 'Контакт изменён' : 'Контакт добавлен', description: saved.fullName })
      onClose()
    }
    if (!contact) return save.mutate({ body: contactCreateBody(values) }, { onSuccess: done })
    const body = contactUpdateBody(initial, values)
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: contact.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={contact ? 'Изменить контакт' : 'Новый контакт'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<ContactFormValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item label="ФИО" name="fullName" rules={[required('Введите ФИО ответственного'), maxLength(255)]}>
          <Input autoFocus autoComplete="off" />
        </Form.Item>
        <Form.Item label="Должность" name="position" rules={[maxLength(255)]}>
          <Input autoComplete="off" />
        </Form.Item>
        <Form.Item label="Телефон" name="phone" rules={[maxLength(32)]}>
          <Input type="tel" autoComplete="off" placeholder="+7 700 000 00 00" />
        </Form.Item>
        <Form.Item
          label="Email"
          name="email"
          rules={[{ type: 'email', message: 'Введите корректный e-mail' }, maxLength(254)]}
        >
          <Input type="email" autoComplete="off" />
        </Form.Item>
        <Form.Item label="Техподдержка поставщика" name="providerSupportContact" rules={[maxLength(500)]}>
          <Input.TextArea autoSize={{ minRows: 1, maxRows: 3 }} />
        </Form.Item>
      </Form>
    </FormDrawer>
  )
}
