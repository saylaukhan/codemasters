import { useCallback, useState } from 'react'

interface DrawerState<T> {
  open: boolean
  /** The row being edited; none — a new record. */
  item?: T
  /** Key of the drawer: each opening starts with a fresh form, the closing one keeps its content. */
  key: number
}

/** Drawer of a list (DESIGN.md §3.20): opened for a new record or for a row. */
export function useDrawer<T>() {
  const [state, setState] = useState<DrawerState<T>>({ open: false, key: 0 })
  const show = useCallback((item?: T) => setState(({ key }) => ({ open: true, item, key: key + 1 })), [])
  const close = useCallback(() => setState((current) => ({ ...current, open: false })), [])
  return { ...state, show, close }
}
