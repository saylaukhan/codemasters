import { useNotification } from '@refinedev/core'
import { Checkbox, Form, Input, Select } from 'antd'
import { useState } from 'react'

import type { DigestScope, DigestSettingsDetail } from '../../api/types'
import { DIGEST_LABELS, DIGEST_SCOPE_LABELS, DIGEST_WEEKDAY_LABELS } from '../../lib/labels'
import styles from '../admin/Admin.module.css'
import { FormDrawer } from '../admin/FormDrawer'
import { useRegionOptions, useSaveDigest } from './digestQueries'

const FIELDS = ['scope', 'regionId', 'weekday', 'hour', 'recipients', 'telegramChatId', 'isActive']

const SCOPE_OPTIONS = (Object.keys(DIGEST_SCOPE_LABELS) as DigestScope[]).map((value) => ({
  value,
  label: DIGEST_SCOPE_LABELS[value],
}))
const WEEKDAY_OPTIONS = Object.keys(DIGEST_WEEKDAY_LABELS).map((key) => ({
  value: Number(key),
  label: DIGEST_WEEKDAY_LABELS[Number(key)],
}))
const HOURS = 24
const HOUR_OPTIONS = Array.from({ length: HOURS }, (_, hour) => ({
  value: hour,
  label: `${String(hour).padStart(2, '0')}:00`,
}))
// Тот же вид адреса, что принимает контракт: одна «@» и никаких пробелов.
const ADDRESS = /^[^@\s]+@[^@\s]+$/

interface DigestFormValues {
  scope: DigestScope
  regionId?: number
  weekday: number
  hour: number
  recipients: string[]
  telegramChatId?: string
  isActive: boolean
}

const formValues = (digest?: DigestSettingsDetail): DigestFormValues => ({
  scope: digest?.scope ?? 'oblast',
  regionId: digest?.regionId ?? undefined,
  weekday: digest?.weekday ?? 1,
  hour: digest?.hour ?? 8,
  recipients: digest?.recipients ?? [],
  telegramChatId: digest?.telegramChatId ?? undefined,
  isActive: digest?.isActive ?? true,
})

interface DigestDrawerProps {
  open: boolean
  /** Изменяемая рассылка; без неё — новая. */
  digest?: DigestSettingsDetail
  onClose: () => void
}

/**
 * Рассылка сводки для руководителя (T-67, DESIGN.md §3.32): охват, день недели и час, адреса,
 * чат Telegram и выключатель. Охват существующей рассылки не меняется, как у профиля порогов.
 */
export function DigestDrawer({ open, digest, onClose }: DigestDrawerProps) {
  const [form] = Form.useForm<DigestFormValues>()
  const save = useSaveDigest()
  const regions = useRegionOptions()
  const { open: notify } = useNotification()
  const [initial] = useState(() => formValues(digest))
  const scope = Form.useWatch('scope', form) ?? initial.scope

  const submit = (values: DigestFormValues) => {
    const done = () => {
      notify?.({ type: 'success', message: digest ? DIGEST_LABELS.changed : DIGEST_LABELS.created })
      onClose()
    }
    const channels = {
      weekday: values.weekday,
      hour: values.hour,
      recipients: values.recipients ?? [],
      telegramChatId: values.telegramChatId ?? null,
      isActive: values.isActive,
    }
    if (digest) return save.mutate({ id: digest.id, body: channels }, { onSuccess: done })
    save.mutate(
      {
        body: {
          ...channels,
          scope: values.scope,
          regionId: values.scope === 'region' ? (values.regionId ?? null) : null,
        },
      },
      { onSuccess: done },
    )
  }

  return (
    <FormDrawer
      title={digest ? DIGEST_LABELS.edit : DIGEST_LABELS.add}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<DigestFormValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        {digest ? (
          <Form.Item label={DIGEST_LABELS.scope}>
            {digest.scope === 'region' ? digest.regionName : DIGEST_SCOPE_LABELS.oblast}
          </Form.Item>
        ) : (
          <>
            <Form.Item label={DIGEST_LABELS.scope} name="scope">
              <Select<DigestScope> options={SCOPE_OPTIONS} />
            </Form.Item>
            {scope === 'region' && (
              <Form.Item
                label={DIGEST_LABELS.region}
                name="regionId"
                rules={[{ required: true, message: DIGEST_LABELS.regionRequired }]}
              >
                <Select<number>
                  placeholder={DIGEST_LABELS.regionPlaceholder}
                  options={regions.data ?? []}
                  loading={regions.isFetching}
                  optionFilterProp="label"
                  showSearch
                />
              </Form.Item>
            )}
          </>
        )}
        <div className={styles.coordinates}>
          <Form.Item label={DIGEST_LABELS.weekday} name="weekday">
            <Select<number> options={WEEKDAY_OPTIONS} />
          </Form.Item>
          <Form.Item
            label={DIGEST_LABELS.hour}
            name="hour"
            extra={DIGEST_LABELS.hourHint}
          >
            <Select<number> options={HOUR_OPTIONS} />
          </Form.Item>
        </div>
        <Form.Item
          label={DIGEST_LABELS.recipients}
          name="recipients"
          extra={DIGEST_LABELS.recipientsHint}
          rules={[
            {
              validator: (_, value: string[] | undefined) =>
                (value ?? []).every((address) => ADDRESS.test(address))
                  ? Promise.resolve()
                  : Promise.reject(new Error(DIGEST_LABELS.recipientsInvalid)),
            },
          ]}
        >
          <Select<string[]> mode="tags" open={false} placeholder={DIGEST_LABELS.recipientsPlaceholder} />
        </Form.Item>
        <Form.Item label={DIGEST_LABELS.telegram} name="telegramChatId">
          <Input placeholder={DIGEST_LABELS.telegramPlaceholder} allowClear />
        </Form.Item>
        <Form.Item name="isActive" valuePropName="checked" extra={DIGEST_LABELS.activeHint}>
          <Checkbox>{DIGEST_LABELS.active}</Checkbox>
        </Form.Item>
      </Form>
    </FormDrawer>
  )
}
