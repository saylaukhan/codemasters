import { Alert } from 'antd'

import { ApiError } from '../../api/client'
import { Button } from './Button'

interface ErrorStateProps {
  error: unknown
  onRetry?: () => void
}

/** Error state (DESIGN.md §3.21): inline alert with «Повторить»; `title` of the problem+json (ADR-009). */
export function ErrorState({ error, onRetry }: ErrorStateProps) {
  const title = error instanceof ApiError ? error.title : 'Не удалось загрузить данные'
  const detail = error instanceof ApiError && error.detail !== error.title ? error.detail : null
  return (
    <Alert
      type="error"
      showIcon
      message={title}
      description={detail ?? undefined}
      action={
        onRetry && (
          <Button kind="outlined" size="small" onClick={onRetry}>
            Повторить
          </Button>
        )
      }
    />
  )
}
