import test from 'node:test'
import assert from 'node:assert/strict'
import { createInteractionRefresh } from './interactionRefresh.js'

function fixture() {
  const requests = []
  const results = []
  const reader = createInteractionRefresh(
    () => new Promise(resolve => requests.push(resolve)),
    value => results.push(value),
    () => {},
  )
  return { reader, requests, results }
}

test('a burst shares one in-flight read and schedules one trailing read', async () => {
  const { reader, requests, results } = fixture()
  const pending = reader.refresh()
  for (let i = 0; i < 20; i++) assert.equal(reader.refresh(), pending)
  assert.equal(requests.length, 1)
  requests[0]('initial')
  await Promise.resolve()
  assert.deepEqual(results, ['initial'])
  assert.equal(requests.length, 2)
  requests[1]('latest')
  await pending
  assert.deepEqual(results, ['initial', 'latest'])
})

test('a committed lifecycle event discards the in-flight snapshot', async () => {
  const { reader, requests, results } = fixture()
  const pending = reader.refresh()
  reader.refresh({ lifecycleChange: true })
  requests[0]('open')
  await Promise.resolve()
  assert.deepEqual(results, [])
  requests[1]('closed')
  await pending
  assert.deepEqual(results, ['closed'])
})
