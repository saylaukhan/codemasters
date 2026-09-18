import { useNotification } from '@refinedev/core'
import { Table, type TableProps } from 'antd'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import type { ExportJob } from '../../api/types'
import { NO_VALUE, formatDate, formatDateTime, formatNumber } from '../../lib/format'
import { EXPORT_FORMAT_LABELS, EXPORT_MODE_LABELS } from '../../lib/labels'
import { Button } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import { ExportStatusBadge } from '../ui/StatusBadge'
import styles from './Exports.module.css'
import { useDownloadExport, useExports } from './queries'

const PAGE_SIZE = 10

// The end of the period is exclusive: the last day of the file is the day before it.
const lastDay = (periodTo: string) => new Date(new Date(periodTo).getTime() - 1)

/**
 * Exports of the user under the constructor (DESIGN.md §3.24, T-33): big ones are built in the background, the list
 * shows «Готовится» until the file is ready and then «Скачать».
 */
export function ExportList() {
  const [page, setPage] = useState(1)
  const exports = useExports(page, PAGE_SIZE)
  const download = useDownloadExport()
  const { open } = useNotification()

  const save = (job: ExportJob) =>
    download.mutate(job, {
      onError: (error) =>
        open?.({
          type: 'error',
          message: 'Файл не скачан',
          description: error instanceof ApiError ? (error.detail ?? error.title) : undefined,
        }),
    })

  const columns: TableProps<ExportJob>['columns'] = [
    {
      key: 'created',
      title: 'Создана',
      render: (_, job) => <span className={styles.number}>{formatDateTime(job.createdAt)}</span>,
    },
    {
      key: 'data',
      title: 'Данные',
      render: (_, job) => `${EXPORT_MODE_LABELS[job.mode]} · ${EXPORT_FORMAT_LABELS[job.format]}`,
    },
    {
      key: 'period',
      title: 'Период',
      render: (_, job) => (
        <span className={styles.number}>
          {formatDate(job.periodFrom)} — {formatDate(lastDay(job.periodTo))}
        </span>
      ),
    },
    {
      key: 'rows',
      title: 'Строк',
      align: 'right',
      render: (_, job) => <span className={styles.number}>{formatNumber(job.rowsCount, 0)}</span>,
    },
    {
      key: 'status',
      title: 'Статус',
      render: (_, job) => (
        <div className={styles.status}>
          <ExportStatusBadge status={job.status} />
          {job.status === 'failed' && job.error && <span className={styles.reason}>{job.error}</span>}
        </div>
      ),
    },
    {
      key: 'expires',
      title: 'Хранится до',
      render: (_, job) => (
        <span className={styles.number}>{job.expiresAt ? formatDate(job.expiresAt) : NO_VALUE}</span>
      ),
    },
    {
      key: 'file',
      title: 'Файл',
      render: (_, job) =>
        job.status === 'ready' ? (
          <Button
            kind="link"
            size="small"
            loading={download.isPending && download.variables?.id === job.id}
            onClick={() => save(job)}
          >
            Скачать
          </Button>
        ) : (
          NO_VALUE
        ),
    },
  ]

  return (
    <section className={styles.card} aria-label="Выгрузки">
      <h2 className={styles.title}>Выгрузки</h2>
      {exports.isError ? (
        <ErrorState error={exports.error} onRetry={() => void exports.refetch()} />
      ) : (
        <Table<ExportJob>
          rowKey="id"
          size="middle"
          columns={columns}
          dataSource={exports.data?.items}
          loading={exports.isPending}
          scroll={{ x: 'max-content' }}
          locale={{
            emptyText: (
              <EmptyState
                title="Выгрузок пока нет"
                description="Большие выгрузки и PDF формируются в фоне и появляются здесь со ссылкой «Скачать»."
              />
            ),
          }}
          pagination={{
            current: page,
            pageSize: PAGE_SIZE,
            total: exports.data?.total,
            hideOnSinglePage: true,
            showSizeChanger: false,
          }}
          onChange={(pagination) => setPage(pagination.current ?? 1)}
        />
      )}
    </section>
  )
}
