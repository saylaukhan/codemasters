// Devices of the administration (T-36): the status filter of the list and the options of the rebinding form.
import type { DeviceDetail, DeviceStatus, MonitoringPointDetail, SchoolListItem } from '../../api/types'

/** The status filter lives in `isActive` of the list view: true — active, false — blocked, none — all. */
export const deviceStatusOf = (isActive: boolean | undefined): DeviceStatus | undefined =>
  isActive === undefined ? undefined : isActive ? 'active' : 'blocked'

/** A computer by its name, by the identifier of its agent when the name is unknown. */
export const deviceName = (device: Pick<DeviceDetail, 'hostname' | 'deviceUid'>): string =>
  device.hostname ?? device.deviceUid

/** A school in the select: School ID first, as it is searched. */
export const schoolOption = (school: Pick<SchoolListItem, 'id' | 'schoolCode' | 'fullName'>) => ({
  value: school.id,
  label: `${school.schoolCode} · ${school.fullName}`,
})

/** A monitoring point in the select: its name and the room the agents of the point sit in. */
export const pointOption = (point: Pick<MonitoringPointDetail, 'id' | 'name' | 'room'>) => ({
  value: point.id,
  label: point.room ? `${point.name} · каб. ${point.room}` : point.name,
})
