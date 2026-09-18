import { useNotification } from '@refinedev/core'
import { Checkbox, Form, Segmented, Select, TimePicker } from 'antd'
import { Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'

import type { ScheduleCreate, ScheduleDetail, ScheduleUpdate } from '../../api/types'
import { SCHEDULE_SCOPE_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import { Button } from '../ui/Button'
import styles from './Admin.module.css'
import { FormDrawer } from './FormDrawer'
import { changedFields } from './form'
import { overlappingSlots, rangeOf, slotOf, type TimeRange } from './hours'
import { useRegionOptions, useSaveSchedule, useSchoolOptions } from './queries'

type Target = 'district' | 'school'

interface ScheduleValues {
  scope: Target
  regionId?: number
  /** With its label: a school picked from one search stays named when the search changes. */
  school?: { value: number; label: string }
  slots: TimeRange[]
  isActive: boolean
}

// 3–5 measurements a day (ТЗ п. 2); the API checks the same.
const MIN_SLOTS = 3
const MAX_SLOTS = 5

// Errors of the school and of the slots go to the alert: the form has no field of those names.
const FIELDS = ['regionId', 'isActive']

const TARGET_OPTIONS = (['district', 'school'] as const).map((value) => ({
  value,
  label: SCHEDULE_SCOPE_LABELS[value],
}))

const updatableOf = (values: ScheduleValues): ScheduleUpdate => ({
  slots: values.slots.map(slotOf),
  isActive: values.isActive,
})

interface ScheduleDrawerProps {
  open: boolean
  /** The schedule being edited; none — a new one of a district or a school. */
  schedule?: ScheduleDetail
  /** Slots a new schedule starts from: those of the global schedule. */
  base?: ScheduleDetail
  onClose: () => void
}

/**
 * Schedule of measurements (ТЗ п. 2, п. 20): the agent measures at a random moment inside each slot and gets new
 * slots with its next configuration, without reinstalling.
 */
export function ScheduleDrawer({ open, schedule, base, onClose }: ScheduleDrawerProps) {
  const [form] = Form.useForm<ScheduleValues>()
  const save = useSaveSchedule()
  const { open: notify } = useNotification()
  const [search, setSearch] = useState('')
  const scope = Form.useWatch('scope', form) ?? 'district'
  const regions = useRegionOptions()
  const schools = useSchoolOptions(search)
  const [initial] = useState<ScheduleValues>(() => ({
    scope: 'district',
    slots: ((schedule ?? base)?.slots ?? []).map(rangeOf),
    isActive: schedule?.isActive ?? true,
  }))

  const submit = (values: ScheduleValues) => {
    const done = () => {
      notify?.({ type: 'success', message: schedule ? 'Расписание изменено' : 'Расписание добавлено' })
      onClose()
    }
    if (!schedule) {
      const body: ScheduleCreate = {
        scope: values.scope,
        regionId: values.scope === 'district' ? values.regionId : null,
        schoolId: values.scope === 'school' ? values.school?.value : null,
        slots: values.slots.map(slotOf),
      }
      return save.mutate({ body }, { onSuccess: done })
    }
    const body = changedFields(updatableOf(initial), updatableOf(values))
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: schedule.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={schedule ? 'Изменить расписание' : 'Новое расписание'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<ScheduleValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        {schedule ? (
          <Form.Item label={SCHEDULE_SCOPE_LABELS[schedule.scope]}>
            {schedule.scope === 'global'
              ? 'Действует, пока у района и школы нет своего расписания'
              : (schedule.regionName ?? schedule.schoolName)}
          </Form.Item>
        ) : (
          <>
            <Form.Item label="Для чего расписание" name="scope">
              <Segmented options={TARGET_OPTIONS} />
            </Form.Item>
            {scope === 'district' ? (
              <Form.Item
                label="Район или город"
                name="regionId"
                rules={[{ required: true, message: 'Выберите район или город' }]}
              >
                <Select<number>
                  placeholder="Выберите из списка"
                  options={regions.data}
                  loading={regions.isPending}
                  optionFilterProp="label"
                  showSearch
                />
              </Form.Item>
            ) : (
              <Form.Item label="Школа" name="school" rules={[{ required: true, message: 'Выберите школу' }]}>
                <Select<ScheduleValues['school']>
                  showSearch
                  labelInValue
                  filterOption={false}
                  placeholder="Поиск по School ID или названию"
                  options={schools.data}
                  loading={schools.isFetching}
                  onSearch={setSearch}
                />
              </Form.Item>
            )}
          </>
        )}
        <Form.List
          name="slots"
          rules={[
            {
              validator: (_, slots: (TimeRange | undefined)[] = []) => {
                if (slots.length < MIN_SLOTS || slots.length > MAX_SLOTS)
                  return Promise.reject(new Error(`Нужно от ${MIN_SLOTS} до ${MAX_SLOTS} слотов`))
                const filled = slots.filter((slot): slot is TimeRange => slot !== undefined)
                if (filled.length === slots.length && overlappingSlots(filled.map(slotOf)).length > 0)
                  return Promise.reject(new Error('Слоты не должны пересекаться'))
                return Promise.resolve()
              },
            },
          ]}
        >
          {(fields, { add, remove }, { errors }) => (
            <Form.Item label="Слоты замеров, Asia/Almaty" extra="Агент делает замер в случайный момент внутри слота.">
              {fields.map((field) => (
                <div key={field.key} className={styles.slot}>
                  <Form.Item
                    name={field.name}
                    noStyle
                    rules={[
                      { required: true, message: 'Укажите начало и конец слота' },
                      {
                        validator: (_, value: TimeRange | undefined) =>
                          value && !value[1].isAfter(value[0])
                            ? Promise.reject(new Error('Конец слота должен быть позже начала'))
                            : Promise.resolve(),
                      },
                    ]}
                  >
                    <TimePicker.RangePicker format="HH:mm" minuteStep={5} allowClear={false} />
                  </Form.Item>
                  <Button
                    kind="flat"
                    tooltip="Убрать слот"
                    disabled={fields.length <= MIN_SLOTS}
                    icon={<Trash2 size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
                    onClick={() => remove(field.name)}
                  />
                </div>
              ))}
              {fields.length < MAX_SLOTS && (
                <Button
                  kind="outlined"
                  icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
                  onClick={() => add()}
                >
                  Добавить слот
                </Button>
              )}
              <Form.ErrorList errors={errors} />
            </Form.Item>
          )}
        </Form.List>
        {schedule && schedule.scope !== 'global' && (
          <Form.Item
            name="isActive"
            valuePropName="checked"
            extra="Отключённое расписание не удаляется: агенты получат следующее в цепочке школа → район → область."
          >
            <Checkbox>Расписание действует</Checkbox>
          </Form.Item>
        )}
      </Form>
    </FormDrawer>
  )
}
