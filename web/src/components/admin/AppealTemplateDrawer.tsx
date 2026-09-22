import { useNotification } from '@refinedev/core'
import { Checkbox, Form, Input, Segmented, Tag } from 'antd'
import { useState } from 'react'

import type { AppealKind, AppealTemplateDetail } from '../../api/types'
import { APPEAL_KIND_LABELS } from '../../lib/labels'
import styles from './Admin.module.css'
import {
  appealTemplateCreateBody,
  appealTemplateFormValues,
  appealTemplateUpdateBody,
  BODY_MAX_LENGTH,
  INSTRUCTIONS_MAX_LENGTH,
  placeholderMark,
  SUBJECT_MAX_LENGTH,
  type AppealTemplateFormValues,
} from './appealTemplates'
import { FormDrawer } from './FormDrawer'
import { maxLength, required } from './form'
import { useAppealPlaceholders, useSaveAppealTemplate } from './queries'

const FIELDS = ['name', 'kind', 'subject', 'body', 'aiInstructions', 'isDefault', 'isActive']

const KIND_OPTIONS = (['appeal', 'claim'] as const).map((value) => ({ value, label: APPEAL_KIND_LABELS[value] }))

// The body is a page of a letter and grows with it.
const BODY_ROWS = { minRows: 10, maxRows: 24 }
const INSTRUCTION_ROWS = { minRows: 2, maxRows: 6 }

interface AppealTemplateDrawerProps {
  open: boolean
  /** The template being edited; none — a new one. */
  template?: AppealTemplateDetail
  onClose: () => void
}

/**
 * Template of a letter to the provider (ТЗ п. 17, п. 20; ADR-011): the subject and the text with `{{…}}` the server
 * fills with the facts of the appeal, and the instructions the model gets. A click on a placeholder appends it to
 * the text. The next draft is written by the saved template; sent letters keep their text.
 */
export function AppealTemplateDrawer({ open, template, onClose }: AppealTemplateDrawerProps) {
  const [form] = Form.useForm<AppealTemplateFormValues>()
  const save = useSaveAppealTemplate()
  const placeholders = useAppealPlaceholders()
  const { open: notify } = useNotification()
  const [initial] = useState(() => appealTemplateFormValues(template))

  const append = (name: string) => {
    const body: string = form.getFieldValue('body') ?? ''
    form.setFieldValue('body', body + (body && !body.endsWith(' ') && !body.endsWith('\n') ? ' ' : '') + placeholderMark(name))
  }

  const submit = (values: AppealTemplateFormValues) => {
    const done = (saved: AppealTemplateDetail) => {
      notify?.({ type: 'success', message: template ? 'Шаблон изменён' : 'Шаблон добавлен', description: saved.name })
      onClose()
    }
    if (!template) return save.mutate({ body: appealTemplateCreateBody(values) }, { onSuccess: done })
    const body = appealTemplateUpdateBody(initial, values)
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: template.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={template ? 'Изменить шаблон письма' : 'Новый шаблон письма'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<AppealTemplateFormValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item label="Название" name="name" rules={[required('Введите название шаблона'), maxLength(255)]}>
          <Input autoFocus />
        </Form.Item>
        <Form.Item
          label="Вид письма"
          name="kind"
          extra="Обращение просит устранить нарушение; претензия ссылается на договор и выдвигает требования."
        >
          <Segmented<AppealKind> block options={KIND_OPTIONS} />
        </Form.Item>
        <Form.Item
          label="Тема письма"
          name="subject"
          rules={[required('Введите тему письма'), maxLength(SUBJECT_MAX_LENGTH)]}
        >
          <Input autoComplete="off" />
        </Form.Item>
        <Form.Item
          label="Текст письма"
          name="body"
          extra="Markdown: абзацы, **жирный**, списки. Сервер заполняет подстановки фактами обращения, модель пишет письмо по заполненному шаблону; без модели редактор открывается с ним."
          rules={[required('Введите текст письма'), maxLength(BODY_MAX_LENGTH)]}
        >
          <Input.TextArea className={styles.code} autoSize={BODY_ROWS} />
        </Form.Item>
        <div className={styles.placeholders} aria-label="Подстановки шаблона">
          {placeholders.data?.map((placeholder) => (
            <Tag
              key={placeholder.name}
              className={styles.placeholder}
              title={placeholder.description}
              onClick={() => append(placeholder.name)}
            >
              {placeholderMark(placeholder.name)}
            </Tag>
          ))}
        </div>
        <Form.Item
          label="Указания модели"
          name="aiInstructions"
          extra="Что учесть сверх фактов: тон, ссылки на пункты договора, требования. Необязательно."
          rules={[maxLength(INSTRUCTIONS_MAX_LENGTH)]}
        >
          <Input.TextArea autoSize={INSTRUCTION_ROWS} />
        </Form.Item>
        <Form.Item
          name="isDefault"
          valuePropName="checked"
          extra="Черновик без выбора шаблона пишется по нему; шаблон по умолчанию один, признак переходит с прежнего."
        >
          <Checkbox>Шаблон по умолчанию</Checkbox>
        </Form.Item>
        {template && (
          <Form.Item
            name="isActive"
            valuePropName="checked"
            extra="Отключённый шаблон не предлагается в редакторе; отправленные по нему письма остаются."
          >
            <Checkbox>Шаблон действует</Checkbox>
          </Form.Item>
        )}
      </Form>
    </FormDrawer>
  )
}
