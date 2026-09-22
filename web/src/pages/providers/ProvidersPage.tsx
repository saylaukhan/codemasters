import { Segmented } from 'antd'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router'

import { ProviderCard } from '../../components/providers/ProviderCard'
import styles from '../../components/providers/Provider.module.css'
import { ProvidersTable } from '../../components/providers/ProvidersTable'
import { useDownloadProviderAct, useProviderCard, useProviderScore } from '../../components/providers/queries'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { FilterBar, FilterChip } from '../../components/ui/FilterBar'
import { PageHeader } from '../../components/ui/PageHeader'
import { PERIOD_LABELS, PROVIDER_LABELS, SECTION_LABELS } from '../../lib/labels'

type Period = keyof typeof PERIOD_LABELS

const PERIODS = Object.keys(PERIOD_LABELS) as Period[]
const DEFAULT_PERIOD: Period = 'month'

const period = (value: string | null): Period => PERIODS.find((preset) => preset === value) ?? DEFAULT_PERIOD

/**
 * Section «Поставщики» (T-68; ТЗ п. 14, п. 19; DESIGN.md §3.29): the score of every provider of the period,
 * the filter «договор ниже норматива» and the card of the selected one with its act. The period, the filter
 * and the selection live in the URL, so the screen of a colleague is one link away (DESIGN.md §2.6).
 */
export function ProvidersPage() {
  const [params, setParams] = useSearchParams()
  const view = {
    period: period(params.get('period')),
    belowNorm: params.get('belowNorm') === '1',
    selected: Number(params.get('provider')) || null,
  }
  const score = useProviderScore(view.period)
  const rows = useMemo(() => {
    const all = score.data?.rows ?? []
    return view.belowNorm ? all.filter((row) => row.linesBelowNormCount > 0) : all
  }, [score.data, view.belowNorm])
  // The card follows the table: without a chosen provider it opens the worst-scored row of it.
  const worst = [...rows].sort((a, b) => (a.score ?? 0) - (b.score ?? 0))[0]
  const selectedId = rows.some((row) => row.id === view.selected) ? view.selected : (worst?.id ?? null)
  const card = useProviderCard(selectedId, view.period)
  const act = useDownloadProviderAct(view.period)

  const change = (next: Partial<typeof view>) =>
    setParams(
      (current) => {
        const search = new URLSearchParams(current)
        if (next.period !== undefined) search.set('period', next.period)
        if (next.belowNorm !== undefined) {
          if (next.belowNorm) search.set('belowNorm', '1')
          else search.delete('belowNorm')
          search.delete('provider')
        }
        if (next.selected !== undefined && next.selected !== null) search.set('provider', String(next.selected))
        return search
      },
      { replace: true },
    )

  const empty = view.belowNorm ? (
    <EmptyState
      title={PROVIDER_LABELS.filteredEmpty}
      description={PROVIDER_LABELS.belowNormHint}
      action={<Button onClick={() => change({ belowNorm: false })}>{PROVIDER_LABELS.reset}</Button>}
    />
  ) : (
    <EmptyState title={PROVIDER_LABELS.empty} description={PROVIDER_LABELS.emptyHint} />
  )

  return (
    <div className={styles.page}>
      <PageHeader
        context={PROVIDER_LABELS.context}
        title={SECTION_LABELS.providers}
        subtitle={PROVIDER_LABELS.subtitle}
        actions={
          <Segmented<Period>
            value={view.period}
            onChange={(next) => change({ period: next })}
            options={PERIODS.map((preset) => ({ value: preset, label: PERIOD_LABELS[preset] }))}
          />
        }
      />
      <FilterBar
        label={PROVIDER_LABELS.scoreTable}
        onReset={view.belowNorm ? () => change({ belowNorm: false }) : undefined}
      >
        <FilterChip
          label={PROVIDER_LABELS.belowNormFilter}
          value={view.belowNorm ? PROVIDER_LABELS.notAClaim : undefined}
          onClick={() => change({ belowNorm: !view.belowNorm })}
          onClear={view.belowNorm ? () => change({ belowNorm: false }) : undefined}
        />
      </FilterBar>
      {score.isError ? (
        <ErrorState error={score.error} onRetry={() => void score.refetch()} />
      ) : score.isPending ? (
        <ContentSkeleton />
      ) : (
        <ProvidersTable
          rows={rows}
          passPct={score.data.weights.passPct}
          selectedId={selectedId}
          loading={score.isFetching}
          empty={empty}
          onSelect={(provider) => change({ selected: provider })}
        />
      )}
      {card.isError ? (
        <ErrorState error={card.error} onRetry={() => void card.refetch()} />
      ) : card.isPending ? (
        selectedId === null ? null : <ContentSkeleton />
      ) : (
        <ProviderCard
          detail={card.data}
          downloading={act.isPending}
          onDownloadAct={() => act.mutate(card.data.provider)}
        />
      )}
    </div>
  )
}
