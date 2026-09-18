// Forms of the administration (T-34): rules of the fields, bodies of POST and PATCH, errors of the API
// under the fields.
import type { FormRule } from 'antd'

import { camelKey } from '../../api/case'
import { ApiError } from '../../api/client'
import type { GeoPoint, SchoolCreate, SchoolDetail, SchoolUpdate } from '../../api/types'

/** A required text: blanks do not count. */
export const required = (message: string): FormRule => ({ required: true, whitespace: true, message })

/** The length limit of the API, checked before sending. */
export const maxLength = (max: number): FormRule => ({ max, message: `Не длиннее ${max} символов` })

/** Message of a form field, as AntD `form.setFields` takes it; `name` is the camelCase field of the form. */
export interface FieldMessage {
  name: string
  errors: string[]
}

/** A value already taken (409) is shown under the field that holds it; the text is the API's `detail`. */
const CONFLICTS: Record<string, { field: string; message: string }> = {
  school_code_taken: { field: 'schoolCode', message: 'Этот School ID уже занят другой школой' },
  provider_name_taken: { field: 'name', message: 'Поставщик с таким названием уже есть' },
  region_code_taken: { field: 'code', message: 'Район или город с таким кодом уже есть' },
  connection_type_code_taken: { field: 'code', message: 'Тип подключения с таким кодом уже есть' },
  main_line_exists: { field: 'status', message: 'У школы уже есть основная линия' },
}

/** Field of the form for a field path of the API: `school_code` → `schoolCode`, `location.lat` → `lat`. */
const formField = (path: string): string => camelKey(path.split('.').pop() ?? path)

/**
 * Where an error of saving is shown: `fields` under the fields of the form (ADR-009: `errors[]` of a 422,
 * the field of a 409), `alert` — in the alert of the drawer when some of it has no field to go under.
 */
export function formErrors(error: unknown, fields: readonly string[]): { fields: FieldMessage[]; alert: boolean } {
  if (error == null) return { fields: [], alert: false }
  if (!(error instanceof ApiError)) return { fields: [], alert: true }
  const conflict = CONFLICTS[error.type]
  if (conflict && fields.includes(conflict.field)) {
    return { fields: [{ name: conflict.field, errors: [error.detail ?? conflict.message] }], alert: false }
  }
  const messages = new Map<string, string[]>()
  let unplaced = error.fieldErrors.length === 0
  for (const { field, message } of error.fieldErrors) {
    const name = formField(field)
    if (fields.includes(name)) messages.set(name, [...(messages.get(name) ?? []), message])
    else unplaced = true
  }
  return { fields: [...messages].map(([name, errors]) => ({ name, errors })), alert: unplaced }
}

/** Optional text: blank is «no value», sent as `null` so that a PATCH clears it. */
export const optionalText = (value: string | null | undefined): string | null => value?.trim() || null

/** Fields of `next` that differ from `initial`: a PATCH sends only them, an absent field stays as it is. */
export function changedFields<T extends object>(initial: T, next: T): Partial<T> {
  return Object.fromEntries(
    Object.entries(next).filter(([key, value]) => JSON.stringify(value) !== JSON.stringify(initial[key as keyof T])),
  ) as Partial<T>
}

export interface SchoolFormValues {
  schoolCode: string
  fullName: string
  regionId?: number
  address: string | null
  /** The point on the map: both coordinates or none, the form checks it. */
  lat: number | null
  lon: number | null
  isActive: boolean
}

export const schoolFormValues = (school?: SchoolDetail): SchoolFormValues => ({
  schoolCode: school?.schoolCode ?? '',
  fullName: school?.fullName ?? '',
  regionId: school?.regionId,
  address: school?.address ?? null,
  lat: school?.location?.lat ?? null,
  lon: school?.location?.lon ?? null,
  isActive: school?.isActive ?? true,
})

/** The point of the form: both coordinates or none. */
export const pointOf = ({ lat, lon }: Pick<SchoolFormValues, 'lat' | 'lon'>): GeoPoint | null =>
  lat != null && lon != null ? { lat, lon } : null

/** Body of POST /api/schools; a new school is active. `regionId` is required by the form before it submits. */
export const schoolCreateBody = (values: SchoolFormValues): SchoolCreate => ({
  schoolCode: values.schoolCode.trim(),
  fullName: values.fullName.trim(),
  regionId: values.regionId as number,
  address: optionalText(values.address),
  location: pointOf(values),
})

/** Body of PATCH /api/schools/{id}: the changed fields only; a cleared address or point is `null`. */
export const schoolUpdateBody = (initial: SchoolFormValues, values: SchoolFormValues): SchoolUpdate =>
  changedFields<SchoolUpdate>(
    { ...schoolCreateBody(initial), isActive: initial.isActive },
    { ...schoolCreateBody(values), isActive: values.isActive },
  )
