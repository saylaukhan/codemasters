// snake_case of the API ↔ camelCase of the panel (ADR-009): the mapping lives only in src/api.

type CamelCase<S extends string> = S extends `${infer Head}_${infer Tail}`
  ? `${Head}${Capitalize<CamelCase<Tail>>}`
  : S

/** Type of an API payload with every key in camelCase, nested objects and arrays included. */
export type Camelize<T> = T extends readonly (infer Item)[]
  ? Camelize<Item>[]
  : T extends object
    ? { [K in keyof T as K extends string ? CamelCase<K> : K]: Camelize<T[K]> }
    : T

const toCamel = (key: string): string => key.replace(/_([a-z0-9])/g, (_, c: string) => c.toUpperCase())

const toSnake = (key: string): string => key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`)

function mapKeys(value: unknown, rename: (key: string) => string): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => mapKeys(item, rename))
  }
  if (value !== null && typeof value === 'object' && Object.getPrototypeOf(value) === Object.prototype) {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [rename(key), mapKeys(item, rename)]),
    )
  }
  return value
}

/** Response body → panel object: keys to camelCase. */
export const camelize = <T>(value: unknown): Camelize<T> => mapKeys(value, toCamel) as Camelize<T>

/** Panel object → request body or query: keys to snake_case. */
export const snakeize = (value: unknown): unknown => mapKeys(value, toSnake)

export const snakeKey = toSnake
