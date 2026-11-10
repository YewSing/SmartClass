import { test } from 'node:test'
import assert from 'node:assert/strict'
import { restoreSession } from './session.js'

const failWith = (status) => async () => { throw Object.assign(new Error('x'), { status }) }

test('no stored token: show Login without calling the server', async () => {
  let called = false
  const r = await restoreSession({ hasStoredSession: false, fetchMe: async () => { called = true } })
  assert.deepEqual(r, { user: null, signOut: false })
  assert.equal(called, false)
})

test('a stored token for a lecturer or admin signs straight in', async () => {
  for (const roleKey of ['lecturer', 'admin']) {
    const me = { name: 'Dr A', roleKey }
    const r = await restoreSession({ hasStoredSession: true, fetchMe: async () => me })
    assert.equal(r.user, me)
  }
})

test("a student's stored token is not used and is cleared", async () => {
  const r = await restoreSession({ hasStoredSession: true, fetchMe: async () => ({ roleKey: 'student' }) })
  assert.deepEqual(r, { user: null, signOut: true })
})

test('a rejected or deactivated session is cleared', async () => {
  for (const status of [401, 403]) {
    const r = await restoreSession({ hasStoredSession: true, fetchMe: failWith(status) })
    assert.deepEqual(r, { user: null, signOut: true })
  }
})

test('a network failure shows Login but keeps the tokens for next time', async () => {
  const r = await restoreSession({ hasStoredSession: true, fetchMe: failWith(undefined) })
  assert.deepEqual(r, { user: null, signOut: false })
})
