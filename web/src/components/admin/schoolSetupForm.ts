// Forms of the lines, monitoring points and contacts of a school (T-35): values of the form ↔ bodies of the API.
import type { FormRule } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'

import type {
  LineCreate,
  LineDetail,
  LineStatus,
  LineUpdate,
  MonitoringPointCreate,
  MonitoringPointDetail,
  MonitoringPointUpdate,
  SchoolContactCreate,
  SchoolContactDetail,
  SchoolContactUpdate,
} from '../../api/types'
import { changedFields, optionalText } from './form'

// --- Lines ---------------------------------------------------------------------------------------

export interface LineFormValues {
  providerId?: number
  connectionTypeId: number | null
  status: LineStatus
  lineIdentifier: string | null
  contractDownMbps: number | null
  contractUpMbps: number | null
  contractNumber: string | null
  contractDate: Dayjs | null
  /** External IP ranges in one field: CIDR separated by commas, spaces or new lines. */
  ipRanges: string | null
}

/** Values of the line form; a new line is `status` — main when the school has none yet, otherwise reserve. */
export const lineFormValues = (line: LineDetail | undefined, status: LineStatus): LineFormValues => ({
  providerId: line?.providerId,
  connectionTypeId: line?.connectionTypeId ?? null,
  status: line?.status ?? status,
  lineIdentifier: line?.lineIdentifier ?? null,
  contractDownMbps: line?.contractDownMbps ?? null,
  contractUpMbps: line?.contractUpMbps ?? null,
  contractNumber: line?.contractNumber ?? null,
  contractDate: line?.contractDate ? dayjs(line.contractDate) : null,
  ipRanges: line?.ipRanges.join(', ') || null,
})

export const splitRanges = (text: string | null | undefined): string[] =>
  text?.split(/[\s,;]+/).filter(Boolean) ?? []

// An address with a prefix length; the API checks the rest (host bits, the range of the prefix).
const CIDR = /^[\da-f:.]+\/\d{1,3}$/i

export const cidrList: FormRule = {
  validator: (_, value: string | null | undefined) =>
    splitRanges(value).every((range) => CIDR.test(range))
      ? Promise.resolve()
      : Promise.reject(new Error('Диапазоны в формате CIDR через запятую, например 203.0.113.0/24')),
}

/** Body of POST /api/schools/{id}/lines; `providerId` is required by the form before it submits. */
export const lineCreateBody = (values: LineFormValues): LineCreate => ({
  providerId: values.providerId as number,
  connectionTypeId: values.connectionTypeId ?? null,
  status: values.status,
  lineIdentifier: optionalText(values.lineIdentifier),
  contractDownMbps: values.contractDownMbps ?? null,
  contractUpMbps: values.contractUpMbps ?? null,
  contractNumber: optionalText(values.contractNumber),
  contractDate: values.contractDate?.format('YYYY-MM-DD') ?? null,
  ipRanges: splitRanges(values.ipRanges),
})

/** Body of PATCH /api/schools/{id}/lines/{lineId}: the changed fields only; a cleared one is `null`. */
export const lineUpdateBody = (initial: LineFormValues, values: LineFormValues): LineUpdate =>
  changedFields<LineUpdate>(lineCreateBody(initial), lineCreateBody(values))

// --- Monitoring points ---------------------------------------------------------------------------

export interface PointFormValues {
  name: string
  room: string | null
  lineId?: number
  isPrimary: boolean
}

/** Values of the point form; a new point is on `lineId` — the main line when there is one. */
export const pointFormValues = (point: MonitoringPointDetail | undefined, lineId?: number): PointFormValues => ({
  name: point?.name ?? '',
  room: point?.room ?? null,
  lineId: point?.lineId ?? lineId,
  isPrimary: point?.isPrimary ?? false,
})

/** Body of POST /api/schools/{id}/points; `lineId` is required by the form before it submits. */
export const pointCreateBody = (values: PointFormValues): MonitoringPointCreate => ({
  name: values.name.trim(),
  room: optionalText(values.room),
  lineId: values.lineId as number,
  isPrimary: values.isPrimary,
})

export const pointUpdateBody = (initial: PointFormValues, values: PointFormValues): MonitoringPointUpdate =>
  changedFields<MonitoringPointUpdate>(pointCreateBody(initial), pointCreateBody(values))

// --- Contacts ------------------------------------------------------------------------------------

export interface ContactFormValues {
  fullName: string
  position: string | null
  phone: string | null
  email: string | null
  providerSupportContact: string | null
}

export const contactFormValues = (contact?: SchoolContactDetail): ContactFormValues => ({
  fullName: contact?.fullName ?? '',
  position: contact?.position ?? null,
  phone: contact?.phone ?? null,
  email: contact?.email ?? null,
  providerSupportContact: contact?.providerSupportContact ?? null,
})

export const contactCreateBody = (values: ContactFormValues): SchoolContactCreate => ({
  fullName: values.fullName.trim(),
  position: optionalText(values.position),
  phone: optionalText(values.phone),
  email: optionalText(values.email),
  providerSupportContact: optionalText(values.providerSupportContact),
})

/** Body of PATCH: the changed fields only; `updatedAt` is set by the server. */
export const contactUpdateBody = (initial: ContactFormValues, values: ContactFormValues): SchoolContactUpdate =>
  changedFields<SchoolContactUpdate>(contactCreateBody(initial), contactCreateBody(values))
