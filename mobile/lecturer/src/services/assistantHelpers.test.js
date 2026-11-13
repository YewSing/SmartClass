import assert from 'node:assert/strict'
import test from 'node:test'
import { materialsSummary } from './assistantHelpers.js'

test('the collapsed Materials header is empty while loading', () => {
  assert.equal(materialsSummary(null), '')
})

test('it says when there are no materials', () => {
  assert.equal(materialsSummary([]), 'none yet')
})

test('it counts files and the ones that are not indexed', () => {
  const mats = [{ status: 'indexed' }, { status: 'no_text' }, { status: 'indexed' }, { status: 'error' }]
  assert.equal(materialsSummary(mats), '4 files · 2 not ready')
})

test('it says all ready when every file is indexed', () => {
  assert.equal(materialsSummary([{ status: 'indexed' }]), '1 file · all ready')
})
