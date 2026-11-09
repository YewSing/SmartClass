import assert from 'node:assert/strict'
import test from 'node:test'
import { buildPdfViewerHtml } from './pdfViewerHtml.js'

const args = { base: 'http://10.0.0.5:8000', fileUrl: '/student/assistant/materials/7/file', token: 'abc', page: 12 }

test('the page holds the file address, cited page and token', () => {
  const html = buildPdfViewerHtml(args)
  assert.ok(html.includes('"fileUrl":"http://10.0.0.5:8000/student/assistant/materials/7/file"'))
  assert.ok(html.includes('"page":12'))
  assert.ok(html.includes('"token":"abc"'))
})

test('pdf.js comes from our own backend, with no third-party script', () => {
  const html = buildPdfViewerHtml(args)
  const hosts = [...html.matchAll(/https?:\/\/[^/"'\s]+/g)].map(m => m[0])
  assert.deepEqual([...new Set(hosts)], ['http://10.0.0.5:8000'])
  assert.ok(html.includes('src="http://10.0.0.5:8000/static/pdfjs/pdf.min.js"'))
})

test('a value cannot break out of the script', () => {
  const html = buildPdfViewerHtml({ ...args, token: '</script><script>alert(1)</script>' })
  assert.ok(!html.includes('<script>alert(1)'))
  assert.ok(html.includes('\\u003c/script>'))
})
