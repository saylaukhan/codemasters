import { Alert, Input } from 'antd'
import { MailX, Sparkles } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router'

import type { AppealDraft, AppealDraftRequest } from '../../api/types'
import styles from '../../components/appeals/Appeal.module.css'
import {
  COMMENT_MAX_LENGTH,
  fallbackDraft,
  periodCaption,
  readAppealTarget,
  SUBJECT_MAX_LENGTH,
  TEXT_MAX_LENGTH,
} from '../../components/appeals/appeals'
import { AppealFacts } from '../../components/appeals/AppealFacts'
import { useAppealDraft } from '../../components/appeals/queries'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader } from '../../components/ui/PageHeader'
import { APPEAL_LABELS, SECTION_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

// Letter of an official appeal: the field is as tall as a page of it, and grows with the text.
const TEXT_ROWS = { minRows: 14, maxRows: 32 }
const COMMENT_ROWS = { minRows: 3, maxRows: 8 }

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      {children}
      {hint && <span className={styles.fieldHint}>{hint}</span>}
    </label>
  )
}

interface AppealEditorProps {
  target: AppealDraftRequest
  /** Nothing came: the request itself failed, so the editor opens with the template (T-47). */
  draft: AppealDraft | undefined
  asking: boolean
  onRetry: () => void
}

/**
 * The letter and the facts of one draft. The text is state of the page, not of the server: a draft is not stored
 * anywhere until «Отправить» (ADR-011), and a new answer from the model replaces the whole editor.
 */
function AppealEditor({ target, draft, asking, onRetry }: AppealEditorProps) {
  const template = fallbackDraft(target)
  const [subject, setSubject] = useState(draft?.subject || template.subject)
  const [text, setText] = useState(draft?.text || template.text)
  const [comment, setComment] = useState('')

  return (
    <>
      <PageHeader
        title={APPEAL_LABELS.draft}
        breadcrumbs={[{ title: SECTION_LABELS.appeals, path: '/appeals' }, { title: APPEAL_LABELS.draft }]}
        subtitle={
          <span className={styles.meta}>
            {draft && (
              <>
                <span>{draft.context.schoolName}</span>
                <span>·</span>
                <span>{draft.context.providerName}</span>
                <span>·</span>
              </>
            )}
            <span className={styles.number}>{periodCaption(target.periodFrom, target.periodTo)}</span>
          </span>
        }
        actions={
          <>
            {/* A new answer of the model replaces the whole editor (DESIGN.md §3.19); a draft that
                never came is asked again by «Повторить» of the alert below. */}
            {draft && (
              <Button
                kind="flat"
                icon={<Sparkles size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
                loading={asking}
                tooltip={APPEAL_LABELS.regenerateHint}
                aria-label={APPEAL_LABELS.regenerate}
                onClick={onRetry}
              >
                {APPEAL_LABELS.regenerate}
              </Button>
            )}
            <Button kind="action" disabled tooltip={APPEAL_LABELS.sendUpcoming} aria-label={APPEAL_LABELS.send}>
              {APPEAL_LABELS.send}
            </Button>
          </>
        }
      />
      {!draft && (
        <Alert
          className={styles.alert}
          type="warning"
          showIcon
          message="Черновик не получен"
          description="Напишите текст обращения сами: в поле открыт шаблон, сведения соберёт сервер."
          action={
            <Button kind="outlined" size="small" loading={asking} onClick={onRetry}>
              Повторить
            </Button>
          }
        />
      )}
      {draft && !draft.aiGenerated && (
        <Alert
          className={styles.alert}
          type="info"
          showIcon
          message="Модель недоступна"
          description="Текст обращения нужно написать самостоятельно: в поле открыт пустой шаблон."
        />
      )}
      <div className={styles.layout}>
        <div className={styles.column}>
          <section className={styles.panel} aria-label="Письмо">
            <h2 className={styles.panelTitle}>Письмо</h2>
            {draft?.aiGenerated && <p className={styles.note}>{APPEAL_LABELS.aiNote}</p>}
            <Field label="Тема">
              <Input
                value={subject}
                maxLength={SUBJECT_MAX_LENGTH}
                placeholder="Тема письма поставщику"
                onChange={(event) => setSubject(event.target.value)}
              />
            </Field>
            <Field label="Текст письма" hint="Разметка Markdown: абзацы, **жирный**, списки.">
              <Input.TextArea
                value={text}
                maxLength={TEXT_MAX_LENGTH}
                autoSize={TEXT_ROWS}
                placeholder="Текст обращения к поставщику"
                onChange={(event) => setText(event.target.value)}
              />
            </Field>
            <Field label="Комментарий" hint="Необязателен; уходит в обращение отдельно от текста письма (ТЗ п. 17).">
              <Input.TextArea
                value={comment}
                maxLength={COMMENT_MAX_LENGTH}
                autoSize={COMMENT_ROWS}
                onChange={(event) => setComment(event.target.value)}
              />
            </Field>
          </section>
        </div>
        <div className={styles.column}>
          <section className={styles.panel} aria-label="Сведения">
            <h2 className={styles.panelTitle}>Сведения</h2>
            {draft ? (
              <AppealFacts context={draft.context} recipientEmail={draft.recipientEmail} />
            ) : (
              <p className={styles.note}>
                Период: {periodCaption(target.periodFrom, target.periodTo)}. Остальные сведения соберёт сервер.
              </p>
            )}
          </section>
        </div>
      </div>
    </>
  )
}

/**
 * Editor of an appeal draft (ТЗ п. 17, DESIGN.md §3.19, ADR-011): the card of an incident or of a school opens it
 * with the target in the address. The text is always edited by a person before sending, and the number is assigned
 * after it, so «Отправить обращение» waits for T-48. A draft that did not arrive is not an error of the screen:
 * the editor opens with the template either way.
 */
export function AppealDraftPage() {
  const [params] = useSearchParams()
  const target = useMemo(() => readAppealTarget(params), [params])
  const draft = useAppealDraft(target)

  if (!target) {
    return (
      <EmptyState
        icon={MailX}
        title="Обращение не о чем"
        description="Откройте черновик кнопкой «Создать обращение» в карточке инцидента или школы."
      />
    )
  }
  if (draft.isPending) return <ContentSkeleton rows={8} />
  return (
    <AppealEditor
      key={draft.dataUpdatedAt}
      target={target}
      draft={draft.data}
      asking={draft.isFetching}
      onRetry={() => void draft.refetch()}
    />
  )
}
