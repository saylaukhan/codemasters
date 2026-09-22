import { FileDown } from 'lucide-react'
import { Link } from 'react-router'

import type { ProviderScoreDetail, ProviderSchoolRow } from '../../api/providers'
import { schoolCardPath } from '../../app/sections'
import { formatDuration, formatNumber, formatPercent, formatSpeed, NO_VALUE } from '../../lib/format'
import {
  PROVIDER_COLUMN_LABELS,
  PROVIDER_KPI_LABELS,
  PROVIDER_LABELS,
  PROVIDER_VERDICT_LABELS,
} from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import { OverviewSection } from '../overview/OverviewSection'
import { Button } from '../ui/Button'
import { KpiStrip, type KpiStripItem } from '../ui/KpiStrip'
import { ResponsiveTable, type ResponsiveColumn } from '../ui/ResponsiveTable'
import { ConnectionStatusBadge } from '../ui/StatusBadge'
import styles from './Provider.module.css'

interface ProviderCardProps {
  detail: ProviderScoreDetail
  downloading: boolean
  onDownloadAct: () => void
}

const duration = (seconds: number | null) => (seconds === null ? NO_VALUE : formatDuration(seconds))

/** Strip of the card in the order of `Providers.html`: what is claimed, and against which norm. */
function kpis(detail: ProviderScoreDetail): KpiStripItem[] {
  const row = detail.provider
  return [
    {
      key: 'belowContract',
      label: PROVIDER_KPI_LABELS.belowContract,
      value: formatPercent(row.belowContractPct),
      alert: (row.belowContractPct ?? 0) > 0,
    },
    {
      key: 'incidents',
      label: PROVIDER_KPI_LABELS.incidents,
      value: formatNumber(row.incidentsOpened, 0),
      hint: PROVIDER_LABELS.incidentsClosed(formatNumber(row.incidentsClosed, 0)),
    },
    {
      key: 'reaction',
      label: PROVIDER_KPI_LABELS.reaction,
      value: duration(row.reactionMedianS),
      hint: PROVIDER_LABELS.reactionNorm(formatDuration(detail.weights.reactionNormHours * 3600)),
    },
    {
      key: 'restore',
      label: PROVIDER_KPI_LABELS.restore,
      value: duration(row.restoreAvgS),
      hint: row.restoreWorstS === null ? undefined : PROVIDER_LABELS.worst(formatDuration(row.restoreWorstS)),
    },
    {
      key: 'availability',
      label: PROVIDER_KPI_LABELS.availability,
      value: formatPercent(row.availabilityPct, 2),
      hint: PROVIDER_LABELS.availabilityNorm(formatPercent(detail.availabilityMinPct, 0)),
      alert: row.availabilityPct !== null && row.availabilityPct < detail.availabilityMinPct,
    },
  ]
}

/**
 * Card of the selected provider (DESIGN.md §3.29, docs/design/README.md §6.3): the strip of its numbers, its
 * schools, the lines whose contract is below the norm — «не претензия» — and the act of non-compliance.
 */
export function ProviderCard({ detail, downloading, onDownloadAct }: ProviderCardProps) {
  const row = detail.provider
  const columns: ResponsiveColumn<ProviderSchoolRow>[] = [
    {
      key: 'name',
      title: PROVIDER_COLUMN_LABELS.school,
      priority: 'primary',
      render: (_, school) => <Link to={schoolCardPath(school.schoolId)}>{school.name}</Link>,
    },
    {
      key: 'region',
      title: PROVIDER_COLUMN_LABELS.region,
      priority: 'minor',
      render: (_, school) => school.regionName ?? NO_VALUE,
    },
    {
      key: 'belowContract',
      title: PROVIDER_LABELS.schoolsBelowContract,
      align: 'right',
      sorter: (a, b) => (a.belowContractPct ?? 0) - (b.belowContractPct ?? 0),
      defaultSortOrder: 'descend',
      render: (_, school) => (
        <span className={styles.number}>{formatPercent(school.belowContractPct)}</span>
      ),
    },
    {
      key: 'status',
      title: PROVIDER_COLUMN_LABELS.status,
      render: (_, school) => <ConnectionStatusBadge status={school.status} />,
    },
  ]

  return (
    <div className={styles.card}>
      <div className={styles.main}>
        <OverviewSection
          title={row.name}
          note={PROVIDER_LABELS.scoreOf(
            row.score === null ? PROVIDER_LABELS.noScore : formatNumber(row.score, 0),
            formatNumber(detail.weights.passPct, 0),
          )}
        >
          <KpiStrip items={kpis(detail)} label={row.name} />
          {row.verdict === 'below_norm' && (
            <p className={styles.note}>
              {PROVIDER_VERDICT_LABELS.below_norm}: {PROVIDER_LABELS.escalationHint}
            </p>
          )}
        </OverviewSection>
        <OverviewSection title={PROVIDER_LABELS.schools} count={detail.schools.length}>
          <ResponsiveTable<ProviderSchoolRow>
            rowKey={(school) => school.schoolId}
            size="middle"
            columns={columns}
            dataSource={detail.schools}
            scroll={{ x: 'max-content' }}
            showSorterTooltip={false}
            pagination={false}
            card={{
              title: (school) => <Link to={schoolCardPath(school.schoolId)}>{school.name}</Link>,
              status: (school) => <ConnectionStatusBadge status={school.status} />,
              description: (school) => school.regionName ?? undefined,
            }}
          />
        </OverviewSection>
      </div>
      <div className={styles.aside}>
        <OverviewSection
          title={PROVIDER_LABELS.belowNorm}
          count={detail.linesBelowNorm.length}
          note={PROVIDER_LABELS.notAClaim}
        >
          <p className={styles.hint}>{PROVIDER_LABELS.belowNormHint}</p>
          {detail.linesBelowNorm.length === 0 ? (
            <p className={styles.note}>{PROVIDER_LABELS.belowNormEmpty}</p>
          ) : (
            <ul className={styles.lines}>
              {detail.linesBelowNorm.map((line) => (
                <li key={line.lineId} className={styles.line}>
                  <Link className={styles.lineSchool} to={schoolCardPath(line.schoolId)}>
                    {line.schoolName}
                  </Link>
                  <span className={styles.lineContract}>
                    {PROVIDER_LABELS.contractOf(
                      formatSpeed(line.contractDownMbps),
                      formatSpeed(line.contractUpMbps),
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </OverviewSection>
        <OverviewSection title={PROVIDER_LABELS.actTitle}>
          <p className={styles.hint}>{PROVIDER_LABELS.actHint}</p>
          <p className={styles.note}>{PROVIDER_LABELS.plannedWorks}</p>
          <div className={styles.actions}>
            <Button
              kind="action"
              loading={downloading}
              icon={<FileDown size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
              onClick={onDownloadAct}
            >
              {PROVIDER_LABELS.act}
            </Button>
          </div>
        </OverviewSection>
      </div>
    </div>
  )
}
