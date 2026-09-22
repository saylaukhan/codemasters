import { Drawer, Input } from 'antd'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { useLocation } from 'react-router'

import type { UserRole } from '../../api/types'
import { useMediaQuery } from '../../app/useMediaQuery'
import { ASSISTANT_LABELS, ASSISTANT_SUGGESTIONS } from '../../lib/labels'
import { PHONE_SCREEN, SIZES } from '../../styles/theme'
import { Button } from '../ui/Button'
import { ContentSkeleton } from '../ui/ContentSkeleton'
import { ErrorState } from '../ui/ErrorState'
import styles from './Assistant.module.css'
import { AssistantAnswer } from './AssistantAnswer'
import {
  QUESTION_MAX_LENGTH,
  cleanQuestion,
  questionBody,
  withAnswer,
  withQuestion,
  type AssistantTurn,
} from './conversation'
import { useAskAssistant } from './queries'
import { assistantScreen } from './screen'

interface AssistantDrawerProps {
  open: boolean
  onClose: () => void
  /** Role of the signed-in user: the same address is the cabinet for a school and a card for the rest. */
  role: UserRole
}

/**
 * Drawer of the interface assistant (T-84, ADR-017; DESIGN.md §3.20): 480px on the right, the
 * whole width on a phone. The body holds the welcome, the frequent questions of the open screen
 * while the dialog is empty, then the dialog itself; the footer holds the question and the one
 * Action of this screen, «Спросить». The dialog lives here, in the browser: it survives the
 * closing of the drawer and a change of page, and «Начать заново» drops it.
 */
export function AssistantDrawer({ open, onClose, role }: AssistantDrawerProps) {
  const phone = useMediaQuery(PHONE_SCREEN)
  const { pathname } = useLocation()
  const screen = assistantScreen(pathname, role)
  const [turns, setTurns] = useState<AssistantTurn[]>([])
  const [draft, setDraft] = useState('')
  const ask = useAskAssistant()
  // An answer that arrives after «Начать заново» belongs to the dropped dialog, not to the new one.
  const dialog = useRef(0)
  const end = useRef<HTMLDivElement>(null)

  // The newest line stays in view: a long answer would otherwise open above the fold.
  useEffect(() => {
    if (open) end.current?.scrollIntoView({ block: 'end' })
  }, [open, turns, ask.isPending])

  const send = (lines: AssistantTurn[]) => {
    const current = dialog.current
    setTurns(lines)
    ask.mutate(questionBody(screen, lines), {
      onSuccess: (answer) => {
        if (dialog.current === current) setTurns((known) => withAnswer(known, answer.text))
      },
    })
  }

  const submit = () => {
    const text = cleanQuestion(draft)
    if (text === null || ask.isPending) return
    setDraft('')
    send(withQuestion(turns, text))
  }

  const restart = () => {
    dialog.current += 1
    setTurns([])
    setDraft('')
    ask.reset()
  }

  // Enter sends, Shift+Enter breaks the line, as in a messenger.
  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  const empty = turns.length === 0

  const footer = (
    <div className={styles.footer}>
      <div className={styles.form}>
        <Input.TextArea
          className={styles.question}
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder={ASSISTANT_LABELS.placeholder}
          aria-label={ASSISTANT_LABELS.placeholder}
          autoSize={{ minRows: 1, maxRows: 4 }}
          maxLength={QUESTION_MAX_LENGTH}
        />
        <Button kind="action" loading={ask.isPending} disabled={cleanQuestion(draft) === null} onClick={submit}>
          {ASSISTANT_LABELS.ask}
        </Button>
      </div>
      <p className={styles.disclaimer}>{ASSISTANT_LABELS.disclaimer}</p>
    </div>
  )

  return (
    <Drawer
      className={styles.drawer}
      title={ASSISTANT_LABELS.title}
      placement="right"
      // DESIGN.md §9.3, row «Drawer и модалка»: 480px, and the whole width at 768px and narrower.
      width={phone ? '100%' : SIZES.drawerWidth}
      open={open}
      onClose={onClose}
      extra={
        <Button kind="flat" size="small" disabled={empty && !ask.isError} onClick={restart}>
          {ASSISTANT_LABELS.restart}
        </Button>
      }
      footer={footer}
    >
      <p className={styles.welcome}>{ASSISTANT_LABELS.welcome}</p>
      {empty && (
        <div className={styles.suggestions} role="group" aria-label={ASSISTANT_LABELS.suggestions}>
          <p className={styles.caption}>{ASSISTANT_LABELS.suggestions}</p>
          {ASSISTANT_SUGGESTIONS[screen].map((text) => (
            <button
              key={text}
              type="button"
              className={styles.chip}
              disabled={ask.isPending}
              onClick={() => send(withQuestion(turns, text))}
            >
              {text}
            </button>
          ))}
        </div>
      )}
      <div className={styles.log} role="log" aria-live="polite">
        {turns.map((turn, index) => (
          <div key={index} className={styles.turn} data-author={turn.author}>
            <span className={styles.author}>
              {turn.author === 'user' ? ASSISTANT_LABELS.you : ASSISTANT_LABELS.assistant}
            </span>
            <div className={styles.bubble}>
              {turn.author === 'user' ? <p>{turn.text}</p> : <AssistantAnswer text={turn.text} />}
            </div>
          </div>
        ))}
        {ask.isPending && (
          <div className={styles.turn} data-author="assistant" aria-label={ASSISTANT_LABELS.thinking}>
            <span className={styles.author}>{ASSISTANT_LABELS.assistant}</span>
            <div className={styles.bubble}>
              <ContentSkeleton rows={2} />
            </div>
          </div>
        )}
        {ask.isError && <ErrorState error={ask.error} onRetry={() => send(turns)} />}
        <div ref={end} />
      </div>
    </Drawer>
  )
}
