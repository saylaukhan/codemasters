import { useNotification } from '@refinedev/core'
import { Form, Input, InputNumber } from 'antd'
import { useEffect, useState } from 'react'

import type { SettingsDetail, SettingsUpdate } from '../../api/types'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { changedFields, formErrors, maxLength, optionalText, required } from '../../components/admin/form'
import { hoursOf, hoursValues, type HoursValues } from '../../components/admin/hours'
import { useSaveSettings, useSystemSettings } from '../../components/admin/queries'
import { WorkingHoursFields } from '../../components/admin/WorkingHoursFields'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { ErrorState } from '../../components/ui/ErrorState'

type SettingsValues = Omit<SettingsDetail, 'speedtest' | 'defaultWorkingHours'> & {
  librespeedUrl: string
  ndt7Url: string | null
  defaultWorkingHours: HoursValues
}

const FIELDS = [
  'librespeedUrl',
  'ndt7Url',
  'heartbeatIntervalS',
  'configRefreshIntervalS',
  'offlineAfterS',
  'schoolStatusMeasurementsCount',
  'availabilityMinPct',
  'contractMismatchThresholdPct',
  'contractMismatchWindowDays',
  'enrollmentCodeTtlDays',
  'exportSyncMaxRows',
  'exportRetentionDays',
  'incidentAutoCloseHours',
]

const valuesOf = ({ speedtest, defaultWorkingHours, ...rest }: SettingsDetail): SettingsValues => ({
  ...rest,
  librespeedUrl: speedtest.librespeedUrl,
  ndt7Url: speedtest.ndt7Url ?? null,
  defaultWorkingHours: hoursValues(defaultWorkingHours),
})

/** The objects of the settings are replaced whole: a changed server sends both addresses (ADR-012). */
const bodyOf = ({ librespeedUrl, ndt7Url, defaultWorkingHours, ...rest }: SettingsValues): SettingsUpdate => ({
  ...rest,
  speedtest: { librespeedUrl: librespeedUrl.trim(), ndt7Url: optionalText(ndt7Url) },
  defaultWorkingHours: hoursOf(defaultWorkingHours),
})

// ndt7 speaks WebSocket: wss:// is as valid here as https://.
const URL_RULE = { pattern: /^(https?|wss?):\/\/\S+$/, message: 'Адрес вида https://… или wss://…' }

interface NumberFieldProps {
  name: keyof SettingsValues
  label: string
  extra?: string
  min?: number
  max?: number
}

const NumberField = ({ name, label, extra, min = 1, max }: NumberFieldProps) => (
  <Form.Item label={label} name={name} extra={extra} rules={[{ required: true, message: 'Введите значение' }]}>
    <InputNumber<number> className={styles.number} min={min} max={max} />
  </Form.Item>
)

function SettingsForm({ settings }: { settings: SettingsDetail }) {
  const [form] = Form.useForm<SettingsValues>()
  const [initial] = useState(() => valuesOf(settings))
  const save = useSaveSettings()
  const { open: notify } = useNotification()
  useEffect(() => {
    const placed = formErrors(save.error, FIELDS).fields
    if (placed.length > 0) form.setFields(placed as Parameters<typeof form.setFields>[0])
  }, [form, save.error])

  const submit = (values: SettingsValues) => {
    const body = changedFields(bodyOf(initial), bodyOf(values))
    if (Object.keys(body).length === 0) return
    save.mutate(body, {
      onSuccess: () =>
        notify?.({
          type: 'success',
          message: 'Настройки сохранены',
          description: 'Агенты получат новые значения при следующем обновлении конфигурации.',
        }),
    })
  }

  return (
    <AdminLayout
      tab="settings"
      action={
        <Button kind="action" loading={save.isPending} onClick={() => form.submit()}>
          Сохранить
        </Button>
      }
    >
      <p className={styles.lead}>
        Значения не зашиты в агент и панель: агенты получают их вместе с расписанием и порогами, без переустановки.
      </p>
      {formErrors(save.error, FIELDS).alert && (
        <div className={styles.lead}>
          <ErrorState error={save.error} />
        </div>
      )}
      <Form<SettingsValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <div className={styles.settings}>
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Сервер замеров</h3>
            <Form.Item
              label="LibreSpeed"
              name="librespeedUrl"
              extra="Основной сервер замеров скорости."
              rules={[required('Введите адрес сервера'), URL_RULE, maxLength(2048)]}
            >
              <Input autoComplete="off" />
            </Form.Item>
            <Form.Item
              label="Резервный ndt7"
              name="ndt7Url"
              extra="Если LibreSpeed недоступен. Пусто — без резервного сервера."
              rules={[URL_RULE, maxLength(2048)]}
            >
              <Input autoComplete="off" />
            </Form.Item>
          </section>
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Рабочие часы по умолчанию</h3>
            <WorkingHoursFields
              name={['defaultWorkingHours']}
              extra="С ними создаётся новая школа; часы существующей школы меняются в её форме на вкладке «Школы»."
            />
          </section>
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Статусы и доступность</h3>
            <NumberField
              name="availabilityMinPct"
              label="Порог доступности, %"
              extra="Доступность школы за период не ниже этого значения (п. 11)."
              min={0}
              max={100}
            />
            <NumberField
              name="schoolStatusMeasurementsCount"
              label="Замеров для статуса школы"
              extra="Сколько последних замеров основной линии дают статус школы."
            />
            <NumberField
              name="offlineAfterS"
              label="«Нет соединения» после, с"
              extra="Без heartbeat дольше — «Нет соединения» в рабочие часы; больше интервала heartbeat."
            />
            <NumberField
              name="contractMismatchThresholdPct"
              label="Несоответствие договору, % замеров"
              min={0}
              max={100}
            />
            <NumberField name="contractMismatchWindowDays" label="Окно несоответствия договору, дней" />
            <NumberField name="incidentAutoCloseHours" label="Закрывать решённый инцидент через, ч" />
          </section>
          <section className={styles.section}>
            <h3 className={styles.sectionTitle}>Агент и выгрузки</h3>
            <NumberField name="heartbeatIntervalS" label="Интервал heartbeat, с" />
            <NumberField name="configRefreshIntervalS" label="Обновление конфигурации агента, с" />
            <NumberField name="enrollmentCodeTtlDays" label="Срок кода установки, дней" />
            <NumberField
              name="exportSyncMaxRows"
              label="Выгрузка сразу — до строк"
              extra="Больше строк и любой PDF формируются в фоне."
            />
            <NumberField name="exportRetentionDays" label="Хранить файлы выгрузок, дней" />
          </section>
        </div>
      </Form>
    </AdminLayout>
  )
}

/** System settings (ТЗ п. 11, п. 20): the measurement server, the default working hours, rules of the statuses. */
export function SettingsPage() {
  const settings = useSystemSettings()
  if (settings.isSuccess) return <SettingsForm key={settings.dataUpdatedAt} settings={settings.data} />
  return (
    <AdminLayout tab="settings" action={null}>
      {settings.isError ? (
        <ErrorState error={settings.error} onRetry={() => void settings.refetch()} />
      ) : (
        <ContentSkeleton rows={8} />
      )}
    </AdminLayout>
  )
}
