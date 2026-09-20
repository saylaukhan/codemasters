import { useGetIdentity, useNotification } from '@refinedev/core'
import { Dropdown, Form, Input, Modal } from 'antd'
import { MoveRight } from 'lucide-react'
import { useState, type DragEvent, type ReactNode } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../../api/client'
import type { CurrentUser, IncidentListItem, IncidentStatus } from '../../api/types'
import { incidentCardPath } from '../../app/sections'
import { INCIDENT_STATUS_LABELS } from '../../lib/labels'
import { maxLength } from '../admin/form'
import { Button } from '../ui/Button'
import { COMMENT_MAX_LENGTH, durationCaption } from './incidents'
import { groupByStatus } from './kanban'
import styles from './Kanban.module.css'
import { useMoveIncident } from './queries'
import { allowedTargets, canMove, commentRequired } from './transitions'

const MODAL_WIDTH = 560

interface IncidentCardProps {
  item: IncidentListItem
  /** Statuses the user may move the incident to; none — the card does not move (transitions.ts). */
  targets: IncidentStatus[]
  dragged: boolean
  onDragStart: () => void
  onDragEnd: () => void
  onMove: (to: IncidentStatus) => void
}

/** Card of the board (DESIGN.md §3.18): the number, the school, the duration and the provider. */
function IncidentCard({ item, targets, dragged, onDragStart, onDragEnd, onMove }: IncidentCardProps) {
  const movable = targets.length > 0
  return (
    <li
      className={dragged ? `${styles.card} ${styles.dragged}` : styles.card}
      draggable={movable}
      onDragStart={(event: DragEvent<HTMLLIElement>) => {
        // Firefox starts a drag only when the data is set; the board itself moves by its own state.
        event.dataTransfer.setData('text/plain', item.number)
        event.dataTransfer.effectAllowed = 'move'
        onDragStart()
      }}
      onDragEnd={onDragEnd}
    >
      <div className={styles.cardHead}>
        <Link className={styles.cardNumber} to={incidentCardPath(item.id)}>
          {item.number}
        </Link>
        {movable && (
          <Dropdown
            trigger={['click']}
            menu={{
              items: targets.map((to) => ({ key: to, label: INCIDENT_STATUS_LABELS[to] })),
              onClick: ({ key }) => onMove(key as IncidentStatus),
            }}
          >
            {/* The same move from the keyboard: dragging is not reachable with Tab (DESIGN.md §9.2). */}
            <Button kind="flat" size="small" icon={<MoveRight size={16} />} tooltip="Перенести в другой статус" />
          </Dropdown>
        )}
      </div>
      <span className={styles.cardSchool}>{item.schoolName}</span>
      <span className={styles.cardMeta}>
        {durationCaption(item)} · {item.providerName}
      </span>
    </li>
  )
}

interface IncidentBoardProps {
  items: IncidentListItem[]
  /** Incidents of the filter on the server: more than the board holds is said under it. */
  total: number
  /** Shown instead of the empty columns when the filter found nothing. */
  empty: ReactNode
}

/**
 * Kanban of incidents (ТЗ п. 19, DESIGN.md §3.18): six columns in the fixed order, a card moves by dragging or by
 * its menu. The target column is offered only when the table of transitions and the role allow it (T-41); the API
 * checks the move again and a comment is required to close (409, 403, 422).
 */
export function IncidentBoard({ items, total, empty }: IncidentBoardProps) {
  const { data: user } = useGetIdentity<CurrentUser>()
  const [dragged, setDragged] = useState<IncidentListItem | null>(null)
  const [closing, setClosing] = useState<IncidentListItem | null>(null)
  const [form] = Form.useForm<{ comment: string }>()
  const move = useMoveIncident()
  const { open: notify } = useNotification()

  const change = (incident: IncidentListItem, to: IncidentStatus, comment: string | null) =>
    move.mutate(
      { incidentId: incident.id, status: to, comment },
      {
        onSuccess: (saved) => {
          setClosing(null)
          form.resetFields()
          notify?.({
            type: 'success',
            message: 'Статус изменён',
            description: `${saved.number} · ${INCIDENT_STATUS_LABELS[saved.status]}`,
          })
        },
        onError: (error) =>
          notify?.({
            type: 'error',
            message: 'Статус не изменён',
            description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
          }),
      },
    )

  // Closing needs a comment (DESIGN.md §3.17): the card waits in the dialog instead of going straight to the API.
  const request = (incident: IncidentListItem, to: IncidentStatus) =>
    commentRequired(to) ? setClosing(incident) : change(incident, to, null)

  const drop = (to: IncidentStatus) => {
    if (dragged && canMove(dragged.status, to, user)) request(dragged, to)
    setDragged(null)
  }

  const cancel = () => {
    setClosing(null)
    form.resetFields()
  }

  if (total === 0) return <>{empty}</>

  return (
    <>
      <div className={styles.board}>
        {groupByStatus(items).map(({ status, items: cards }) => {
          const droppable = dragged === null ? undefined : canMove(dragged.status, status, user)
          return (
            <section
              key={status}
              className={styles.column}
              aria-label={INCIDENT_STATUS_LABELS[status]}
              data-droppable={droppable === undefined ? undefined : String(droppable)}
              onDragOver={(event) => {
                if (droppable) event.preventDefault()
              }}
              onDrop={() => drop(status)}
            >
              <header className={styles.columnHead}>
                <span>{INCIDENT_STATUS_LABELS[status]}</span>
                <span className={styles.count}>{cards.length}</span>
              </header>
              <ul className={styles.cards}>
                {cards.map((item) => (
                  <IncidentCard
                    key={item.id}
                    item={item}
                    targets={allowedTargets(item.status, user)}
                    dragged={dragged?.id === item.id}
                    onDragStart={() => setDragged(item)}
                    onDragEnd={() => setDragged(null)}
                    onMove={(to) => request(item, to)}
                  />
                ))}
              </ul>
            </section>
          )
        })}
      </div>
      {items.length < total && (
        <p className={styles.hint}>
          На доске первые {items.length} инцидентов из {total}: уточните фильтры или откройте список.
        </p>
      )}
      <Modal
        title="Закрыть инцидент"
        open={closing !== null}
        width={MODAL_WIDTH}
        maskClosable={false}
        onCancel={cancel}
        footer={
          <>
            <Button kind="flat" onClick={cancel}>
              Отмена
            </Button>
            <Button kind="action" loading={move.isPending} onClick={() => form.submit()}>
              Закрыть инцидент
            </Button>
          </>
        }
      >
        <Form<{ comment: string }>
          form={form}
          layout="vertical"
          initialValues={{ comment: '' }}
          requiredMark={false}
          onFinish={({ comment }) => closing && change(closing, 'closed', comment.trim())}
        >
          <Form.Item
            label={`${closing?.number ?? ''} · комментарий, обязателен для закрытия`}
            name="comment"
            rules={[
              { required: true, whitespace: true, message: 'Напишите, чем закончился инцидент' },
              maxLength(COMMENT_MAX_LENGTH),
            ]}
          >
            <Input.TextArea autoSize={{ minRows: 2, maxRows: 6 }} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
