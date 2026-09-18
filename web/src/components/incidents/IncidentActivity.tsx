import { useNotification } from '@refinedev/core'
import { Form, Input, Timeline } from 'antd'

import { ApiError } from '../../api/client'
import type { IncidentEventDetail } from '../../api/types'
import { formatDateTime } from '../../lib/format'
import { maxLength, required } from '../admin/form'
import { Button } from '../ui/Button'
import styles from './Incident.module.css'
import { COMMENT_MAX_LENGTH, eventAuthor, eventCaption } from './incidents'
import { useCommentIncident } from './queries'

interface IncidentActivityProps {
  incidentId: number
  /** The whole history, oldest first (`incident_events`). */
  events: IncidentEventDetail[]
  /** The comment field at the end, for a role with `incidents:update`. */
  canComment: boolean
}

/** Activity feed of the card (DESIGN.md §3.17): dots of 8px, the author, the time, the action; a comment at the end. */
export function IncidentActivity({ incidentId, events, canComment }: IncidentActivityProps) {
  const [form] = Form.useForm<{ comment: string }>()
  const comment = useCommentIncident(incidentId)
  const { open: notify } = useNotification()

  const submit = (values: { comment: string }) =>
    comment.mutate(values.comment.trim(), {
      onSuccess: () => form.resetFields(),
      onError: (error) =>
        notify?.({
          type: 'error',
          message: 'Комментарий не добавлен',
          description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
        }),
    })

  return (
    <>
      <Timeline
        items={events.map((event) => ({
          key: event.id,
          dot: <span className={styles.dot} aria-hidden />,
          children: (
            <>
              <div className={styles.eventHead}>
                <span className={styles.author}>{eventAuthor(event)}</span>
                <span className={styles.time}>{formatDateTime(event.createdAt)}</span>
              </div>
              <p className={styles.eventText}>{eventCaption(event)}</p>
              {event.comment && <p className={styles.comment}>{event.comment}</p>}
            </>
          ),
        }))}
      />
      {canComment && (
        <Form<{ comment: string }>
          form={form}
          layout="vertical"
          initialValues={{ comment: '' }}
          onFinish={submit}
          requiredMark={false}
        >
          <Form.Item
            label="Комментарий"
            name="comment"
            rules={[required('Напишите комментарий'), maxLength(COMMENT_MAX_LENGTH)]}
          >
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
          </Form.Item>
          <div className={styles.formActions}>
            <Button kind="outlined" htmlType="submit" loading={comment.isPending}>
              Добавить комментарий
            </Button>
          </div>
        </Form>
      )}
    </>
  )
}
