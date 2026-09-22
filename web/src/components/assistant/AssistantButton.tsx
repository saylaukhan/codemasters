import { useGetIdentity } from '@refinedev/core'
import { MessageCircleQuestionMark } from 'lucide-react'
import { useState } from 'react'

import type { CurrentUser } from '../../api/types'
import { useMediaQuery } from '../../app/useMediaQuery'
import { ASSISTANT_LABELS } from '../../lib/labels'
import { NARROW_SCREEN, SIZES } from '../../styles/theme'
import { Button } from '../ui/Button'
import { AssistantDrawer } from './AssistantDrawer'
import { useAssistantStatus } from './queries'

// Every role has it (backend/app/auth/permissions.py); the API then says whether the assistant is on.
export const ASSISTANT_PERMISSION = 'assistant:ask'

/**
 * Button of the header (T-84, DESIGN.md §3.5): a flat icon with a tooltip next to the bell and
 * the drawer of ADR-017 behind it. It is in the header only when the role may ask and the
 * assistant is on: switched off or without a model there is nothing to open. In the cabinet of
 * a school the button carries its word — the director sees no sidebar and reads no icons, and
 * the header has the room (§3.27); at 1024px and narrower it is an icon like the rest.
 */
export function AssistantButton() {
  const { data: user } = useGetIdentity<CurrentUser>()
  const narrow = useMediaQuery(NARROW_SCREEN)
  const [open, setOpen] = useState(false)
  const allowed = user?.permissions.includes(ASSISTANT_PERMISSION) ?? false
  const status = useAssistantStatus(allowed)
  if (!user || !allowed || !status.data?.available) return null
  const labelled = user.role === 'school' && !narrow
  return (
    <>
      <Button
        kind="flat"
        tooltip={ASSISTANT_LABELS.open}
        icon={<MessageCircleQuestionMark size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} />}
        onClick={() => setOpen(true)}
      >
        {labelled ? ASSISTANT_LABELS.title : undefined}
      </Button>
      <AssistantDrawer open={open} onClose={() => setOpen(false)} role={user.role} />
    </>
  )
}
