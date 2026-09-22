import { useGo, useNotification, useParsed } from '@refinedev/core'
import { useMutation } from '@tanstack/react-query'
import { Alert, Card, Form, Input } from 'antd'
import { Wifi } from 'lucide-react'
import { useState } from 'react'

import { confirmPasswordReset } from '../../api/auth'
import { ApiError } from '../../api/client'
import { PASSWORD_RULES } from '../../components/admin/users'
import { Button } from '../../components/ui/Button'
import { APP_NAME } from '../../lib/app-info'
import { PASSWORD_RESET_LABELS as LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import styles from './LoginPage.module.css'

interface ConfirmValues {
  password: string
  repeat: string
}

/** A refused link and a missing one read the same: the panel never guesses why (ADR-009). */
const messageOf = (error: unknown): string =>
  error instanceof ApiError && error.status !== 400 ? (error.detail ?? error.title) : LABELS.invalid

/**
 * Page of the link from the letter: `/password-reset?token=…` (T-65, docs/design/README.md §4.6).
 * The password rules are the ones the user administration applies; after a change the person
 * goes to the sign-in screen and enters the new password there.
 */
export function PasswordResetPage() {
  const [error, setError] = useState<string | null>(null)
  const go = useGo()
  const { open: notify } = useNotification()
  const { params } = useParsed<{ token?: string }>()
  const token = params?.token ?? ''
  const confirm = useMutation({
    mutationFn: (values: ConfirmValues) => confirmPasswordReset(token, values.password),
    onSuccess: () => {
      notify?.({ type: 'success', message: LABELS.done })
      go({ to: '/login', type: 'replace' })
    },
    onError: (failure: unknown) => setError(messageOf(failure)),
  })

  return (
    <main className={styles.page}>
      <Card className={styles.card}>
        <div className={styles.brand}>
          <Wifi size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} aria-hidden />
          {APP_NAME}
        </div>
        <h1 className={styles.title}>{LABELS.confirmTitle}</h1>
        {token === '' ? (
          <>
            <Alert className={styles.error} type="error" showIcon message={LABELS.invalid} />
            <Button kind="action" size="large" block onClick={() => go({ to: '/login', type: 'replace' })}>
              {LABELS.toLogin}
            </Button>
          </>
        ) : (
          <Form<ConfirmValues>
            layout="vertical"
            size="large"
            requiredMark={false}
            onFinish={(values) => {
              setError(null)
              confirm.mutate(values)
            }}
          >
            <p className={styles.hint}>{LABELS.confirmHint}</p>
            <Form.Item label={LABELS.password} name="password" rules={PASSWORD_RULES}>
              <Input.Password autoComplete="new-password" autoFocus />
            </Form.Item>
            <Form.Item
              label={LABELS.repeat}
              name="repeat"
              dependencies={['password']}
              rules={[
                { required: true, message: LABELS.repeatRequired },
                ({ getFieldValue }) => ({
                  validator: (_rule, value: string) =>
                    value === undefined || value === getFieldValue('password')
                      ? Promise.resolve()
                      : Promise.reject(new Error(LABELS.mismatch)),
                }),
              ]}
            >
              <Input.Password autoComplete="new-password" />
            </Form.Item>
            {error && <Alert className={styles.error} type="error" showIcon message={error} />}
            <Button kind="action" htmlType="submit" size="large" block loading={confirm.isPending}>
              {LABELS.save}
            </Button>
          </Form>
        )}
      </Card>
    </main>
  )
}
