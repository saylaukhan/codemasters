import type { UseQueryResult } from '@tanstack/react-query'
import { Table, type TableColumnsType } from 'antd'
import { SearchX } from 'lucide-react'
import type { ReactNode } from 'react'

import { PAGE_SIZES } from '../schools/useSchoolListView'
import { Button } from '../ui/Button'
import { ContentSkeleton } from '../ui/ContentSkeleton'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import type { AdminListView } from './useAdminListView'

interface AdminTableProps<T extends { id: number }> {
  query: UseQueryResult<{ items: T[]; total: number }>
  columns: TableColumnsType<T>
  view: AdminListView
  onChange: (view: AdminListView) => void
  /** Empty list without a search or a filter: what to do to fill it. */
  empty: { title: string; description: string }
  /** «Изменить» of a row: opens the drawer. */
  onEdit?: (item: T) => void
  /** Actions of a row in place of «Изменить», e.g. the «⋯» menu of a device (DESIGN.md §3.12). */
  rowActions?: (item: T) => ReactNode
}

/**
 * List of the administration in its three states (DESIGN.md §2.7): pages on the server, «Изменить» of a row
 * is Flat (§3.1) and opens the drawer.
 */
export function AdminTable<T extends { id: number }>({
  query,
  columns,
  view,
  onChange,
  empty,
  onEdit,
  rowActions,
}: AdminTableProps<T>) {
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  if (query.isPending) return <ContentSkeleton />

  const filtered = view.q.trim() !== '' || view.isActive !== undefined
  const emptyText = filtered ? (
    <EmptyState
      icon={SearchX}
      title="Ничего не найдено"
      description="Измените запрос или сбросьте поиск."
      action={
        <Button onClick={() => onChange({ ...view, q: '', isActive: undefined, page: 1 })}>Сбросить поиск</Button>
      }
    />
  ) : (
    <EmptyState title={empty.title} description={empty.description} />
  )

  return (
    <Table<T>
      rowKey="id"
      size="middle"
      columns={[
        ...columns,
        {
          key: 'edit',
          align: 'right',
          render: (_, item) =>
            rowActions?.(item) ??
            (onEdit && (
              <Button kind="flat" size="small" onClick={() => onEdit(item)}>
                Изменить
              </Button>
            )),
        },
      ]}
      dataSource={query.data.items}
      loading={query.isFetching && query.isPlaceholderData}
      scroll={{ x: 'max-content' }}
      locale={{ emptyText }}
      pagination={{
        current: view.page,
        pageSize: view.pageSize,
        total: query.data.total,
        pageSizeOptions: PAGE_SIZES.map(String),
        showSizeChanger: true,
        showTotal: (count, [from, to]) => `${from}–${to} из ${count}`,
      }}
      onChange={(pagination) => {
        const pageSize = pagination.pageSize ?? view.pageSize
        onChange({ ...view, pageSize, page: pageSize === view.pageSize ? (pagination.current ?? 1) : 1 })
      }}
    />
  )
}
