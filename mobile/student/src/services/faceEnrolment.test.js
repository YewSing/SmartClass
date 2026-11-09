import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  statusInfo, canStartEnrolment, consentNeeded, retakeFromError, enrolmentParts,
  SELFIE_STEPS, TOTAL_STEPS,
} from './faceEnrolment.js'

const err422 = (detail) => Object.assign(new Error('x'), { status: 422, detail })

test('every status has a label, and unknown ones fall back to not enrolled', () => {
  assert.equal(statusInfo('active').label, 'Active')
  assert.equal(statusInfo('pending_review').label, 'Pending review')
  assert.equal(statusInfo('rejected').label, 'Rejected')
  assert.equal(statusInfo('something_new').label, 'Not enrolled')
})

test('enrolment can start only when not enrolled or rejected', () => {
  assert.equal(canStartEnrolment('not_enrolled'), true)
  assert.equal(canStartEnrolment('rejected'), true)
  assert.equal(canStartEnrolment('pending_review'), false)
  assert.equal(canStartEnrolment('active'), false)
})

test('consent is needed when missing, withdrawn or for an older notice', () => {
  assert.equal(consentNeeded(null), true)
  assert.equal(consentNeeded({ active: false, version: null, current_version: 'v2' }), true)
  assert.equal(consentNeeded({ active: true, version: 'v1', current_version: 'v2' }), true)
  assert.equal(consentNeeded({ active: true, version: 'v2', current_version: 'v2' }), false)
})

test('three guided selfies then the card', () => {
  assert.deepEqual(SELFIE_STEPS.map(s => s.key), ['front', 'left', 'right'])
  assert.equal(TOTAL_STEPS, 4)
})

test('a card quality 422 asks to retake the card with the server message', () => {
  const r = retakeFromError(err422({
    reasons: ['glare'], message: 'Glare is covering your card details.',
    blocked_attempts: 1, can_submit_anyway: false,
  }))
  assert.equal(r.retake, 'card')
  assert.equal(r.message, 'Glare is covering your card details.')
  assert.equal(r.blockedAttempts, 1)
  assert.equal(r.canSubmitAnyway, false)
})

test('submit anyway is offered after the server allows it', () => {
  const r = retakeFromError(err422({
    reasons: ['blurry', 'glare'], message: 'm', blocked_attempts: 2, can_submit_anyway: true,
  }))
  assert.equal(r.retake, 'card')
  assert.equal(r.canSubmitAnyway, true)
})

test('no face in the selfies asks to retake the selfies, never submit anyway', () => {
  const r = retakeFromError(err422({
    reasons: ['no_face_in_selfies'], message: 'We could not see your face.',
    blocked_attempts: 0, can_submit_anyway: true,
  }))
  assert.equal(r.retake, 'selfies')
  assert.equal(r.canSubmitAnyway, false)
})

test('a photo that is not an image asks to retake all photos', () => {
  const r = retakeFromError(err422({ reasons: ['not_an_image'], message: 'm' }))
  assert.equal(r.retake, 'all')
})

test('other errors are not retakes', () => {
  assert.equal(retakeFromError(err422('Take 3 to 5 selfies.')), null)
  assert.equal(retakeFromError(Object.assign(new Error('x'), { status: 409, detail: 'Already enrolled' })), null)
  assert.equal(retakeFromError(new Error('network')), null)
  assert.equal(retakeFromError(undefined), null)
})

test('multipart parts carry the selfies, the card and submit anyway', () => {
  const parts = enrolmentParts([{ uri: 'a' }, { uri: 'b' }, { uri: 'c' }], { uri: 'k' }, true)
  assert.deepEqual(parts.map(p => p[0]), ['selfies', 'selfies', 'selfies', 'card', 'submit_anyway'])
  assert.deepEqual(parts[0][1], { uri: 'a', name: 'selfie-1.jpg', type: 'image/jpeg' })
  assert.deepEqual(parts[3][1], { uri: 'k', name: 'card.jpg', type: 'image/jpeg' })
  assert.equal(parts[4][1], 'true')
  assert.equal(enrolmentParts([{ uri: 'a' }], { uri: 'k' }).some(p => p[0] === 'submit_anyway'), false)
})
