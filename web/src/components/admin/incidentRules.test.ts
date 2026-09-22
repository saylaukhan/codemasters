import { describe, expect, it } from 'vitest'

import type { IncidentRuleDetail } from '../../api/types'
import {
  formatOpening,
  formatRecovery,
  formatTarget,
  incidentRuleCreateBody,
  incidentRuleFormValues,
  incidentRuleUpdateBody,
} from './incidentRules'

const noConnection: IncidentRuleDetail = {
  id: 6,
  name: 'Нет соединения',
  metric: 'no_connection',
  scope: 'global',
  schoolId: null,
  schoolCode: null,
  schoolName: null,
  consecutiveViolations: 3,
  durationMin: 30,
  recoveryNormalCount: 2,
  isActive: true,
}

const satellite: IncidentRuleDetail = {
  ...noConnection,
  id: 7,
  name: 'Ping по спутнику',
  metric: 'ping_ms',
  scope: 'school',
  schoolId: 42,
  schoolCode: 'VKO-UK-042',
  schoolName: 'Школа № 42',
}

describe('formatting', () => {
  it('writes the conditions that open an incident', () => {
    expect(formatOpening({ consecutiveViolations: 3, durationMin: 30 })).toBe('3 подряд или 30 мин')
    expect(formatOpening({ consecutiveViolations: 3, durationMin: null })).toBe('3 подряд')
    expect(formatOpening({ consecutiveViolations: null, durationMin: 30 })).toBe('30 мин')
  })

  it('names the school of a rule and the oblast of a global one', () => {
    expect(formatTarget(satellite)).toBe('Школа № 42 · VKO-UK-042')
    expect(formatTarget(noConnection)).toBe('Все школы без своего правила')
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
        scope: 'global',
        consecutiveViolations: 3,
        durationMin: null,
        recoveryNormalCount: 2,
        isActive: true,
      }),
    ).toEqual({
      name: 'Ping выше порога',
      metric: 'ping_ms',
      scope: 'global',
      schoolId: null,
      consecutiveViolations: 3,
      durationMin: null,
      recoveryNormalCount: 2,
    })
  })

  it('sends the school of a school rule and drops a school picked for a global one', () => {
    const values = { ...incidentRuleFormValues(satellite), school: { value: 42, label: 'VKO-UK-042 · Школа № 42' } }
    expect(incidentRuleCreateBody(values)).toMatchObject({ scope: 'school', schoolId: 42 })
    expect(incidentRuleCreateBody({ ...values, scope: 'global' })).toMatchObject({ scope: 'global', schoolId: null })
    expect(incidentRuleFormValues(satellite).school).toEqual({ value: 42, label: 'VKO-UK-042 · Школа № 42' })
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
