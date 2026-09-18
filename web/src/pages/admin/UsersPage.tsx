import { useGetIdentity, useNotification } from '@refinedev/core'
import { App, Dropdown, Segmented, type TableColumnsType } from 'antd'
import { Ellipsis, Plus } from 'lucide-react'
import { useState } from 'react'

import { ApiError } from '../../api/client'
import type { CurrentUser, UserDetail } from '../../api/types'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { PasswordDrawer } from '../../components/admin/PasswordDrawer'
import { useSaveUser, useUsers } from '../../components/admin/queries'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { UserDrawer } from '../../components/admin/UserDrawer'
import { Button } from '../../components/ui/Button'
import { SearchInput } from '../../components/ui/SearchInput'
import { UserStatusBadge } from '../../components/ui/StatusBadge'
import { DEVICE_STATUS_FILTER_LABELS, ROLE_LABELS, WHOLE_OBLAST_SCOPE_LABEL } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

type StatusFilter = keyof typeof DEVICE_STATUS_FILTER_LABELS

const IS_ACTIVE: Record<StatusFilter, boolean | undefined> = { all: undefined, active: true, blocked: false }

const STATUS_OPTIONS = (Object.keys(DEVICE_STATUS_FILTER_LABELS) as StatusFilter[]).map((value) => ({
  value,
  label: DEVICE_STATUS_FILTER_LABELS[value],
}))

const statusFilterOf = (isActive: boolean | undefined): StatusFilter =>
  isActive === undefined ? 'all' : isActive ? 'active' : 'blocked'

/** Confirmation of a block (DESIGN.md §3.20): the question names the user, blocking is Danger. */
const CONFIRMS = {
  block: {
    title: 'Заблокировать пользователя',
    content: 'Пользователь не сможет войти, его сессии завершатся. Записи журнала о нём сохранятся.',
    ok: 'Заблокировать',
    done: 'Пользователь заблокирован',
    danger: true,
  },
  unblock: {
    title: 'Разблокировать пользователя',
    content: 'Пользователь снова сможет войти со своим паролем.',
    ok: 'Разблокировать',
    done: 'Пользователь разблокирован',
    danger: false,
  },
} as const

type UserAction = keyof typeof CONFIRMS

const COLUMNS: TableColumnsType<UserDetail> = [
  {
    key: 'user',
    title: 'Пользователь',
    fixed: 'left',
    render: (_, user) => (
      <span className={styles.stack}>
        <span className={styles.name}>{user.fullName}</span>
        <span className={styles.muted}>{user.email}</span>
      </span>
    ),
  },
  { key: 'role', title: 'Роль', render: (_, user) => ROLE_LABELS[user.role] },
  {
    key: 'scope',
    title: 'Область видимости',
    render: (_, user) => user.scopeName ?? <span className={styles.muted}>{WHOLE_OBLAST_SCOPE_LABEL}</span>,
  },
  { key: 'status', title: 'Статус', render: (_, user) => <UserStatusBadge active={user.isActive} /> },
]

/** Users of the panel (ТЗ п. 16): a role with its scope, a password reset, blocking without losing history. */
export function UsersPage() {
  const [view, setView] = useAdminListView()
  const users = useUsers(view)
  const drawer = useDrawer<UserDetail>()
  const [resetFor, setResetFor] = useState<UserDetail>()
  const save = useSaveUser()
  const { data: me } = useGetIdentity<CurrentUser>()
  const { modal } = App.useApp()
  const { open: notify } = useNotification()

  const confirm = (user: UserDetail, kind: UserAction) => {
    const text = CONFIRMS[kind]
    modal.confirm({
      title: `${text.title} ${user.fullName}?`,
      content: text.content,
      okText: text.ok,
      cancelText: 'Отмена',
      okButtonProps: { danger: text.danger },
      onOk: () =>
        save.mutateAsync({ id: user.id, body: { isActive: kind === 'unblock' } }).then(
          () => notify?.({ type: 'success', message: text.done, description: user.fullName }),
          (error: Error) =>
            notify?.({
              type: 'error',
              message: 'Действие не выполнено',
              description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
            }),
        ),
    })
  }

  const rowActions = (user: UserDetail) => (
    <Dropdown
      trigger={['click']}
      menu={{
        items: [
          { key: 'edit', label: 'Изменить' },
          { key: 'password', label: 'Сбросить пароль' },
          // The signed-in administrator cannot block himself: the API refuses it too.
          ...(user.id === me?.id
            ? []
            : [
                user.isActive
                  ? { key: 'block', label: 'Заблокировать', danger: true }
                  : { key: 'unblock', label: 'Разблокировать' },
              ]),
        ],
        onClick: ({ key }) => {
          if (key === 'edit') drawer.show(user)
          else if (key === 'password') setResetFor(user)
          else confirm(user, key as UserAction)
        },
      }}
    >
      <Button
        kind="flat"
        size="small"
        tooltip="Действия"
        icon={<Ellipsis size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
      />
    </Dropdown>
  )

  return (
    <AdminLayout
      tab="users"
      action={
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          Добавить пользователя
        </Button>
      }
    >
      <div className={styles.toolbar}>
        <SearchInput
          className={styles.search}
          value={view.q}
          placeholder="Поиск по ФИО или e-mail"
          onSearch={(q) => setView({ ...view, q, page: 1 })}
        />
        <Segmented<StatusFilter>
          aria-label="Статус пользователя"
          value={statusFilterOf(view.isActive)}
          options={STATUS_OPTIONS}
          onChange={(filter) => setView({ ...view, isActive: IS_ACTIVE[filter], page: 1 })}
        />
      </div>
      <AdminTable
        query={users}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{
          title: 'Пользователей пока нет',
          description: 'Добавьте пользователя кнопкой «Добавить пользователя».',
        }}
        rowActions={rowActions}
      />
      <UserDrawer
        key={drawer.key}
        open={drawer.open}
        user={drawer.item}
        isSelf={drawer.item !== undefined && drawer.item.id === me?.id}
        onClose={drawer.close}
      />
      {resetFor && <PasswordDrawer key={resetFor.id} user={resetFor} open onClose={() => setResetFor(undefined)} />}
    </AdminLayout>
  )
}
