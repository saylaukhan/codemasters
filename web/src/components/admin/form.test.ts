import { describe, expect, it } from 'vitest'

import { ApiError } from '../../api/client'
import type { SchoolDetail } from '../../api/types'
import { changedFields, formErrors, schoolCreateBody, schoolFormValues, schoolUpdateBody } from './form'

const SCHOOL_FIELDS = ['schoolCode', 'fullName', 'regionId', 'address', 'lat', 'lon', 'isActive']

const SCHOOL = {
  id: 7,
  schoolCode: 'VKO-UKG-017',
  fullName: 'КГУ «Школа-лицей № 17»',
  regionId: 3,
  regionName: 'Усть-Каменогорск',
  address: 'ул. Абая, 1',
  location: { lat: 49.9483, lon: 82.6286 },
  isActive: true,
} as SchoolDetail

describe('formErrors', () => {
  it('puts a taken value under its field with the text of the API', () => {
    const error = new ApiError({ status: 409, type: 'school_code_taken', title: 'Конфликт', detail: 'School ID занят' })

    expect(formErrors(error, SCHOOL_FIELDS)).toEqual({
      fields: [{ name: 'schoolCode', errors: ['School ID занят'] }],
      alert: false,
    })
    expect(formErrors(new ApiError({ status: 409, type: 'region_code_taken', title: 'Конфликт' }), ['code', 'name']))
      .toEqual({ fields: [{ name: 'code', errors: ['Район или город с таким кодом уже есть'] }], alert: false })
  })

  it('maps the snake_case paths of a 422 to the fields of the form', () => {
    const error = new ApiError({
      status: 422,
      type: 'validation_error',
      title: 'Ошибка валидации',
      errors: [
        { field: 'region_id', message: 'Район не найден' },
        { field: 'location.lat', message: 'Не больше 90' },
      ],
    })

    expect(formErrors(error, SCHOOL_FIELDS)).toEqual({
      fields: [
        { name: 'regionId', errors: ['Район не найден'] },
        { name: 'lat', errors: ['Не больше 90'] },
      ],
      alert: false,
    })
  })

  it('falls back to the alert when no field of the form can show the error', () => {
    const outside = new ApiError({
      status: 422,
      type: 'validation_error',
      title: 'Ошибка валидации',
      errors: [{ field: 'location', message: 'Нужны обе координаты' }],
    })

    expect(formErrors(outside, SCHOOL_FIELDS)).toEqual({ fields: [], alert: true })
    expect(formErrors(new ApiError({ status: 500, type: 'internal', title: 'Ошибка сервера' }), SCHOOL_FIELDS).alert)
      .toBe(true)
    expect(formErrors(new Error('offline'), SCHOOL_FIELDS).alert).toBe(true)
    expect(formErrors(null, SCHOOL_FIELDS)).toEqual({ fields: [], alert: false })
  })
})

describe('school bodies', () => {
  it('trims the texts and sends no address and no point for blanks', () => {
    const values = { ...schoolFormValues(), schoolCode: ' VKO-UKG-018 ', fullName: ' Школа № 18 ', regionId: 3 }

    expect(schoolCreateBody({ ...values, address: '  ', lat: 49.9, lon: null })).toEqual({
      schoolCode: 'VKO-UKG-018',
      fullName: 'Школа № 18',
      regionId: 3,
      address: null,
      location: null,
    })
    expect(schoolCreateBody({ ...values, lat: 49.9, lon: 82.6 }).location).toEqual({ lat: 49.9, lon: 82.6 })
  })

  it('patches only what changed and clears the address and the point with null', () => {
    const initial = schoolFormValues(SCHOOL)

    expect(schoolUpdateBody(initial, { ...initial })).toEqual({})
    expect(schoolUpdateBody(initial, { ...initial, address: '', lat: null, lon: null, isActive: false })).toEqual({
      address: null,
      location: null,
      isActive: false,
    })
    expect(schoolUpdateBody(initial, { ...initial, fullName: 'Школа-лицей № 17', lon: 82.7 })).toEqual({
      fullName: 'Школа-лицей № 17',
      location: { lat: 49.9483, lon: 82.7 },
    })
  })

  it('compares nested values by content', () => {
    expect(changedFields({ a: 1, point: { lat: 1, lon: 2 } }, { a: 1, point: { lat: 1, lon: 2 } })).toEqual({})
    expect(changedFields({ email: 'a@example.kz' as string | null }, { email: null })).toEqual({ email: null })
  })
})
