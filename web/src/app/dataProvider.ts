// Refine data provider to /api (ADR-009): lists `{items, total, page, page_size}`, sort as
// `field` / `-field`, filters and pagination as query parameters in snake_case.
import type {
  BaseRecord,
  CreateParams,
  DataProvider,
  DeleteOneParams,
  GetListParams,
  GetOneParams,
  MetaQuery,
  UpdateParams,
} from '@refinedev/core'

import { API_BASE, apiRequest, type QueryValue } from '../api/client'

interface Page {
  items: BaseRecord[]
  total: number
}

// A resource may live under another path, e.g. `meta: { path: 'admin/users' }`.
const pathOf = (resource: string, meta?: MetaQuery): string =>
  `/${typeof meta?.path === 'string' ? meta.path : resource}`

export const dataProvider: DataProvider = {
  getApiUrl: () => API_BASE,

  async getList<TData extends BaseRecord>({ resource, pagination, sorters, filters, meta }: GetListParams) {
    const query: Record<string, QueryValue> = {}
    if (pagination?.mode !== 'off') {
      query.page = pagination?.currentPage ?? 1
      query.pageSize = pagination?.pageSize ?? 25
    }
    const [sorter] = sorters ?? []
    if (sorter) query.sort = sorter.order === 'desc' ? `-${sorter.field}` : sorter.field
    for (const filter of filters ?? []) {
      if ('field' in filter && (filter.operator === 'eq' || filter.operator === 'in')) {
        query[filter.field] = filter.value as QueryValue
      }
    }
    const page = await apiRequest<Page>(pathOf(resource, meta), {
      query,
      signal: meta?.queryContext?.signal,
    })
    return { data: page.items as TData[], total: page.total }
  },

  async getOne<TData extends BaseRecord>({ resource, id, meta }: GetOneParams) {
    const data = await apiRequest<BaseRecord>(`${pathOf(resource, meta)}/${id}`, {
      signal: meta?.queryContext?.signal,
    })
    return { data: data as TData }
  },

  async create<TData extends BaseRecord, TVariables>({ resource, variables, meta }: CreateParams<TVariables>) {
    const data = await apiRequest<BaseRecord>(pathOf(resource, meta), { method: 'POST', body: variables })
    return { data: data as TData }
  },

  async update<TData extends BaseRecord, TVariables>({ resource, id, variables, meta }: UpdateParams<TVariables>) {
    const data = await apiRequest<BaseRecord>(`${pathOf(resource, meta)}/${id}`, {
      method: 'PATCH',
      body: variables,
    })
    return { data: data as TData }
  },

  async deleteOne<TData extends BaseRecord, TVariables>({ resource, id, meta }: DeleteOneParams<TVariables>) {
    await apiRequest<null>(`${pathOf(resource, meta)}/${id}`, { method: 'DELETE' })
    return { data: { id } as TData }
  },
}
