import assert from 'node:assert/strict'
import test from 'node:test'
import { parseInline, parseMarkdown } from './markdown.js'

test('bold, italic and code become styled spans with no markers left', () => {
  assert.deepEqual(parseInline('A **bold** and *italic* and `code` end'), [
    { text: 'A ' }, { text: 'bold', bold: true }, { text: ' and ' }, { text: 'italic', italic: true },
    { text: ' and ' }, { text: 'code', code: true }, { text: ' end' },
  ])
})

test('underscore forms and italic inside bold work', () => {
  assert.deepEqual(parseInline('__b__ _i_'), [{ text: 'b', bold: true }, { text: ' ' }, { text: 'i', italic: true }])
  assert.deepEqual(parseInline('**a *b***'), [{ text: 'a ', bold: true }, { text: 'b', bold: true, italic: true }])
})

test('maths and identifiers are not treated as markers', () => {
  for (const text of ['3 * 4 * 5', 'a*b*c', 'snake_case_name', 'O(n*log n)', '2 ** 8']) {
    assert.deepEqual(parseInline(text), [{ text }], text)
  }
})

test('citations stay in the text', () => {
  assert.deepEqual(parseInline('**Greedy** works here [1][2].'), [
    { text: 'Greedy', bold: true }, { text: ' works here [1][2].' },
  ])
})

test('headings, bullets and numbered lists become blocks', () => {
  const blocks = parseMarkdown('## Title\nIntro line\nsecond line\n\n* one\n- **two**\n  - nested\n1. first\n2) second')
  assert.deepEqual(blocks.map(b => b.type), ['heading', 'paragraph', 'bullet', 'bullet', 'bullet', 'numbered', 'numbered'])
  assert.deepEqual(blocks[0].spans, [{ text: 'Title' }])
  assert.deepEqual(blocks[1].spans, [{ text: 'Intro line\nsecond line' }])
  assert.deepEqual(blocks[3].spans, [{ text: 'two', bold: true }])
  assert.equal(blocks[4].indent, 1)
  assert.equal(blocks[6].n, 2)
})

test('code fences keep their text as written', () => {
  const blocks = parseMarkdown('Before\n```python\nx = a * b * c\n# not a heading\n```\nAfter')
  assert.deepEqual(blocks[1], { type: 'code', text: 'x = a * b * c\n# not a heading' })
  assert.equal(blocks[2].spans[0].text, 'After')
})

test('rules are dropped, quotes keep their text, and an unclosed fence loses nothing', () => {
  assert.deepEqual(parseMarkdown('a\n\n---\n\n> b').map(b => b.spans[0].text), ['a', 'b'])
  assert.deepEqual(parseMarkdown('```\ncode'), [{ type: 'code', text: 'code' }])
})

test('plain and empty answers are safe', () => {
  assert.deepEqual(parseMarkdown('This is a test answer [1].'), [
    { type: 'paragraph', spans: [{ text: 'This is a test answer [1].' }] },
  ])
  assert.deepEqual(parseMarkdown(''), [])
  assert.deepEqual(parseMarkdown(null), [])
})
