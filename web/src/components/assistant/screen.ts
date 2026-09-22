import type { AssistantScreen, UserRole } from '../../api/types'

/**
 * Screen of the panel behind an address (T-84): what the assistant is told the person is
 * looking at. The sections are those of `app/sections.ts`; a card is told from its list by the
 * id after it, the draft of an appeal by `new`. The same address `/schools/:id` is the cabinet
 * for the school role and the card of T-25 for everyone else (T-61). An address without a
 * screen of its own — the root, the sign-in, the wall, the placeholder of «Устройства» — is
 * `other`, and the assistant answers from the common part of its description.
 */
export function assistantScreen(pathname: string, role: UserRole | undefined): AssistantScreen {
  // `useLocation().pathname` carries no query, but a full address is accepted just the same.
  const [section, id] = pathname.split(/[?#]/, 1)[0].split('/').filter(Boolean)
  switch (section) {
    case 'overview':
      return 'overview'
    case 'map':
      return 'map'
    case 'schools':
      if (id === undefined) return 'schools'
      return role === 'school' ? 'school_cabinet' : 'school_card'
    case 'devices':
      return id === undefined ? 'other' : 'device_card'
    case 'incidents':
      return id === undefined ? 'incidents' : 'incident_card'
    case 'appeals':
      if (id === undefined) return 'appeals'
      return id === 'new' ? 'appeal_draft' : 'appeal_card'
    case 'providers':
      return 'providers'
    case 'rollout':
      return 'rollout'
    case 'analytics':
      return 'analytics'
    case 'exports':
      return 'exports'
    case 'admin':
      return 'admin'
    default:
      return 'other'
  }
}
