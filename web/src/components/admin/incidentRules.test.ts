import { describe, expect, it } from 'vitest'

import type { IncidentRuleDetail } from '../../api/types'
import {
  formatOpening,
  formatRecovery,
  incidentRuleCreateBody,
  incidentRuleFormValues,
  incidentRuleUpdateBody,
} from './incidentRules'

const noConnection: IncidentRuleDetail = {
  id: 6,
  name: 'Нет соединения',
  metric: 'no_connection',
  consecutiveViolations: 3,
  durationMin: 30,
  recoveryNormalCount: 2,
  isActive: true,
}

describe('formatting', () => {
  it('writes the conditions that open an incident', () => {
    expect(formatOpening({ consecutiveViolations: 3, durationMin: 30 })).toBe('3 подряд или 30 мин')
    expect(formatOpening({ consecutiveViolations: 3, durationMin: null })).toBe('3 подряд')
    expect(formatOpening({ consecutiveViolations: null, durationMin: 30 })).toBe('30 мин')
  })

  it('writes the recovery in the right case', () => {
    expect(formatRecovery(2)).toBe('после 2 нормальных подряд')
    expect(formatRecovery(1)).toBe('после 1 нормального подряд')
    expect(formatRecovery(11)).toBe('после 11 нормальных подряд')
    expect(formatRecovery(21)).toBe('после 21 нормального подряд')
  })
})

describe('incident rules of the administration', () => {
  it('sends a new rule with an absent condition as null', () => {
    expect(
      incidentRuleCreateBody({
        name: ' Ping выше порога ',
        metric: 'ping_ms',
        consecutiveViolations: 3,
        durationMin: null,
        recoveryNormalCount: 2,
        isActive: true,
      }),
    ).toEqual({
      name: 'Ping выше порога',
      metric: 'ping_ms',
      consecutiveViolations: 3,
      durationMin: null,
      recoveryNormalCount: 2,
    })
  })

  it('patches only what changed and a cleared condition as null', () => {
    const initial = incidentRuleFormValues(noConnection)
    expect(incidentRuleUpdateBody(initial, { ...initial, durationMin: null })).toEqual({ durationMin: null })
    expect(incidentRuleUpdateBody(initial, { ...initial, consecutiveViolations: 4, isActive: false })).toEqual({
      consecutiveViolations: 4,
      isActive: false,
    })
    expect(incidentRuleUpdateBody(initial, { ...initial, name: 'Нет соединения ' })).toEqual({})
  })
})
