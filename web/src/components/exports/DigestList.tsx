import { useNotification } from '@refinedev/core'
import { Popconfirm } from 'antd'
import { Plus } from 'lucide-react'

import type { DigestSettingsDetail } from '../../api/types'
import { formatDateTime } from '../../lib/format'
import {
  DIGEST_CHANNEL_LABELS,
  DIGEST_LABELS,
  DIGEST_SCOPE_LABELS,
  DIGEST_RESULT_LABELS,
  DIGEST_WEEKDAY_LABELS,
} from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import styles from '../admin/Admin.module.css'
import { AdminTable } from '../admin/AdminTable'
import { useAdminListView } from '../admin/useAdminListView'
import { useDrawer } from '../admin/useDrawer'
import { Button } from '../ui/Button'
import type { ResponsiveColumn } from '../ui/ResponsiveTable'
import { DigestDrawer } from './DigestDrawer'
import { useDeleteDigest, useDigestPreview, useDigests, useSendDigest } from './digestQueries'
import listStyles from './Exports.module.css'

/** Куда уходит выпуск: адреса почты и чат Telegram, каждый канал — по желанию. */
const channels = (digest: DigestSettingsDetail): string => {
  const used = [
    digest.recipients.length > 0 && `${DIGEST_CHANNEL_LABELS.email} · ${digest.recipients.length}`,
    digest.telegramChatId && DIGEST_CHANNEL_LABELS.telegram,
  ].filter(Boolean)
  return used.join(', ')
}

const COLUMNS: readonly ResponsiveColumn<DigestSettingsDetail>[] = [
  {
    key: 'scope',
    title: DIGEST_LABELS.scope,
    render: (_, digest) => (
      <span className={styles.name}>
        {digest.scope === 'region' ? digest.regionName : DIGEST_SCOPE_LABELS.oblast}
      </span>
    ),
  },
  {
    key: 'when',
    title: DIGEST_LABELS.when,
    render: (_, digest) =>
      `${DIGEST_WEEKDAY_LABELS[digest.weekday]}, ${String(digest.hour).padStart(2, '0')}:00`,
  },
  { key: 'channels', title: DIGEST_LABELS.channels, render: (_, digest) => channels(digest) },
  {
    key: 'lastSent',
    title: DIGEST_LABELS.lastSent,
    render: (_, digest) =>
      digest.lastSentAt ? (
        formatDateTime(new Date(digest.lastSentAt))
      ) : (
        <span className={styles.muted}>{DIGEST_LABELS.neverSent}</span>
      ),
  },
  {
    key: 'active',
    title: DIGEST_LABELS.active,
    render: (_, digest) =>
      digest.isActive ? DIGEST_LABELS.active : <span className={styles.muted}>{DIGEST_LABELS.activeHint}</span>,
  },
]

/**
 * Вкладка «Сводки» экрана «Отчёты и экспорт» (T-67, DESIGN.md §3.32): рассылки сводки, drawer
 * настройки, «Отправить сейчас» с подтверждением и «Предпросмотр», который скачивает тот же PDF,
 * что уходит письмом.
 */
export function DigestList() {
  const [view, setView] = useAdminListView()
  const digests = useDigests(view)
  const drawer = useDrawer<DigestSettingsDetail>()
  const send = useSendDigest()
  const preview = useDigestPreview()
  const remove = useDeleteDigest()
  const { open: notify } = useNotification()

  const rowActions = (digest: DigestSettingsDetail) => (
    <div className={listStyles.rowActions}>
      <Popconfirm
        title={DIGEST_LABELS.sendConfirmTitle}
        description={DIGEST_LABELS.sendConfirmText}
        okText={DIGEST_LABELS.sendConfirmOk}
        cancelText={DIGEST_LABELS.sendConfirmCancel}
        onConfirm={() =>
          send.mutate(digest.id, {
            onSuccess: (result) =>
              notify?.({
                type: 'success',
                message: DIGEST_LABELS.sent,
                description: result.deliveries
                  .map((item) => `${DIGEST_CHANNEL_LABELS[item.channel]}: ${DIGEST_RESULT_LABELS[item.result]}`)
                  .join(', '),
              }),
          })
        }
      >
        <Button size="small" loading={send.isPending && send.variables === digest.id}>
          {DIGEST_LABELS.sendNow}
        </Button>
      </Popconfirm>
      <Button
        kind="flat"
        size="small"
        loading={preview.isPending && preview.variables === digest.id}
        onClick={() => preview.mutate(digest.id)}
      >
        {DIGEST_LABELS.preview}
      </Button>
      <Button kind="flat" size="small" onClick={() => drawer.show(digest)}>
        Изменить
      </Button>
      <Popconfirm
        title={DIGEST_LABELS.removeConfirmTitle}
        description={DIGEST_LABELS.removeConfirmText}
        okText={DIGEST_LABELS.remove}
        cancelText={DIGEST_LABELS.sendConfirmCancel}
        onConfirm={() =>
          remove.mutate(digest.id, {
            onSuccess: () => notify?.({ type: 'success', message: DIGEST_LABELS.removed }),
          })
        }
      >
        <Button kind="flat" size="small">
          {DIGEST_LABELS.remove}
        </Button>
      </Popconfirm>
    </div>
  )

  return (
    <>
      <div className={listStyles.digestHeader}>
        <p>{DIGEST_LABELS.lead}</p>
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          {DIGEST_LABELS.addAction}
        </Button>
      </div>
      <div className={listStyles.list}>
        <AdminTable
          query={digests}
          columns={COLUMNS}
          view={view}
          onChange={setView}
          empty={{ title: DIGEST_LABELS.emptyTitle, description: DIGEST_LABELS.emptyDescription }}
          rowActions={rowActions}
        />
      </div>
      <DigestDrawer key={drawer.key} open={drawer.open} digest={drawer.item} onClose={drawer.close} />
    </>
  )
}
