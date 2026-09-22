import { useNotification } from '@refinedev/core'
import { Alert, Table, Upload, type TableColumnsType } from 'antd'
import { FileSpreadsheet } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../../api/client'
import type { ContractImportReport, ContractImportRequest, ContractImportRow } from '../../api/types'
import { schoolCardPath } from '../../app/sections'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import {
  base64OfDataUrl,
  canApply,
  importRequest,
  importSummary,
  isAcceptedFile,
  MAX_FILE_SIZE,
  rowChangeLines,
} from '../../components/admin/contractImport'
import { useImportContracts, usePreviewContractImport } from '../../components/admin/queries'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { ErrorState } from '../../components/ui/ErrorState'
import { NO_VALUE } from '../../lib/format'
import {
  CONTRACT_IMPORT_ACTION_LABELS,
  CONTRACT_IMPORT_COLUMN_LABELS,
  CONTRACT_IMPORT_LABELS,
} from '../../lib/labels'
import { PAGE_SIZES } from '../../components/schools/useSchoolListView'
import { SIZES } from '../../styles/theme'

const COLUMNS: TableColumnsType<ContractImportRow> = [
  {
    key: 'row',
    title: CONTRACT_IMPORT_COLUMN_LABELS.row,
    width: 80,
    render: (_, item) => <span className={styles.number}>{item.row}</span>,
  },
  {
    key: 'school',
    title: CONTRACT_IMPORT_COLUMN_LABELS.school,
    render: (_, item) => (
      <span className={styles.stack}>
        {item.schoolName ? <span className={styles.name}>{item.schoolName}</span> : <span>{NO_VALUE}</span>}
        <span className={`${styles.code} ${styles.muted}`}>{item.schoolCode ?? NO_VALUE}</span>
      </span>
    ),
  },
  { key: 'provider', title: CONTRACT_IMPORT_COLUMN_LABELS.provider, render: (_, item) => item.providerName ?? NO_VALUE },
  {
    key: 'action',
    title: CONTRACT_IMPORT_COLUMN_LABELS.action,
    render: (_, item) => (
      <span className={styles.stack}>
        <span className={item.action === 'error' ? styles.failed : item.action === 'unchanged' ? styles.muted : undefined}>
          {CONTRACT_IMPORT_ACTION_LABELS[item.action]}
        </span>
        {item.error && <span className={styles.muted}>{item.error}</span>}
        {item.schoolId !== null && item.action !== 'error' && (
          <Link className={styles.muted} to={`${schoolCardPath(item.schoolId)}?tab=lines`}>
            Линии школы
          </Link>
        )}
      </span>
    ),
  },
  {
    key: 'changes',
    title: CONTRACT_IMPORT_COLUMN_LABELS.changes,
    render: (_, item) => {
      const lines = rowChangeLines(item)
      if (lines.length === 0) return <span className={styles.muted}>{NO_VALUE}</span>
      return (
        <ul className={styles.changes}>
          {lines.map((line) => (
            <li key={line.field}>
              <span className={styles.muted}>{line.field}:</span> {line.old} → {line.new}
            </li>
          ))}
        </ul>
      )
    },
  },
]

interface ChosenFile {
  request: ContractImportRequest
  size: number
}

/**
 * Import of a contract registry (ТЗ п. 14, п. 20; T-61): a CSV or XLSX file is checked first — every row gets its
 * verdict without writing — and applied with the single Action of the screen. The lines get what the school card
 * edits by hand: the number, the date and the speeds of the contract, the identifier and the technology of the line.
 */
export function ContractsPage() {
  const [file, setFile] = useState<ChosenFile | null>(null)
  const preview = usePreviewContractImport()
  const apply = useImportContracts()
  const { open: notify } = useNotification()
  const report: ContractImportReport | undefined = apply.data ?? preview.data

  const check = (chosen: ChosenFile) => {
    apply.reset()
    setFile(chosen)
    preview.mutate(chosen.request)
  }

  const read = (raw: File) => {
    if (!isAcceptedFile(raw.name)) {
      notify?.({ type: 'error', message: CONTRACT_IMPORT_LABELS.previewFailed, description: CONTRACT_IMPORT_LABELS.uploadHint })
      return
    }
    if (raw.size > MAX_FILE_SIZE) {
      notify?.({ type: 'error', message: CONTRACT_IMPORT_LABELS.previewFailed, description: 'Файл больше 2 МиБ' })
      return
    }
    const reader = new FileReader()
    reader.onload = () => check({ request: importRequest(raw.name, base64OfDataUrl(String(reader.result))), size: raw.size })
    reader.readAsDataURL(raw)
  }

  const run = () =>
    file &&
    apply.mutate(file.request, {
      onSuccess: (applied) =>
        notify?.({ type: 'success', message: CONTRACT_IMPORT_LABELS.applied, description: importSummary(applied) }),
      onError: (error) =>
        notify?.({
          type: 'error',
          message: CONTRACT_IMPORT_LABELS.applyFailed,
          description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
        }),
    })

  return (
    <AdminLayout
      tab="contracts"
      action={
        <Button
          kind="action"
          loading={apply.isPending}
          disabled={!canApply(preview.data) || apply.isSuccess}
          onClick={run}
        >
          {CONTRACT_IMPORT_LABELS.apply}
        </Button>
      }
    >
      <p className={styles.lead}>
        Реестр договоров загружается в линии школ: строка находит линию по School ID и поставщику (и по идентификатору
        линии, если он есть), а без такой линии создаёт новую. Колонки файла: School ID и Поставщик — обязательные;
        Идентификатор линии, Статус линии, Тип подключения, Номер договора, Дата договора, Download и Upload по
        договору — по наличию. Пустая ячейка ничего не меняет. Сначала файл проверяется, запись — кнопкой «
        {CONTRACT_IMPORT_LABELS.apply}».
      </p>
      {file === null ? (
        <Upload.Dragger
          className={styles.dropzone}
          accept=".csv,.xlsx"
          maxCount={1}
          showUploadList={false}
          beforeUpload={(raw) => {
            read(raw)
            return Upload.LIST_IGNORE
          }}
        >
          <p className={styles.dropIcon}>
            <FileSpreadsheet size={SIZES.iconEmpty} strokeWidth={SIZES.iconStroke} aria-hidden />
          </p>
          <p className={styles.dropTitle}>{CONTRACT_IMPORT_LABELS.upload}</p>
          <p className={styles.muted}>{CONTRACT_IMPORT_LABELS.uploadHint}</p>
        </Upload.Dragger>
      ) : (
        <div className={styles.toolbar}>
          <span className={styles.code}>{file.request.fileName}</span>
          <Button kind="outlined" size="small" disabled={apply.isPending} onClick={() => setFile(null)}>
            {CONTRACT_IMPORT_LABELS.chooseAnother}
          </Button>
        </div>
      )}
      {preview.isPending && <ContentSkeleton rows={6} />}
      {preview.isError && file && (
        <ErrorState error={preview.error} onRetry={() => preview.mutate(file.request)} />
      )}
      {report && !preview.isPending && (
        <>
          <Alert
            className={styles.alert}
            type={report.dryRun ? (canApply(report) ? 'info' : 'warning') : 'success'}
            showIcon
            message={
              report.dryRun
                ? canApply(report)
                  ? CONTRACT_IMPORT_LABELS.preview
                  : CONTRACT_IMPORT_LABELS.nothingToApply
                : CONTRACT_IMPORT_LABELS.result
            }
            description={importSummary(report)}
          />
          <Table<ContractImportRow>
            rowKey="row"
            size="middle"
            columns={COLUMNS}
            dataSource={report.items}
            scroll={{ x: 'max-content' }}
            pagination={{
              defaultPageSize: PAGE_SIZES[1] ?? PAGE_SIZES[0],
              pageSizeOptions: PAGE_SIZES.map(String),
              showSizeChanger: true,
              showTotal: (count, [from, to]) => `${from}–${to} из ${count}`,
            }}
          />
        </>
      )}
    </AdminLayout>
  )
}
