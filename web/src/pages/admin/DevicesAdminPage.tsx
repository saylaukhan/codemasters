import { useNotification } from '@refinedev/core'
import { App, Dropdown, Segmented, Tooltip, type TableColumnsType } from 'antd'
import { Ellipsis, Gauge, KeyRound } from 'lucide-react'
import { Link } from 'react-router'

import { ApiError } from '../../api/client'
import type { DeviceDetail } from '../../api/types'
import { deviceCardPath, schoolCardPath } from '../../app/sections'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { deviceName, deviceStatusOf } from '../../components/admin/devices'
import { useAdminDevices, useDeviceAction, type DeviceAction } from '../../components/admin/queries'
import { RebindDrawer } from '../../components/admin/RebindDrawer'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { Button } from '../../components/ui/Button'
import { SearchInput } from '../../components/ui/SearchInput'
import { DeviceStatusBadge } from '../../components/ui/StatusBadge'
import { NO_VALUE, formatDateTime, formatRelative } from '../../lib/format'
import { DEVICE_STATUS_FILTER_LABELS, MEASURE_PENDING_LABEL, TOKEN_ROTATION_PENDING_LABEL } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

type StatusFilter = keyof typeof DEVICE_STATUS_FILTER_LABELS

const IS_ACTIVE: Record<StatusFilter, boolean | undefined> = { all: undefined, active: true, blocked: false }

const STATUS_OPTIONS = (Object.keys(DEVICE_STATUS_FILTER_LABELS) as StatusFilter[]).map((value) => ({
  value,
  label: DEVICE_STATUS_FILTER_LABELS[value],
}))

/** Confirmation of an action (DESIGN.md §3.20): the question names the computer, blocking is Danger. */
const CONFIRMS: Record<DeviceAction, { title: string; content: string; ok: string; done: string; danger?: boolean }> = {
  block: {
    title: 'Заблокировать компьютер',
    content: 'Сервер будет отклонять запросы агента, история замеров сохранится. Разблокировать можно в любой момент.',
    ok: 'Заблокировать',
    done: 'Компьютер заблокирован',
    danger: true,
  },
  unblock: {
    title: 'Разблокировать компьютер',
    content: 'Агент снова сможет передавать замеры со своим токеном.',
    ok: 'Разблокировать',
    done: 'Компьютер разблокирован',
  },
  rotate: {
    title: 'Заменить токен компьютера',
    content:
      'Агент получит новый токен сам при следующем обновлении настроек, старый токен сразу перестанет работать. ' +
      'Участие пользователя на ПК не нужно.',
    ok: 'Заменить токен',
    done: 'Замена токена запрошена',
  },
  measure: {
    title: 'Замерить сейчас на компьютере',
    content:
      'Агент получит запрос со следующим сигналом «жив» — обычно в течение пяти минут — и сделает один замер ' +
      'вне расписания. Если компьютер выключен дольше часа, запрос сгорает. Расписание замеров не меняется.',
    ok: 'Замерить',
    done: 'Замер запрошен',
  },
}

const COLUMNS: TableColumnsType<DeviceDetail> = [
  {
    key: 'device',
    title: 'Компьютер',
    fixed: 'left',
    render: (_, device) => (
      <span className={styles.stack}>
        <Link className={styles.name} to={deviceCardPath(device.id)}>
          {deviceName(device)}
        </Link>
        <span className={styles.code}>{device.deviceUid}</span>
      </span>
    ),
  },
  {
    key: 'school',
    title: 'Школа',
    render: (_, device) => (
      <span className={styles.stack}>
        <Link className={styles.name} to={schoolCardPath(device.schoolId)} title={device.schoolName}>
          {device.schoolName}
        </Link>
        <span className={styles.code}>{device.schoolCode}</span>
      </span>
    ),
  },
  {
    key: 'point',
    title: 'Точка и кабинет',
    render: (_, device) => (
      <span className={styles.stack}>
        <span>{device.monitoringPointName}</span>
        <span className={styles.muted}>{device.room ?? NO_VALUE}</span>
      </span>
    ),
  },
  { key: 'version', title: 'Версия агента', render: (_, device) => device.agentVersion ?? NO_VALUE },
  {
    key: 'seen',
    title: 'Последняя связь',
    render: (_, device) => <span title={formatDateTime(device.lastSeenAt)}>{formatRelative(device.lastSeenAt)}</span>,
  },
  {
    key: 'status',
    title: 'Статус',
    render: (_, device) => (
      <span className={styles.stack}>
        <DeviceStatusBadge status={device.status} />
        {device.measureRequestedAt && (
          <Tooltip title={`Запрошен ${formatDateTime(device.measureRequestedAt)}`}>
            <span className={styles.mark}>
              <Gauge size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />
              {MEASURE_PENDING_LABEL}
            </span>
          </Tooltip>
        )}
        {device.tokenRotationRequestedAt && (
          <Tooltip title={`Запрошена ${formatDateTime(device.tokenRotationRequestedAt)}`}>
            <span className={styles.mark}>
              <KeyRound size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />
              {TOKEN_ROTATION_PENDING_LABEL}
            </span>
          </Tooltip>
        )}
      </span>
    ),
  },
]

/** Computers of the oblast (ТЗ п. 12, п. 20): rebinding to a point, blocking without losing history, a new token. */
export function DevicesAdminPage() {
  const [view, setView] = useAdminListView()
  const devices = useAdminDevices(view)
  const drawer = useDrawer<DeviceDetail>()
  const action = useDeviceAction()
  const { modal } = App.useApp()
  const { open: notify } = useNotification()

  const confirm = (device: DeviceDetail, kind: DeviceAction) => {
    const text = CONFIRMS[kind]
    modal.confirm({
      title: `${text.title} ${deviceName(device)}?`,
      content: text.content,
      okText: text.ok,
      cancelText: 'Отмена',
      okButtonProps: { danger: text.danger },
      onOk: () =>
        action.mutateAsync({ action: kind, deviceId: device.id }).then(
          () => notify?.({ type: 'success', message: text.done, description: deviceName(device) }),
          (error: Error) =>
            notify?.({
              type: 'error',
              message: 'Действие не выполнено',
              description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
            }),
        ),
    })
  }

  const rowActions = (device: DeviceDetail) => (
    <Dropdown
      trigger={['click']}
      menu={{
        items: [
          { key: 'measure', label: 'Замерить сейчас' },
          { key: 'rebind', label: 'Перепривязать' },
          { key: 'rotate', label: 'Заменить токен' },
          device.status === 'active'
            ? { key: 'block', label: 'Заблокировать', danger: true }
            : { key: 'unblock', label: 'Разблокировать' },
        ],
        onClick: ({ key }) => (key === 'rebind' ? drawer.show(device) : confirm(device, key as DeviceAction)),
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
    <AdminLayout tab="devices" action={null}>
      <div className={styles.toolbar}>
        <SearchInput
          className={styles.search}
          value={view.q}
          placeholder="Поиск по компьютеру, школе или School ID"
          onSearch={(q) => setView({ ...view, q, page: 1 })}
        />
        <Segmented<StatusFilter>
          aria-label="Статус компьютера"
          value={deviceStatusOf(view.isActive) ?? 'all'}
          options={STATUS_OPTIONS}
          onChange={(filter) => setView({ ...view, isActive: IS_ACTIVE[filter], page: 1 })}
        />
      </div>
      <AdminTable
        query={devices}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{
          title: 'Компьютеров пока нет',
          description: 'Выдайте код установки в карточке школы и установите агент на ПК.',
        }}
        rowActions={rowActions}
      />
      {drawer.item && <RebindDrawer key={drawer.key} device={drawer.item} open={drawer.open} onClose={drawer.close} />}
    </AdminLayout>
  )
}
