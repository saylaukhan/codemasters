import dayjs from 'dayjs'
import { describe, expect, it } from 'vitest'

import { ApiError } from '../../api/client'
import type { LineDetail, SchoolContactDetail } from '../../api/types'
import { formErrors } from './form'
import {
  cidrList,
  contactFormValues,
  contactUpdateBody,
  lineCreateBody,
  lineFormValues,
  lineUpdateBody,
  pointCreateBody,
  pointFormValues,
  splitRanges,
} from './schoolSetupForm'

const LINE = {
  id: 5,
  providerId: 2,
  providerName: 'Казахтелеком',
  connectionTypeId: null,
  status: 'main',
  lineIdentifier: 'ACC-42',
  contractDownMbps: 50,
  contractUpMbps: null,
  contractNumber: 'Д-17',
  contractDate: '2026-01-15',
  ipRanges: ['203.0.113.0/24'],
} as LineDetail

const checkRanges = (value: string) =>
  (cidrList as { validator: (rule: unknown, value: string) => Promise<void> }).validator({}, value)

describe('line form', () => {
  it('starts a new line with the given status and sends the contract as the API takes it', () => {
    const values = {
      ...lineFormValues(undefined, 'reserve'),
      providerId: 3,
      contractDownMbps: 20,
      contractNumber: '  ',
      contractDate: dayjs('2026-02-01'),
      ipRanges: '203.0.113.0/24,  198.51.100.0/24\n',
    }

    expect(values.status).toBe('reserve')
    expect(lineCreateBody(values)).toEqual({
      providerId: 3,
      connectionTypeId: null,
      status: 'reserve',
      lineIdentifier: null,
      contractDownMbps: 20,
      contractUpMbps: null,
      contractNumber: null,
      contractDate: '2026-02-01',
      ipRanges: ['203.0.113.0/24', '198.51.100.0/24'],
    })
  })

  it('sends only the changed fields of a line; a cleared date is null', () => {
    const initial = lineFormValues(LINE, 'reserve')

    expect(initial.ipRanges).toBe('203.0.113.0/24')
    expect(lineUpdateBody(initial, { ...initial, status: 'disabled', contractDate: null })).toEqual({
      status: 'disabled',
      contractDate: null,
    })
    expect(lineUpdateBody(initial, { ...initial })).toEqual({})
  })

  it('accepts CIDR ranges only', async () => {
    expect(splitRanges(null)).toEqual([])
    await expect(checkRanges('203.0.113.0/24; 2001:db8::/32')).resolves.toBeUndefined()
    await expect(checkRanges('203.0.113.7')).rejects.toThrow('CIDR')
  })

  it('shows a second main line under the status', () => {
    const error = new ApiError({ status: 409, type: 'main_line_exists', title: 'Конфликт', detail: 'Основная уже есть' })

    expect(formErrors(error, ['status', 'providerId'])).toEqual({
      fields: [{ name: 'status', errors: ['Основная уже есть'] }],
      alert: false,
    })
  })
})

describe('point and contact forms', () => {
  it('puts a new point on the given line and trims its texts', () => {
    expect(pointCreateBody({ ...pointFormValues(undefined, 5), name: ' Кабинет 214 ', room: ' ' })).toEqual({
      name: 'Кабинет 214',
      room: null,
      lineId: 5,
      isPrimary: false,
    })
  })

  it('sends only the changed fields of a contact', () => {
    const initial = contactFormValues({
      id: 1,
      fullName: 'Иванова А. Б.',
      position: null,
      phone: '+7 700 000 00 00',
      email: null,
      providerSupportContact: null,
    } as SchoolContactDetail)

    expect(contactUpdateBody(initial, { ...initial, phone: '', position: 'Учитель' })).toEqual({
      position: 'Учитель',
      phone: null,
    })
  })
})
