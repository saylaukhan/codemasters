import { useNotification } from '@refinedev/core'
import { Form, Input, Select } from 'antd'

import { ApiError } from '../../api/client'
import type { IncidentStatus } from '../../api/types'
import { INCIDENT_STATUS_LABELS } from '../../lib/labels'
import { formErrors, maxLength } from '../admin/form'
import { Button } from '../ui/Button'
import styles from './Incident.module.css'
import { COMMENT_MAX_LENGTH } from './incidents'
import { useChangeIncidentStatus } from './queries'
import { commentRequired } from './transitions'

// Fields of the form the errors of the API may point at; 409 and 403 have none and go to a notification.
const FIELDS = ['status', 'comment']

interface StatusFormValues {
  status?: IncidentStatus
  comment: string
}

interface IncidentStatusFormProps {
  incidentId: number
  /** Statuses the user may choose, from the table of transitions (transitions.ts). */
  targets: IncidentStatus[]
}

/**
 * Status change of the card (DESIGN.md §3.17): Select + comment + «Сохранить», the Action of the screen. The comment
 * is optional, for «Закрыт» it is required; the API checks the transition and the role again (409, 403).
 */
export function IncidentStatusForm({ incidentId, targets }: IncidentStatusFormProps) {
  const [form] = Form.useForm<StatusFormValues>()
  const change = useChangeIncidentStatus(incidentId)
  const { open: notify } = useNotification()
  const status = Form.useWatch('status', form)

  const submit = ({ status: to, comment }: StatusFormValues) =>
    change.mutate(
      { status: to as IncidentStatus, comment: comment.trim() || null },
      {
        onSuccess: (saved) => {
          notify?.({
            type: 'success',
            message: 'Статус изменён',
            description: `${saved.number} · ${INCIDENT_STATUS_LABELS[saved.status]}`,
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
              message: 'Статус не изменён',
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
        <Form.Item label="Новый статус" name="status" rules={[{ required: true, message: 'Выберите статус' }]}>
          <Select<IncidentStatus>
            placeholder="Выберите из списка"
            options={targets.map((value) => ({ value, label: INCIDENT_STATUS_LABELS[value] }))}
          />
        </Form.Item>
        <Form.Item
          label={commentRequired(status) ? 'Комментарий, обязателен для закрытия' : 'Комментарий'}
          name="comment"
          dependencies={['status']}
          rules={[
            {
              required: commentRequired(status),
              whitespace: true,
              message: 'Напишите, чем закончился инцидент',
            },
            maxLength(COMMENT_MAX_LENGTH),
          ]}
        >
          <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
        </Form.Item>
      </div>
      <div className={styles.formActions}>
        <Button kind="action" htmlType="submit" loading={change.isPending}>
          Сохранить
        </Button>
      </div>
    </Form>
  )
}
