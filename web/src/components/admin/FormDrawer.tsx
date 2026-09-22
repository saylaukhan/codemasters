import { Drawer, type FormInstance } from 'antd'
import { useEffect, type ReactNode } from 'react'

import { useMediaQuery } from '../../app/useMediaQuery'
import { PHONE_SCREEN, SIZES } from '../../styles/theme'
import { Button } from '../ui/Button'
import { ErrorState } from '../ui/ErrorState'
import styles from './Admin.module.css'
import { formErrors } from './form'

interface FormDrawerProps {
  title: string
  open: boolean
  onClose: () => void
  /** Form of the drawer: «Сохранить» submits it, errors of the API land in it. */
  form: FormInstance
  /** Fields of the form (camelCase) the errors of the API may point at; a constant of the module. */
  fields: readonly string[]
  saving: boolean
  /** Error of the last save: under its fields when it names them, otherwise in the alert. */
  error: unknown
  /** False while the record is loading: there is nothing to save yet. */
  ready?: boolean
  children: ReactNode
}

/**
 * Drawer of 480px with a form (DESIGN.md §3.20): a separate screen with its own Action «Сохранить»,
 * «Отмена» is Outlined. Errors of the API go under the fields (ADR-009) or into an inline alert.
 */
export function FormDrawer({
  title,
  open,
  onClose,
  form,
  fields,
  saving,
  error,
  ready = true,
  children,
}: FormDrawerProps) {
  const phone = useMediaQuery(PHONE_SCREEN)

  useEffect(() => {
    const placed = formErrors(error, fields).fields
    if (placed.length > 0) form.setFields(placed)
  }, [form, fields, error])

  return (
    <Drawer
      title={title}
      open={open}
      onClose={onClose}
      // DESIGN.md §9.3, row «Drawer и модалка»: 480px, and the whole width at 768px and narrower.
      width={phone ? '100%' : SIZES.drawerWidth}
      footer={
        <div className={styles.footer}>
          <Button kind="outlined" onClick={onClose}>
            Отмена
          </Button>
          <Button kind="action" loading={saving} disabled={!ready} onClick={() => form.submit()}>
            Сохранить
          </Button>
        </div>
      }
    >
      {children}
      {formErrors(error, fields).alert && (
        <div className={styles.alert}>
          <ErrorState error={error} />
        </div>
      )}
    </Drawer>
  )
}
