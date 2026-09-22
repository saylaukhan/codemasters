import type { ReactNode } from 'react'

// Rules of `ResponsiveTable` (DESIGN.md §3.12, §9.3): which columns survive at which width and
// which of them become the «подпись — значение» pairs of a phone card. Pure, so the three steps
// of §3.12 are checked without a DOM; the component only renders what these return.

/**
 * Weight of a column (DESIGN.md §3.12, step 1):
 * - `primary` — always on the table, never a pair: the card head already shows it;
 * - `secondary` — the default: on the table while it fits, a pair on a phone;
 * - `minor` — first to go when the width runs out, still a pair on a phone.
 */
export type ColumnPriority = 'primary' | 'secondary' | 'minor'

export interface PrioritisedColumn {
  priority?: ColumnPriority
}

export interface SortableColumn {
  key?: string | number
  sorter?: unknown
}

/** What the table looks like right now (DESIGN.md §9.3, row «Таблицы»). */
export type TableLayout = 'table' | 'scroll' | 'cards'

/** ≥ 1025 the plain table, 769–1024 scrolling inside the card, ≤ 768 a list of cards. */
export function tableLayout(narrow: boolean, phone: boolean): TableLayout {
  if (phone) return 'cards'
  return narrow ? 'scroll' : 'table'
}

// A column of an existing table carries no priority; it behaves as `secondary`, which keeps it
// visible at every width and turns it into a card pair on a phone.
const priorityOf = (column: object): ColumnPriority => (column as PrioritisedColumn).priority ?? 'secondary'

/**
 * Columns the table shows at this layout: everything but `minor` while it scrolls inside the card,
 * everything otherwise. The card list gets the whole set and picks from it with `cardColumns`.
 */
export function visibleColumns<C extends object>(columns: readonly C[], layout: TableLayout): C[] {
  if (layout !== 'scroll') return [...columns]
  return columns.filter((column) => priorityOf(column) !== 'minor')
}

/**
 * Columns that become the pairs of a phone card, at most `limit` of them (DESIGN.md §3.12, step 3:
 * «2–4 ключевых значения»). `primary` columns are left out — they are the title, the status pill
 * and the description of the card; `secondary` comes before `minor`, each group in its own order.
 */
export function cardColumns<C extends object>(columns: readonly C[], limit = 4): C[] {
  const secondary = columns.filter((column) => priorityOf(column) === 'secondary')
  const minor = columns.filter((column) => priorityOf(column) === 'minor')
  return [...secondary, ...minor].slice(0, limit)
}

/**
 * Columns the select above the card list can sort by (DESIGN.md §3.12, step 3). Only a client-side
 * comparator counts: a column with `sorter: true` is sorted by the server, which the list of cards
 * cannot ask for on its own — that stays with the page (T-62).
 */
export function sortableColumns<C extends object>(columns: readonly C[]): C[] {
  return columns.filter((column) => {
    const { key, sorter } = column as SortableColumn
    return typeof sorter === 'function' && key !== undefined
  })
}
/** What the caller gave `pagination`; AntD's own config, read back by the card list. */
export interface CardPaginationInput {
  current?: number
  pageSize?: number
  defaultPageSize?: number
  total?: number
}

/** The page the card list shows right now (DESIGN.md §3.12: «Пагинация в подвале»). */
export interface CardPage {
  current: number
  pageSize: number
  total: number
}

/** AntD's own default page size; the card list follows the table it replaces. */
export const DEFAULT_PAGE_SIZE = 10

/**
 * Page of the card list, or nothing when the caller turned pagination off. A controlled `current`
 * wins over the list's own; `total` falls back to the rows at hand, which is the client-side case.
 */
export function cardPage(
  pagination: CardPaginationInput | false | undefined,
  ownCurrent: number,
  rowCount: number,
): CardPage | undefined {
  if (pagination === false) return undefined
  const config = pagination ?? {}
  return {
    current: config.current ?? ownCurrent,
    pageSize: config.pageSize ?? config.defaultPageSize ?? DEFAULT_PAGE_SIZE,
    total: config.total ?? rowCount,
  }
}

/**
 * Rows of one page. Like AntD, the source is cut only when it holds more than a page: a server
 * that already sent one page (`total` bigger than the rows at hand) is shown as it is.
 */
export function pageRows<T>(rows: readonly T[], page: CardPage | undefined): T[] {
  if (!page || rows.length <= page.pageSize) return [...rows]
  const start = (page.current - 1) * page.pageSize
  return rows.slice(start, start + page.pageSize)
}

// An AntD column is a union of shapes; reading a cell back needs only `dataIndex` and `render`,
// so the wrapper looks at them structurally instead of narrowing the union at every call.
interface Renderable {
  dataIndex?: unknown
  render?: unknown
}

const cellValue = (column: Renderable, row: object): unknown => {
  const { dataIndex } = column
  if (dataIndex === undefined || dataIndex === null) return undefined
  const path: unknown[] = Array.isArray(dataIndex) ? dataIndex : [dataIndex]
  return path.reduce<unknown>((value, step) => (value as Record<string, unknown> | undefined)?.[String(step)], row)
}

/**
 * The value of one card pair: the column's own `render` when it has one, the raw field otherwise.
 * `AdminTable` builds its card out of the columns its page handed it, so this is exported.
 */
export function columnContent<T extends object>(column: object, row: T, index: number): ReactNode {
  const value = cellValue(column as Renderable, row)
  const { render } = column as Renderable
  if (typeof render === 'function') {
    return (render as (value: unknown, row: T, index: number) => ReactNode)(value, row, index)
  }
  return value as ReactNode
}
