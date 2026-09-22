import { Fragment } from 'react'

import { parseAnswer, type Inline } from './markup'

const runs = (parts: Inline[]) =>
  parts.map((part, index) =>
    part.strong ? <strong key={index}>{part.text}</strong> : <Fragment key={index}>{part.text}</Fragment>,
  )

/** Answer of the model drawn as paragraphs, lists and bold, without the symbols of Markdown (T-84). */
export function AssistantAnswer({ text }: { text: string }) {
  return (
    <>
      {parseAnswer(text).map((block, index) => {
        if (block.kind === 'paragraph') return <p key={index}>{runs(block.inlines)}</p>
        const items = block.items.map((item, position) => <li key={position}>{runs(item)}</li>)
        return block.ordered ? <ol key={index}>{items}</ol> : <ul key={index}>{items}</ul>
      })}
    </>
  )
}
