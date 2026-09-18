import { Input } from 'antd'
import { Search } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { SIZES } from '../../styles/theme'

// Pause after the last key before the list is asked again.
const SEARCH_DELAY_MS = 300

interface SearchInputProps {
  /** Search applied to the list, e.g. the `q` of the URL. */
  value: string
  placeholder: string
  onSearch: (value: string) => void
  className?: string
}

/** Search field of DESIGN.md §3.2: magnifier on the left, clear button; searches after a pause or on Enter. */
export function SearchInput({ value, placeholder, onSearch, className }: SearchInputProps) {
  const [text, setText] = useState(value)
  const [applied, setApplied] = useState(value)
  const timer = useRef<number | undefined>(undefined)
  // The search changed outside the field (e.g. «Сбросить поиск»): the field shows it.
  if (value !== applied) {
    setApplied(value)
    setText(value)
  }
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const search = (next: string, delay: number) => {
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => onSearch(next), delay)
  }

  return (
    <Input
      className={className}
      aria-label={placeholder}
      placeholder={placeholder}
      value={text}
      prefix={<Search size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
      allowClear
      onChange={(event) => {
        setText(event.target.value)
        search(event.target.value, event.target.value ? SEARCH_DELAY_MS : 0)
      }}
      onPressEnter={() => search(text, 0)}
    />
  )
}
