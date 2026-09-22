import { useMutation } from '@tanstack/react-query'
import { Alert, Form, Input, Modal } from 'antd'
import { useState } from 'react'

import { requestPasswordReset } from '../../api/auth'
import { Button } from '../../components/ui/Button'
import { PASSWORD_RESET_LABELS as LABELS } from '../../lib/labels'
import styles from './LoginPage.module.css'

interface RequestValues {
  email: string
}

/**
 * «Забыли пароль?»: the e-mail of the account and one neutral answer (T-65). The API answers
 * the same for every address, so the notice never says whether an account was found.
 */
export function PasswordResetModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const request = useMutation({
    mutationFn: (values: RequestValues) => requestPasswordReset(values.email.trim()),
    onSuccess: () => {
      setError(null)
      setSent(true)
    },
    onError: () => setError(LABELS.requestFailed),
  })

  const close = () => {
    setSent(false)
    setError(null)
    onClose()
  }

  return (
    <Modal title={LABELS.requestTitle} open={open} onCancel={close} footer={null} destroyOnClose>
      {sent ? (
        <>
          <Alert className={styles.error} type="success" showIcon message={LABELS.sent} />
          <Button kind="action" block onClick={close}>
            {LABELS.toLogin}
          </Button>
        </>
      ) : (
        <Form<RequestValues> layout="vertical" requiredMark={false} onFinish={(values) => request.mutate(values)}>
          <p className={styles.hint}>{LABELS.requestHint}</p>
          <Form.Item label={LABELS.email} name="email" rules={[{ required: true, message: LABELS.emailRequired }]}>
            <Input type="email" autoComplete="username" autoFocus />
          </Form.Item>
          {error && <Alert className={styles.error} type="error" showIcon message={error} />}
          <Button kind="action" htmlType="submit" block loading={request.isPending}>
            {LABELS.send}
          </Button>
        </Form>
      )}
    </Modal>
  )
}
