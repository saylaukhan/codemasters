import { describe, expect, it } from 'vitest'

import type { AppealContext } from '../../api/types'
import {
  appealCreateBody,
  appealEventCaption,
  appealListQuery,
  appealTargetQuery,
  appealTargets,
  canCreateAppeal,
  canUpdateAppeal,
  contractCaption,
  fallbackDraft,
  incidentAppealTarget,
  isAppealFiltered,
  metricRows,
  periodCaption,
  readAppealListView,
  readAppealTarget,
  schoolAppealTarget,
  writeAppealListView,
} from './appeals'

const NOW = new Date('2026-09-13T09:00:00Z')

describe('target of an appeal', () => {
  it('takes the period of an incident from its start to its restoring', () => {
    const incident = { id: 12, startedAt: '2026-09-12T10:00:00Z', restoredAt: '2026-09-12T14:30:00Z' }
    expect(incidentAppealTarget(incident, NOW)).toEqual({
      incidentId: 12,
      periodFrom: '2026-09-12T10:00:00Z',
      periodTo: '2026-09-12T14:30:00Z',
    })
  })

  it('ends the period of an incident that goes on at the current moment', () => {
    const target = incidentAppealTarget({ id: 12, startedAt: '2026-09-12T10:00:00Z', restoredAt: null }, NOW)
    expect(target.periodTo).toBe('2026-09-13T09:00:00.000Z')
  })

  it('takes the last week for a line of a school', () => {
    expect(schoolAppealTarget(4, 7, NOW)).toEqual({
      schoolId: 4,
      lineId: 7,
      periodFrom: '2026-09-06T09:00:00.000Z',
      periodTo: '2026-09-13T09:00:00.000Z',
    })
  })
})

describe('address of the editor', () => {
  it('carries an incident there and back', () => {
    const target = incidentAppealTarget({ id: 12, startedAt: '2026-09-12T10:00:00Z', restoredAt: null }, NOW)
    const params = appealTargetQuery(target)
    expect(params.get('incident_id')).toBe('12')
    expect(params.get('school_id')).toBeNull()
    expect(readAppealTarget(params)).toEqual({
      incidentId: 12,
      periodFrom: '2026-09-12T10:00:00.000Z',
      periodTo: '2026-09-13T09:00:00.000Z',
    })
  })

  it('carries a line of a school there and back', () => {
    expect(readAppealTarget(appealTargetQuery(schoolAppealTarget(4, 7, NOW)))).toEqual({
      schoolId: 4,
      lineId: 7,
      periodFrom: '2026-09-06T09:00:00.000Z',
      periodTo: '2026-09-13T09:00:00.000Z',
    })
  })

  it('has no target without a whole one', () => {
    const period = 'period_from=2026-09-12T10:00:00Z&period_to=2026-09-13T09:00:00Z'
    expect(readAppealTarget(new URLSearchParams())).toBeNull()
    expect(readAppealTarget(new URLSearchParams(period))).toBeNull()
    expect(readAppealTarget(new URLSearchParams(`school_id=4&${period}`))).toBeNull()
    expect(readAppealTarget(new URLSearchParams(`incident_id=0&${period}`))).toBeNull()
    expect(readAppealTarget(new URLSearchParams('incident_id=12'))).toBeNull()
  })

  it('has no target when the period is unreadable or turned around', () => {
    expect(readAppealTarget(new URLSearchParams('incident_id=12&period_from=вчера&period_to=сегодня'))).toBeNull()
    const turned = 'incident_id=12&period_from=2026-09-13T09:00:00Z&period_to=2026-09-12T10:00:00Z'
    expect(readAppealTarget(new URLSearchParams(turned))).toBeNull()
  })

  it('reads a target of the school card even when the incident is named empty', () => {
    const params = new URLSearchParams(
      'incident_id=&school_id=4&line_id=7&period_from=2026-09-06T09:00:00Z&period_to=2026-09-13T09:00:00Z',
    )
    expect(readAppealTarget(params)).toMatchObject({ schoolId: 4, lineId: 7 })
  })
})

// Facts of plan.md §8 as the server sends them; the contacts of the school are not among them (ADR-011).
const context: AppealContext = {
  incidentId: null,
  incidentNumber: null,
  schoolId: 4,
  schoolCode: 'VKO-001',
  schoolName: 'Школа № 1',
  lineId: 7,
  lineIdentifier: 'L-77',
  providerId: 2,
  providerName: 'Казахтелеком',
  contractNumber: '12/2026',
  contractDate: '2026-01-12',
  contractDownMbps: 50,
  contractUpMbps: 50,
  periodFrom: '2026-09-06T09:00:00Z',
  periodTo: '2026-09-13T09:00:00Z',
  measurementsCount: 28,
  problemCount: 9,
  downloadMbps: { avg: 8.4, min: 1.2, max: 22 },
  uploadMbps: null,
  pingMs: { avg: 180, min: 40, max: 400 },
  jitterMs: null,
  packetLossPct: { avg: 12, min: 0, max: 40 },
  thresholds: {
    downloadMinMbps: 20,
    uploadMinMbps: 20,
    pingMaxMs: 100,
    jitterMaxMs: 30,
    packetLossMaxPct: 2,
  },
  outagesCount: 3,
  outagesDurationS: 4800,
}

describe('facts of an appeal', () => {
  it('puts the average of every metric next to its threshold', () => {
    expect(metricRows(context)).toEqual([
      { metric: 'download_mbps', value: 8.4, threshold: 20 },
      { metric: 'upload_mbps', value: null, threshold: 20 },
      { metric: 'ping_ms', value: 180, threshold: 100 },
      { metric: 'jitter_ms', value: null, threshold: 30 },
      { metric: 'packet_loss_pct', value: 12, threshold: 2 },
    ])
  })

  it('writes the contract and the period', () => {
    expect(contractCaption(context)).toBe('№ 12/2026 от 12.01.2026')
    expect(contractCaption({ contractNumber: null, contractDate: null })).toBe('—')
    expect(contractCaption({ contractNumber: null, contractDate: '2026-01-12' })).toBe('от 12.01.2026')
    // Asia/Almaty: the period of the facts is shown in the zone of the panel (ADR-014).
    expect(periodCaption(context.periodFrom, context.periodTo)).toBe('06.09.2026 14:00 — 13.09.2026 14:00')
  })
})

describe('draft that did not arrive', () => {
  it('opens the editor with a template holding the period', () => {
    const template = fallbackDraft(schoolAppealTarget(4, 7, NOW))
    expect(template.subject).not.toBe('')
    expect(template.text).toContain('06.09.2026 14:00 — 13.09.2026 14:00')
  })
})

describe('right to write to a provider', () => {
  it('follows the permission of the API, not the role', () => {
    expect(canCreateAppeal({ permissions: ['appeals:read', 'appeals:create'] })).toBe(true)
    expect(canCreateAppeal({ permissions: ['appeals:read'] })).toBe(false)
    expect(canCreateAppeal(undefined)).toBe(false)
  })
})

describe('view of the appeal list', () => {
  it('reads the statuses in the order of ТЗ п. 19 and drops unknown ones', () => {
    const view = readAppealListView(new URLSearchParams('status=resolved&status=new&status=lost&q=ОБР&page=2'))
    expect(view).toEqual({ statuses: ['new', 'resolved'], q: 'ОБР', page: 2, pageSize: 25 })
    expect(isAppealFiltered(view)).toBe(true)
  })

  it('falls back to the first page and the default size', () => {
    const view = readAppealListView(new URLSearchParams('page=-1&page_size=33'))
    expect(view).toEqual({ statuses: [], q: '', page: 1, pageSize: 25 })
    expect(isAppealFiltered(view)).toBe(false)
  })

  it('writes the view back next to the other parameters', () => {
    const params = writeAppealListView(new URLSearchParams('status=new&other=1'), {
      statuses: ['in_progress', 'awaiting_info'],
      q: '',
      page: 1,
      pageSize: 50,
    })
    expect(params.getAll('status')).toEqual(['in_progress', 'awaiting_info'])
    expect(params.get('other')).toBe('1')
    expect(params.get('q')).toBeNull()
    expect(readAppealListView(params)).toEqual({
      statuses: ['in_progress', 'awaiting_info'],
      q: '',
      page: 1,
      pageSize: 50,
    })
  })

  it('asks the API only for what is filled in', () => {
    expect(appealListQuery({ statuses: ['new'], q: ' 45 ', page: 2, pageSize: 50 })).toEqual({
      status: ['new'],
      q: '45',
      page: 2,
      pageSize: 50,
    })
    expect(appealListQuery({ statuses: [], q: '  ', page: 1, pageSize: 25 }).q).toBeUndefined()
  })
})

describe('sending an appeal', () => {
  it('sends the target of the editor with the letter as the person left it', () => {
    const target = incidentAppealTarget({ id: 12, startedAt: '2026-09-12T10:00:00Z', restoredAt: null }, NOW)
    expect(appealCreateBody(target, { subject: ' Тема ', text: ' Письмо ', comment: '  ' })).toEqual({
      incidentId: 12,
      periodFrom: '2026-09-12T10:00:00Z',
      periodTo: '2026-09-13T09:00:00.000Z',
      subject: 'Тема',
      text: 'Письмо',
      userComment: null,
    })
    expect(appealCreateBody(target, { subject: 'Тема', text: 'Письмо', comment: ' Срочно ' }).userComment).toBe(
      'Срочно',
    )
  })
})

describe('statuses of an appeal', () => {
  it('offers the transitions of an incident and keeps «Закрыт» for the closing roles', () => {
    const provider = { role: 'provider' as const, permissions: ['appeals:read', 'appeals:update'] }
    expect(appealTargets('resolved', provider)).toEqual(['in_progress'])
    expect(appealTargets('resolved', { role: 'district', permissions: ['appeals:update'] })).toEqual([
      'in_progress',
      'closed',
    ])
    expect(appealTargets('closed', provider)).toEqual([])
    expect(appealTargets('new', { role: 'school', permissions: ['appeals:read'] })).toEqual([])
    expect(canUpdateAppeal(provider)).toBe(true)
    expect(canCreateAppeal(provider)).toBe(false)
  })

  it('writes the history entries', () => {
    expect(appealEventCaption({ status: 'sent_to_provider' })).toBe('Статус: Передан поставщику')
    expect(appealEventCaption({ status: null })).toBe('Комментарий')
  })
})
