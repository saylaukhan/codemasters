import { useNotification } from '@refinedev/core'
import { Checkbox, Form, Input, InputNumber, Select, type FormInstance, type FormRule } from 'antd'
import { Suspense, lazy, useCallback, useState, type ReactNode } from 'react'

import type { GeoPoint, SchoolCreate, SchoolDetail, SchoolUpdate } from '../../api/types'
import { Button } from '../ui/Button'
import { ContentSkeleton } from '../ui/ContentSkeleton'
import { ErrorState } from '../ui/ErrorState'
import styles from './Admin.module.css'
import { FormDrawer } from './FormDrawer'
import {
  maxLength,
  pointOf,
  required,
  schoolCreateBody,
  schoolFormValues,
  schoolUpdateBody,
  type SchoolFormValues,
} from './form'
import { useRegionOptions, useSaveSchool, useSchoolToEdit, type Save } from './queries'
import { WorkingHoursFields } from './WorkingHoursFields'

// The map library is loaded when a school form is opened, not with the list.
const LocationPicker = lazy(() => import('./LocationPicker').then((module) => ({ default: module.LocationPicker })))

const FIELDS = ['schoolCode', 'fullName', 'regionId', 'address', 'lat', 'lon', 'isActive']

/** A point needs both coordinates: the empty one of the pair is marked. */
const pairedWith =
  (other: 'lat' | 'lon'): FormRule =>
  ({ getFieldValue }) => ({
    validator: (_, value: number | null | undefined) =>
      value == null && getFieldValue(other) != null
        ? Promise.reject(new Error('Нужны обе координаты'))
        : Promise.resolve(),
  })

type SchoolSave = Save<SchoolCreate, SchoolUpdate>

interface SchoolFormProps {
  form: FormInstance<SchoolFormValues>
  /** The school being edited; none — a new one. */
  school?: SchoolDetail
  /** `null` — nothing changed. */
  onSave: (save: SchoolSave | null) => void
}

function SchoolForm({ form, school, onSave }: SchoolFormProps) {
  const [initial] = useState(() => schoolFormValues(school))
  const regions = useRegionOptions()
  const lat = Form.useWatch('lat', form) ?? null
  const lon = Form.useWatch('lon', form) ?? null
  const setPoint = useCallback(
    (point: GeoPoint | null) =>
      form.setFields([
        { name: 'lat', value: point?.lat ?? null, errors: [] },
        { name: 'lon', value: point?.lon ?? null, errors: [] },
      ]),
    [form],
  )

  const finish = (values: SchoolFormValues) => {
    if (!school) return onSave({ body: schoolCreateBody(values) })
    const body = schoolUpdateBody(initial, values)
    onSave(Object.keys(body).length > 0 ? { id: school.id, body } : null)
  }

  return (
    <Form<SchoolFormValues> form={form} layout="vertical" initialValues={initial} onFinish={finish}>
      <Form.Item
        label="School ID"
        name="schoolCode"
        extra="От заказчика; если его нет — VKO-<код района>-<номер>."
        rules={[required('Введите School ID'), maxLength(64)]}
      >
        <Input className={styles.code} autoComplete="off" />
      </Form.Item>
      <Form.Item label="Полное название" name="fullName" rules={[required('Введите название школы'), maxLength(500)]}>
        <Input.TextArea autoSize={{ minRows: 1, maxRows: 3 }} />
      </Form.Item>
      <Form.Item
        label="Район или город"
        name="regionId"
        rules={[{ required: true, message: 'Выберите район или город' }]}
      >
        <Select<number>
          placeholder="Выберите из списка"
          options={regions.data}
          loading={regions.isPending}
          notFoundContent={regions.isError ? 'Список не загрузился, откройте форму ещё раз' : undefined}
          optionFilterProp="label"
          showSearch
        />
      </Form.Item>
      <Form.Item label="Адрес" name="address" rules={[maxLength(500)]}>
        <Input />
      </Form.Item>
      <div className={styles.point}>
        <div className={styles.coordinates}>
          <Form.Item label="Широта" name="lat" dependencies={['lon']} rules={[pairedWith('lon')]}>
            <InputNumber<number> className={styles.number} min={-90} max={90} step={0.0001} />
          </Form.Item>
          <Form.Item label="Долгота" name="lon" dependencies={['lat']} rules={[pairedWith('lat')]}>
            <InputNumber<number> className={styles.number} min={-180} max={180} step={0.0001} />
          </Form.Item>
        </div>
        <Suspense fallback={<div className={styles.picker} />}>
          <LocationPicker start={pointOf(initial)} lat={lat} lon={lon} onPick={setPoint} />
        </Suspense>
        <div className={styles.pointHint}>
          <span>Точка на карте: щёлкните по карте или введите координаты. Без точки школы нет на карте.</span>
          {lat != null && lon != null && (
            <Button kind="flat" size="small" onClick={() => setPoint(null)}>
              Убрать точку
            </Button>
          )}
        </div>
      </div>
      {school && (
        <WorkingHoursFields
          name={['workingHours']}
          extra="Простой и «Нет соединения» считаются только в рабочие часы: ночью ПК выключены — это не авария."
        />
      )}
      {school && (
        <Form.Item
          name="isActive"
          valuePropName="checked"
          extra="Школа не удаляется: история замеров и инцидентов сохраняется, включить её можно снова."
        >
          <Checkbox>Школа активна</Checkbox>
        </Form.Item>
      )}
    </Form>
  )
}

interface SchoolDrawerProps {
  open: boolean
  /** The school being edited; none — a new one. */
  schoolId?: number
  onClose: () => void
}

/** New school or a change of one (ТЗ п. 20): School ID, name, district, address, point, working hours, activity. */
export function SchoolDrawer({ open, schoolId, onClose }: SchoolDrawerProps) {
  const [form] = Form.useForm<SchoolFormValues>()
  const editing = schoolId !== undefined
  const school = useSchoolToEdit(schoolId)
  const save = useSaveSchool()
  const { open: notify } = useNotification()

  const submit = (next: SchoolSave | null) => {
    if (next === null) return onClose()
    save.mutate(next, {
      onSuccess: (saved) => {
        notify?.({
          type: 'success',
          message: editing ? 'Школа изменена' : 'Школа добавлена',
          description: saved.fullName,
        })
        onClose()
      },
    })
  }

  let content: ReactNode
  if (editing && school.isError) content = <ErrorState error={school.error} onRetry={() => void school.refetch()} />
  else if (editing && school.isPending) content = <ContentSkeleton rows={8} />
  else content = <SchoolForm form={form} school={school.data} onSave={submit} />

  return (
    <FormDrawer
      title={editing ? 'Изменить школу' : 'Новая школа'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
      ready={!editing || school.isSuccess}
    >
      {content}
    </FormDrawer>
  )
}
