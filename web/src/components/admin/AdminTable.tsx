import type { UseQueryResult } from '@tanstack/react-query'
import { SearchX } from 'lucide-react'
import type { ReactNode } from 'react'

import { PAGE_SIZES } from '../schools/useSchoolListView'
import { Button } from '../ui/Button'
import { ContentSkeleton } from '../ui/ContentSkeleton'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import { ResponsiveTable, type ResponsiveColumn } from '../ui/ResponsiveTable'
import { columnContent } from '../ui/responsive-table'
import type { AdminListView } from './useAdminListView'

interface AdminTableProps<T extends { id: number }> {
  query: UseQueryResult<{ items: T[]; total: number }>
  columns: readonly ResponsiveColumn<T>[]
  view: AdminListView
  onChange: (view: AdminListView) => void
  /** Empty list without a search or a filter: what to do to fill it. */
  empty: { title: string; description: string }
  /** «Изменить» of a row: opens the drawer. */
  onEdit?: (item: T) => void
  /** Actions of a row in place of «Изменить», e.g. the «⋯» menu of a device (DESIGN.md §3.12). */
  rowActions?: (item: T) => ReactNode
  /** Muted line under the title of a phone card (DESIGN.md §3.12, step 3); the pairs come from the columns. */
  cardDescription?: (item: T) => ReactNode
}

/**
 * Default priorities of the nine administration lists (DESIGN.md §3.12, step 1): the first column
 * names the row and the last one carries its status, so both head the phone card instead of
 * becoming its pairs. A page that knows better sets `priority` on its own columns.
 */
const prioritised = <T,>(columns: readonly ResponsiveColumn<T>[]): ResponsiveColumn<T>[] =>
  columns.map((column, index) => ({
    ...column,
    priority: column.priority ?? (index === 0 || index === columns.length - 1 ? 'primary' : 'secondary'),
  }))

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
  cardDescription,
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

  const action = (item: T) =>
    rowActions?.(item) ??
    (onEdit && (
      <Button kind="flat" size="small" onClick={() => onEdit(item)}>
        Изменить
      </Button>
    ))
  const shown = prioritised(columns)

  return (
    <ResponsiveTable<T>
      rowKey="id"
      size="middle"
      columns={[...shown, { key: 'edit', priority: 'primary', align: 'right', render: (_, item) => action(item) }]}
      card={
        shown.length > 0
          ? {
              title: (item) => columnContent(shown[0], item, 0),
              status: shown.length > 1 ? (item) => columnContent(shown[shown.length - 1], item, 0) : undefined,
              description: cardDescription,
              action: onEdit || rowActions ? action : undefined,
            }
          : undefined
      }
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
