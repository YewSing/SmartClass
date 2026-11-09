// Turns the simple markdown the assistant writes into blocks the app can style.
// Plain JS with no React Native imports, so `npm test` can run it under Node.

// `code` | **bold** | __bold__ | *italic* | _italic_
// Italic markers must sit next to text and not inside a word, so 3 * 4 * 5 and snake_case_name stay as typed.
const INLINE_RE = /`([^`\n]+)`|\*\*(.+?)\*\*(?!\*)|__(.+?)__|(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])|(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])/g

export function parseInline(text, style = {}) {
  const spans = []
  let last = 0
  for (const m of text.matchAll(INLINE_RE)) {
    if (m.index > last) spans.push({ text: text.slice(last, m.index), ...style })
    if (m[1] !== undefined) spans.push({ text: m[1], ...style, code: true })
    else if (m[2] !== undefined || m[3] !== undefined) spans.push(...parseInline(m[2] ?? m[3], { ...style, bold: true }))
    else spans.push(...parseInline(m[4] ?? m[5], { ...style, italic: true }))
    last = m.index + m[0].length
  }
  if (last < text.length) spans.push({ text: text.slice(last), ...style })
  return spans
}

const FENCE_RE = /^\s*```/
const HEADING_RE = /^\s*#{1,6}\s+(.*)$/
const BULLET_RE = /^(\s*)[-*+•]\s+(.*)$/
const NUMBERED_RE = /^(\s*)(\d+)[.)]\s+(.*)$/
const RULE_RE = /^\s*([-*_])(\s*\1){2,}\s*$/
const QUOTE_RE = /^\s*>\s?(.*)$/

const indentLevel = (spaces) => Math.min(Math.floor(spaces.replace(/\t/g, '  ').length / 2), 3)

export function parseMarkdown(text) {
  const blocks = []
  let paragraph = []
  const endParagraph = () => {
    if (paragraph.length) blocks.push({ type: 'paragraph', spans: parseInline(paragraph.join('\n')) })
    paragraph = []
  }

  const lines = (text ?? '').replace(/\r\n/g, '\n').split('\n')
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    if (FENCE_RE.test(line)) {
      endParagraph()
      const code = []
      for (i++; i < lines.length && !FENCE_RE.test(lines[i]); i++) code.push(lines[i])
      blocks.push({ type: 'code', text: code.join('\n') })
      continue
    }
    if (!line.trim()) { endParagraph(); continue }
    if (RULE_RE.test(line)) { endParagraph(); continue }

    let m
    if ((m = line.match(HEADING_RE))) {
      endParagraph()
      blocks.push({ type: 'heading', spans: parseInline(m[1].replace(/\s*#+\s*$/, '')) })
    } else if ((m = line.match(BULLET_RE))) {
      endParagraph()
      blocks.push({ type: 'bullet', indent: indentLevel(m[1]), spans: parseInline(m[2]) })
    } else if ((m = line.match(NUMBERED_RE))) {
      endParagraph()
      blocks.push({ type: 'numbered', indent: indentLevel(m[1]), n: Number(m[2]), spans: parseInline(m[3]) })
    } else if ((m = line.match(QUOTE_RE))) {
      paragraph.push(m[1])
    } else {
      paragraph.push(line.trim())
    }
  }
  endParagraph()
  return blocks
}
