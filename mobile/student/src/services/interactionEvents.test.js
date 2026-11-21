import test from 'node:test'
import assert from 'node:assert/strict'
import { applyInteractionStatus, readInteractionEvent } from './interactionEvents.js'

test('reconnect bootstrap disables actions immediately if the class ended during disconnect', () => {
  const cached = { status: 'open', can_participate: true, questions: [{ id: 1 }] }
  const data = JSON.stringify({ event: 'interaction.state', attendance_session_id: 23, status: 'closed' })
  const event = readInteractionEvent(data, 23)
  assert.deepEqual(applyInteractionStatus(cached, event), { ...cached, status: 'closed', can_participate: false })
  assert.equal(readInteractionEvent(data, 24), null)
})

test('only supported interaction messages for the current session are accepted', () => {
  assert.equal(readInteractionEvent('null', 23), null)
  assert.equal(readInteractionEvent('not json', 23), null)
  assert.equal(readInteractionEvent('{"event":"attendance_update","attendance_session_id":23}', 23), null)
  assert.equal(readInteractionEvent('{"event":"interaction.polls_changed","attendance_session_id":23}', 23).event,
    'interaction.polls_changed')
})
