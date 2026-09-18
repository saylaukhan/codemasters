import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'

import {
  basisCaption,
  durationCaption,
  eventAuthor,
  eventCaption,
  formatMetricValue,
  incidentCreateBody,
  incidentListQuery,
  isFiltered,
  readIncidentListView,
  writeIncidentListView,
} from './incidents'

const NBSP = '\u00a0'

describe('view of the incident list', () => {
  it('reads the statuses in the order of ТЗ п. 19 and drops unknown ones', () => {
    const view = readIncidentListView(new URLSearchParams('status=resolved&status=new&status=lost&q=INC&page=2'))
    expect(view).toEqual({ statuses: ['new', 'resolved'], q: 'INC', days: undefined, page: 2, pageSize: 25 })
    expect(isFiltered(view)).toBe(true)
  })

  it('falls back to the first page and the default size', () => {
    const view = readIncidentListView(new URLSearchParams('page=-1&page_size=33&from=2026-09-10&to=2026-09-01'))
    expect(view).toEqual({ statuses: [], q: '', days: undefined, page: 1, pageSize: 25 })
    expect(isFiltered(view)).toBe(false)
  })

  it('writes the view back next to the other parameters', () => {
    const params = writeIncidentListView(new URLSearchParams('status=new&other=1'), {
      statuses: ['in_progress', 'awaiting_info'],
      q: '',
      days: ['2026-09-01', '2026-09-10'],
      page: 1,
      pageSize: 50,
    })
    expect(params.getAll('status')).toEqual(['in_progress', 'awaiting_info'])
    expect(params.get('other')).toBe('1')
    expect(params.get('q')).toBeNull()
    expect(readIncidentListView(params).days).toEqual(['2026-09-01', '2026-09-10'])
  })

  it('asks the API for whole days, the end exclusive', () => {
    const days: [string, string] = ['2026-09-01', '2026-09-01']
    const query = incidentListQuery({ statuses: ['new'], q: ' 12 ', days, page: 1, pageSize: 25 })
    expect(query.status).toEqual(['new'])
    expect(query.q).toBe('12')
    expect(dayjs(query.periodTo as string).diff(dayjs(query.periodFrom as string), 'hour')).toBe(24)
    expect(incidentListQuery({ statuses: [], q: '  ', page: 1, pageSize: 25 }).q).toBeUndefined()
  })
})

describe('captions of an incident', () => {
  it('writes the value of a metric in its unit', () => {
    expect(formatMetricValue('download_mbps', 8.4)).toBe(`8,4${NBSP}Мбит/с`)
    expect(formatMetricValue('ping_ms', 180)).toBe(`180${NBSP}мс`)
    expect(formatMetricValue('packet_loss_pct', 12)).toBe('12%')
    expect(formatMetricValue('no_connection', null)).toBe('—')
    expect(formatMetricValue('upload_mbps', null)).toBe('—')
  })

  it('lists the basis metrics', () => {
    expect(basisCaption([{ metric: 'download_mbps' }, { metric: 'no_connection' }])).toBe('Download, Нет соединения')
    expect(basisCaption([])).toBe('—')
  })

  it('shows the duration, or the time since the start while it goes on', () => {
    const startedAt = '2026-09-12T10:00:00Z'
    expect(durationCaption({ durationS: 4 * 3600 + 12 * 60, startedAt })).toBe(`4${NBSP}ч 12${NBSP}мин`)
    expect(durationCaption({ durationS: null, startedAt }, new Date('2026-09-12T12:30:00Z'))).toBe(
      `идёт 2${NBSP}ч 30${NBSP}мин`,
    )
  })

  it('writes the history entries', () => {
    expect(eventCaption({ kind: 'status_change', fromStatus: 'new', toStatus: 'in_progress' })).toBe(
      'Статус: Новый → В работе',
    )
    expect(eventCaption({ kind: 'created', fromStatus: null, toStatus: 'new' })).toBe('Инцидент создан')
    expect(eventCaption({ kind: 'restored', fromStatus: null, toStatus: null })).toBe('Показатели восстановлены')
    expect(eventAuthor({ authorUserId: null, authorUserName: null })).toBe('Система')
    expect(eventAuthor({ authorUserId: 3, authorUserName: 'Иванов И.' })).toBe('Иванов И.')
  })
})

describe('manual incident', () => {
  it('sends the author as responsible only when asked', () => {
    const values = {
      lineId: 4,
      metrics: ['download_mbps' as const],
      description: '  Скорость упала  ',
      startedAt: dayjs('2026-09-12T10:00:00Z'),
      responsible: true,
    }
    expect(incidentCreateBody(values, 7)).toEqual({
      lineId: 4,
      metrics: ['download_mbps'],
      description: 'Скорость упала',
      startedAt: '2026-09-12T10:00:00.000Z',
      responsibleUserId: 7,
    })
    expect(incidentCreateBody({ ...values, responsible: false, startedAt: null }, 7)).toMatchObject({
      startedAt: null,
      responsibleUserId: null,
    })
  })
})
