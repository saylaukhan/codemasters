import { describe, expect, it } from 'vitest'

import { DIALOG_MAX_MESSAGES, cleanQuestion, questionBody, withAnswer, withQuestion, type AssistantTurn } from './conversation'

describe('dialog of the assistant (T-84)', () => {
  it('appends the question and the answer in turn', () => {
    const asked = withQuestion([], 'Где замеры?')
    const answered = withAnswer(asked, 'В карточке компьютера.')

    expect(answered).toEqual([
      { author: 'user', text: 'Где замеры?' },
      { author: 'assistant', text: 'В карточке компьютера.' },
    ])
  })

  it('sends the open screen and the whole dialog, the question last', () => {
    const turns = withQuestion(withAnswer(withQuestion([], 'Где замеры?'), 'В карточке.'), 'А за месяц?')

    expect(questionBody('school_cabinet', turns)).toEqual({
      screen: 'school_cabinet',
      messages: [
        { author: 'user', text: 'Где замеры?' },
        { author: 'assistant', text: 'В карточке.' },
        { author: 'user', text: 'А за месяц?' },
      ],
    })
  })

  it('keeps only as many lines as the API takes, the oldest staying in the browser', () => {
    let turns: AssistantTurn[] = []
    for (let index = 0; index < DIALOG_MAX_MESSAGES; index += 1) {
      turns = withAnswer(withQuestion(turns, `вопрос ${index}`), `ответ ${index}`)
    }
    const body = questionBody('other', withQuestion(turns, 'последний'))

    expect(body.messages).toHaveLength(DIALOG_MAX_MESSAGES)
    expect(body.messages.at(-1)).toEqual({ author: 'user', text: 'последний' })
    expect(body.messages[0].text).not.toBe('вопрос 0')
  })

  it('sends a question trimmed and never an empty one', () => {
    expect(cleanQuestion('  Как выгрузить замеры?  ')).toBe('Как выгрузить замеры?')
    expect(cleanQuestion('   ')).toBeNull()
    expect(cleanQuestion('')).toBeNull()
  })
})
