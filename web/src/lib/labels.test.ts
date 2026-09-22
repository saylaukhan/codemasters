// T-66: the two dictionaries of the panel must stay the same shape. labels.kk.ts is generated
// from labels.ru.ts and then translated value by value, so a key added on one side only, a
// shortened array of forms or a string that turned into an object is the mistake to catch —
// labels.ts hands the Kazakh module to 92 modules typed after the Russian one.
import { describe, expect, it } from 'vitest'

import * as kk from './labels.kk'
import * as ru from './labels.ru'

type Value = unknown

const kind = (value: Value): string => (Array.isArray(value) ? 'array' : typeof value)

/** Every place where the two dictionaries differ in shape, as `EXPORT.key.key` paths. */
function differences(russian: Value, kazakh: Value, path: string): string[] {
  if (kind(russian) !== kind(kazakh)) {
    return [`${path}: ${kind(russian)} in labels.ru, ${kind(kazakh)} in labels.kk`]
  }
  if (Array.isArray(russian) && Array.isArray(kazakh)) {
    if (russian.length !== kazakh.length) {
      return [`${path}: ${russian.length} items in labels.ru, ${kazakh.length} in labels.kk`]
    }
    return russian.flatMap((item, index) => differences(item, kazakh[index], `${path}[${index}]`))
  }
  if (typeof russian !== 'object' || russian === null || typeof kazakh !== 'object' || kazakh === null) {
    return []
  }
  const left = russian as Record<string, Value>
  const right = kazakh as Record<string, Value>
  const missing = Object.keys(left)
    .filter((key) => !(key in right))
    .map((key) => `${path}.${key}: missing from labels.kk`)
  const extra = Object.keys(right)
    .filter((key) => !(key in left))
    .map((key) => `${path}.${key}: missing from labels.ru`)
  const common = Object.keys(left)
    .filter((key) => key in right)
    .flatMap((key) => differences(left[key], right[key], `${path}.${key}`))
  return [...missing, ...extra, ...common]
}

describe('dictionaries of the two languages', () => {
  it('export the same names', () => {
    expect(Object.keys(kk).sort()).toEqual(Object.keys(ru).sort())
  })

  it('match by key, array length and type of a value', () => {
    expect(differences(ru, kk, 'labels')).toEqual([])
  })

  it('catches the mismatch it is written for', () => {
    const withoutNormal: Record<string, string> = { ...ru.SCHOOL_STATUS_LABELS }
    delete withoutNormal.normal
    expect(differences(ru.SCHOOL_STATUS_LABELS, withoutNormal, 'SCHOOL_STATUS_LABELS')).toEqual([
      'SCHOOL_STATUS_LABELS.normal: missing from labels.kk',
    ])
    expect(differences(ru.SCHOOL_COUNT_FORMS, ['мектеп', 'мектеп'], 'SCHOOL_COUNT_FORMS')).toEqual([
      'SCHOOL_COUNT_FORMS: 3 items in labels.ru, 2 in labels.kk',
    ])
    expect(differences('Норма', { normal: 'Қалыпты' }, 'SYSTEM_AUTHOR_LABEL')).toEqual([
      'SYSTEM_AUTHOR_LABEL: string in labels.ru, object in labels.kk',
    ])
  })
})
