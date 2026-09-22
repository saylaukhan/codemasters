import { useGo, useInvalidateAuthStore, useLogin, useParsed } from '@refinedev/core'
import { useQuery } from '@tanstack/react-query'
import { Alert, Card, Form, Input } from 'antd'
import { useState } from 'react'

import { getLoginInfo } from '../../api/auth'
import { ApiError } from '../../api/client'
import { BrandMark } from '../../components/ui/BrandMark'
import { Button } from '../../components/ui/Button'
import { LocaleSwitch } from '../../components/ui/LocaleSwitch'
import { APP_NAME } from '../../lib/app-info'
import { PASSWORD_RESET_LABELS, SIGN_IN_LABELS } from '../../lib/labels'
import styles from './LoginPage.module.css'
import { PasswordResetModal } from './PasswordResetModal'

interface LoginValues {
  email: string
  password: string
}

const messageOf = (error: unknown): string =>
  error instanceof ApiError ? (error.detail ?? error.title) : SIGN_IN_LABELS.failed

/**
 * Sign-in by e-mail and password (DESIGN.md §3.26); the error stays inline above the button.
 * The language switch stands in the corner above the card: the screen is picked before anyone
 * is signed in, so the choice lives in the browser until a profile can keep it (T-66).
 */
export function LoginPage() {
  const [error, setError] = useState<string | null>(null)
  const [resetOpen, setResetOpen] = useState(false)
  // Three states of the query (DESIGN.md §2.7) on a screen that has no room for a skeleton:
  // while it is pending, and if it fails, the sign-in shows neither the link nor a contact —
  // both are promises the panel cannot keep without the answer (T-65).
  const loginInfo = useQuery({ queryKey: ['login-info'], queryFn: ({ signal }) => getLoginInfo(signal) })
  const go = useGo()
  const invalidateAuthStore = useInvalidateAuthStore()
  const { params } = useParsed<{ to?: string }>()
  // Refine's default handler shows a toast; the design wants the message inside the form.
  const { mutate: login, isPending } = useLogin<LoginValues>({
    mutationOptions: {
      onSuccess: async (result) => {
        if (!result.success) {
          setError(messageOf(result.error))
          return
        }
        await invalidateAuthStore()
        go({ to: params?.to ?? '/', type: 'replace' })
      },
      onError: (failure) => setError(messageOf(failure)),
    },
  })

  const onFinish = (values: LoginValues) => {
    setError(null)
    login(values)
  }

  return (
    <main className={styles.page}>
      <div className={styles.locale}>
        <LocaleSwitch />
      </div>
      <Card className={styles.card}>
        <div className={styles.brand}>
          <BrandMark />
          {APP_NAME}
        </div>
        <h1 className={styles.title}>{SIGN_IN_LABELS.title}</h1>
        <Form<LoginValues> layout="vertical" size="large" requiredMark={false} onFinish={onFinish}>
          <Form.Item
            label={SIGN_IN_LABELS.email}
            name="email"
            rules={[{ required: true, message: SIGN_IN_LABELS.emailRequired }]}
          >
            <Input type="email" autoComplete="username" autoFocus />
          </Form.Item>
          <Form.Item label={SIGN_IN_LABELS.password} name="password" rules={[{ required: true, message: SIGN_IN_LABELS.passwordRequired }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          {loginInfo.data?.passwordResetAvailable && (
            <Button className={styles.reset} kind="link" onClick={() => setResetOpen(true)}>
              {PASSWORD_RESET_LABELS.link}
            </Button>
          )}
          {error && <Alert className={styles.error} type="error" showIcon message={error} />}
          <Button kind="action" htmlType="submit" size="large" block loading={isPending}>
            {SIGN_IN_LABELS.submit}
          </Button>
        </Form>
        {loginInfo.data && !loginInfo.data.passwordResetAvailable && loginInfo.data.supportContact && (
          <p className={styles.support}>
            {PASSWORD_RESET_LABELS.supportTitle}: {loginInfo.data.supportContact}
          </p>
        )}
        <PasswordResetModal open={resetOpen} onClose={() => setResetOpen(false)} />
      </Card>
    </main>
  )
}
