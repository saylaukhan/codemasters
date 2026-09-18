import { useGo, useInvalidateAuthStore, useLogin, useParsed } from '@refinedev/core'
import { Alert, Card, Form, Input } from 'antd'
import { Wifi } from 'lucide-react'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import { Button } from '../../components/ui/Button'
import { APP_NAME } from '../../lib/app-info'
import { SIZES } from '../../styles/theme'
import styles from './LoginPage.module.css'

interface LoginValues {
  email: string
  password: string
}

const messageOf = (error: unknown): string =>
  error instanceof ApiError ? (error.detail ?? error.title) : 'Не удалось войти, попробуйте ещё раз'

/** Sign-in by e-mail and password (DESIGN.md §3.26); the error stays inline above the button. */
export function LoginPage() {
  const [error, setError] = useState<string | null>(null)
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
      <Card className={styles.card}>
        <div className={styles.brand}>
          <Wifi size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} aria-hidden />
          {APP_NAME}
        </div>
        <h1 className={styles.title}>Вход в систему</h1>
        <Form<LoginValues> layout="vertical" size="large" requiredMark={false} onFinish={onFinish}>
          <Form.Item
            label="E-mail"
            name="email"
            rules={[{ required: true, message: 'Введите e-mail' }]}
          >
            <Input type="email" autoComplete="username" autoFocus />
          </Form.Item>
          <Form.Item label="Пароль" name="password" rules={[{ required: true, message: 'Введите пароль' }]}>
            <Input.Password autoComplete="current-password" />
          </Form.Item>
          {error && <Alert className={styles.error} type="error" showIcon message={error} />}
          <Button kind="action" htmlType="submit" size="large" block loading={isPending}>
            Войти
          </Button>
        </Form>
      </Card>
    </main>
  )
}
