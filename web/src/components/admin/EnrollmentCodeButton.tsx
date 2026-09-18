import { useNotification } from '@refinedev/core'
import { Modal, Typography } from 'antd'
import { KeyRound } from 'lucide-react'

import { ApiError } from '../../api/client'
import { formatDateTime } from '../../lib/format'
import { SIZES } from '../../styles/theme'
import { Button } from '../ui/Button'
import styles from './Admin.module.css'
import { useIssueEnrollmentCode } from './queries'

// Modal of a short message (DESIGN.md §3.20): 400 / 560 / 800px.
const MODAL_WIDTH = 560

/**
 * «Выдать код установки» of a school (plan.md §4.1): a one-time code for ENROLL_CODE of the installer, shown once
 * with its expiry; the server keeps only its hash (ADR-005).
 */
export function EnrollmentCodeButton({ schoolId }: { schoolId: number }) {
  const issue = useIssueEnrollmentCode()
  const { open: notify } = useNotification()
  const issued = issue.data

  return (
    <>
      <Button
        kind="outlined"
        icon={<KeyRound size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
        loading={issue.isPending}
        onClick={() =>
          issue.mutate(schoolId, {
            onError: (error) =>
              notify?.({
                type: 'error',
                message: 'Код не выдан',
                description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
              }),
          })
        }
      >
        Выдать код установки
      </Button>
      <Modal
        title="Код установки агента"
        open={issued !== undefined}
        width={MODAL_WIDTH}
        maskClosable={false}
        onCancel={() => issue.reset()}
        footer={
          <Button kind="action" onClick={() => issue.reset()}>
            Готово
          </Button>
        }
      >
        {issued && (
          <>
            <Typography.Paragraph
              className={styles.enrollCode}
              copyable={{ text: issued.code, tooltips: ['Скопировать', 'Скопировано'] }}
            >
              {issued.code}
            </Typography.Paragraph>
            <Typography.Paragraph>
              Укажите код в параметре ENROLL_CODE установщика агента. Код подходит для одного компьютера и действует
              до {formatDateTime(issued.expiresAt)}.
            </Typography.Paragraph>
            <Typography.Paragraph type="secondary">
              Код больше не будет показан: скопируйте его сейчас. Для следующего компьютера выдайте новый код.
            </Typography.Paragraph>
          </>
        )}
      </Modal>
    </>
  )
}
