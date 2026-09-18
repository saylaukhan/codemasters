// HTTP client to /api (ADR-009): access token in memory, refresh through the httpOnly cookie,
// errors as application/problem+json, snake_case ↔ camelCase at the boundary.
import { camelize, snakeize, snakeKey, type Camelize } from './case'
import type { FieldError } from './types'

export const API_BASE = '/api'

/**
 * Error of the API in RFC 9457 terms; `type` is the stable code the panel branches on. Also
 * shaped as Refine's HttpError: `statusCode` and `errors` by field land in forms as is.
 */
export class ApiError extends Error {
  readonly status: number
  readonly statusCode: number
  readonly type: string
  readonly title: string
  readonly detail: string | null
  readonly fieldErrors: FieldError[]
  readonly errors: Record<string, string>

  constructor(problem: {
    status: number
    type: string
    title: string
    detail?: string | null
    errors?: FieldError[]
  }) {
    super(problem.detail ?? problem.title)
    this.name = 'ApiError'
    this.status = problem.status
    this.statusCode = problem.status
    this.type = problem.type
    this.title = problem.title
    this.detail = problem.detail ?? null
    this.fieldErrors = problem.errors ?? []
    this.errors = Object.fromEntries(this.fieldErrors.map((error) => [error.field, error.message]))
  }
}

let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null

export const hasAccessToken = (): boolean => accessToken !== null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

/**
 * New access token from the refresh cookie. Concurrent callers share one request, so a burst
 * of 401s after the token expires turns into a single refresh.
 */
export function refreshAccessToken(): Promise<boolean> {
  refreshing ??= fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
    .then(async (response) => {
      if (!response.ok) {
        accessToken = null
        return false
      }
      const body = camelize<{ access_token: string }>(await response.json())
      accessToken = body.accessToken
      return true
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

export type QueryValue = string | number | boolean | null | undefined | readonly (string | number | boolean)[]

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  query?: Record<string, QueryValue>
  body?: unknown
  signal?: AbortSignal
  /** Send the access token and refresh it once on 401; off for the sign-in itself. */
  auth?: boolean
}

function buildUrl(path: string, query: RequestOptions['query']): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === '') continue
    for (const item of Array.isArray(value) ? value : [value]) {
      params.append(snakeKey(key), String(item))
    }
  }
  const search = params.toString()
  return `${API_BASE}${path}${search ? `?${search}` : ''}`
}

async function toApiError(response: Response): Promise<ApiError> {
  const problem = await response.json().catch(() => null)
  if (problem && typeof problem === 'object' && 'type' in problem && 'title' in problem) {
    return new ApiError(camelize<ConstructorParameters<typeof ApiError>[0]>(problem))
  }
  return new ApiError({ status: response.status, type: 'http_error', title: 'Ошибка сервера' })
}

async function send(path: string, options: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.auth !== false && accessToken) headers.Authorization = `Bearer ${accessToken}`
  try {
    return await fetch(buildUrl(path, options.query), {
      method: options.method ?? 'GET',
      headers,
      body: options.body === undefined ? undefined : JSON.stringify(snakeize(options.body)),
      credentials: 'same-origin',
      signal: options.signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError({ status: 0, type: 'network_error', title: 'Нет связи с сервером' })
  }
}

/** Request to `/api{path}`; `T` is the snake_case schema of the response, the result is camelCase. */
export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<Camelize<T>> {
  let response = await send(path, options)
  if (response.status === 401 && options.auth !== false && (await refreshAccessToken())) {
    response = await send(path, options)
  }
  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as Camelize<T>
  return camelize<T>(await response.json())
}

/** File of `/api{path}` with its name from Content-Disposition: exports are fetched with the token, not by a link. */
export async function apiDownload(path: string, signal?: AbortSignal): Promise<{ blob: Blob; fileName: string | null }> {
  let response = await send(path, { signal })
  if (response.status === 401 && (await refreshAccessToken())) {
    response = await send(path, { signal })
  }
  if (!response.ok) throw await toApiError(response)
  const disposition = response.headers.get('Content-Disposition') ?? ''
  return { blob: await response.blob(), fileName: /filename="([^"]+)"/.exec(disposition)?.[1] ?? null }
}
