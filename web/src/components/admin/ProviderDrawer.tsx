import { useNotification } from '@refinedev/core'
import { Form, Input } from 'antd'

import type { ProviderCreate, ProviderDetail } from '../../api/types'
import { FormDrawer } from './FormDrawer'
import { changedFields, maxLength, optionalText, required } from './form'
import { useSaveProvider } from './queries'

interface ProviderValues {
  name: string
  appealsEmail: string | null
}

const FIELDS = ['name', 'appealsEmail']

const bodyOf = (values: ProviderValues): ProviderCreate => ({
  name: values.name.trim(),
  appealsEmail: optionalText(values.appealsEmail),
})

interface ProviderDrawerProps {
  open: boolean
  /** The provider being edited; none — a new one. */
  provider?: ProviderDetail
  onClose: () => void
}

/** New provider or a change of one: the name and the service address for appeals (T-48). */
export function ProviderDrawer({ open, provider, onClose }: ProviderDrawerProps) {
  const [form] = Form.useForm<ProviderValues>()
  const save = useSaveProvider()
  const { open: notify } = useNotification()
  const initial: ProviderValues = { name: provider?.name ?? '', appealsEmail: provider?.appealsEmail ?? null }

  const submit = (values: ProviderValues) => {
    const done = (saved: ProviderDetail) => {
      notify?.({ type: 'success', message: provider ? 'Поставщик изменён' : 'Поставщик добавлен', description: saved.name })
      onClose()
    }
    if (!provider) return save.mutate({ body: bodyOf(values) }, { onSuccess: done })
    const body = changedFields(bodyOf(initial), bodyOf(values))
    if (Object.keys(body).length === 0) return onClose()
    save.mutate({ id: provider.id, body }, { onSuccess: done })
  }

  return (
    <FormDrawer
      title={provider ? 'Изменить поставщика' : 'Новый поставщик'}
      open={open}
      onClose={onClose}
      form={form}
      fields={FIELDS}
      saving={save.isPending}
      error={save.error}
    >
      <Form<ProviderValues> form={form} layout="vertical" initialValues={initial} onFinish={submit}>
        <Form.Item label="Название" name="name" rules={[required('Введите название поставщика'), maxLength(255)]}>
          <Input autoFocus />
        </Form.Item>
        <Form.Item
          label="E-mail для обращений"
          name="appealsEmail"
          extra="Служебный адрес поставщика, на который уходят обращения; не личный e-mail."
          rules={[{ type: 'email', message: 'Введите корректный e-mail' }, maxLength(254)]}
        >
          <Input type="email" autoComplete="off" />
        </Form.Item>
      </Form>
    </FormDrawer>
  )
}
