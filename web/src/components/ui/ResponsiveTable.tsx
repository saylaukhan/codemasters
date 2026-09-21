import { Select, Table, type TableProps } from 'antd'
import { useMemo, useState, type ReactNode } from 'react'

import { useMediaQuery } from '../../app/useMediaQuery'
import { RESPONSIVE_TABLE_LABELS } from '../../lib/labels'
import { NARROW_SCREEN, PHONE_SCREEN } from '../../styles/theme'
import styles from './ResponsiveTable.module.css'
import { cardColumns, sortableColumns, tableLayout, visibleColumns, type ColumnPriority } from './responsive-table'

/** Column of `ResponsiveTable`: an AntD column plus the priority of DESIGN.md §3.12. */
export type ResponsiveColumn<T> = NonNullable<TableProps<T>['columns']>[number] & {
  priority?: ColumnPriority
}

/** How a row reads as a card on a phone (DESIGN.md §3.12, step 3); the pairs come from the columns. */
export interface ResponsiveCard<T> {
  /** Title of the card: the name the row is known by. */
  title: (row: T) => ReactNode
  /** Status pill, right of the title; a row without a status leaves it out. */
  status?: (row: T) => ReactNode
  /** Muted line under the title: «Усть-Каменогорск · замер 13:47». */
  description?: (row: T) => ReactNode
  /** Row action: «⋯» or a link; the whole card is not a link, so Tab keeps working. */
  action?: (row: T) => ReactNode
}

export interface ResponsiveTableProps<T> extends Omit<TableProps<T>, 'columns'> {
  columns: readonly ResponsiveColumn<T>[]
  /** Without it a phone still gets the plain table: a list of cards needs a title to head it. */
  card?: ResponsiveCard<T>
  /** How many «подпись — значение» pairs a card holds; DESIGN.md §3.12 says two to four. */
  cardPairLimit?: number
}

// An AntD column is a union of shapes; reading it back needs only these five fields, so the
// wrapper looks at them structurally instead of narrowing the union at every call.
interface Renderable {
  key?: unknown
  title?: unknown
  dataIndex?: unknown
  render?: unknown
  sorter?: unknown
}

const columnKey = (column: Renderable, index: number): string => {
  if (column.key !== undefined && column.key !== null) return String(column.key)
  const { dataIndex } = column
  if (Array.isArray(dataIndex)) return dataIndex.join('.')
  if (typeof dataIndex === 'string' || typeof dataIndex === 'number') return String(dataIndex)
  return String(index)
}

const cellValue = (column: Renderable, row: object): unknown => {
  const { dataIndex } = column
  if (dataIndex === undefined || dataIndex === null) return undefined
  const path: unknown[] = Array.isArray(dataIndex) ? dataIndex : [dataIndex]
  return path.reduce<unknown>((value, step) => (value as Record<string, unknown> | undefined)?.[String(step)], row)
}

/** The value of one card pair: the column's own `render` when it has one, the raw field otherwise. */
const cellContent = <T extends object>(column: Renderable, row: T, index: number): ReactNode => {
  const value = cellValue(column, row)
  if (typeof column.render === 'function') {
    return (column.render as (value: unknown, row: T, index: number) => ReactNode)(value, row, index)
  }
  return value as ReactNode
}

/**
 * Table that follows DESIGN.md §3.12 and §9.3 on its own, so no page has to know about widths:
 * from 1025px the plain AntD table; at 769–1024 it scrolls inside its card with the first column
 * pinned and the `minor` columns hidden; at 768px and narrower every row becomes a card — title,
 * status pill, up to four «подпись — значение» pairs and the row action — with a sort select above
 * the list built from the sortable columns. The rules themselves live in `responsive-table.ts`.
 */
export function ResponsiveTable<T extends object>({
  columns,
  card,
  cardPairLimit,
  rowKey,
  dataSource,
  ...props
}: ResponsiveTableProps<T>) {
  const narrow = useMediaQuery(NARROW_SCREEN)
  const phone = useMediaQuery(PHONE_SCREEN)
  const layout = card ? tableLayout(narrow, phone) : tableLayout(narrow, false)

  const [sortKey, setSortKey] = useState<string>()

  const sortable = useMemo(
    () => sortableColumns(columns.map((column, index) => ({ ...column, key: columnKey(column, index) }))),
    [columns],
  )

  const rows = useMemo(() => {
    const source = dataSource ? [...dataSource] : []
    if (layout !== 'cards' || !sortKey) return source
    const column = sortable.find((candidate) => candidate.key === sortKey)
    const comparator = column?.sorter
    if (typeof comparator !== 'function') return source
    return source.sort((left, right) => Number(comparator(left, right, 'ascend')))
  }, [dataSource, layout, sortKey, sortable])

  if (layout !== 'cards' || !card) {
    const shown = visibleColumns(columns, layout)
    // The pinned first column of step 2 is AntD's own `fixed`; above 1024 nothing is pinned.
    const fixed =
      layout === 'scroll' && shown.length > 0 ? [{ ...shown[0], fixed: 'left' as const }, ...shown.slice(1)] : shown
    return (
      <Table<T>
        {...props}
        rowKey={rowKey}
        columns={fixed}
        dataSource={dataSource}
        scroll={layout === 'scroll' ? { x: 'max-content' } : props.scroll}
      />
    )
  }

  const pairs = cardColumns(columns, cardPairLimit)
  const rowId = (row: T, index: number): React.Key =>
    typeof rowKey === 'function' ? rowKey(row, index) : ((row as Record<string, React.Key>)[String(rowKey)] ?? index)

  return (
    <div className={styles.cards}>
      {sortable.length > 0 && (
        <label className={styles.sort}>
          {RESPONSIVE_TABLE_LABELS.sort}
          <Select<string>
            className={styles.sortField}
            value={sortKey}
            placeholder={RESPONSIVE_TABLE_LABELS.defaultOrder}
            onChange={setSortKey}
            options={sortable.map((column) => ({ value: String(column.key), label: column.title as ReactNode }))}
            allowClear
            onClear={() => setSortKey(undefined)}
          />
        </label>
      )}
      {rows.map((row, index) => (
        <div key={rowId(row, index)} className={styles.card}>
          <div className={styles.head}>
            <span className={styles.title}>{card.title(row)}</span>
            {card.status?.(row)}
          </div>
          {card.description && <span className={styles.description}>{card.description(row)}</span>}
          {pairs.length > 0 && (
            <div className={styles.pairs}>
              {pairs.map((column, columnIndex) => (
                <div key={columnKey(column, columnIndex)} className={styles.pair}>
                  <span className={styles.pairLabel}>{column.title as ReactNode}</span>
                  <span className={styles.pairValue}>{cellContent(column, row, index)}</span>
                </div>
              ))}
            </div>
          )}
          {card.action && <div className={styles.action}>{card.action(row)}</div>}
        </div>
      ))}
    </div>
  )
}
