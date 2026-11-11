import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  reasonLabel, percent, matricCheck, splitImages, rejectReasonError, pendingLabel, REJECT_REASON_MAX,
} from './faceReview.js'

test('known check codes get a readable label, unknown ones a tidied code', () => {
  assert.equal(reasonLabel('not_um_card'), 'Not a UM matric card')
  assert.equal(reasonLabel('selfies_inconsistent'), 'Selfies look like different people')
  assert.equal(reasonLabel('glare'), 'Glare on the card')
  assert.equal(reasonLabel('some_new_check'), 'Some new check')
})

test('scores show as whole percentages, missing ones as a dash', () => {
  assert.equal(percent(0.4567), '46%')
  assert.equal(percent(0), '0%')
  assert.equal(percent(null), '—')
  assert.equal(percent(undefined), '—')
})

test('card matric is compared with the account matric', () => {
  assert.deepEqual(matricCheck({ matric_no: '23004908', ocr_matric: '23004908' }), { text: '23004908', ok: true })
  assert.deepEqual(matricCheck({ matric_no: '23004908', ocr_matric: '23004999' }), { text: '23004999', ok: false })
  assert.deepEqual(matricCheck({ matric_no: '23004908', ocr_matric: null }), { text: 'Not readable', ok: false })
})

test('selfies come out in position order and the card separately', () => {
  const { selfies, card } = splitImages([
    { id: 4, kind: 'card', position: 0 },
    { id: 2, kind: 'selfie', position: 1 },
    { id: 1, kind: 'selfie', position: 0 },
  ])
  assert.deepEqual(selfies.map(i => i.id), [1, 2])
  assert.equal(card.id, 4)
  assert.deepEqual(splitImages(), { selfies: [], card: null })
})

test('a reject reason is required, trimmed and at most 500 characters', () => {
  assert.match(rejectReasonError(''), /Give a reason/)
  assert.match(rejectReasonError('   '), /Give a reason/)
  assert.match(rejectReasonError(undefined), /Give a reason/)
  assert.match(rejectReasonError('x'.repeat(REJECT_REASON_MAX + 1)), /under 500/)
  assert.equal(rejectReasonError(`  ${'x'.repeat(REJECT_REASON_MAX)}  `), null)
  assert.equal(rejectReasonError('Card belongs to someone else'), null)
})

test('the dashboard banner counts submissions in words', () => {
  assert.equal(pendingLabel(1), '1 face enrolment waiting for review')
  assert.equal(pendingLabel(3), '3 face enrolments waiting for review')
})
