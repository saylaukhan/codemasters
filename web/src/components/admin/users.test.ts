import { describe, expect, it } from 'vitest'

import type { UserDetail } from '../../api/types'
import { userCreateBody, userFormValues, userUpdateBody } from './users'

const district: UserDetail = {
  id: 7,
  email: 'rayon@example.kz',
  fullName: 'Иванова А. К.',
  role: 'district',
  scope: { regionId: 3, regionName: 'Усть-Каменогорск', providerId: null, schoolId: null },
  scopeName: 'Усть-Каменогорск',
  isActive: true,
}

describe('users of the administration', () => {
  it('sends only the scope id of the chosen role', () => {
    expect(
      userCreateBody({
        fullName: ' Новый ',
        email: 'new@example.kz',
        role: 'school',
        regionId: 3,
        schoolId: { value: 11, label: 'VKO-0011 · Школа № 11' },
        password: 'Password1',
      }),
    ).toEqual({ email: 'new@example.kz', fullName: 'Новый', role: 'school', schoolId: 11, password: 'Password1' })
  })

  it('patches only what changed and the role together with its scope', () => {
    const initial = userFormValues(district)
    expect(userUpdateBody(initial, { ...initial, fullName: 'Петрова А. К.' })).toEqual({ fullName: 'Петрова А. К.' })
    expect(userUpdateBody(initial, { ...initial, regionId: 4 })).toEqual({ role: 'district', regionId: 4 })
    expect(userUpdateBody(initial, { ...initial, role: 'oblast' })).toEqual({ role: 'oblast' })
    expect(userUpdateBody(initial, initial)).toEqual({})
  })
})
