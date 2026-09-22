// Answer of the assistant as blocks (T-84): the model writes paragraphs, lists and **bold**
// (rule 5 of its prompt), and the panel draws them without the symbols of Markdown. Nothing
// else is understood on purpose: no HTML, no links, no tables; a heading is a paragraph.

export interface Inline {
  strong: boolean
  text: string
}

export type Block = { kind: 'paragraph'; inlines: Inline[] } | { kind: 'list'; ordered: boolean; items: Inline[][] }

const BULLET = /^[-*•]\s+/
const NUMBER = /^\d+[.)]\s+/
const HEADING = /^#{1,6}\s+/
const STRONG = /\*\*(.+?)\*\*/g

/** Text with `**bold**` split into plain and bold runs; unpaired asterisks stay text. */
export function inlines(text: string): Inline[] {
  const parts: Inline[] = []
  let last = 0
  for (const match of text.matchAll(STRONG)) {
    if (match.index > last) parts.push({ strong: false, text: text.slice(last, match.index) })
    parts.push({ strong: true, text: match[1] })
    last = match.index + match[0].length
  }
  if (last < text.length) parts.push({ strong: false, text: text.slice(last) })
  return parts
}

/**
 * Lines of the answer grouped into paragraphs and lists. Lines of one paragraph are joined by
 * a space, an empty line ends it; a line that starts with `- `, `* ` or `1. ` is an item, and
 * neighbouring items of one kind make one list; a heading is a bold paragraph of its own.
 */
export function parseAnswer(text: string): Block[] {
  const blocks: Block[] = []
  let paragraph: string[] = []
  const flush = () => {
    if (paragraph.length > 0) blocks.push({ kind: 'paragraph', inlines: inlines(paragraph.join(' ')) })
    paragraph = []
  }
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim()
    if (line === '') {
      flush()
      continue
    }
    const ordered = NUMBER.test(line)
    if (ordered || BULLET.test(line)) {
      flush()
      const item = inlines(line.replace(ordered ? NUMBER : BULLET, ''))
      const last = blocks.at(-1)
      if (last?.kind === 'list' && last.ordered === ordered) last.items.push(item)
      else blocks.push({ kind: 'list', ordered, items: [item] })
      continue
    }
    if (HEADING.test(line)) {
      // The prompt forbids headings; one that slipped through is a bold line of its own.
      flush()
      blocks.push({ kind: 'paragraph', inlines: [{ strong: true, text: line.replace(HEADING, '') }] })
      continue
    }
    paragraph.push(line)
  }
  flush()
  return blocks
}
