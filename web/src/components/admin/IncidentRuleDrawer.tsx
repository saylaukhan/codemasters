import { useNotification } from '@refinedev/core'
import { Checkbox, Form, Input, InputNumber, Segmented, Select } from 'antd'
import { useState } from 'react'

import type { IncidentMetric, IncidentRuleDetail, IncidentRuleScope } from '../../api/types'
import { INCIDENT_METRIC_LABELS, INCIDENT_RULE_SCOPE_LABELS } from '../../lib/labels'
import styles from './Admin.module.css'
import { FormDrawer } from './FormDrawer'
import { maxLength, required } from './form'
import {
  formatTarget,
  incidentRuleCreateBody,
  incidentRuleFormValues,
  incidentRuleUpdateBody,
  type IncidentRuleFormValues,
} from './incidentRules'
import { useSaveIncidentRule, useSchoolOptions } from './queries'

// An error of the rule as a whole (no N and no T) goes to the alert: the form has no field of that name.
const FIELDS = ['name', 'metric', 'consecutiveViolations', 'durationMin', 'recoveryNormalCount', 'isActive']

const METRIC_OPTIONS = (Object.keys(INCIDENT_METRIC_LABELS) as IncidentMetric[]).map((value) => ({
  value,
  label: INCIDENT_METRIC_LABELS[value],
}))

const SCOPE_OPTIONS = (['global', 'school'] as const).map((value) => ({
  value,
  label: INCIDENT_RULE_SCOPE_LABELS[value],
}))

const countRule = { type: 'integer' as const, min: 1, message: 'Целое число не меньше 1' }

interface IncidentRuleDrawerProps {
  open: boolean
  /** The rule being edited; none — a new one. */
  rule?: IncidentRuleDetail
  onClose: () => void
}

/**
 * Incident rule (ТЗ п. 18, ADR-007): N violations in a row or T minutes open an incident, M normal results in a row
 * restore it; the next detection takes the new values. A rule of one school replaces the rule of the oblast for
 * its lines by the same metric (T-85).
 */
export function IncidentRuleDrawer({ open, rule, onClose }: IncidentRuleDrawerProps) {
  const [form] = Form.useForm<IncidentRuleFormValues>()
  const save = useSaveIncidentRule()
  const { open: notify } = useNotification()
  const [search, setSearch] = useState('')
  const scope: IncidentRuleScope = Form.useWatch('scope', form) ?? 'global'
  const schools = useSchoolOptions(search)
  const [initial] = useState(() => incidentRuleFormValues(rule))

  const submit = (values: IncidentRuleFormValues) => {
    const done = (saved: IncidentRuleDetail) => {
      notify?.({ type: 'success', message: rule ? 'Правило изменено' : 'Правило добавлено', description: saved.name })
      onClose()
    }
    if (!rule) return save.mutate({ body: incidentRuleCreateBody(values) }, { onSuccess: done })
    const body = incidentRuleUpdateBody(initial, values)
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: rule.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={rule ? 'Изменить правило' : 'Новое правило'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<IncidentRuleFormValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item label="Название" name="name" rules={[required('Введите название правила'), maxLength(255)]}>
          <Input autoFocus />
        </Form.Item>
        {rule ? (
          <>
            <Form.Item label="Показатель" extra="Показатель не меняется: для другого показателя добавьте новое правило.">
              {INCIDENT_METRIC_LABELS[rule.metric]}
            </Form.Item>
            <Form.Item label={INCIDENT_RULE_SCOPE_LABELS[rule.scope]}>{formatTarget(rule)}</Form.Item>
          </>
        ) : (
          <>
            <Form.Item label="Показатель" name="metric" rules={[{ required: true, message: 'Выберите показатель' }]}>
              <Select<IncidentMetric> placeholder="Выберите из списка" options={METRIC_OPTIONS} />
            </Form.Item>
            <Form.Item
              label="Для кого правило"
              name="scope"
              extra="Правило школы заменяет для её линий правило области по тому же показателю."
            >
              <Segmented options={SCOPE_OPTIONS} />
            </Form.Item>
            {scope === 'school' && (
              <Form.Item label="Школа" name="school" rules={[{ required: true, message: 'Выберите школу' }]}>
                <Select<IncidentRuleFormValues['school']>
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
        <div className={styles.coordinates}>
          <Form.Item
            label="Нарушений подряд"
            name="consecutiveViolations"
            dependencies={['durationMin']}
            rules={[
              countRule,
              ({ getFieldValue }) => ({
                validator: (_, value: number | null) =>
                  value == null && getFieldValue('durationMin') == null
                    ? Promise.reject(new Error('Задайте число нарушений подряд или длительность'))
                    : Promise.resolve(),
              }),
            ]}
          >
            <InputNumber<number> className={styles.number} min={1} precision={0} />
          </Form.Item>
          <Form.Item label="Или нарушение дольше" name="durationMin" rules={[countRule]}>
            <InputNumber<number> className={styles.number} min={1} precision={0} suffix="мин" />
          </Form.Item>
        </div>
        <Form.Item
          label="Нормальных подряд для восстановления"
          name="recoveryNormalCount"
          extra="После стольких нормальных результатов подряд у инцидента заполняется время восстановления."
          rules={[{ required: true, message: 'Введите значение' }, countRule]}
        >
          <InputNumber<number> className={styles.number} min={1} precision={0} />
        </Form.Item>
        {rule && (
          <Form.Item
            name="isActive"
            valuePropName="checked"
            extra="Отключённое правило не удаляется: его инциденты остаются, новые по нему не открываются."
          >
            <Checkbox>Правило действует</Checkbox>
          </Form.Item>
        )}
      </Form>
    </FormDrawer>
  )
}
