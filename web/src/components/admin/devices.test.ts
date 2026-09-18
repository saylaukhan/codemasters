import { describe, expect, it } from 'vitest'

import { deviceName, deviceStatusOf, pointOption, schoolOption } from './devices'

describe('devices of the administration', () => {
  it('keeps the status filter in isActive of the list view', () => {
    expect(deviceStatusOf(undefined)).toBeUndefined()
    expect(deviceStatusOf(true)).toBe('active')
    expect(deviceStatusOf(false)).toBe('blocked')
  })

  it('names a computer by its agent identifier when the name is unknown', () => {
    expect(deviceName({ hostname: 'PC-12', deviceUid: 'a1b2' })).toBe('PC-12')
    expect(deviceName({ hostname: null, deviceUid: 'a1b2' })).toBe('a1b2')
  })

  it('labels the options of the rebinding form', () => {
    expect(schoolOption({ id: 3, schoolCode: 'VKO-0011', fullName: 'КГУ «Школа № 11»' })).toEqual({
      value: 3,
      label: 'VKO-0011 · КГУ «Школа № 11»',
    })
    expect(pointOption({ id: 7, name: 'Информатика', room: '214' }).label).toBe('Информатика · каб. 214')
    expect(pointOption({ id: 8, name: 'Серверная', room: null }).label).toBe('Серверная')
  })
})
