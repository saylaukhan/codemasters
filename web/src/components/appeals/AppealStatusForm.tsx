import { useNotification } from '@refinedev/core'
import { Form, Input, Select } from 'antd'

import { ApiError } from '../../api/client'
import type { IncidentStatus } from '../../api/types'
import { APPEAL_FORM_LABELS, APPEAL_LABELS, APPEAL_STATUS_LABELS } from '../../lib/labels'
import { formErrors, maxLength } from '../admin/form'
import { commentRequired } from '../incidents/transitions'
import { Button } from '../ui/Button'
import styles from './Appeal.module.css'
import { COMMENT_MAX_LENGTH } from './appeals'
import { useUpdateAppeal } from './queries'

// Fields of the form the errors of the API may point at; 409 and 403 have none and go to a notification.
const FIELDS = ['status', 'comment']

interface StatusFormValues {
  status?: IncidentStatus
  comment: string
}

interface AppealStatusFormProps {
  appealId: number
  /** Statuses the user may choose, from the table of transitions (incidents/transitions.ts). */
  targets: IncidentStatus[]
}

/**
 * Status change and comments of the appeal card (ТЗ п. 17, DESIGN.md §3.17): Select + comment + «Сохранить», the
 * Action of the screen. Either of the two is enough — a comment alone is an entry of `appeal_events` too; for
 * «Закрыт» the comment is required. The API checks the transition and the role again (409, 403).
 */
export function AppealStatusForm({ appealId, targets }: AppealStatusFormProps) {
  const [form] = Form.useForm<StatusFormValues>()
  const update = useUpdateAppeal(appealId)
  const { open: notify } = useNotification()
  const status = Form.useWatch('status', form)
  // Nothing to send without either of them, and «Закрыт» is not closed without a reason.
  const needsComment = status === undefined || commentRequired(status)

  const submit = ({ status: to, comment }: StatusFormValues) =>
    update.mutate(
      { status: to, comment: comment.trim() || null },
      {
        onSuccess: (saved) => {
          notify?.({
            type: 'success',
            message: APPEAL_LABELS.statusChange,
            description: `${saved.number} · ${APPEAL_STATUS_LABELS[saved.status]}`,
          })
          form.resetFields()
        },
        onError: (error) => {
          const placed = formErrors(error, FIELDS)
          if (placed.fields.length > 0) {
            form.setFields(placed.fields.map(({ name, errors }) => ({ name: name as keyof StatusFormValues, errors })))
          }
          if (placed.alert) {
            notify?.({
              type: 'error',
              message: 'Изменение не сохранено',
              description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
            })
          }
        },
      },
    )

  return (
    <Form<StatusFormValues>
      form={form}
      layout="vertical"
      initialValues={{ comment: '' }}
      onFinish={submit}
      requiredMark={false}
    >
      <div className={styles.fields}>
        <Form.Item label={APPEAL_FORM_LABELS.status} name="status">
          <Select<IncidentStatus>
            allowClear
            placeholder="Оставить статус без изменения"
            options={targets.map((value) => ({ value, label: APPEAL_STATUS_LABELS[value] }))}
          />
        </Form.Item>
        <Form.Item
          label={needsComment ? APPEAL_FORM_LABELS.requiredComment : APPEAL_FORM_LABELS.comment}
          name="comment"
          dependencies={['status']}
          rules={[
            { required: needsComment, whitespace: true, message: 'Напишите комментарий' },
            maxLength(COMMENT_MAX_LENGTH),
          ]}
        >
          <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
        </Form.Item>
      </div>
      <div className={styles.formActions}>
        <Button kind="action" htmlType="submit" loading={update.isPending}>
          Сохранить
        </Button>
      </div>
    </Form>
  )
}
