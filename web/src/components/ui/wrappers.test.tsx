import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'

import { BrandMark } from './BrandMark'
import { DayStrip } from './DayStrip'
import { FactBar } from './FactBar'
import { FilterChip } from './FilterBar'
import { KpiStrip } from './KpiStrip'
import { ResponsiveTable } from './ResponsiveTable'
import { StatusStrip } from './StatusStrip'

describe('StatusStrip (DESIGN.md §3.10, §3.28)', () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <StatusStrip
        items={[
          { status: 'normal', count: 312, href: '/schools?status=normal', delta: 3 },
          { status: 'unstable', count: 21, href: '/schools?status=unstable', delta: 0 },
          { status: 'critical', count: 9, href: '/schools?status=critical', delta: 2 },
          { status: 'offline', count: 8, href: '/schools?status=offline', delta: -5 },
        ]}
        footnote="Нет данных: 4"
      />
    </MemoryRouter>,
  )

  it('declines «школа» by the count', () => {
    expect(html).toContain('312</span><span class="_unit_')
    expect(html).toContain('>школ<')
    expect(html).toContain('>школа<')
  })

  it('reads a change over the day in words, not only by colour', () => {
    expect(html).toContain('▲ 3 за сутки')
    expect(html).toContain('▼ 5 за сутки')
    expect(html).toContain('без изменений')
  })

  it('keeps «Нет данных» out of the clickable columns (ADR-004)', () => {
    expect(html.match(/<a /g)).toHaveLength(4)
    expect(html).toContain('Нет данных: 4')
  })
})

describe('KpiStrip (DESIGN.md §3.10)', () => {
  it('prints the caption, the ready value, the unit, the hint and the delta', () => {
    const html = renderToStaticMarkup(
      <KpiStrip
        items={[
          { key: 'schools', label: 'Подключённые школы', value: '350', hint: 'из 366 в реестре' },
          {
            key: 'down',
            label: 'Средняя загрузка',
            value: '46,2',
            unit: 'Мбит/с',
            delta: { text: '▲ 1,8', tone: 'good' },
          },
        ]}
      />,
    )

    expect(html).toContain('Подключённые школы')
    expect(html).toContain('из 366 в реестре')
    expect(html).toContain('Мбит/с')
    expect(html).toContain('data-tone="good"')
  })
})

describe('DayStrip (DESIGN.md §3.27)', () => {
  it('titles every cell «DD.MM · статус», so colour is never the only carrier', () => {
    const html = renderToStaticMarkup(
      <DayStrip
        days={[
          { date: '2026-09-01T00:00:00Z', status: 'normal' },
          { date: '2026-09-02T00:00:00Z', status: 'offline' },
        ]}
        captions={['23 августа', '2 сен · без связи 3 ч', 'сегодня']}
      />,
    )

    expect(html).toContain('title="01.09 · Норма"')
    expect(html).toContain('title="02.09 · Нет соединения"')
    expect(html).toContain('2 сен · без связи 3 ч')
  })
})

describe('FactBar (DESIGN.md §3.10, §3.27)', () => {
  it('gives a speed both ticks and says what they mean', () => {
    const html = renderToStaticMarkup(
      <FactBar value={45.3} scale={60} threshold={20} contract={50} status="normal" unit="Мбит/с" higherIsBetter />,
    )

    expect(html).toContain('data-kind="threshold"')
    expect(html).toContain('data-kind="contract"')
    expect(html).toContain('норма от 20')
    expect(html).toContain('по договору 50')
    expect(html).toContain('aria-valuetext="45,3 Мбит/с"')
  })

  it('gives ping only the norm tick', () => {
    const html = renderToStaticMarkup(
      <FactBar value={27} scale={150} threshold={100} status="normal" unit="мс" higherIsBetter={false} />,
    )

    expect(html).toContain('data-kind="threshold"')
    expect(html).not.toContain('data-kind="contract"')
    expect(html).toContain('чем меньше, тем лучше')
    expect(html).toContain('норма до 100')
  })
})

describe('FilterChip (DESIGN.md §3.9)', () => {
  it('shows «Подпись: значение» and a clear button once it is set', () => {
    const active = renderToStaticMarkup(<FilterChip label="Район" value="Усть-Каменогорск" onClear={() => {}} />)
    expect(active).toContain('data-active="true"')
    expect(active).toContain('Район:')
    expect(active).toContain('aria-label="Очистить фильтр: Район"')
    // One pill holds both controls, so the cross is drawn inside it and not beside it (§3.9).
    expect(active).toContain('data-clearable="true"')
    // The cross is an icon button, so it carries both a label and a tooltip (DESIGN.md §3.0).
    expect(active).toContain('aria-describedby=')

    const empty = renderToStaticMarkup(<FilterChip label="Район" />)
    expect(empty).toContain('data-active="false"')
    expect(empty).not.toContain('aria-label="Очистить фильтр: Район"')
  })
})

describe('ResponsiveTable (DESIGN.md §3.12)', () => {
  it('renders the plain table where there is no window to measure (vitest runs on node)', () => {
    const html = renderToStaticMarkup(
      <ResponsiveTable<{ id: number; name: string; region: string }>
        rowKey="id"
        columns={[
          { key: 'name', title: 'Школа', dataIndex: 'name', priority: 'primary' },
          { key: 'region', title: 'Район', dataIndex: 'region' },
        ]}
        dataSource={[{ id: 1, name: 'Школа-гимназия № 12', region: 'Усть-Каменогорск' }]}
        pagination={false}
        card={{ title: (row) => row.name }}
      />,
    )

    expect(html).toContain('Школа-гимназия № 12')
    expect(html).toContain('Усть-Каменогорск')
  })
})

describe('BrandMark (DESIGN.md §1)', () => {
  it('is decorative: hidden from assistive technology, no text of its own', () => {
    const html = renderToStaticMarkup(<BrandMark />)
    expect(html).toContain('aria-hidden="true"')
    expect(html).toContain('<svg')
    expect(html).not.toMatch(/>[^<]+</)
  })

  it('takes the wall size on the wall', () => {
    expect(renderToStaticMarkup(<BrandMark size="lg" />)).toMatch(/class="_mark_[^"]* _lg_/)
  })
})
