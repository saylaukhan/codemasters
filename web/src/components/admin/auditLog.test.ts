import { describe, expect, it } from 'vitest'

import { auditLogQuery, changeLines, isFiltered, readAuditLogView, writeAuditLogView } from './auditLog'

describe('logs of the administration', () => {
  it('keeps the filters in the URL and drops actions of the other tab', () => {
    const params = new URLSearchParams('q=admin&action=update&action=transfer_error&from=2026-09-10&to=2026-09-12')
    const view = readAuditLogView(params, 'audit')
    expect(view).toEqual({ q: 'admin', actions: ['update'], days: ['2026-09-10', '2026-09-12'], page: 1, pageSize: 25 })
    expect(readAuditLogView(writeAuditLogView(new URLSearchParams(), view), 'audit')).toEqual(view)
    expect(readAuditLogView(new URLSearchParams('from=2026-09-12&to=2026-09-10'), 'audit').days).toBeUndefined()
  })

  it('asks for the actions of the tab and whole days of the period', () => {
    const view = readAuditLogView(new URLSearchParams('from=2026-09-10&to=2026-09-12'), 'events')
    const query = auditLogQuery(view, 'events')
    expect(query.action).toEqual(['transfer_error'])
    expect(query.q).toBeUndefined()
    expect(new Date(query.periodTo as string).getTime() - new Date(query.periodFrom as string).getTime()).toBe(
      3 * 24 * 3600 * 1000,
    )
    expect(auditLogQuery({ ...view, days: undefined }, 'audit').action).toContain('login_failure')
    expect(isFiltered(view)).toBe(true)
    expect(isFiltered({ ...view, days: undefined })).toBe(false)
  })

  it('shows the changed fields with their labels', () => {
    expect(
      changeLines({ isActive: { old: true, new: false }, name: { old: null, new: 'Школа № 1' }, slots: { new: [1] } }),
    ).toEqual([
      { field: 'Активен', old: 'да', new: 'нет' },
      { field: 'Название', old: 'пусто', new: 'Школа № 1' },
      { field: 'Слоты', old: 'пусто', new: '[1]' },
    ])
    expect(changeLines(null)).toEqual([])
  })
})
