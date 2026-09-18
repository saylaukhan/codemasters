import { SearchX } from 'lucide-react'
import { Link } from 'react-router'

import { EmptyState } from '../../components/ui/EmptyState'

export function NotFoundPage() {
  return (
    <EmptyState
      icon={SearchX}
      title="Страница не найдена"
      description="Проверьте адрес или вернитесь на главную."
      action={<Link to="/">На главную</Link>}
    />
  )
}
