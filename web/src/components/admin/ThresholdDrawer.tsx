import { useNotification } from '@refinedev/core'
import { Checkbox, Form, InputNumber, Segmented, Select } from 'antd'
import { useState } from 'react'

import type {
  ThresholdProfileCreate,
  ThresholdProfileDetail,
  ThresholdProfileUpdate,
  ThresholdValues,
} from '../../api/types'
import { LINE_STATUS_LABELS, PROFILE_SCOPE_LABELS } from '../../lib/labels'
import styles from './Admin.module.css'
import { FormDrawer } from './FormDrawer'
import { changedFields } from './form'
import { useRegionOptions, useSaveThresholdProfile, useSchoolLineOptions, useSchoolOptions } from './queries'

type Target = 'district' | 'line'

interface ProfileValues extends ThresholdValues {
  scope: Target
  regionId?: number
  /** With its label: a school picked from one search stays named when the search changes. */
  school?: { value: number; label: string }
  lineId?: number
  unstableDeviationPct: number
  isActive: boolean
}

const FIELDS = [
  'regionId',
  'lineId',
  'downloadMinMbps',
  'uploadMinMbps',
  'pingMaxMs',
  'jitterMaxMs',
  'packetLossMaxPct',
  'unstableDeviationPct',
  'isActive',
]

const TARGET_OPTIONS = (['district', 'line'] as const).map((value) => ({ value, label: PROFILE_SCOPE_LABELS[value] }))

// Limits of «Норма» (ТЗ п. 11): speeds from below, delays and losses from above.
const METRICS: { name: keyof ThresholdValues; label: string; max?: number }[] = [
  { name: 'downloadMinMbps', label: 'Download не ниже, Мбит/с' },
  { name: 'uploadMinMbps', label: 'Upload не ниже, Мбит/с' },
  { name: 'pingMaxMs', label: 'Ping не выше, мс' },
  { name: 'jitterMaxMs', label: 'Jitter не выше, мс' },
  { name: 'packetLossMaxPct', label: 'Packet Loss не выше, %', max: 100 },
]

const NO_THRESHOLDS: ThresholdValues = {
  downloadMinMbps: 0,
  uploadMinMbps: 0,
  pingMaxMs: 0,
  jitterMaxMs: 0,
  packetLossMaxPct: 0,
}

const thresholdsOf = (values: ProfileValues): ThresholdValues => ({
  downloadMinMbps: values.downloadMinMbps,
  uploadMinMbps: values.uploadMinMbps,
  pingMaxMs: values.pingMaxMs,
  jitterMaxMs: values.jitterMaxMs,
  packetLossMaxPct: values.packetLossMaxPct,
})

const updatableOf = (values: ProfileValues): ThresholdProfileUpdate => ({
  thresholds: thresholdsOf(values),
  unstableDeviationPct: values.unstableDeviationPct,
  isActive: values.isActive,
})

const valueRule = { required: true, message: 'Введите значение' }

interface ThresholdDrawerProps {
  open: boolean
  /** The profile being edited; none — a new one of a district or a line. */
  profile?: ThresholdProfileDetail
  /** Values a new profile starts from: those of the global profile. */
  base?: ThresholdProfileDetail
  onClose: () => void
}

/** Profile of thresholds (ТЗ п. 11, ADR-004): the new values judge the next measurement, history keeps its own. */
export function ThresholdDrawer({ open, profile, base, onClose }: ThresholdDrawerProps) {
  const [form] = Form.useForm<ProfileValues>()
  const save = useSaveThresholdProfile()
  const { open: notify } = useNotification()
  const [search, setSearch] = useState('')
  const scope = Form.useWatch('scope', form) ?? 'district'
  const schoolId = Form.useWatch('school', form)?.value
  const regions = useRegionOptions()
  const schools = useSchoolOptions(search)
  const lines = useSchoolLineOptions(schoolId)
  const [initial] = useState<ProfileValues>(() => {
    const source = profile ?? base
    return {
      scope: 'district',
      ...(source?.thresholds ?? NO_THRESHOLDS),
      unstableDeviationPct: source?.unstableDeviationPct ?? 0,
      isActive: profile?.isActive ?? true,
    }
  })

  const submit = (values: ProfileValues) => {
    const done = () => {
      notify?.({ type: 'success', message: profile ? 'Профиль порогов изменён' : 'Профиль порогов добавлен' })
      onClose()
    }
    if (!profile) {
      const body: ThresholdProfileCreate = {
        scope: values.scope,
        regionId: values.scope === 'district' ? values.regionId : null,
        lineId: values.scope === 'line' ? values.lineId : null,
        thresholds: thresholdsOf(values),
        unstableDeviationPct: values.unstableDeviationPct,
      }
      return save.mutate({ body }, { onSuccess: done })
    }
    const body = changedFields(updatableOf(initial), updatableOf(values))
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: profile.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={profile ? 'Изменить профиль порогов' : 'Новый профиль порогов'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<ProfileValues>
        form={form}
        layout="vertical"
        initialValues={initial}
        onFinish={submit}
        onValuesChange={(changed: Partial<ProfileValues>) => {
          if ('school' in changed) form.setFieldValue('lineId', undefined)
        }}
      >
        {profile ? (
          <Form.Item label={PROFILE_SCOPE_LABELS[profile.scope]}>
            {profile.scope === 'global'
              ? 'Действует, пока у района и линии нет своего профиля'
              : (profile.regionName ?? `${profile.schoolName} · ${profile.providerName}`)}
          </Form.Item>
        ) : (
          <>
            <Form.Item label="Для чего профиль" name="scope">
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
              <>
                <Form.Item label="Школа" name="school" rules={[{ required: true, message: 'Выберите школу' }]}>
                  <Select<ProfileValues['school']>
                    showSearch
                    labelInValue
                    filterOption={false}
                    placeholder="Поиск по School ID или названию"
                    options={schools.data}
                    loading={schools.isFetching}
                    onSearch={setSearch}
                  />
                </Form.Item>
                <Form.Item label="Линия" name="lineId" rules={[{ required: true, message: 'Выберите линию' }]}>
                  <Select<number>
                    placeholder={lines.data?.length === 0 ? 'У школы нет линий' : 'Выберите из списка'}
                    options={lines.data?.map((line) => ({
                      value: line.id,
                      label: `${LINE_STATUS_LABELS[line.status]} · ${line.providerName}`,
                    }))}
                    loading={schoolId !== undefined && lines.isPending}
                    disabled={schoolId === undefined || lines.data?.length === 0}
                  />
                </Form.Item>
              </>
            )}
          </>
        )}
        <div className={styles.coordinates}>
          {METRICS.map(({ name, label, max }) => (
            <Form.Item key={name} label={label} name={name} rules={[valueRule]}>
              <InputNumber<number> className={styles.number} min={0} max={max} />
            </Form.Item>
          ))}
        </div>
        <Form.Item
          label="Граница «Нестабильно», % от порога"
          name="unstableDeviationPct"
          extra="Один показатель хуже порога не больше чем на столько — «Нестабильно»; больше или несколько показателей — «Критично»."
          rules={[valueRule]}
        >
          <InputNumber<number> className={styles.number} min={0} max={100} step={5} />
        </Form.Item>
        {profile && profile.scope !== 'global' && (
          <Form.Item
            name="isActive"
            valuePropName="checked"
            extra="Отключённый профиль не удаляется: замеры оцениваются по следующему в цепочке линия → район → область."
          >
            <Checkbox>Профиль действует</Checkbox>
          </Form.Item>
        )}
      </Form>
    </FormDrawer>
  )
}
