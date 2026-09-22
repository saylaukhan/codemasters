import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { AssistantAnswer } from './AssistantAnswer'
import { inlines, parseAnswer } from './markup'

describe('markup of an answer (T-84)', () => {
  it('splits bold runs and leaves an unpaired asterisk alone', () => {
    expect(inlines('Нажмите **«Спросить»** и ждите')).toEqual([
      { strong: false, text: 'Нажмите ' },
      { strong: true, text: '«Спросить»' },
      { strong: false, text: ' и ждите' },
    ])
    expect(inlines('2 * 2')).toEqual([{ strong: false, text: '2 * 2' }])
  })

  it('groups lines into paragraphs and lists of one kind', () => {
    const blocks = parseAnswer(
      ['Откройте кабинет.', 'Затем:', '', '1. Нажмите **«Сообщить о проблеме»**.', '2) Проверьте письмо.', '- Это подсказка', '', '## Итог', 'Готово.'].join('\n'),
    )

    expect(blocks.map((block) => block.kind)).toEqual(['paragraph', 'list', 'list', 'paragraph', 'paragraph'])
    expect(blocks[0]).toEqual({ kind: 'paragraph', inlines: [{ strong: false, text: 'Откройте кабинет. Затем:' }] })
    expect(blocks[1]).toMatchObject({ kind: 'list', ordered: true })
    expect(blocks[1].kind === 'list' && blocks[1].items).toHaveLength(2)
    expect(blocks[2]).toMatchObject({ kind: 'list', ordered: false })
    // A heading the prompt forbids is not lost: it becomes a bold line of its own.
    expect(blocks[3]).toEqual({ kind: 'paragraph', inlines: [{ strong: true, text: 'Итог' }] })
    expect(blocks[4]).toEqual({ kind: 'paragraph', inlines: [{ strong: false, text: 'Готово.' }] })
  })

  it('draws the blocks without a symbol of Markdown left', () => {
    const html = renderToStaticMarkup(<AssistantAnswer text={'Шаги:\n\n1. Откройте **«Отчёты и экспорт»**.\n2. Нажмите «Скачать».'} />)

    expect(html).toBe(
      '<p>Шаги:</p><ol><li>Откройте <strong>«Отчёты и экспорт»</strong>.</li><li>Нажмите «Скачать».</li></ol>',
    )
    expect(html).not.toContain('**')
  })
})
