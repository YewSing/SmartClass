import { test } from 'node:test'
import assert from 'node:assert/strict'
import { bubbleTextWidth } from './bubbleWidth.js'

const PHONE = 400   // the widest text in a bubble here is (400 - 24) * 0.88 - 24 = 306

test('a short message gets a little more room than it measured', () => {
  assert.ok(bubbleTextWidth(100, PHONE) > 100)
})

test('the width is a whole number, rounded up from the measurement', () => {
  assert.equal(bubbleTextWidth(100.2, PHONE) % 1, 0)
  assert.ok(bubbleTextWidth(100.2, PHONE) >= 101)
})

test('a long message stops at the widest the bubble can be', () => {
  assert.equal(bubbleTextWidth(306, PHONE), 306)
  assert.equal(bubbleTextWidth(500, PHONE), 306)
})

test('turning the phone gives the bubble more room again', () => {
  assert.ok(bubbleTextWidth(500, 800) > bubbleTextWidth(500, PHONE))
})
