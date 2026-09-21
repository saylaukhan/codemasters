import { describe, expect, it } from 'vitest'

import type { IncidentStatus, UserRole } from '../../api/types'
import { INCIDENT_STATUS_ORDER } from '../../lib/labels'
import {
  allowedTargets,
  canClose,
  canMove,
  commentRequired,
  INCIDENT_TRANSITIONS,
  isTransition,
  targetsHint,
} from './transitions'

// The table of T-41 written out pair by pair: every other pair of the 36 is refused.
const ALLOWED = new Set([
  'new→sent_to_provider',
  'new→in_progress',
  'new→awaiting_info',
  'new→resolved',
  'sent_to_provider→in_progress',
  'sent_to_provider→awaiting_info',
  'sent_to_provider→resolved',
  'in_progress→awaiting_info',
  'in_progress→resolved',
  'awaiting_info→in_progress',
  'awaiting_info→resolved',
  'resolved→in_progress',
  'resolved→closed',
])

const user = (role: UserRole, permissions = ['incidents:read', 'incidents:update']) => ({ role, permissions })

describe('table of transitions', () => {
  it('allows exactly the transitions of T-41', () => {
    for (const from of INCIDENT_STATUS_ORDER) {
      for (const to of INCIDENT_STATUS_ORDER) {
        expect(isTransition(from, to), `${from} → ${to}`).toBe(ALLOWED.has(`${from}→${to}`))
      }
    }
  })

  it('keeps the targets in the order of ТЗ п. 19', () => {
    for (const from of INCIDENT_STATUS_ORDER) {
      const targets = INCIDENT_TRANSITIONS[from]
      const order = targets.map((to) => INCIDENT_STATUS_ORDER.indexOf(to))
      expect(order).toEqual([...order].sort((a, b) => a - b))
    }
  })

  it('never stays in the same status and never leaves «Закрыт»', () => {
    for (const status of INCIDENT_STATUS_ORDER) expect(isTransition(status, status)).toBe(false)
    expect(INCIDENT_TRANSITIONS.closed).toEqual([])
  })
})

describe('targets of a user', () => {
  it('offers «Закрыт» only to Район/город, Область and Администратор', () => {
    expect(canClose('district')).toBe(true)
    expect(canClose('oblast')).toBe(true)
    expect(canClose('admin')).toBe(true)
    expect(canClose('provider')).toBe(false)
    expect(canClose('school')).toBe(false)
    expect(canClose(undefined)).toBe(false)

    expect(allowedTargets('resolved', user('oblast'))).toEqual(['in_progress', 'closed'])
    expect(allowedTargets('resolved', user('provider'))).toEqual(['in_progress'])
    expect(canMove('resolved', 'closed', user('provider'))).toBe(false)
    expect(canMove('resolved', 'closed', user('district'))).toBe(true)
  })

  it('offers nothing without incidents:update', () => {
    const readOnly: IncidentStatus[] = allowedTargets('new', user('school', ['incidents:read']))
    expect(readOnly).toEqual([])
    expect(allowedTargets('new', undefined)).toEqual([])
    expect(canMove('new', 'in_progress', user('admin', []))).toBe(false)
  })

  it('offers the whole row of the table to a closing role', () => {
    for (const from of INCIDENT_STATUS_ORDER) {
      expect(allowedTargets(from, user('admin'))).toEqual(INCIDENT_TRANSITIONS[from])
    }
    expect(allowedTargets('closed', user('admin'))).toEqual([])
  })

  it('requires a comment only to close', () => {
    expect(INCIDENT_STATUS_ORDER.filter(commentRequired)).toEqual(['closed'])
    expect(commentRequired(undefined)).toBe(false)
  })
})

describe('hint of the available transitions', () => {
  it('names the targets in the order of ТЗ п. 19', () => {
    expect(targetsHint(allowedTargets('sent_to_provider', user('admin')))).toBe(
      'Доступно: В работе, Ожидает информации, Устранён',
    )
    expect(targetsHint(allowedTargets('resolved', user('oblast')))).toBe('Доступно: В работе, Закрыт')
    expect(targetsHint(allowedTargets('resolved', user('provider')))).toBe('Доступно: В работе')
  })

  it('says so when nothing is available', () => {
    expect(targetsHint([])).toBe('Из этого статуса переходов нет')
    expect(targetsHint(allowedTargets('closed', user('admin')))).toBe('Из этого статуса переходов нет')
    expect(targetsHint(allowedTargets('new', user('school', ['incidents:read'])))).toBe(
      'Из этого статуса переходов нет',
    )
  })
})
